from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..config import Settings
from ..models import MonitoringSummary, PipelineRun, RecentRunSummary
from ..pipeline import HeadlinePipeline
from ..repository import RunRepository


@dataclass
class DashboardSnapshot:
    sample: PipelineRun
    recent_runs: list[RecentRunSummary]
    monitoring: MonitoringSummary


class NewsCuratorService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository_factory: Callable[[], RunRepository],
        pipeline_factory: Callable[[], HeadlinePipeline],
        safe_pipeline_factory: Callable[[], HeadlinePipeline],
    ) -> None:
        self.settings = settings
        self._repository_factory = repository_factory
        self._pipeline_factory = pipeline_factory
        self._safe_pipeline_factory = safe_pipeline_factory

    def initialize(self) -> None:
        self.repository.initialize()

    @property
    def repository(self) -> RunRepository:
        return self._repository_factory()

    @property
    def pipeline(self) -> HeadlinePipeline:
        return self._pipeline_factory()

    @property
    def safe_pipeline(self) -> HeadlinePipeline:
        return self._safe_pipeline_factory()

    async def preview_headline(self, headline: str) -> PipelineRun:
        return await self.pipeline.preview(headline)

    async def run_headline(self, headline: str) -> PipelineRun:
        return await self.pipeline.run(headline)

    def list_recent_runs(self, limit: int = 8) -> list[RecentRunSummary]:
        return self.repository.list_recent_runs(limit=limit)

    def get_monitoring_summary(self) -> MonitoringSummary:
        return self.repository.get_monitoring_summary(
            search_provider=self.settings.news_search_provider,
            openai_enabled=bool(self.settings.openai_api_key),
        )

    async def build_dashboard_snapshot(self) -> DashboardSnapshot:
        recent_runs = self.list_recent_runs()
        if recent_runs:
            sample = self.repository.get_run(recent_runs[0].run_id)
            if sample is None:
                sample = await self.safe_pipeline.preview(
                    "Urgente: Banco Central anuncia nova medida que afeta o credito no Brasil"
                )
        else:
            sample = await self.safe_pipeline.preview(
                "Urgente: Banco Central anuncia nova medida que afeta o credito no Brasil"
            )

        return DashboardSnapshot(
            sample=sample,
            recent_runs=recent_runs,
            monitoring=self.get_monitoring_summary(),
        )
