import httpx
import pytest

from news_curator_os.agents import NewsCurationAgents
from news_curator_os.config import Settings, get_settings
from news_curator_os.models import AnalysisPayload, SearchEvidence
from news_curator_os.search import NewsApiSearchProvider, QuerySpec


# --- NewsAPI degradation ---


@pytest.mark.asyncio
async def test_newsapi_without_key_returns_degraded() -> None:
    settings = Settings(NEWS_SEARCH_PROVIDER="newsapi", NEWSAPI_KEY="", NEWS_MAX_ARTICLES=5)
    provider = NewsApiSearchProvider(settings)
    result = await provider.search("Banco Central anuncia medida")
    assert result.mode == "degraded"
    assert result.total_results == 0
    assert result.evidence == []
    assert "NEWSAPI_KEY" in (result.note or "")


@pytest.mark.asyncio
async def test_newsapi_handles_http_error_per_query(monkeypatch) -> None:
    settings = Settings(
        NEWS_SEARCH_PROVIDER="newsapi",
        NEWSAPI_KEY="test-key",
        NEWS_MAX_ARTICLES=3,
    )
    provider = NewsApiSearchProvider(settings)
    call_count = 0

    async def fake_fetch_always_fails(spec: QuerySpec) -> list[SearchEvidence]:
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError(
            "Forbidden",
            request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
            response=httpx.Response(403),
        )

    monkeypatch.setattr(provider, "_fetch_articles", fake_fetch_always_fails)

    result = await provider.search("Banco Central anuncia medida")
    assert call_count >= 1
    assert result.mode == "live-empty"
    assert result.total_results == 0
    assert result.evidence == []
    assert any("erro=" in entry for entry in result.query_plan)


@pytest.mark.asyncio
async def test_newsapi_handles_timeout(monkeypatch) -> None:
    settings = Settings(
        NEWS_SEARCH_PROVIDER="newsapi",
        NEWSAPI_KEY="test-key",
        NEWS_MAX_ARTICLES=3,
    )
    provider = NewsApiSearchProvider(settings)

    async def fake_fetch_timeout(spec: QuerySpec) -> list[SearchEvidence]:
        raise httpx.ReadTimeout(
            "Read timed out",
            request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
        )

    monkeypatch.setattr(provider, "_fetch_articles", fake_fetch_timeout)

    result = await provider.search("Banco Central anuncia medida")
    assert result.mode == "live-empty"
    assert result.evidence == []
    assert any("ReadTimeout" in entry for entry in result.query_plan)


@pytest.mark.asyncio
async def test_newsapi_partial_failure_still_returns_evidence(monkeypatch) -> None:
    settings = Settings(
        NEWS_SEARCH_PROVIDER="newsapi",
        NEWSAPI_KEY="test-key",
        NEWS_MAX_ARTICLES=3,
    )
    provider = NewsApiSearchProvider(settings)
    call_index = 0

    async def fake_fetch_partial(spec: QuerySpec) -> list[SearchEvidence]:
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            raise httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
                response=httpx.Response(500),
            )
        return [
            SearchEvidence(
                title="Artigo recuperado",
                source="Reuters",
                url="https://reuters.com/article/1",
                source_domain="reuters.com",
                source_type="news",
                description="Artigo valido.",
                query=spec.query,
                relevance_score=85,
            ),
        ]

    monkeypatch.setattr(provider, "_fetch_articles", fake_fetch_partial)

    result = await provider.search("Banco Central anuncia medida")
    assert result.mode == "live"
    assert len(result.evidence) >= 1
    assert any("erro=" in entry for entry in result.query_plan)


# --- Agent degradation ---


@pytest.mark.asyncio
async def test_agent_without_openai_key_uses_fallback() -> None:
    agents = NewsCurationAgents(Settings(OPENAI_API_KEY=""))
    assert agents.llm_mode == "local-fallback"

    result = await agents.analyze("Banco Central anuncia medida", [])
    assert result.summary
    assert result.score > 0


