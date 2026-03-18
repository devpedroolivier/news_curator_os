import pytest

from news_curator_os.infrastructure import build_curation_service


@pytest.mark.asyncio
async def test_dashboard_snapshot_uses_safe_preview_when_empty_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "news_curator.db"))
    monkeypatch.setenv("NEWS_SEARCH_PROVIDER", "manual")
    monkeypatch.setenv("NEWSAPI_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    from news_curator_os.config import get_settings

    get_settings.cache_clear()
    service = build_curation_service()

    snapshot = await service.build_dashboard_snapshot()

    assert snapshot.sample.headline
    assert snapshot.recent_runs == []
    assert snapshot.monitoring.database_ready is True
