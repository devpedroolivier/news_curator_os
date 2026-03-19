import logging

import uvicorn

from .config import get_settings


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    uvicorn.run(
        "news_curator_os.agent_runtime:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )
