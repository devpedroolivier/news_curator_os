import pytest

from news_curator_os.agents import NewsCurationAgents
from news_curator_os.config import Settings
from news_curator_os.models import AnalysisPayload, SearchEvidence
from news_curator_os.search import NewsApiSearchProvider, QuerySpec


@pytest.mark.asyncio
async def test_newsapi_search_consolidates_up_to_five_unique_sources(monkeypatch) -> None:
    settings = Settings(
        NEWS_SEARCH_PROVIDER="newsapi",
        NEWSAPI_KEY="test-key",
        NEWS_MAX_ARTICLES=5,
    )
    provider = NewsApiSearchProvider(settings)

    async def fake_fetch(spec: QuerySpec) -> list[SearchEvidence]:
        if spec.domains:
            return [
                SearchEvidence(
                    title="Banco Central publica nova regra de credito",
                    source="Banco Central do Brasil",
                    url="https://www.bcb.gov.br/detalhenoticia/credito",
                    source_domain="bcb.gov.br",
                    source_type="official",
                    is_official=True,
                    description="Comunicado oficial sobre credito.",
                    query=spec.query,
                    relevance_score=98,
                )
            ]
        return [
            SearchEvidence(
                title="Reuters sobre credito",
                source="Reuters",
                url="https://www.reuters.com/world/americas/credito-1",
                source_domain="reuters.com",
                source_type="news",
                description="Fonte independente 1.",
                query=spec.query,
                relevance_score=90,
            ),
            SearchEvidence(
                title="AP sobre credito",
                source="Associated Press",
                url="https://apnews.com/article/credito-2",
                source_domain="apnews.com",
                source_type="news",
                description="Fonte independente 2.",
                query=spec.query,
                relevance_score=88,
            ),
            SearchEvidence(
                title="BBC sobre credito",
                source="BBC News",
                url="https://www.bbc.com/news/credito-3",
                source_domain="bbc.com",
                source_type="news",
                description="Fonte independente 3.",
                query=spec.query,
                relevance_score=86,
            ),
            SearchEvidence(
                title="G1 sobre credito",
                source="G1",
                url="https://g1.globo.com/economia/noticia/credito-4.ghtml",
                source_domain="g1.globo.com",
                source_type="news",
                description="Fonte independente 4.",
                query=spec.query,
                relevance_score=84,
            ),
            SearchEvidence(
                title="Reuters repetido",
                source="Reuters",
                url="https://www.reuters.com/world/americas/credito-5",
                source_domain="reuters.com",
                source_type="news",
                description="Mesmo dominio nao deve duplicar.",
                query=spec.query,
                relevance_score=70,
            ),
            SearchEvidence(
                title="Valor sobre credito",
                source="Valor Economico",
                url="https://valor.globo.com/financas/noticia/credito-6.ghtml",
                source_domain="valor.globo.com",
                source_type="news",
                description="Fonte independente 5.",
                query=spec.query,
                relevance_score=82,
            ),
        ]

    monkeypatch.setattr(provider, "_fetch_articles", fake_fetch)

    result = await provider.search("Banco Central anuncia nova medida para o credito no Brasil")

    assert result.mode == "live"
    assert result.unique_source_count == 5
    assert result.official_source_count == 1
    assert len(result.evidence) == 5
    assert result.evidence[0].is_official is True
    assert len({item.source_domain for item in result.evidence}) == 5


@pytest.mark.asyncio
async def test_fallback_verification_flags_divergence_and_official_sources() -> None:
    agents = NewsCurationAgents(Settings(OPENAI_API_KEY=""))
    analysis = AnalysisPayload(
        summary="Analise preliminar.",
        entities=["Banco Central do Brasil"],
        key_claims=["Banco Central anuncia medida."],
        risk_signals=[],
        score=72,
    )
    evidence = [
        SearchEvidence(
            title="Banco Central confirma linha de credito de 10 bilhoes",
            source="Banco Central do Brasil",
            url="https://www.bcb.gov.br/detalhenoticia/credito",
            source_domain="bcb.gov.br",
            source_type="official",
            is_official=True,
            description="O BC confirma a nova linha de credito de 10 bilhoes.",
            relevance_score=95,
        ),
        SearchEvidence(
            title="Reuters diz que medida pode chegar a 12 bilhoes",
            source="Reuters",
            url="https://www.reuters.com/world/americas/credito-1",
            source_domain="reuters.com",
            source_type="news",
            description="Agentes do mercado falam em 12 bilhoes.",
            relevance_score=88,
        ),
        SearchEvidence(
            title="Analistas negam impacto imediato da medida",
            source="BBC News",
            url="https://www.bbc.com/news/credito-3",
            source_domain="bbc.com",
            source_type="news",
            description="Relato diz que a medida nao confirma efeito imediato.",
            relevance_score=82,
        ),
    ]

    result = await agents.verify(
        "Banco Central anuncia nova medida para o credito no Brasil",
        evidence,
        analysis,
    )

    assert result.divergence_detected is True
    assert result.official_source_points
    assert any("numeros diferentes" in item for item in result.conflicting_points)
    assert "fonte oficial" in result.source_consensus.casefold()
