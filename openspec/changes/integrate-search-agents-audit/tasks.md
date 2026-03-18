<artifact id="tasks" change="integrate-search-agents-audit">

## 1. Busca real
- [x] 1.1 Adicionar configuracao de provider e chave por ambiente.
- [x] 1.2 Integrar `NewsAPI /v2/everything` com fallback manual.

## 2. Agentes e orquestracao
- [x] 2.1 Adicionar agentes especializados para analise, verificacao e qualificacao.
- [x] 2.2 Manter fallback local seguro quando OpenAI nao estiver ativa.
- [x] 2.3 Atualizar o workflow registrado no AgentOS para usar o novo fluxo.

## 3. Persistencia operacional
- [x] 3.1 Criar repositrio SQLite para runs, evidencias e auditoria.
- [x] 3.2 Persistir execucoes do endpoint principal.
- [x] 3.3 Expor endpoint para historico recente.

## 4. Painel e qualidade
- [x] 4.1 Atualizar o dashboard com evidencias e historico.
- [x] 4.2 Atualizar testes de integracao do app.
- [x] 4.3 Atualizar README e `.env.example`.

</artifact>
