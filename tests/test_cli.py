from pathlib import Path

from news_curator_os.cli import (
    load_headlines_from_file,
    render_terminal_report,
    resolve_markdown_output_path,
    write_json_output,
    write_markdown_output,
)


def test_load_headlines_from_txt(tmp_path: Path) -> None:
    source = tmp_path / "headlines.txt"
    source.write_text(
        "# comentario\nHeadline A\n\nHeadline B\n",
        encoding="utf-8",
    )
    assert load_headlines_from_file(str(source)) == ["Headline A", "Headline B"]


def test_load_headlines_from_csv(tmp_path: Path) -> None:
    source = tmp_path / "headlines.csv"
    source.write_text("headline\nHeadline A\nHeadline B\n", encoding="utf-8")
    assert load_headlines_from_file(str(source)) == ["Headline A", "Headline B"]


def test_write_json_output_and_render_report(tmp_path: Path) -> None:
    payload = {
        "run_id": "abc",
        "headline": "Headline A",
        "execution_mode": "fallback-manual",
        "llm_mode": "local-fallback",
        "search_provider": "manual",
        "evidence": [],
        "article_markdown": "# Headline A\n\nTexto\n",
        "output": {
            "credibility_band": "baixa",
            "confidence_score": 10,
            "recommended_action": "Revisar",
        },
        "stages": [{"key": "search", "state": "attention", "score": 20, "summary": "Sem evidencia"}],
        "audit": [{"stage": "input", "severity": "info", "message": "ok"}],
    }
    target = tmp_path / "result.json"
    write_json_output(str(target), payload)
    assert target.exists()
    rendered = render_terminal_report(payload, mode="flow")
    assert "mode: flow" in rendered
    assert "run_id: abc" in rendered
    md_path = write_markdown_output(None, payload, mode="flow")
    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8").startswith("# Headline A")


def test_resolve_markdown_output_path_for_batch(tmp_path: Path) -> None:
    payload = {"headline": "Headline A", "run_id": "abc12345"}
    path = resolve_markdown_output_path(str(tmp_path), payload, mode="workflow", batch=True)
    assert path.name.endswith(".md")
    assert path.parent == tmp_path
