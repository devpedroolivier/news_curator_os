import os

import httpx
import pytest

from news_curator_os.app import create_base_app
from news_curator_os.config import get_settings


pytestmark = pytest.mark.e2e


def _live_env_ready() -> bool:
    return all(
        [
            os.getenv("RUN_LIVE_E2E") == "1",
            os.getenv("OPENAI_API_KEY"),
            os.getenv("NEWSAPI_KEY"),
        ]
    )


@pytest.mark.skipif(
    not _live_env_ready(),
    reason="Define RUN_LIVE_E2E=1, OPENAI_API_KEY e NEWSAPI_KEY para rodar o smoke test real.",
)
@pytest.mark.asyncio
async def test_live_pipeline_run_smoke() -> None:
    get_settings.cache_clear()
    app = create_base_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=120.0,
    ) as client:
        response = await client.post(
            "/api/v1/pipeline/run",
            json={"headline": "Banco Central anuncia nova medida para o credito no Brasil"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_provider"] == "newsapi"
    assert payload["llm_mode"] == "agno-openai"
    assert payload["execution_mode"].startswith("newsapi-")
    assert payload["run_id"]
    assert len(payload["stages"]) == 5
    assert payload["audit"]
    assert payload["output"]["recommended_action"]
