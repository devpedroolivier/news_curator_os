# Commit Strategy

## Goal

Publicar o projeto no GitHub com historico inicial limpo, legivel e facil de revisar.

## Recommended convention

Use Conventional Commits:

- `feat:` nova funcionalidade
- `fix:` correcao de bug
- `refactor:` mudanca estrutural sem alterar comportamento esperado
- `docs:` documentacao
- `test:` cobertura de testes
- `chore:` manutencao, CI, tooling

## Initial commit sequence

Se quiser dividir o bootstrap atual em commits logicos antes do primeiro push, a sequencia recomendada e:

1. `chore: bootstrap project with uv, fastapi and agno`
2. `feat: add headline curation pipeline and sqlite persistence`
3. `feat: add dashboard and terminal workflow execution`
4. `feat: add markdown redaction and multi-source verification`
5. `refactor: introduce application service and bootstrap wiring`
6. `test: cover cli, service and multi-source verification flows`
7. `docs: add architecture, review, roadmap and changelog`
8. `chore: add github actions and repository metadata`

## Branch strategy

- `main`: branch protegida e sempre estavel
- feature branches: `feat/<scope>`, `fix/<scope>`, `refactor/<scope>`

Exemplos:

- `feat/search-provider-fallback`
- `fix/workflow-timeout`
- `refactor/service-boundaries`

## Pull request policy

- um objetivo tecnico por PR
- incluir impacto no fluxo editorial
- citar riscos e dependencias externas
- anexar comandos de validacao executados

## First GitHub publish flow

1. revisar `.gitignore` e confirmar que `.env` nao esta versionado
2. revisar `README.md`, `CHANGELOG.md` e `ROADMAP.md`
3. rodar `pytest` e `ruff`
4. criar commit inicial estruturado
5. criar repositorio remoto
6. adicionar `origin`
7. fazer `push` para `main`

## Suggested commands

```bash
git init
git add .
git commit -m "chore: bootstrap repository structure"
git branch -M main
git remote add origin <repo-url>
git push -u origin main
```
