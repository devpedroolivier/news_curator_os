from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from pathlib import Path
from typing import Any

from .config import get_settings
from .infrastructure import build_curation_service
from .workflow import build_bootstrap_workflow


def add_common_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--persist", action="store_true", help="Persiste o run no SQLite.")
    parser.add_argument("--stream", action="store_true", help="Exibe progresso etapa por etapa no terminal.")
    parser.add_argument("--output-json", help="Caminho para salvar o resultado em JSON.")
    parser.add_argument("--output-md", help="Caminho do arquivo .md ou diretorio de saida para a redacao final.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="news-curator-cli",
        description="Executa o fluxo e o workflow end-to-end do News Curator OS via terminal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    flow_parser = subparsers.add_parser("flow", help="Executa o pipeline diretamente.")
    flow_parser.add_argument("headline", help="Headline para curadoria.")
    add_common_execution_args(flow_parser)

    workflow_parser = subparsers.add_parser("workflow", help="Executa via Agno Workflow.")
    workflow_parser.add_argument("headline", help="Headline para curadoria.")
    add_common_execution_args(workflow_parser)

    batch_parser = subparsers.add_parser("batch", help="Executa varias headlines via .txt ou .csv.")
    batch_parser.add_argument("input_file", help="Arquivo .txt ou .csv com headlines.")
    batch_parser.add_argument(
        "--mode",
        choices=["flow", "workflow"],
        default="flow",
        help="Escolhe entre pipeline direto e workflow do Agno.",
    )
    add_common_execution_args(batch_parser)

    return parser


def build_stream_callback(prefix: str):
    def _callback(event: str, payload: dict[str, Any]) -> None:
        print(f"[{prefix}:{event}] {json.dumps(payload, ensure_ascii=False)}", flush=True)

    return _callback


async def run_flow(headline: str, persist: bool, stream: bool = False) -> dict[str, Any]:
    service = build_curation_service(get_settings())
    pipeline = service.pipeline
    callback = build_stream_callback("flow") if stream else None
    result = await (
        pipeline.run(headline, event_callback=callback)
        if persist
        else pipeline.preview(headline, event_callback=callback)
    )
    return result.model_dump(mode="json")


async def run_workflow(headline: str, persist: bool, stream: bool = False) -> dict[str, Any]:
    workflow = build_bootstrap_workflow()
    result = workflow.run({"headline": headline, "persist": persist, "stream": stream})
    content = result.content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "headline": headline,
                "execution_mode": "workflow-error",
                "llm_mode": "-",
                "search_provider": "-",
                "evidence": [],
                "output": {
                    "credibility_band": "-",
                    "confidence_score": "-",
                    "recommended_action": content,
                },
                "stages": [],
                "audit": [],
            }
    if isinstance(content, dict):
        return content
    return {"content": str(content)}


