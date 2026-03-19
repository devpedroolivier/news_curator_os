from __future__ import annotations

from ..application import NewsCuratorService
from ..config import Settings, get_settings
from ..deep_pipeline import DeepHeadlinePipeline
from ..pipeline import HeadlinePipeline
from ..repository import RunRepository


def build_repository(settings: Settings | None = None) -> RunRepository:
    active_settings = settings or get_settings()
    repository = RunRepository(active_settings.app_db_path)
    repository.initialize()
    return repository


def build_pipeline(
    settings: Settings | None = None,
    repository: RunRepository | None = None,
) -> HeadlinePipeline:
    active_settings = settings or get_settings()
    active_repository = repository or build_repository(active_settings)
    return HeadlinePipeline(settings=active_settings, repository=active_repository)


def build_safe_pipeline(settings: Settings | None = None) -> HeadlinePipeline:
    active_settings = settings or get_settings()
    safe_settings = active_settings.model_copy(
        update={
            "news_search_provider": "manual",
            "newsapi_key": None,
            "openai_api_key": None,
            "openai_organization": None,
        }
    )
    repository = build_repository(active_settings)
    return HeadlinePipeline(settings=safe_settings, repository=repository)


def build_deep_pipeline(
    settings: Settings | None = None,
    repository: RunRepository | None = None,
) -> DeepHeadlinePipeline:
    active_settings = settings or get_settings()
    active_repository = repository or build_repository(active_settings)
    return DeepHeadlinePipeline(settings=active_settings, repository=active_repository)


def build_curation_service(settings: Settings | None = None) -> NewsCuratorService:
    active_settings = settings or get_settings()
    return NewsCuratorService(
        settings=active_settings,
        repository_factory=lambda: build_repository(active_settings),
        pipeline_factory=lambda: build_pipeline(active_settings),
        safe_pipeline_factory=lambda: build_safe_pipeline(active_settings),
        deep_pipeline_factory=lambda: build_deep_pipeline(active_settings),
    )
