<artifact id="design" change="integrate-search-agents-audit">

## Motivation & Context
A primeira entrega definiu o contrato do fluxo e a interface inicial. A segunda iteracao precisa reduzir a distancia entre demo e operacao real: buscar noticias em um provider externo, produzir parecer com agentes especializados e deixar rastros persistidos para revisao editorial.

## Proposed Architecture
- **Busca Real Configuravel**: `NewsSearchProvider` abstrai o provider; nesta fase foi integrado `NewsAPI /v2/everything`, mantendo fallback manual quando nao houver chave.
- **Agentes Especializados**: `NewsCurationAgents` organiza tres agentes logicos (`analysis`, `verification`, `qualification`) com `Agno + OpenAIResponses`. Se a chave nao existir, o sistema recua para heuristicas locais previsiveis.
- **Persistencia Operacional**: `RunRepository` grava `pipeline_runs`, `evidences` e `audit_events` em SQLite, preservando payload completo e resumo para listagem.
- **Painel Expandido**: o dashboard passa a exibir evidencias encontradas, historico recente e auditoria da rodada.

## Alternatives Considered
- **Persistir apenas payload JSON em arquivo**. Rejeitado porque dificultaria consulta de historico e evolucao de auditoria.
- **Bloquear execucao sem OpenAI/NewsAPI**. Rejeitado porque reduziria utilidade do ambiente de desenvolvimento e impediria fallback controlado.

## API / Interface Changes
- `POST /api/v1/pipeline/run`: executa e persiste.
- `GET /api/v1/runs/recent`: lista execucoes recentes.
- `POST /api/v1/pipeline/preview`: continua disponivel, mas sem persistencia.

## Data Storage Changes
- Novo SQLite com tabelas `pipeline_runs`, `evidences` e `audit_events`.
- O banco e local e configurado por `APP_DB_PATH`.

</artifact>
