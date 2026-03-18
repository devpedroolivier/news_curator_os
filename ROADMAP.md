# Roadmap v1

## Objective

Evoluir o projeto de uma base operacional de curadoria para uma plataforma confiavel de verificacao, qualificacao e monitoramento editorial.

## Phase 1: Stabilize the core

Status: em andamento

- adicionar um segundo provider de busca para redundancia
- separar contratos HTTP dos modelos internos de dominio
- reforcar heuristicas de divergencia e confianca
- ampliar testes de erro, timeout e degradacao de providers
- fechar versao `0.1.x` com baseline estavel para demos e validacao

## Phase 2: Strengthen verification

Status: planejado

- integrar fontes de fact-check
- consultar fontes oficiais com estrategia dedicada por tema
- introduzir score de confianca por evidencia
- diferenciar melhor noticia, opiniao, rumor e comunicado oficial
- registrar por que uma evidencia foi aceita ou descartada

## Phase 3: Improve editorial operations

Status: planejado

- streaming em tempo real no dashboard
- drill-down completo de auditoria por run
- filtros por idioma, pais, dominio e periodo
- export estruturado para redacao, revisao e aprovacao
- historico comparativo entre execucoes da mesma headline

## Phase 4: Prepare production

Status: planejado

- migrar de SQLite para banco mais robusto
- adicionar migracoes formais de schema
- instrumentar logs, traces e metricas
- endurecer seguranca de configuracao e secrets
- preparar deploy e ambiente de staging

## Release targets

- `0.1.x`: estabilizacao da arquitetura atual
- `0.2.0`: verificacao fortalecida e redundancia de busca
- `0.3.0`: operacao editorial mais rica no dashboard
- `1.0.0`: baseline de producao com persistencia e observabilidade maduras
