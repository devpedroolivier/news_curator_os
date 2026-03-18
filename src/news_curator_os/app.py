from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .infrastructure import build_curation_service
from .models import HeadlineRequest, MonitoringSummary, PipelineRun

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_curation_service():
    return build_curation_service(get_settings())


def create_base_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        get_curation_service().initialize()
        yield

    app = FastAPI(
        title="News Curator OS",
        version="0.1.0",
        description="Painel de curadoria e verificacao de noticias baseado em headline.",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        service = get_curation_service()
        snapshot = await service.build_dashboard_snapshot()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "sample": snapshot.sample.model_dump(mode="json"),
                "recent_runs": [item.model_dump(mode="json") for item in snapshot.recent_runs],
                "monitoring": snapshot.monitoring.model_dump(mode="json"),
            },
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str | bool]:
        settings = get_settings()
        return {
            "status": "ok",
            "openai_enabled": bool(settings.openai_api_key),
            "news_provider": settings.news_search_provider,
        }

    @app.get("/readyz")
    async def readyz() -> dict[str, str | bool]:
        summary = get_curation_service().get_monitoring_summary()
        return {
            "status": "ready" if summary.database_ready else "not-ready",
            "database_ready": summary.database_ready,
            "openai_enabled": summary.openai_enabled,
            "news_provider": summary.search_provider,
        }

    @app.get("/api/v1/runs/recent")
    async def recent_runs() -> JSONResponse:
        items = [item.model_dump(mode="json") for item in get_curation_service().list_recent_runs()]
        return JSONResponse(items)

    @app.get("/api/v1/monitoring/summary", response_model=MonitoringSummary)
    async def monitoring_summary() -> MonitoringSummary:
        return get_curation_service().get_monitoring_summary()

    @app.post("/api/v1/pipeline/preview", response_model=PipelineRun)
    async def preview_pipeline(payload: HeadlineRequest) -> PipelineRun:
        return await get_curation_service().preview_headline(payload.headline)

    @app.post("/api/v1/pipeline/run", response_model=PipelineRun)
    async def run_pipeline(payload: HeadlineRequest) -> PipelineRun:
        return await get_curation_service().run_headline(payload.headline)

    return app
