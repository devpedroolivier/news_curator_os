# Architecture

## Objective

O projeto executa um fluxo editorial de curadoria de noticias a partir de uma headline:

`headline -> busca -> analise -> verificacao -> qualificacao -> redacao final`

## Layers

### Presentation

- `src/news_curator_os/app.py`
- `src/news_curator_os/cli.py`
- `src/news_curator_os/workflow.py`
- `src/news_curator_os/templates/`
- `src/news_curator_os/static/`

Responsavel por HTTP, terminal, streaming de eventos e integracao com o workflow do Agno.

### Application

- `src/news_curator_os/application/services.py`

Expõe o caso de uso principal do sistema:

- executar preview
- executar run persistido
- listar historico
- montar snapshot da dashboard

Essa camada conhece o fluxo do produto, mas nao conhece detalhes de UI.

### Domain

- `src/news_curator_os/models.py`
- `src/news_curator_os/pipeline.py`
- `src/news_curator_os/agents.py`

Contem entidades, contratos do fluxo, regras de verificacao, qualificacao e redacao.

### Infrastructure

- `src/news_curator_os/infrastructure/bootstrap.py`
- `src/news_curator_os/repository.py`
- `src/news_curator_os/search.py`
- `src/news_curator_os/config.py`

Responsavel por wiring, SQLite, configuracao e adaptadores de busca externa.

## Current Design Decisions

- `HeadlinePipeline` permanece como orquestrador unico do fluxo.
- `NewsCuratorService` centraliza os casos de uso reutilizados por API, CLI e Workflow.
- `bootstrap.py` concentra a composicao das dependencias para reduzir acoplamento.
- O fallback local continua ativo para manter o sistema operante sem chaves externas.

## Next Architecture Steps

1. Extrair interfaces formais para `SearchProvider` e `RunStore`.
2. Separar DTOs HTTP de modelos internos do dominio.
3. Introduzir um provider adicional de busca/fact-check para redundancia.
4. Adicionar migracoes de banco em vez de bootstrap ad-hoc do SQLite.
