from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .agents import NewsCurationAgents
from .config import Settings
from .models import (
    AnalysisPayload,
    AuditEntry,
    PipelineRun,
    QualificationOutput,
    SearchEvidence,
    SearchExecution,
    StageCard,
    StageState,
    VerificationPayload,
)
from .repository import RunRepository
from .tavily_search import TavilySearchProvider
from .text_utils import extract_entities

logger = logging.getLogger(__name__)

PipelineEventCallback = Callable[[str, dict[str, Any]], None]

ROUND_LABELS = ["Rodada 1: busca principal (PT)", "Rodada 2: busca ampliada (EN)", "Rodada 3: busca dirigida"]


class DeepHeadlinePipeline:
    """Pipeline de curadoria profunda com 3 rodadas de busca Tavily + veredito consolidado."""

    def __init__(self, settings: Settings, repository: RunRepository | None = None):
        self.settings = settings
        self.repository = repository
        self.tavily = TavilySearchProvider(settings)
        self.agents = NewsCurationAgents(settings)

    async def preview(self, headline: str, event_callback: PipelineEventCallback | None = None) -> PipelineRun:
        return await self._execute(headline=headline, persist=False, event_callback=event_callback)

    async def run(self, headline: str, event_callback: PipelineEventCallback | None = None) -> PipelineRun:
        return await self._execute(headline=headline, persist=True, event_callback=event_callback)

    async def _execute(
        self,
        *,
        headline: str,
        persist: bool,
        event_callback: PipelineEventCallback | None = None,
    ) -> PipelineRun:
        normalized = self._normalize(headline)
        now = self._now()
        audit: list[AuditEntry] = []
        all_evidence: list[SearchEvidence] = []
        all_query_plans: list[str] = []
        round_summaries: list[str] = []

        logger.info("Deep pipeline started: %.80s (persist=%s)", normalized, persist)
        self._emit(event_callback, "deep_pipeline_started", {
            "headline": normalized, "total_rounds": 3,
        })
        audit.append(AuditEntry(
            stage="input", severity="info",
            message=f"Curadoria profunda iniciada para headline com {len(normalized)} caracteres. 3 rodadas planejadas.",
            created_at=now,
        ))

        # --- ROUND 1: Portuguese search ---
        self._emit(event_callback, "round_started", {"round": 1, "label": ROUND_LABELS[0]})
        r1 = await self.tavily.search(normalized, language="pt", topic="news")
        all_evidence.extend(r1.evidence)
        all_query_plans.extend([f"[R1] {q}" for q in r1.query_plan])
        round_summaries.append(f"R1 (PT): {r1.total_results} resultados via Tavily")
        audit.append(AuditEntry(
            stage="search-r1", severity="info" if r1.evidence else "warning",
            message=f"Rodada 1 (PT): {r1.total_results} resultados. {r1.note or ''}",
            created_at=self._now(),
        ))
        self._emit(event_callback, "round_completed", {
            "round": 1, "results": r1.total_results, "evidence_so_far": len(all_evidence),
        })

        # --- Intermediate analysis to guide round 2 ---
        r1_analysis = await self.agents.analyze(normalized, all_evidence)

        # --- ROUND 2: English search (broader) ---
        self._emit(event_callback, "round_started", {"round": 2, "label": ROUND_LABELS[1]})
        en_entities = extract_entities(normalized)
        en_query = " ".join(en_entities[:5]) if en_entities else normalized
        r2 = await self.tavily.search(
            normalized,
            language="en",
            topic="news",
            extra_queries=[en_query, f"{en_query} latest news"],
        )
        all_evidence.extend(r2.evidence)
        all_query_plans.extend([f"[R2] {q}" for q in r2.query_plan])
        round_summaries.append(f"R2 (EN): {r2.total_results} resultados via Tavily")
        audit.append(AuditEntry(
            stage="search-r2", severity="info" if r2.evidence else "warning",
            message=f"Rodada 2 (EN): {r2.total_results} resultados. {r2.note or ''}",
            created_at=self._now(),
        ))
        self._emit(event_callback, "round_completed", {
            "round": 2, "results": r2.total_results, "evidence_so_far": len(all_evidence),
        })

        # --- Intermediate verification to find gaps ---
        r2_verification = await self.agents.verify(normalized, all_evidence, r1_analysis)

        # --- ROUND 3: Targeted search based on gaps ---
        self._emit(event_callback, "round_started", {"round": 3, "label": ROUND_LABELS[2]})
        gap_queries = self._build_gap_queries(normalized, r1_analysis, r2_verification)
        r3 = await self.tavily.search(
            normalized,
            language="pt",
            topic="news",
            extra_queries=gap_queries,
        )
        all_evidence.extend(r3.evidence)
        all_query_plans.extend([f"[R3] {q}" for q in r3.query_plan])
        round_summaries.append(f"R3 (dirigida): {r3.total_results} resultados via Tavily")
        audit.append(AuditEntry(
            stage="search-r3", severity="info" if r3.evidence else "warning",
            message=f"Rodada 3 (dirigida): {r3.total_results} resultados. Queries: {'; '.join(gap_queries[:3])}",
            created_at=self._now(),
        ))
        self._emit(event_callback, "round_completed", {
            "round": 3, "results": r3.total_results, "evidence_so_far": len(all_evidence),
        })

        # --- Deduplicate all evidence ---
        unique_evidence = self._dedupe_all(all_evidence)
        audit.append(AuditEntry(
            stage="consolidation", severity="info",
            message=f"Consolidacao: {len(all_evidence)} resultados brutos -> {len(unique_evidence)} fontes unicas apos 3 rodadas.",
            created_at=self._now(),
        ))

        # --- Final analysis on consolidated evidence ---
        self._emit(event_callback, "analysis_started", {"evidence_count": len(unique_evidence)})
        final_analysis = await self.agents.analyze(normalized, unique_evidence)
        self._emit(event_callback, "analysis_completed", {"score": final_analysis.score})
        audit.append(AuditEntry(
            stage="analysis", severity="info",
            message=f"Analise final consolidada com score {final_analysis.score} sobre {len(unique_evidence)} fontes.",
            created_at=self._now(),
        ))

        # --- Final verification ---
        self._emit(event_callback, "verification_started", {"evidence_count": len(unique_evidence)})
        final_verification = await self.agents.verify(normalized, unique_evidence, final_analysis)
        self._emit(event_callback, "verification_completed", {
            "score": final_verification.score,
            "divergence": final_verification.divergence_detected,
        })
        audit.append(AuditEntry(
            stage="verification", severity="info",
            message=f"Verificacao final: score {final_verification.score}, divergencia={final_verification.divergence_detected}.",
            created_at=self._now(),
        ))

        # --- Final qualification ---
        self._emit(event_callback, "qualification_started", {})
        final_output = await self.agents.qualify(normalized, unique_evidence, final_analysis, final_verification)
        self._emit(event_callback, "qualification_completed", {
            "confidence": final_output.confidence_score,
            "band": final_output.credibility_band,
        })
        audit.append(AuditEntry(
            stage="qualification", severity="info",
            message=f"Qualificacao final: confianca {final_output.confidence_score}, faixa {final_output.credibility_band}.",
            created_at=self._now(),
        ))

        # --- Final article ---
        self._emit(event_callback, "redaction_started", {})
        article = await self.agents.draft_article(
            normalized, unique_evidence, final_analysis, final_verification, final_output,
        )
        self._emit(event_callback, "redaction_completed", {"chars": len(article)})
        audit.append(AuditEntry(
            stage="redaction", severity="info",
            message=f"Redacao final gerada com {len(article)} caracteres consolidando {len(unique_evidence)} fontes de 3 rodadas.",
            created_at=self._now(),
        ))

        # --- Build search execution summary ---
        search_execution = SearchExecution(
            provider="tavily",
            mode="deep-3-rounds",
            primary_query=normalized,
            query_plan=all_query_plans,
            total_results=len(unique_evidence),
            evidence=unique_evidence,
            unique_source_count=len(unique_evidence),
            official_source_count=sum(1 for e in unique_evidence if e.is_official),
            note=" | ".join(round_summaries),
        )

        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            created_at=now,
            headline=headline.strip(),
            normalized_headline=normalized,
            execution_mode=f"tavily-deep-{self.agents.llm_mode}",
            llm_mode=self.agents.llm_mode,
            search_provider="tavily",
            stages=self._build_stages(search_execution, final_analysis, final_verification, final_output),
            evidence=unique_evidence,
            output=final_output,
            article_markdown=article,
            next_actions=self._next_actions(unique_evidence, final_output, final_verification),
            audit=audit,
        )

        if persist and self.repository is not None:
            audit.append(AuditEntry(
                stage="storage", severity="info",
                message="Execucao persistida em SQLite.",
                created_at=self._now(),
            ))
            self._emit(event_callback, "storage_started", {"run_id": run.run_id})
            self.repository.save_run(run)
            self._emit(event_callback, "storage_completed", {"run_id": run.run_id})

        self._emit(event_callback, "deep_pipeline_completed", {
            "run_id": run.run_id,
            "total_evidence": len(unique_evidence),
            "confidence": final_output.confidence_score,
        })
        logger.info(
            "Deep pipeline completed: run_id=%s evidence=%d confidence=%s",
            run.run_id, len(unique_evidence), final_output.confidence_score,
        )
        return run

    def _build_gap_queries(
        self,
        headline: str,
        analysis: AnalysisPayload,
        verification: VerificationPayload,
    ) -> list[str]:
        queries: list[str] = []
        entities = extract_entities(headline)
        entity_str = " ".join(entities[:3]) if entities else headline

        if verification.missing_context:
            for gap in verification.missing_context[:2]:
                keywords = " ".join(gap.split()[:6])
                queries.append(f"{entity_str} {keywords}")

        if verification.conflicting_points:
            queries.append(f"{entity_str} fact check verificacao")

        if analysis.risk_signals:
            queries.append(f"{entity_str} desmentido fake news")

        if not queries:
            queries.append(f"{entity_str} dados oficiais")
            queries.append(f"{entity_str} analise impacto")

        return queries[:4]

    def _dedupe_all(self, evidence: list[SearchEvidence]) -> list[SearchEvidence]:
        seen: dict[str, SearchEvidence] = {}
        for item in evidence:
            key = (item.source_domain or item.url or item.title or "").casefold()
            if not key:
                continue
            current = seen.get(key)
            if current is None or (item.relevance_score or 0) > (current.relevance_score or 0):
                seen[key] = item
        return sorted(seen.values(), key=lambda e: e.relevance_score or 0, reverse=True)

    def _build_stages(
        self,
        search: SearchExecution,
        analysis: AnalysisPayload,
        verification: VerificationPayload,
        output: QualificationOutput,
    ) -> list[StageCard]:
        return [
            StageCard(
                key="search",
                title="Busca Profunda (3 rodadas)",
                state=StageState.completed if search.evidence else StageState.attention,
                summary=search.note or f"{search.total_results} fontes em 3 rodadas via Tavily.",
                details=search.query_plan[:8],
                score=min(95, 20 + search.total_results * 8),
            ),
            StageCard(
                key="analysis",
                title="Analise Consolidada",
                state=StageState.completed,
                summary=analysis.summary,
                details=[
                    f"Entidades: {', '.join(analysis.entities[:6]) or 'nenhuma'}",
                    f"Claims: {', '.join(analysis.key_claims[:3]) or 'nenhum'}",
                    f"Riscos: {', '.join(analysis.risk_signals) or 'nenhum sinal'}",
                ],
                score=analysis.score,
            ),
            StageCard(
                key="verification",
                title="Verificacao Cruzada",
                state=StageState.completed if not verification.divergence_detected else StageState.attention,
                summary=verification.summary,
                details=(
                    verification.corroborated_points[:3]
                    + verification.official_source_points[:2]
                    + verification.conflicting_points[:2]
                    + verification.missing_context[:2]
                ),
                score=verification.score,
            ),
            StageCard(
                key="qualification",
                title="Veredito Final",
                state=StageState.completed,
                summary=output.editorial_verdict,
                details=[
                    f"Credibilidade: {output.credibility_band}",
                    f"Risco de desinformacao: {output.misinformation_risk}",
                    f"Acao: {output.recommended_action}",
                ],
                score=output.confidence_score,
            ),
        ]

    def _next_actions(
        self,
        evidence: list[SearchEvidence],
        output: QualificationOutput,
        verification: VerificationPayload,
    ) -> list[str]:
        actions = [output.recommended_action]
        if verification.divergence_detected:
            actions.append("Confrontar divergencias entre fontes antes da decisao final.")
        if not any(e.is_official for e in evidence):
            actions.append("Buscar confirmacao em fontes oficiais.")
        if len(evidence) < 3:
            actions.append("Ampliar busca com termos adicionais para maior cobertura.")
        return actions

    def _normalize(self, headline: str) -> str:
        compact = " ".join(headline.strip().split())
        return compact[:1].upper() + compact[1:] if compact else ""

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _emit(self, cb: PipelineEventCallback | None, event: str, payload: dict[str, Any]) -> None:
        if cb is not None:
            cb(event, payload)
