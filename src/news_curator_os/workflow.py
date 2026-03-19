import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from agno.workflow import Step, Workflow

from .infrastructure import build_curation_service

logger = logging.getLogger(__name__)


async def _run_pipeline_from_workflow_input(headline: str, persist: bool, stream: bool) -> str:
    service = build_curation_service()
    pipeline = service.pipeline
    callback = None
    if stream:
        def callback(event: str, payload: dict[str, object]) -> None:
            logger.info("[workflow:%s] %s", event, json.dumps(payload, ensure_ascii=False))
    result = (
        await pipeline.run(
            headline or "Headline de exemplo para triagem editorial",
            event_callback=callback,
        )
        if persist
        else await pipeline.preview(
            headline or "Headline de exemplo para triagem editorial",
            event_callback=callback,
        )
    )
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


def _preview_workflow_step(step_input):
    workflow_input = getattr(step_input, "input", None)
    if isinstance(workflow_input, dict):
        headline = workflow_input.get("headline")
        persist = bool(workflow_input.get("persist", False))
        stream = bool(workflow_input.get("stream", False))
    else:
        headline = getattr(workflow_input, "headline", None)
        persist = bool(getattr(workflow_input, "persist", False))
        stream = bool(getattr(workflow_input, "stream", False))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            asyncio.run,
            _run_pipeline_from_workflow_input(headline or "", persist, stream),
        )
        return future.result()


def build_bootstrap_workflow() -> Workflow:
    return Workflow(
        name="headline-curation-workflow",
        description="Workflow bootstrap para busca, analise, verificacao e qualificacao de headlines.",
        steps=[
            Step(
                name="headline-curation",
                description="Executa o fluxo editorial completo em modo preview.",
                executor=_preview_workflow_step,
            )
        ],
    )
