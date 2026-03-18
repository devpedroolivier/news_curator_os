import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "news_curator_os.agent_runtime:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )
