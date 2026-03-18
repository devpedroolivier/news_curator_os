# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog and the project uses Semantic Versioning.

## [Unreleased]

### Added

- documentacao de arquitetura, revisao tecnica e contribuicao
- camada de aplicacao com `NewsCuratorService`
- bootstrap centralizado de dependencias
- CI basica com GitHub Actions
- consolidacao de ate 5 fontes distintas
- classificacao de fontes oficiais, jornalisticas e outras
- deteccao de divergencias entre fontes
- geracao automatica de redacao final em Markdown

### Changed

- simplificacao do `app.py`, `cli.py` e `workflow.py` para reduzir acoplamento
- reorganizacao da documentacao para publicacao e colaboracao no GitHub

## [0.1.0] - 2026-03-18

### Added

- bootstrap inicial com `uv`, `FastAPI`, `Agno AgentOS` e `OpenSpec`
- dashboard para monitoramento do fluxo de curadoria
- pipeline `headline -> busca -> analise -> verificacao -> qualificacao -> output`
- persistencia local em SQLite
- CLI para fluxo direto, workflow e batch
- smoke tests locais e teste E2E real opcional