def load_headlines_from_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    if file_path.suffix.lower() == ".txt":
        return [
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames and "headline" in reader.fieldnames:
                return [row["headline"].strip() for row in reader if row.get("headline", "").strip()]
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            rows = [row for row in reader if row]
        return [row[0].strip() for row in rows if row[0].strip()]

    raise ValueError("Formato nao suportado. Use .txt ou .csv")


def write_json_output(path: str, payload: Any) -> None:
    file_path = Path(path)
    parent = file_path.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(
            f"O caminho pai '{parent}' existe como arquivo. Use outro diretorio para --output-json."
        )
    parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify_headline(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "headline"


def resolve_markdown_output_path(path: str | None, payload: dict[str, Any], *, mode: str, batch: bool = False) -> Path:
    headline = payload.get("headline", "headline")
    run_id = payload.get("run_id", "run")
    default_name = f"{mode}_{slugify_headline(headline)[:60]}_{str(run_id)[:8]}.md"

    if path is None:
        base_dir = Path("artifacts/batch_markdown" if batch else "artifacts")
        return base_dir / default_name

    candidate = Path(path)
    if batch or candidate.suffix.lower() != ".md":
        return candidate / default_name
    return candidate


def write_markdown_output(path: str | None, payload: dict[str, Any], *, mode: str, batch: bool = False) -> Path:
    file_path = resolve_markdown_output_path(path, payload, mode=mode, batch=batch)
    parent = file_path.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(
            f"O caminho pai '{parent}' existe como arquivo. Use outro diretorio para o markdown."
        )
    parent.mkdir(parents=True, exist_ok=True)
    markdown = payload.get("article_markdown", "").strip()
    if not markdown:
        markdown = f"# {payload.get('headline', 'Sem titulo')}\n\nNenhuma redacao foi gerada.\n"
    file_path.write_text(markdown + ("\n" if not markdown.endswith("\n") else ""), encoding="utf-8")
    return file_path


def render_terminal_report(payload: dict[str, Any], *, mode: str) -> str:
    lines: list[str] = []
    lines.append(f"mode: {mode}")
    lines.append(f"run_id: {payload.get('run_id', '-')}")
    lines.append(f"headline: {payload.get('headline', '-')}")
    lines.append(f"execution_mode: {payload.get('execution_mode', '-')}")
    lines.append(f"llm_mode: {payload.get('llm_mode', '-')}")
    lines.append(f"search_provider: {payload.get('search_provider', '-')}")
    lines.append(f"evidence_count: {len(payload.get('evidence', []))}")

    output = payload.get("output", {})
    lines.append(f"credibility_band: {output.get('credibility_band', '-')}")
    lines.append(f"confidence_score: {output.get('confidence_score', '-')}")
    lines.append(f"recommended_action: {output.get('recommended_action', '-')}")
    if payload.get("article_markdown"):
        lines.append(f"article_markdown_chars: {len(payload.get('article_markdown', ''))}")

    stages = payload.get("stages", [])
    if stages:
        lines.append("")
        lines.append("stages:")
        for stage in stages:
            lines.append(
                f"- {stage.get('key')}: state={stage.get('state')} score={stage.get('score')} summary={stage.get('summary')}"
            )

    evidence = payload.get("evidence", [])
    if evidence:
        lines.append("")
        lines.append("evidence:")
        for item in evidence[:3]:
            lines.append(f"- {item.get('source')}: {item.get('title')}")

    audit = payload.get("audit", [])
    if audit:
        lines.append("")
        lines.append("audit:")
        for item in audit[:5]:
            lines.append(f"- {item.get('stage')} [{item.get('severity')}]: {item.get('message')}")

    return "\n".join(lines)


async def run_batch(
    input_file: str,
    *,
    mode: str,
    persist: bool,
    stream: bool,
    output_md: str | None,
) -> list[dict[str, Any]]:
    headlines = load_headlines_from_file(input_file)
    results: list[dict[str, Any]] = []
    for index, headline in enumerate(headlines, start=1):
        print(f"batch_item: {index}/{len(headlines)} | headline: {headline}", flush=True)
        if mode == "flow":
            payload = await run_flow(headline, persist, stream=stream)
        else:
            payload = await run_workflow(headline, persist, stream=stream)
        results.append(payload)
        md_path = write_markdown_output(output_md, payload, mode=mode, batch=True)
        print(f"markdown_saved: {md_path}", flush=True)
        print(render_terminal_report(payload, mode=f"{mode}-batch"), flush=True)
        print("", flush=True)
    return results


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    get_settings.cache_clear()

    if args.command == "flow":
        payload = await run_flow(args.headline, args.persist, stream=args.stream)
        if args.output_json:
            write_json_output(args.output_json, payload)
        md_path = write_markdown_output(args.output_md, payload, mode="flow")
        print(render_terminal_report(payload, mode=args.command))
        print(f"\nmarkdown_saved: {md_path}")
    elif args.command == "workflow":
        payload = await run_workflow(args.headline, args.persist, stream=args.stream)
        if args.output_json:
            write_json_output(args.output_json, payload)
        md_path = write_markdown_output(args.output_md, payload, mode="workflow")
        print(render_terminal_report(payload, mode=args.command))
        print(f"\nmarkdown_saved: {md_path}")
    else:
        payloads = await run_batch(
            args.input_file,
            mode=args.mode,
            persist=args.persist,
            stream=args.stream,
            output_md=args.output_md,
        )
        if args.output_json:
            write_json_output(args.output_json, payloads)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
