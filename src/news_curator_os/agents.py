from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Type, TypeVar

from pydantic import BaseModel

from .config import Settings
from .models import AnalysisPayload, QualificationOutput, SearchEvidence, VerificationPayload

SENSATIONAL_TERMS = {
    "urgente",
    "chocante",
    "bombastico",
    "bombástico",
    "exclusivo",
    "ultima hora",
    "última hora",
}

CONTRADICTION_TERMS = {
    "desmente",
    "nega",
    "negou",
    "contestou",
    "sem provas",
    "sem evidencia",
    "sem evidência",
    "nao confirma",
    "não confirma",
}

CONFIRMATION_TERMS = {
    "anuncia",
    "anunciou",
    "confirma",
    "confirmou",
    "aprova",
    "aprovou",
    "publica",
    "publicou",
}

REGULATORY_TERMS = {
    "governo",
    "ministerio",
    "ministério",
    "decreto",
    "portaria",
    "lei",
    "banco central",
    "cvm",
    "stf",
    "senado",
    "camara",
    "câmara",
}

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class NewsCurationAgents:
    settings: Settings

    @property
    def llm_mode(self) -> str:
        return "agno-openai" if self.settings.openai_api_key else "local-fallback"

    async def analyze(self, headline: str, evidence: list[SearchEvidence]) -> AnalysisPayload:
        if not self.settings.openai_api_key:
            return self._fallback_analysis(headline, evidence)

        prompt = {
            "headline": headline,
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "task": "Analise editorial da headline e identifique entidades, claims e sinais de risco.",
        }
        content = await self._run_structured(
            name="news-analysis-agent",
            instructions=[
                "Voce e um analista editorial de noticias.",
                "Responda em portugues.",
                "Extraia entidades, claims principais e sinais de risco sem inventar fatos ausentes.",
            ],
            payload=prompt,
            output_schema=AnalysisPayload,
        )
        return content or self._fallback_analysis(headline, evidence)

    async def verify(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
    ) -> VerificationPayload:
        if not self.settings.openai_api_key:
            return self._fallback_verification(headline, evidence, analysis)

        prompt = {
            "headline": headline,
            "analysis": analysis.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "task": "Verifique se as evidencias suportam, contradizem ou deixam lacunas sobre a headline.",
        }
        content = await self._run_structured(
            name="news-verification-agent",
            instructions=[
                "Voce e um verificador de fatos editorial.",
                "Use apenas as evidencias fornecidas.",
                "Nao afirme corroboracao quando o material for insuficiente.",
                "Aponte divergencias materiais entre fontes e destaque quando houver fonte oficial.",
            ],
            payload=prompt,
            output_schema=VerificationPayload,
        )
        return content or self._fallback_verification(headline, evidence, analysis)

    async def qualify(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
        verification: VerificationPayload,
    ) -> QualificationOutput:
        if not self.settings.openai_api_key:
            return self._fallback_qualification(headline, evidence, analysis, verification)

        prompt = {
            "headline": headline,
            "analysis": analysis.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "evidence_count": len(evidence),
            "task": "Qualifique a headline para decisao editorial, com score, risco e recomendacao pratica.",
        }
        content = await self._run_structured(
            name="news-qualification-agent",
            instructions=[
                "Voce decide a qualificacao editorial final.",
                "Se faltar evidencia, seja conservador.",
                "Retorne um parecer objetivo, acionavel e em portugues.",
            ],
            payload=prompt,
            output_schema=QualificationOutput,
        )
        return content or self._fallback_qualification(headline, evidence, analysis, verification)

    async def draft_article(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
        verification: VerificationPayload,
        qualification: QualificationOutput,
    ) -> str:
        if not self.settings.openai_api_key:
            return self._fallback_article(headline, evidence, analysis, verification, qualification)

        prompt = {
            "headline": headline,
            "analysis": analysis.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "qualification": qualification.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "task": (
                "Escreva uma redacao jornalistica completa em Markdown com titulo, subtitulo, "
                "contexto, desenvolvimento, impactos, limites de verificacao e fontes."
            ),
        }
        content = await self._run_text(
            name="news-redaction-agent",
            instructions=[
                "Voce e um redator editorial.",
                "Responda em portugues do Brasil.",
                "Escreva em Markdown limpo.",
                "Nao invente fatos ausentes nas evidencias fornecidas.",
                "Use ate 5 fontes e destaque fontes oficiais quando existirem.",
                "Inclua uma secao de divergencias entre fontes, mesmo que para dizer que nao houve divergencia relevante.",
                "Inclua uma secao final chamada '## Fontes consultadas'.",
            ],
            payload=prompt,
        )
        return content or self._fallback_article(headline, evidence, analysis, verification, qualification)

    async def _run_structured(
        self,
        *,
        name: str,
        instructions: list[str],
        payload: dict,
        output_schema: Type[ModelT],
    ) -> ModelT | None:
        from agno.agent import Agent
        from agno.models.openai import OpenAIResponses

        agent = Agent(
            name=name,
            model=OpenAIResponses(
                id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                organization=self.settings.openai_organization,
                temperature=0.1,
            ),
            instructions=instructions,
            markdown=False,
            telemetry=False,
        )
        try:
            run_output = await agent.arun(
                json.dumps(payload, ensure_ascii=False),
                output_schema=output_schema,
            )
            return self._coerce_output(run_output.content, output_schema)
        except Exception:
            return None

    async def _run_text(
        self,
        *,
        name: str,
        instructions: list[str],
        payload: dict,
    ) -> str | None:
        from agno.agent import Agent
        from agno.models.openai import OpenAIResponses

        agent = Agent(
            name=name,
            model=OpenAIResponses(
                id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                organization=self.settings.openai_organization,
                temperature=0.2,
            ),
            instructions=instructions,
            markdown=True,
            telemetry=False,
        )
        try:
            run_output = await agent.arun(json.dumps(payload, ensure_ascii=False))
            return str(run_output.content).strip() if run_output.content else None
        except Exception:
            return None

    def _coerce_output(self, content: object, output_schema: Type[ModelT]) -> ModelT | None:
        if content is None:
            return None
        if isinstance(content, output_schema):
            return content
        if isinstance(content, BaseModel):
            return output_schema.model_validate(content.model_dump())
        if isinstance(content, dict):
            return output_schema.model_validate(content)
        if isinstance(content, str):
            candidate = content.strip()
            try:
                return output_schema.model_validate_json(candidate)
            except Exception:
                pass
            try:
                return output_schema.model_validate(json.loads(candidate))
            except Exception:
                return None
        return None

    def _fallback_analysis(self, headline: str, evidence: list[SearchEvidence]) -> AnalysisPayload:
        entities = self._extract_entities(" ".join([headline] + [item.title for item in evidence]))
        risk_signals = [term for term in SENSATIONAL_TERMS if term in headline.casefold()]
        key_claims = [headline]
        if evidence:
            key_claims.append(f"Foram encontradas {len(evidence)} evidencias externas relacionadas.")
        score = 52 + min(len(evidence) * 8, 24) - min(len(risk_signals) * 10, 20)
        return AnalysisPayload(
            summary="Analise gerada por fallback local com base na headline e nas evidencias recuperadas.",
            entities=entities[:6],
            key_claims=key_claims,
            risk_signals=risk_signals,
            score=max(20, min(score, 88)),
        )

    def _fallback_verification(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
    ) -> VerificationPayload:
        unique_sources = sorted({item.source for item in evidence})
        official_sources = [
            item for item in evidence if item.is_official or item.source_type == "official"
        ]
        corroborated = [f"Fonte encontrada: {source}" for source in unique_sources[:5]]
        missing_context = []
        conflicting_points = self._detect_divergences(evidence)
        official_points = [
            (
                f"Fonte oficial consultada: {item.source}"
                + (f" ({item.source_domain})" if item.source_domain else "")
            )
            for item in official_sources[:3]
        ]
        if not evidence:
            missing_context.append("Nenhuma evidencia externa foi recuperada.")
        if analysis.risk_signals:
            missing_context.append("A headline contem sinais de sensacionalismo e exige revisao humana.")
        if self._requires_official_confirmation(headline) and not official_sources:
            missing_context.append("Nao foi encontrada fonte oficial para um tema regulatorio ou institucional.")
        score = 24 + min(len(unique_sources) * 12, 48) + min(len(official_sources) * 10, 20)
        if conflicting_points:
            score -= min(len(conflicting_points) * 8, 24)
        if not evidence:
            score = 18
        return VerificationPayload(
            summary=(
                "Verificacao derivada do cruzamento de ate 5 fontes, destacando consenso, divergencias e respaldo oficial."
            ),
            corroborated_points=corroborated,
            conflicting_points=conflicting_points,
            missing_context=missing_context,
            official_source_points=official_points,
            source_consensus=self._build_consensus_statement(unique_sources, official_sources, conflicting_points),
            divergence_detected=bool(conflicting_points),
            score=max(15, min(score, 90)),
        )

    def _fallback_qualification(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
        verification: VerificationPayload,
    ) -> QualificationOutput:
        confidence = int((analysis.score + verification.score) / 2)
        if confidence >= 75:
            band = "moderada a alta"
            risk = "baixo"
            action = "Prosseguir para revisao editorial final com anexacao das evidencias."
        elif confidence >= 50:
            band = "moderada"
            risk = "moderado"
            action = "Revisar a headline, anexar evidencias e validar os pontos sensiveis antes de publicar."
        else:
            band = "baixa"
            risk = "alto"
            action = "Segurar publicacao e acionar verificacao humana com busca adicional."

        if not evidence:
            action = "Executar busca real ou verificacao humana antes de qualquer decisao editorial."
            risk = "alto"
            band = "baixa"
            confidence = min(confidence, 42)
        elif verification.divergence_detected:
            action = "Confrontar as divergencias entre fontes, priorizar registros oficiais e validar a versao final antes de publicar."
            risk = "moderado" if confidence >= 60 else "alto"
            band = "moderada"
            confidence = min(confidence, 68)
        elif verification.official_source_points:
            action = "Prosseguir com revisao editorial, preservando as evidencias oficiais e as fontes independentes na apuracao."
            confidence = min(92, confidence + 6)

        return QualificationOutput(
            editorial_verdict=(
                "Headline com suporte editorial inicial razoavel."
                if confidence >= 60
                else "Headline ainda insuficientemente comprovada para liberacao direta."
            ),
            credibility_band=band,
            misinformation_risk=risk,
            recommended_action=action,
            confidence_score=confidence,
        )

    def _fallback_article(
        self,
        headline: str,
        evidence: list[SearchEvidence],
        analysis: AnalysisPayload,
        verification: VerificationPayload,
        qualification: QualificationOutput,
    ) -> str:
        lead = analysis.summary
        corroborated = verification.corroborated_points or ["Ainda nao ha corroboracao externa suficiente."]
        gaps = verification.missing_context or ["A verificacao ainda depende de apuracao complementar."]
        divergences = verification.conflicting_points or ["Nao foram identificadas divergencias materiais entre as fontes consultadas."]
        official_points = verification.official_source_points or ["Nenhuma fonte oficial foi localizada nesta execucao."]
        sources = (
            "\n".join(
                [
                    f"- **{item.source}** ({item.source_type}){' [oficial]' if item.is_official else ''}: [{item.title}]({item.url})"
                    if item.url
                    else f"- **{item.source}** ({item.source_type}){' [oficial]' if item.is_official else ''}: {item.title}"
                    for item in evidence[:5]
                ]
            )
            if evidence
            else "- Nenhuma fonte externa confirmada nesta execucao."
        )

        return "\n".join(
            [
                f"# {headline}",
                "",
                f"> Credibilidade: **{qualification.credibility_band}** | Score: **{qualification.confidence_score}**",
                "",
                "## Resumo",
                lead,
                "",
                "## O que se sabe",
                *(f"- {item}" for item in corroborated),
                "",
                "## Fontes oficiais e registros primarios",
                *(f"- {item}" for item in official_points),
                "",
                "## Divergencias entre fontes",
                *(f"- {item}" for item in divergences),
                "",
                "## Pontos que ainda exigem verificacao",
                *(f"- {item}" for item in gaps),
                "",
                "## Impacto editorial",
                qualification.editorial_verdict,
                "",
                "## Consenso entre fontes",
                verification.source_consensus or "Consenso ainda inconclusivo.",
                "",
                "## Acao recomendada",
                qualification.recommended_action,
                "",
                "## Fontes consultadas",
                sources,
                "",
            ]
        )

    def _extract_entities(self, text: str) -> list[str]:
        matches = re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ-]{2,}\b", text)
        unique: list[str] = []
        for item in matches:
            if item not in unique:
                unique.append(item)
        return unique

    def _detect_divergences(self, evidence: list[SearchEvidence]) -> list[str]:
        if len(evidence) < 2:
            return []

        points: list[str] = []
        number_claims: dict[str, set[str]] = {}
        stance_buckets = {"confirmation": [], "contradiction": []}

        for item in evidence:
            text = " ".join(filter(None, [item.title, item.description])).casefold()
            source_label = item.source
            numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", text))
            if numbers:
                number_claims[source_label] = numbers
            if any(term in text for term in CONFIRMATION_TERMS):
                stance_buckets["confirmation"].append(source_label)
            if any(term in text for term in CONTRADICTION_TERMS):
                stance_buckets["contradiction"].append(source_label)

        distinct_numbers = sorted({number for values in number_claims.values() for number in values})
        if len(distinct_numbers) > 1:
            points.append(
                "As fontes citam valores ou numeros diferentes no desenvolvimento da noticia: "
                + ", ".join(distinct_numbers[:5])
                + "."
            )

        if stance_buckets["confirmation"] and stance_buckets["contradiction"]:
            points.append(
                "Ha contraste de enquadramento entre fontes que confirmam o fato e fontes que o negam ou relativizam."
            )

        return points

    def _requires_official_confirmation(self, headline: str) -> bool:
        lowered = headline.casefold()
        return any(term in lowered for term in REGULATORY_TERMS)

    def _build_consensus_statement(
        self,
        unique_sources: list[str],
        official_sources: list[SearchEvidence],
        conflicting_points: list[str],
    ) -> str:
        if not unique_sources:
            return "Sem consenso verificavel por falta de evidencia externa."
        if conflicting_points:
            if official_sources:
                return (
                    f"Foram comparadas {len(unique_sources)} fontes, incluindo fonte oficial, mas ha divergencias materiais que exigem conciliacao editorial."
                )
            return (
                f"Foram comparadas {len(unique_sources)} fontes, mas ha divergencias materiais que exigem conciliacao editorial."
            )
        if official_sources:
            return (
                f"Foram comparadas {len(unique_sources)} fontes e ao menos uma fonte oficial reforca o enquadramento principal."
            )
        return f"Foram comparadas {len(unique_sources)} fontes independentes sem divergencia material relevante."
