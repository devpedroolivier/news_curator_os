import httpx
import pytest

from news_curator_os.app import create_base_app
from news_curator_os.config import get_settings


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "news_curator.db"))
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("APP_RELOAD", "false")
    monkeypatch.setenv("NEWS_SEARCH_PROVIDER", "manual")
    monkeypatch.setenv("NEWSAPI_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_ORGANIZATION", "")
    get_settings.cache_clear()
    return create_base_app()


@pytest.mark.asyncio
async def test_healthcheck(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["news_provider"] == "manual"


@pytest.mark.asyncio
async def test_readiness_and_monitoring(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ready = await client.get("/readyz")
        summary = await client.get("/api/v1/monitoring/summary")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["database_ready"] is True
    assert payload["total_runs"] == 0


@pytest.mark.asyncio
async def test_dashboard_renders(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "Curadoria de noticias" in response.text
    assert "Historico" in response.text
    assert "Runs" in response.text


@pytest.mark.asyncio
async def test_pipeline_run_persists_and_lists_recent(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/pipeline/run",
            json={"headline": "Urgente: ministerio confirma nova regra para exportacao"},
        )
        recent = await client.get("/api/v1/runs/recent")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "fallback-manual"
    assert len(payload["stages"]) == 5
    assert payload["run_id"]
    assert payload["audit"]
    assert payload["output"]["recommended_action"]
    assert recent.status_code == 200
    recent_payload = recent.json()
    assert len(recent_payload) == 1
    assert recent_payload[0]["headline"] == "Urgente: ministerio confirma nova regra para exportacao"
