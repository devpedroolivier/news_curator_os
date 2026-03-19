from __future__ import annotations

import logging
from urllib.parse import urlparse

from .config import Settings
from .models import SearchEvidence, SearchExecution
from .search import OFFICIAL_DOMAINS, TRUSTED_NEWS_DOMAINS
from .text_utils import derive_official_domains, extract_entities, tokenize

logger = logging.getLogger(__name__)


class TavilySearchProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(
        self,
        headline: str,
        *,
        language: str = "pt",
        extra_queries: list[str] | None = None,
        topic: str = "news",
    ) -> SearchExecution:
        if not self.settings.tavily_api_key:
            logger.warning("Tavily API key not configured")
            return SearchExecution(
                provider="tavily",
                mode="degraded",
                primary_query=headline,
                query_plan=["TAVILY_API_KEY nao configurada."],
                total_results=0,
                evidence=[],
                unique_source_count=0,
                official_source_count=0,
                note="TAVILY_API_KEY nao configurada.",
            )

        from tavily import TavilyClient

        client = TavilyClient(api_key=self.settings.tavily_api_key)
        queries = self._build_queries(headline, language=language, extra_queries=extra_queries)
        collected: list[SearchEvidence] = []
        query_plan: list[str] = []
        target = min(max(self.settings.news_max_articles, 1), 10)

        for query_text in queries:
            try:
                response = client.search(
                    query=query_text,
                    search_depth="advanced",
                    topic=topic,
                    max_results=7,
                    include_answer=False,
                )
            except Exception as exc:
                logger.warning("Tavily search failed for %r: %s", query_text, exc)
                query_plan.append(f"{query_text} | erro={exc.__class__.__name__}")
                continue

            results = response.get("results", [])
            query_plan.append(f"{query_text} | results={len(results)}")

            for item in results:
                url = item.get("url", "")
                domain = self._extract_domain(url)
                source_type, is_official = self._classify_source(
                    item.get("title", ""), domain,
                )
                collected.append(SearchEvidence(
                    title=item.get("title", "Sem titulo"),
                    source=domain or "Fonte desconhecida",
                    url=url,
                    source_domain=domain,
                    source_type=source_type,
                    is_official=is_official,
                    description=item.get("content", ""),
                    query=query_text,
                    relevance_score=int((item.get("score", 0.5)) * 100),
                ))

            if len(self._dedupe(collected)) >= target:
                break

        selected = self._dedupe(collected)[:target]
        official_count = sum(1 for e in selected if e.is_official)

        return SearchExecution(
            provider="tavily",
            mode="live" if selected else "live-empty",
            primary_query=queries[0] if queries else headline,
            query_plan=query_plan,
            total_results=len(selected),
            evidence=selected,
            unique_source_count=len(selected),
            official_source_count=official_count,
            note=(
                f"Tavily: {len(selected)} fontes consolidadas, {official_count} oficial(is)."
                if selected
                else "Tavily: busca executada mas sem resultados relevantes."
            ),
        )

    def _build_queries(
        self,
        headline: str,
        *,
        language: str,
        extra_queries: list[str] | None,
    ) -> list[str]:
        entities = extract_entities(headline)
        tokens = tokenize(headline)
        official_domains = derive_official_domains(headline)

        queries: list[str] = []
        if extra_queries:
            queries.extend(extra_queries)
        else:
            queries.append(headline)

            entity_query = " ".join(entities[:5]) if entities else " ".join(tokens[:5])
            if entity_query != headline:
                queries.append(entity_query)

            if official_domains and entities:
                queries.append(f"{' '.join(entities[:3])} site:{official_domains[0]}")

        seen = set()
        unique: list[str] = []
        for q in queries:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                unique.append(q)
        return unique

    def _dedupe(self, evidence: list[SearchEvidence]) -> list[SearchEvidence]:
        seen: dict[str, SearchEvidence] = {}
        for item in evidence:
            key = item.source_domain or item.url or item.title
            if key not in seen or (item.relevance_score or 0) > (seen[key].relevance_score or 0):
                seen[key] = item
        return sorted(seen.values(), key=lambda e: e.relevance_score or 0, reverse=True)

    def _extract_domain(self, url: str) -> str | None:
        if not url:
            return None
        try:
            hostname = urlparse(url).hostname or ""
        except ValueError:
            return None
        hostname = hostname.casefold().strip(".")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname or None

    def _classify_source(self, title: str, domain: str | None) -> tuple[str, bool]:
        d = (domain or "").casefold()
        if self._is_official(d):
            return "official", True
        if any(d == t or d.endswith(f".{t}") for t in TRUSTED_NEWS_DOMAINS):
            return "news", False
        return "other", False

    def _is_official(self, domain: str) -> bool:
        if not domain:
            return False
        if domain.endswith(".gov") or domain.endswith(".gov.br"):
            return True
        if domain.endswith(".jus.br") or domain.endswith(".leg.br"):
            return True
        return any(domain == c or domain.endswith(f".{c}") for c in OFFICIAL_DOMAINS)
