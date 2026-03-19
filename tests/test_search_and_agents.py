import pytest

from news_curator_os.agents import NewsCurationAgents
from news_curator_os.config import Settings
from news_curator_os.models import AnalysisPayload, QualificationOutput, SearchEvidence, VerificationPayload
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
                    description="Comunicado oficial do Banco Central sobre nova medida de credito no Brasil.",
                    query=spec.query,
                    relevance_score=98,
                )
            ]
        return [
            SearchEvidence(
                title="Banco Central anuncia medida de credito segundo Reuters",
                source="Reuters",
                url="https://www.reuters.com/world/americas/credito-1",
                source_domain="reuters.com",
                source_type="news",
                description="O Banco Central anunciou nova medida para o credito no Brasil.",
                query=spec.query,
                relevance_score=90,
            ),
            SearchEvidence(
                title="Nova medida do Banco Central para credito no Brasil",
                source="Associated Press",
                url="https://apnews.com/article/credito-2",
                source_domain="apnews.com",
                source_type="news",
                description="Banco Central do Brasil anuncia medida que afeta o credito.",
                query=spec.query,
                relevance_score=88,
            ),
            SearchEvidence(
                title="Banco Central do Brasil anuncia nova regra de credito",
                source="BBC News",
                url="https://www.bbc.com/news/credito-3",
                source_domain="bbc.com",
                source_type="news",
                description="Medida do Banco Central pode impactar o credito brasileiro.",
                query=spec.query,
                relevance_score=86,
            ),
            SearchEvidence(
                title="Banco Central anuncia medida para credito",
                source="G1",
                url="https://g1.globo.com/economia/noticia/credito-4.ghtml",
                source_domain="g1.globo.com",
                source_type="news",
                description="Nova medida do Banco Central para o credito no Brasil.",
                query=spec.query,
                relevance_score=84,
            ),
            SearchEvidence(
                title="Banco Central medida credito Reuters duplicado",
                source="Reuters",
                url="https://www.reuters.com/world/americas/credito-5",
                source_domain="reuters.com",
                source_type="news",
                description="Mesmo dominio nao deve duplicar. Banco Central credito Brasil.",
                query=spec.query,
                relevance_score=70,
            ),
            SearchEvidence(
                title="Credito no Brasil recebe nova medida do Banco Central",
                source="Valor Economico",
                url="https://valor.globo.com/financas/noticia/credito-6.ghtml",
                source_domain="valor.globo.com",
                source_type="news",
                description="Banco Central anuncia medida que afeta credito no Brasil.",
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


# --- Fix 1: Relevance filter ---


def test_select_evidence_filters_irrelevant_articles() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="test-key", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    evidence = [
        SearchEvidence(
            title="Banco Central anuncia nova taxa Selic",
            source="Reuters", url="https://reuters.com/1",
            source_domain="reuters.com", source_type="news",
            description="O Banco Central decidiu manter a Selic em patamar elevado.",
            relevance_score=90,
        ),
        SearchEvidence(
            title="Receita de bolo de chocolate para festas",
            source="Food Blog", url="https://foodblog.com/bolo",
            source_domain="foodblog.com", source_type="other",
            description="Aprenda a fazer um bolo delicioso.",
            relevance_score=85,
        ),
    ]
    result = provider._select_evidence(
        "Banco Central anuncia nova taxa Selic", evidence, limit=5,
    )
    assert len(result) == 1
    assert result[0].source == "Reuters"


def test_select_evidence_keeps_all_when_all_relevant() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="test-key", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    evidence = [
        SearchEvidence(
            title="Selic sobe para 14 por cento", source="Reuters",
            url="https://reuters.com/1", source_domain="reuters.com",
            source_type="news", description="Banco Central elevou Selic.", relevance_score=90,
        ),
        SearchEvidence(
            title="Impacto da Selic no credito", source="BBC",
            url="https://bbc.com/1", source_domain="bbc.com",
            source_type="news", description="Banco Central e o credito.", relevance_score=85,
        ),
    ]
    result = provider._select_evidence(
        "Banco Central anuncia nova taxa Selic", evidence, limit=5,
    )
    assert len(result) == 2


def test_select_evidence_fallback_keeps_all_when_none_pass_threshold() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="test-key", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    evidence = [
        SearchEvidence(
            title="Totally unrelated article about sports",
            source="ESPN", url="https://espn.com/1",
            source_domain="espn.com", source_type="other",
            description="Football scores today.", relevance_score=70,
        ),
    ]
    result = provider._select_evidence(
        "Banco Central anuncia nova taxa Selic", evidence, limit=5,
    )
    assert len(result) == 1


# --- Fix 2: Smarter queries ---


def test_build_queries_uses_entities() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="test-key", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    queries = provider._build_queries(
        "Banco Central anuncia nova medida para o credito no Brasil",
    )
    entity_query = next((q for q in queries if q.label == "entity-focused"), None)
    assert entity_query is not None
    assert any(term in entity_query.query for term in ["Banco", "Central", "Brasil"])


def test_build_queries_includes_thematic_terms() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="test-key", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    queries = provider._build_queries("Governo anuncia novo decreto sobre saude")
    entity_query = next((q for q in queries if q.label == "entity-focused"), None)
    assert entity_query is not None
    assert any(term in entity_query.query for term in ["Governo", "decreto", "saude"])


# --- Fix 3: Score guardrail ---


@pytest.mark.asyncio
async def test_qualify_caps_score_at_42_when_no_evidence(monkeypatch) -> None:
    settings = Settings(OPENAI_API_KEY="sk-test-key")
    agents = NewsCurationAgents(settings)

    async def fake_run_structured(*, name, instructions, payload, output_schema):
        return QualificationOutput(
            editorial_verdict="Headline confiavel.",
            credibility_band="alta",
            misinformation_risk="baixo",
            recommended_action="Publicar.",
            confidence_score=85,
        )

    monkeypatch.setattr(agents, "_run_structured", fake_run_structured)

    analysis = AnalysisPayload(summary="A.", entities=[], key_claims=[], risk_signals=[], score=70)
    verification = VerificationPayload(summary="V.", score=60)

    result = await agents.qualify("Headline sem evidencia", [], analysis, verification)
    assert result.confidence_score <= 42


@pytest.mark.asyncio
async def test_qualify_does_not_cap_when_evidence_exists(monkeypatch) -> None:
    settings = Settings(OPENAI_API_KEY="sk-test-key")
    agents = NewsCurationAgents(settings)

    async def fake_run_structured(*, name, instructions, payload, output_schema):
        return QualificationOutput(
            editorial_verdict="Headline confiavel.",
            credibility_band="alta",
            misinformation_risk="baixo",
            recommended_action="Publicar.",
            confidence_score=85,
        )

    monkeypatch.setattr(agents, "_run_structured", fake_run_structured)

    analysis = AnalysisPayload(summary="A.", entities=[], key_claims=[], risk_signals=[], score=70)
    verification = VerificationPayload(summary="V.", score=60)
    evidence = [
        SearchEvidence(title="Artigo real", source="Reuters", url="https://reuters.com/1",
                       source_domain="reuters.com", source_type="news", relevance_score=90),
    ]
    result = await agents.qualify("Headline com evidencia", evidence, analysis, verification)
    assert result.confidence_score == 85


# --- Fix 4: URL sanitization ---


def test_sanitize_keeps_valid_urls() -> None:
    agents = NewsCurationAgents(Settings(OPENAI_API_KEY=""))
    evidence = [
        SearchEvidence(title="Artigo", source="Reuters",
                       url="https://reuters.com/article/1",
                       source_domain="reuters.com", source_type="news", relevance_score=90),
    ]
    article = "Leia em [Reuters](https://reuters.com/article/1) aqui."
    result = agents._sanitize_article_urls(article, evidence)
    assert "[Reuters](https://reuters.com/article/1)" in result


def test_sanitize_strips_hallucinated_urls() -> None:
    agents = NewsCurationAgents(Settings(OPENAI_API_KEY=""))
    evidence = [
        SearchEvidence(title="Artigo", source="Reuters",
                       url="https://reuters.com/article/1",
                       source_domain="reuters.com", source_type="news", relevance_score=90),
    ]
    article = "Leia em [Fonte Falsa](https://fakesource.com/inventado) aqui."
    result = agents._sanitize_article_urls(article, evidence)
    assert "https://fakesource.com/inventado" not in result
    assert "Fonte Falsa" in result


def test_sanitize_removes_all_links_when_no_evidence_urls() -> None:
    agents = NewsCurationAgents(Settings(OPENAI_API_KEY=""))
    evidence = [
        SearchEvidence(title="Artigo", source="Reuters", url=None,
                       source_domain="reuters.com", source_type="news", relevance_score=90),
    ]
    article = "Veja [SEBRAE](https://sebrae.com.br/algo) para detalhes."
    result = agents._sanitize_article_urls(article, evidence)
    assert "https://sebrae.com.br/algo" not in result
    assert "SEBRAE" in result
