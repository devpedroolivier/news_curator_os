<artifact id="design" change="bootstrap-news-curation-platform">

## Motivation & Context
O objetivo desta fase nao e entregar a verificacao factual completa, mas preparar um alicerce correto para isso. A abordagem combina `uv` para ambiente e dependencias, `OpenSpec` para governanca de mudanca, `FastAPI` para API/painel e `Agno AgentOS` como runtime-alvo da orquestracao de agentes.

## Proposed Architecture
- **Runtime Base**: O app HTTP principal sera um `FastAPI` encapsulado por `AgentOS`, permitindo evolucao futura para workflows e agentes especializados sem refazer a base da aplicacao.
- **Pipeline Bootstrap**: O fluxo headline -> busca -> analise -> verificacao -> qualificacao -> output sera inicialmente modelado por um servico local deterministico. Isso reduz risco enquanto o contrato de dados e o painel sao consolidados.
- **Dashboard Editorial**: O painel sera server-rendered com `Jinja2` e enriquecido com `fetch` no frontend para testar headlines e atualizar o fluxo dinamicamente.
- **Configuracao**: `pydantic-settings` centraliza variaveis de ambiente da API da OpenAI e do provider de busca.

## Alternatives Considered
- **Implementar agentes reais ja na primeira etapa**. Rejeitado porque ainda nao foi escolhido o provedor de busca/noticias nem definida a persistencia de evidencias, o que aumentaria o retrabalho.
- **Criar frontend SPA completo agora**. Rejeitado nesta fase porque o maior risco inicial esta na definicao do contrato do pipeline, nao na complexidade de frontend.

## API / Interface Changes
- `GET /`: dashboard inicial de monitoramento.
- `GET /healthz`: healthcheck.
- `POST /api/v1/pipeline/preview`: recebe uma headline e retorna o estado estruturado dos estagios e o output editorial inicial.

## Data Storage Changes
Nenhuma persistencia obrigatoria nesta fase. O pipeline opera em memoria e retorna previews efemeros. Persistencia de execucoes, fontes e scores fica para a proxima mudanca.

</artifact>
