# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install dependencies
uv sync --group dev

# Run dashboard (FastAPI)
uv run uvicorn news_curator_os.agent_runtime:app --host 0.0.0.0 --port 8000 --reload

# Run terminal flow
./scripts/run_terminal_flow.sh "Headline text" --persist --stream

# Run Agno workflow
./scripts/run_terminal_workflow.sh "Headline text" --persist --stream

# Batch processing
./scripts/run_terminal_batch.sh headlines.txt --mode workflow --persist
```

## Testing & Linting

```bash
uv run pytest -q                    # All tests
uv run pytest -q tests/test_app.py  # Single test file
uv run pytest -q -k "test_name"     # Single test by name
uv run ruff check .                 # Lint

# Live E2E tests (requires real API keys in .env)
RUN_LIVE_E2E=1 uv run pytest -q tests/test_e2e_live.py
```

CI runs `ruff check` + `pytest -q` on all PRs via GitHub Actions.

## Architecture

**Pipeline flow:** `headline → search → analysis → verification → qualification → article`

Four-layer architecture:

- **Presentation** (`app.py`, `cli.py`, `workflow.py`): FastAPI dashboard + REST API, CLI with flow/workflow/batch subcommands, Agno Workflow integration. Entry point: `news_curator_os.agent_runtime:app`.
- **Application** (`application/services.py`): `NewsCuratorService` orchestrates use cases via factory-injected dependencies. Methods: `preview_headline()`, `run_headline()`, `deep_run_headline()`.
- **Domain** (`pipeline.py`, `deep_pipeline.py`, `agents.py`, `models.py`): `HeadlinePipeline` is the standard flow. `DeepHeadlinePipeline` does 3-round Tavily search (PT → EN → gap-directed). `NewsCurationAgents` wraps LLM calls with automatic fallback to local heuristics when no OpenAI key.
- **Infrastructure** (`infrastructure/bootstrap.py`, `repository.py`, `search.py`, `config.py`): Factory composition in `bootstrap.py`. SQLite persistence (tables: `pipeline_runs`, `evidences`, `audit_events`). `NewsSearchProvider` (NewsAPI) and `TavilySearchProvider` for search.

## Key Patterns

- **Graceful degradation**: System runs without any external API. `safe_pipeline` forces `manual` search + no LLM. Agents return heuristic-based results when OpenAI is unavailable.
- **Factory wiring**: All dependencies composed in `infrastructure/bootstrap.py`. Service receives factories, not instances.
- **Event callbacks**: Pipelines emit events during execution for streaming progress to UI/CLI.
- **Score guardrails**: Confidence capped at 42 when no evidence exists. URL anti-hallucination via prompt instructions + post-processing sanitization.
- **Audit trail**: Every pipeline stage emits `AuditEntry` with severity + message, persisted to SQLite.

## Configuration

Pydantic Settings loaded from `.env` (see `.env.example`). Key vars:
- `NEWS_SEARCH_PROVIDER`: `manual` (no API) or `newsapi`
- `OPENAI_API_KEY`: Empty = local fallback mode
- `TAVILY_API_KEY`: Required for deep pipeline only
- `APP_DB_PATH`: SQLite path (default: `data/news_curator.db`)

## Conventions

- Language: Portuguese (pt-BR) for UI, logs, and documentation
- Commits: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`)
- Ruff: line-length 100, target py310
- All domain contracts use Pydantic models (`models.py`)
- Tests use `monkeypatch` + `get_settings.cache_clear()` for isolation
