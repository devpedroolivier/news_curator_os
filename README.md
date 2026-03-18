# News Curator OS

Sistema de curadoria de noticias com agentes de IA, pensado para transformar uma headline em um fluxo editorial completo:

`headline -> busca -> analise -> verificacao -> qualificacao -> redacao final`

O projeto combina:

- `Agno AgentOS` para runtime e workflow
- `OpenAI API` para agentes especializados
- `NewsAPI` para busca real de noticias
- `SQLite` para historico, evidencias e auditoria
- `OpenSpec` para organizacao de mudancas
- `uv` para ambiente e dependencias

## What is implemented

- dashboard FastAPI para monitoramento
- CLI para fluxo, workflow e batch
- persistencia local de runs, evidencias e auditoria
- consolidacao de ate 5 fontes distintas
- destaque para fontes oficiais e registros primarios
- deteccao de divergencias entre fontes
- geracao de artigo final em Markdown
- fallback local para operar sem chaves externas

## Architecture

Documentacao principal:

- [Architecture](docs/architecture.md)
- [Project Review](docs/review.md)
- [Contributing](CONTRIBUTING.md)
- [Commit Strategy](docs/commit-strategy.md)
- [Roadmap v1](ROADMAP.md)
- [Changelog](CHANGELOG.md)

Camadas atuais:

- `presentation`: HTTP, dashboard, CLI e workflow
- `application`: casos de uso compartilhados
- `domain`: pipeline, modelos e regras editoriais
- `infrastructure`: configuracao, busca, persistencia e bootstrap

## Local setup

```bash
cp .env.example .env
/root/.local/bin/uv sync --group dev
```

Variaveis principais:

- `OPENAI_API_KEY`
- `NEWSAPI_KEY`
- `NEWS_SEARCH_PROVIDER=manual|newsapi`
- `APP_PORT`

## Run the dashboard

```bash
./scripts/run_dashboard.sh
```

Rotas principais:

- `GET /`
- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/monitoring/summary`
- `POST /api/v1/pipeline/preview`
- `POST /api/v1/pipeline/run`
- `GET /api/v1/runs/recent`

## Run in terminal

Fluxo direto:

```bash
./scripts/run_terminal_flow.sh "Banco Central anuncia nova medida para o credito no Brasil" --persist --stream --output-json artifacts/flow.json --output-md artifacts/flow.md
```

Workflow do Agno:

```bash
./scripts/run_terminal_workflow.sh "Banco Central anuncia nova medida para o credito no Brasil" --persist --stream --output-json artifacts/workflow.json --output-md artifacts/workflow.md
```

Batch via `.txt` ou `.csv`:

```bash
./scripts/run_terminal_batch.sh headlines.txt --mode workflow --persist --stream --output-json artifacts/batch.json --output-md artifacts/batch_markdown
```

## Tests

Suite local:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check .
```

Smoke test real:

```bash
set -a && source .env && set +a
RUN_LIVE_E2E=1 ./.venv/bin/python -m pytest -q tests/test_e2e_live.py
```

## Project layout

```text
src/news_curator_os/
  application/
  infrastructure/
  agents.py
  app.py
  cli.py
  config.py
  models.py
  pipeline.py
  repository.py
  search.py
  workflow.py

docs/
  architecture.md
  review.md

openspec/
  changes/
  specs/
```

## GitHub readiness

O projeto ja inclui:

- `.gitignore` ajustado para ambiente local, artefatos e banco
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `ROADMAP.md`
- estrategia de commits em `docs/commit-strategy.md`
- GitHub Actions em `.github/workflows/ci.yml`
- template de pull request em `.github/pull_request_template.md`
- documentacao inicial de arquitetura e revisao tecnica

Antes de publicar:

1. confirme que `.env` nao sera versionado
2. revise `CHANGELOG.md` e `ROADMAP.md`
3. confira `docs/commit-strategy.md`
4. rode `pytest` e `ruff`
