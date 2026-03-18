from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import Settings
from .models import SearchEvidence, SearchExecution

OFFICIAL_DOMAINS = {
    "gov.br",
    "bcb.gov.br",
    "fazenda.gov.br",
    "planalto.gov.br",
    "in.gov.br",
    "ibge.gov.br",
    "saude.gov.br",
    "cvm.gov.br",
    "camara.leg.br",
    "senado.leg.br",
    "tse.jus.br",
    "stf.jus.br",
    "who.int",
    "whitehouse.gov",
    "treasury.gov",
    "sec.gov",
    "federalreserve.gov",
    "justice.gov",
    "cdc.gov",
    "fda.gov",
    "worldbank.org",
    "imf.org",
    "europa.eu",
    "ec.europa.eu",
}

TRUSTED_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "ft.com",
    "nytimes.com",
    "wsj.com",
    "theguardian.com",
    "g1.globo.com",
    "globo.com",
    "folha.uol.com.br",
    "uol.com.br",
    "estadao.com.br",
    "valor.globo.com",
    "cnn.com",
    "bloomberg.com",
    "cnbc.com",
}

OFFICIAL_KEYWORD_DOMAINS = {
    "banco central": ["bcb.gov.br", "fazenda.gov.br", "gov.br"],
    "credito": ["bcb.gov.br", "fazenda.gov.br", "gov.br"],
    "selic": ["bcb.gov.br", "fazenda.gov.br"],
    "pix": ["bcb.gov.br"],
    "ministerio": ["gov.br", "planalto.gov.br", "in.gov.br"],
    "governo": ["gov.br", "planalto.gov.br", "in.gov.br"],
    "decreto": ["planalto.gov.br", "in.gov.br", "gov.br"],
    "portaria": ["in.gov.br", "gov.br"],
    "lei": ["planalto.gov.br", "camara.leg.br", "senado.leg.br"],
    "saude": ["saude.gov.br", "gov.br", "who.int"],
    "vacina": ["saude.gov.br", "gov.br", "who.int", "fda.gov", "cdc.gov"],
    "inflacao": ["ibge.gov.br", "bcb.gov.br"],
    "inflação": ["ibge.gov.br", "bcb.gov.br"],
    "desemprego": ["ibge.gov.br"],
    "eleicao": ["tse.jus.br", "camara.leg.br", "senado.leg.br"],
    "eleição": ["tse.jus.br", "camara.leg.br", "senado.leg.br"],
    "stf": ["stf.jus.br"],
    "cvm": ["cvm.gov.br", "sec.gov"],
    "bitcoin": ["bcb.gov.br", "cvm.gov.br", "sec.gov"],
    "crypto": ["bcb.gov.br", "cvm.gov.br", "sec.gov"],
}


@dataclass(frozen=True)
class QuerySpec:
    query: str
    language: str | None
    domains: tuple[str, ...] = ()
    label: str = "news"


class NewsSearchProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, headline: str) -> SearchExecution:
        if self.settings.news_search_provider == "newsapi":
            provider = NewsApiSearchProvider(self.settings)
            return await provider.search(headline)
        return ManualSearchProvider(self.settings).search(headline)


class ManualSearchProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, headline: str) -> SearchExecution:
        entities = self._extract_entities(headline)
        official_domains = self._suggest_official_domains(headline)
        query_plan = [
            f'Consulta exata: "{headline}"',
            f"Consulta expandida: {' '.join(self._tokens(headline)[:6])} fact check",
            (
                f"Consulta por entidades: {' '.join(entities[:3])} site:reuters.com OR site:apnews.com OR site:bbc.com"
                if entities
                else "Consulta por contexto: data local fonte oficial"
            ),
        ]
        if official_domains:
            query_plan.append(
                "Consulta oficial sugerida: "
                + ", ".join(f"site:{domain}" for domain in official_domains[:5])
            )

        return SearchExecution(
            provider="manual",
            mode="fallback",
            primary_query=headline,
            query_plan=query_plan,
            total_results=0,
            evidence=[],
            unique_source_count=0,
            official_source_count=0,
            note="Provider real nao configurado. O sistema esta sugerindo consultas para verificacao manual.",
        )

    def _extract_entities(self, headline: str) -> list[str]:
        matches = re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇ-]{2,}\b", headline)
        unique: list[str] = []
        for item in matches:
            if item not in unique:
                unique.append(item)
        return unique

    def _suggest_official_domains(self, headline: str) -> list[str]:
        lowered = headline.casefold()
        domains: list[str] = []
        for keyword, candidates in OFFICIAL_KEYWORD_DOMAINS.items():
            if keyword in lowered:
                for domain in candidates:
                    if domain not in domains:
                        domains.append(domain)
        return domains

    def _tokens(self, headline: str) -> list[str]:
        return [token for token in re.findall(r"\w+", headline) if len(token) > 3]


class NewsApiSearchProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, headline: str) -> SearchExecution:
        if not self.settings.newsapi_key:
            return SearchExecution(
                provider="newsapi",
                mode="degraded",
                primary_query=headline,
                query_plan=[f'GET /v2/everything q="{headline}" via X-Api-Key'],
                total_results=0,
                evidence=[],
                unique_source_count=0,
                official_source_count=0,
                note="NEWSAPI_KEY nao configurada. Provider real indisponivel neste ambiente.",
            )

        query_specs = self._build_queries(headline)
        collected: list[SearchEvidence] = []
        query_plan: list[str] = []
        target_sources = min(max(self.settings.news_max_articles, 1), 5)

        for spec in query_specs:
            try:
                result = await self._fetch_articles(spec)
            except httpx.HTTPError as exc:
                query_plan.append(
                    f"{spec.query} | language={spec.language or 'all'} | domains={','.join(spec.domains) or 'all'} | erro={exc.__class__.__name__}"
                )
                continue

            collected.extend(result)
            query_plan.append(
                f"{spec.query} | language={spec.language or 'all'} | domains={','.join(spec.domains) or 'all'} | results={len(result)}"
            )

            selected_preview = self._select_evidence(collected, limit=target_sources)
            if len(selected_preview) >= target_sources and self._official_coverage_sufficient(headline, selected_preview):
                break

        selected = self._select_evidence(collected, limit=target_sources)
        official_count = sum(1 for item in selected if item.is_official)
        mode = "live" if selected else "live-empty"

        return SearchExecution(
            provider="newsapi",
            mode=mode,
            primary_query=query_specs[0].query if query_specs else headline,
            query_plan=query_plan,
            total_results=len(selected),
            evidence=selected,
            unique_source_count=len(selected),
            official_source_count=official_count,
            note=(
                f"Busca consolidada em ate {target_sources} fontes distintas, incluindo {official_count} fonte(s) oficial(is)."
                if selected
                else "Busca real executada, mas sem artigos retornados apos todos os fallbacks de consulta."
            ),
        )

    async def _fetch_articles(self, spec: QuerySpec) -> list[SearchEvidence]:
        params = {
            "q": spec.query,
            "searchIn": "title,description",
            "sortBy": "publishedAt",
            "pageSize": str(min(max(self.settings.news_max_articles * 2, 5), 20)),
        }
        if spec.language:
            params["language"] = spec.language
        if spec.domains:
            params["domains"] = ",".join(spec.domains)
        headers = {"X-Api-Key": self.settings.newsapi_key or ""}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(self.settings.newsapi_base_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        articles = payload.get("articles", [])
        normalized: list[SearchEvidence] = []
        for index, article in enumerate(articles, start=1):
            url = article.get("url")
            source_domain = self._extract_domain(url)
            source = (article.get("source") or {}).get("name") or source_domain or "Fonte desconhecida"
            source_type, is_official = self._classify_source(source, source_domain)
            trust_bonus = 14 if is_official else 8 if source_type == "news" else 0
            normalized.append(
                SearchEvidence(
                    title=article.get("title") or "Sem titulo",
                    source=source,
                    url=url,
                    source_domain=source_domain,
                    source_type=source_type,
                    is_official=is_official,
                    published_at=article.get("publishedAt"),
                    description=article.get("description"),
                    query=spec.query,
                    relevance_score=max(35, 100 - (index * 7) + trust_bonus),
                )
            )
        return normalized

    def _build_queries(self, headline: str) -> list[QuerySpec]:
        tokens = self._tokens(headline)
        short_tokens = tokens[:4]
        medium_tokens = tokens[:6]
        entity_like = [token for token in short_tokens if len(token) > 4]
        official_domains = tuple(self._derive_official_domains(headline))

        raw_candidates = [
            QuerySpec(query=f'"{headline}"', language=self.settings.news_language, label="exact"),
            QuerySpec(query=" ".join(medium_tokens) or headline, language=self.settings.news_language, label="expanded"),
            QuerySpec(query=" ".join(short_tokens) or headline, language=self.settings.news_language, label="short"),
            QuerySpec(query=" ".join(entity_like) or " ".join(short_tokens) or headline, language=None, label="global"),
        ]
        if official_domains:
            raw_candidates.append(
                QuerySpec(
                    query=" ".join(entity_like) or " ".join(short_tokens) or headline,
                    language=None,
                    domains=official_domains[:5],
                    label="official",
                )
            )

        unique: OrderedDict[tuple[str, str | None, tuple[str, ...]], QuerySpec] = OrderedDict()
        for candidate in raw_candidates:
            query = candidate.query.strip()
            key = (query, candidate.language, candidate.domains)
            if query and key not in unique:
                unique[key] = QuerySpec(
                    query=query,
                    language=candidate.language,
                    domains=candidate.domains,
                    label=candidate.label,
                )
        return list(unique.values())

    def _select_evidence(self, evidence: list[SearchEvidence], *, limit: int) -> list[SearchEvidence]:
        deduped: dict[str, SearchEvidence] = {}
        for item in evidence:
            key = self._evidence_key(item)
            current = deduped.get(key)
            if current is None or self._evidence_rank(item) > self._evidence_rank(current):
                deduped[key] = item

        ranked = sorted(
            deduped.values(),
            key=lambda item: self._evidence_rank(item),
            reverse=True,
        )
        return ranked[:limit]

    def _official_coverage_sufficient(self, headline: str, evidence: list[SearchEvidence]) -> bool:
        if not self._derive_official_domains(headline):
            return True
        return any(item.is_official for item in evidence)

    def _derive_official_domains(self, headline: str) -> list[str]:
        lowered = headline.casefold()
        domains: list[str] = []
        for keyword, candidates in OFFICIAL_KEYWORD_DOMAINS.items():
            if keyword in lowered:
                for domain in candidates:
                    if domain not in domains:
                        domains.append(domain)
        return domains

    def _evidence_key(self, item: SearchEvidence) -> str:
        if item.source_domain:
            return item.source_domain
        if item.url:
            return item.url.casefold()
        return re.sub(r"\W+", "-", item.source.casefold()).strip("-")

    def _evidence_rank(self, item: SearchEvidence) -> tuple[int, int, int, str]:
        quality = 2 if item.is_official else 1 if item.source_type == "news" else 0
        return (
            quality,
            item.relevance_score or 0,
            1 if item.description else 0,
            item.published_at or "",
        )

    def _classify_source(self, source: str, domain: str | None) -> tuple[str, bool]:
        normalized_domain = (domain or "").casefold()
        if self._is_official_domain(normalized_domain):
            return "official", True
        if any(
            normalized_domain == trusted or normalized_domain.endswith(f".{trusted}")
            for trusted in TRUSTED_NEWS_DOMAINS
        ):
            return "news", False
        if "reuters" in source.casefold() or "bbc" in source.casefold():
            return "news", False
        return "other", False

    def _is_official_domain(self, domain: str) -> bool:
        if not domain:
            return False
        if domain.endswith(".gov") or domain.endswith(".gov.br"):
            return True
        if domain.endswith(".jus.br") or domain.endswith(".leg.br") or domain.endswith(".mil.br"):
            return True
        return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in OFFICIAL_DOMAINS)

    def _extract_domain(self, url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        hostname = (parsed.hostname or "").casefold().strip(".")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname or None

    def _tokens(self, headline: str) -> list[str]:
        return [token for token in re.findall(r"\w+", headline) if len(token) > 3]