@pytest.mark.asyncio
async def test_agent_with_invalid_key_falls_back_gracefully(monkeypatch) -> None:
    """When _run_structured catches an internal error it returns None,
    causing the public method to fall back to the local heuristic."""
    settings = Settings(OPENAI_API_KEY="sk-invalid-key-for-test")
    agents = NewsCurationAgents(settings)
    assert agents.llm_mode == "agno-openai"

    async def fake_run_structured_returns_none(*, name, instructions, payload, output_schema):
        return None

    monkeypatch.setattr(agents, "_run_structured", fake_run_structured_returns_none)

    evidence = [
        SearchEvidence(
            title="Artigo de teste",
            source="Reuters",
            url="https://reuters.com/test",
            source_domain="reuters.com",
            source_type="news",
            description="Descricao.",
            relevance_score=80,
        ),
    ]
    result = await agents.analyze("Banco Central anuncia medida", evidence)
    assert result.summary
    assert result.score > 0


@pytest.mark.asyncio
async def test_agent_verify_falls_back_on_error(monkeypatch) -> None:
    settings = Settings(OPENAI_API_KEY="sk-invalid")
    agents = NewsCurationAgents(settings)

    async def fake_run_structured_returns_none(*, name, instructions, payload, output_schema):
        return None

    monkeypatch.setattr(agents, "_run_structured", fake_run_structured_returns_none)

    analysis = AnalysisPayload(
        summary="Analise.",
        entities=["Banco Central"],
        key_claims=["Medida anunciada."],
        risk_signals=[],
        score=60,
    )
    result = await agents.verify("Banco Central anuncia medida", [], analysis)
    assert result.summary
    assert result.score >= 15


@pytest.mark.asyncio
async def test_agent_qualify_falls_back_on_error(monkeypatch) -> None:
    settings = Settings(OPENAI_API_KEY="sk-invalid")
    agents = NewsCurationAgents(settings)

    async def fake_run_structured_returns_none(*, name, instructions, payload, output_schema):
        return None

    monkeypatch.setattr(agents, "_run_structured", fake_run_structured_returns_none)

    from news_curator_os.models import VerificationPayload

    analysis = AnalysisPayload(
        summary="Analise.", entities=[], key_claims=[], risk_signals=[], score=50,
    )
    verification = VerificationPayload(
        summary="Verificacao.", score=40,
    )
    result = await agents.qualify("Headline de teste segura", [], analysis, verification)
    assert result.editorial_verdict
    assert result.confidence_score > 0


@pytest.mark.asyncio
async def test_agent_draft_article_falls_back_on_error(monkeypatch) -> None:
    settings = Settings(OPENAI_API_KEY="sk-invalid")
    agents = NewsCurationAgents(settings)

    async def fake_run_text_returns_none(*, name, instructions, payload):
        return None

    monkeypatch.setattr(agents, "_run_text", fake_run_text_returns_none)

    from news_curator_os.models import VerificationPayload

    analysis = AnalysisPayload(
        summary="Analise.", entities=[], key_claims=[], risk_signals=[], score=50,
    )
    verification = VerificationPayload(summary="Verificacao.", score=40)
    from news_curator_os.models import QualificationOutput

    qualification = QualificationOutput(
        editorial_verdict="Headline com suporte editorial inicial razoavel.",
        credibility_band="moderada",
        misinformation_risk="moderado",
        recommended_action="Revisar.",
        confidence_score=55,
    )
    result = await agents.draft_article("Headline teste", [], analysis, verification, qualification)
    assert "# Headline teste" in result
    assert len(result) > 50


# --- Full pipeline degradation via HTTP ---


@pytest.fixture
def degraded_app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "news_curator.db"))
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("APP_RELOAD", "false")
    monkeypatch.setenv("NEWS_SEARCH_PROVIDER", "newsapi")
    monkeypatch.setenv("NEWSAPI_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_ORGANIZATION", "")
    get_settings.cache_clear()
    from news_curator_os.app import create_base_app

    return create_base_app()


@pytest.mark.asyncio
async def test_pipeline_runs_in_fully_degraded_mode(degraded_app) -> None:
    transport = httpx.ASGITransport(app=degraded_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/pipeline/run",
            json={"headline": "Banco Central anuncia nova medida para o credito no Brasil"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "newsapi-degraded"
    assert payload["llm_mode"] == "local-fallback"
    assert payload["search_provider"] == "newsapi"
    assert len(payload["stages"]) == 5
    assert payload["output"]["confidence_score"] > 0
    assert payload["article_markdown"]


@pytest.mark.asyncio
async def test_healthz_reflects_degraded_state(degraded_app) -> None:
    transport = httpx.ASGITransport(app=degraded_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openai_enabled"] is False
    assert payload["news_provider"] == "newsapi"
