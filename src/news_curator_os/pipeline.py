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
    SearchExecution,
    StageCard,
    StageState,
    VerificationPayload,
)
from .repository import RunRepository
from .search import NewsSearchProvider

logger = logging.getLogger(__name__)

PipelineEventCallback = Callable[[str, dict[str, Any]], None]


class HeadlinePipeline:
    def __init__(self, settings: Settings, repository: RunRepository | None = None):
        self.settings = settings
        self.repository = repository
        self.search_provider = NewsSearchProvider(settings)
        self.agents = NewsCurationAgents(settings)

    async def preview(
        self,
        headline: str,
        event_callback: PipelineEventCallback | None = None,
    ) -> PipelineRun:
        return await self._execute(headline=headline, persist=False, event_callback=event_callback)

    async def run(
        self,
        headline: str,
        event_callback: PipelineEventCallback | None = None,
    ) -> PipelineRun:
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
        logger.info("Pipeline started for headline: %.80s (persist=%s)", normalized, persist)
        self._emit(
            event_callback,
            "input_received",
            {"headline": headline.strip(), "normalized_headline": normalized, "persist": persist},
        )
        audit = [
            AuditEntry(
                stage="input",
                severity="info",
                message=f"Headline recebida com {len(normalized)} caracteres.",
                created_at=now,
            )
        ]

        self._emit(event_callback, "search_started", {"headline": normalized})
        search_execution = await self.search_provider.search(normalized)
        self._emit(
            event_callback,
            "search_completed",
            {
                "provider": search_execution.provider,
                "mode": search_execution.mode,
                "total_results": search_execution.total_results,
                "evidence_count": len(search_execution.evidence),
                "unique_source_count": search_execution.unique_source_count,
                "official_source_count": search_execution.official_source_count,
            },
        )
        audit.append(
            AuditEntry(
                stage="search",
                severity="info" if search_execution.total_results else "warning",
                message=(
                    f"Busca executada via {search_execution.provider} em modo {search_execution.mode}."
                    if search_execution.provider != "manual"
                    else "Busca real indisponivel; sistema operando com consultas sugeridas."
                ),
                created_at=self._now(),
            )
        )

        self._emit(event_callback, "analysis_started", {"headline": normalized})
        analysis = await self.agents.analyze(normalized, search_execution.evidence)
        self._emit(
            event_callback,
            "analysis_completed",
            {"score": analysis.score, "entities": analysis.entities[:5]},
        )
        audit.append(
            AuditEntry(
                stage="analysis",
                severity="info",
                message=f"Analise concluida em modo {self.agents.llm_mode} com score {analysis.score}.",
                created_at=self._now(),
            )
        )

        self._emit(
            event_callback,
            "verification_started",
            {"evidence_count": len(search_execution.evidence)},
        )
        verification = await self.agents.verify(normalized, search_execution.evidence, analysis)
        self._emit(
            event_callback,
            "verification_completed",
            {
                "score": verification.score,
                "missing_context": verification.missing_context[:3],
                "divergence_detected": verification.divergence_detected,
            },
        )
        audit.append(
            AuditEntry(
                stage="verification",
                severity="info" if search_execution.evidence else "warning",
                message=f"Verificacao concluida com score {verification.score} e {len(search_execution.evidence)} evidencias.",
                created_at=self._now(),
            )
        )

        self._emit(event_callback, "qualification_started", {"headline": normalized})
        output = await self.agents.qualify(normalized, search_execution.evidence, analysis, verification)
        self._emit(
            event_callback,
            "qualification_completed",
            {
                "confidence_score": output.confidence_score,
                "credibility_band": output.credibility_band,
            },
        )
        audit.append(
            AuditEntry(
                stage="qualification",
                severity="info",
                message=f"Qualificacao final emitida com confianca {output.confidence_score}.",
                created_at=self._now(),
            )
        )

        self._emit(event_callback, "redaction_started", {"headline": normalized})
        article_markdown = await self.agents.draft_article(
            normalized,
            search_execution.evidence,
            analysis,
            verification,
            output,
        )
        self._emit(
            event_callback,
            "redaction_completed",
            {"markdown_chars": len(article_markdown)},
        )
        audit.append(
            AuditEntry(
                stage="redaction",
                severity="info",
                message=f"Redacao final em Markdown gerada com {len(article_markdown)} caracteres.",
                created_at=self._now(),
            )
        )

        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            created_at=now,
            headline=headline.strip(),
            normalized_headline=normalized,
            execution_mode=self._execution_mode(search_execution),
            llm_mode=self.agents.llm_mode,
            search_provider=search_execution.provider,
            stages=self._build_stages(search_execution, analysis, verification, output),
            evidence=search_execution.evidence,
            output=output,
            article_markdown=article_markdown,
            next_actions=self._next_actions(search_execution, output),
            audit=audit,
        )

        if persist and self.repository is not None:
            run.audit.append(
                AuditEntry(
                    stage="storage",
                    severity="info",
                    message="Execucao persistida em SQLite com auditoria e evidencias.",
                    created_at=self._now(),
                )
            )
            self._emit(event_callback, "storage_started", {"run_id": run.run_id})
            self.repository.save_run(run)
            self._emit(event_callback, "storage_completed", {"run_id": run.run_id})

        self._emit(
            event_callback,
            "run_completed",
            {
                "run_id": run.run_id,
                "execution_mode": run.execution_mode,
                "confidence_score": run.output.confidence_score,
            },
        )
        logger.info(
            "Pipeline completed: run_id=%s mode=%s confidence=%s",
            run.run_id, run.execution_mode, run.output.confidence_score,
        )
        return run

    def _build_stages(
        self,
        search_execution: SearchExecution,
        analysis: AnalysisPayload,
        verification: VerificationPayload,
        output: QualificationOutput,
    ) -> list[StageCard]:
        search_details = search_execution.query_plan.copy()
        if search_execution.evidence:
            search_details.extend(
                [f"{item.source}: {item.title}" for item in search_execution.evidence[:3]]
            )
            search_details.append(
                f"Fontes distintas: {search_execution.unique_source_count} | Fontes oficiais: {search_execution.official_source_count}"
            )
        if search_execution.note:
            search_details.append(search_execution.note)

        verification_details = (
            verification.corroborated_points
            + verification.official_source_points
            + verification.conflicting_points
        )
        verification_details.extend(verification.missing_context)
        if verification.source_consensus:
            verification_details.append(verification.source_consensus)

        return [
            StageCard(
                key="search",
                title="Busca",
                state=StageState.completed if search_execution.evidence else StageState.attention,
                summary=(
                    f"{search_execution.unique_source_count or search_execution.total_results} fontes recuperadas pelo provider {search_execution.provider}, com {search_execution.official_source_count} oficiais."
                    if search_execution.evidence
                    else "Nenhuma evidencia externa validada; o sistema permaneceu em modo de contingencia ou retorno vazio."
                ),
                details=search_details,
                score=min(88, 28 + (search_execution.total_results * 12)),
            ),
            StageCard(
                key="analysis",
                title="Analise",
                state=StageState.completed,
                summary=analysis.summary,
                details=[
                    f"Entidades: {', '.join(analysis.entities) if analysis.entities else 'nenhuma entidade forte detectada'}",
                    f"Claims: {', '.join(analysis.key_claims[:2]) if analysis.key_claims else 'nao identificado'}",
                    f"Riscos: {', '.join(analysis.risk_signals) if analysis.risk_signals else 'nenhum sinal forte'}",
                ],
                score=analysis.score,
            ),
            StageCard(
                key="verification",
                title="Verificacao",
                state=StageState.completed if search_execution.evidence else StageState.attention,
                summary=verification.summary,
                details=verification_details or ["Sem itens adicionais de verificacao."],
                score=verification.score,
            ),
            StageCard(
                key="qualification",
                title="Qualificacao",
                state=StageState.completed,
                summary=output.editorial_verdict,
                details=[
                    f"Faixa de credibilidade: {output.credibility_band}",
                    f"Risco de desinformacao: {output.misinformation_risk}",
                    f"Acao recomendada: {output.recommended_action}",
                ],
                score=output.confidence_score,
            ),
            StageCard(
                key="output",
                title="Output",
                state=StageState.completed,
                summary="Parecer consolidado com historico, evidencias e proxima acao editorial.",
                details=[
                    f"Modo de execucao: {self._execution_mode(search_execution)}",
                    f"Modo LLM: {self.agents.llm_mode}",
                    f"Evidencias anexadas: {len(search_execution.evidence)}",
                ],
                score=output.confidence_score,
            ),
        ]

    def _execution_mode(self, search_execution: SearchExecution) -> str:
        if search_execution.provider == "manual":
            return "fallback-manual"
        if search_execution.evidence:
            return f"{search_execution.provider}-{self.agents.llm_mode}"
        return f"{search_execution.provider}-degraded"

    def _next_actions(self, search_execution: SearchExecution, output: QualificationOutput) -> list[str]:
        actions = [output.recommended_action]
        if not search_execution.evidence:
            actions.append("Adicionar ou corrigir o provider de busca para recuperar evidencias externas.")
        elif search_execution.official_source_count == 0:
            actions.append("Tentar ampliar a busca com fontes oficiais ou registros primarios antes da decisao final.")
        if self.agents.llm_mode != "agno-openai":
            actions.append("Configurar OPENAI_API_KEY para habilitar agentes especializados no Agno.")
        actions.append("Revisar o historico persistido no painel antes da decisao final.")
        return actions

    def _normalize(self, headline: str) -> str:
        compact = " ".join(headline.strip().split())
        return compact[:1].upper() + compact[1:] if compact else ""

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _emit(
        self,
        event_callback: PipelineEventCallback | None,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        if event_callback is not None:
            event_callback(event, payload)
