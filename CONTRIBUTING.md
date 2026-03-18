# Contributing

## Local setup

```bash
cp .env.example .env
/root/.local/bin/uv sync
```

## Test and lint

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check .
```

## Development rules

- Mantenha o fluxo principal em `HeadlinePipeline`.
- Use `NewsCuratorService` para novos casos de uso compartilhados entre API, CLI e workflow.
- Preserve fallback local quando integrar novos providers externos.
- Adicione testes para qualquer mudanca comportamental no fluxo.

## Pull requests

- Descreva o problema e o impacto no fluxo editorial.
- Liste riscos, dependencias externas e mudancas de configuracao.
- Inclua validacao local executada.

## Commit messages

- Use Conventional Commits.
- Referencia rapida: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Estrategia inicial recomendada em `docs/commit-strategy.md`.
