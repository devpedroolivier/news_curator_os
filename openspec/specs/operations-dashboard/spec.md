# operations-dashboard Specification

## Purpose
Definir o painel que acompanha o estado do pipeline de curadoria de noticias.

## Requirements
### Requirement: Flow Visibility
O painel MUST apresentar todos os estagios do pipeline e seus respectivos resumos operacionais.

#### Scenario: Dashboard loaded
- **WHEN** o usuario abre o painel
- **THEN** ele visualiza os estagios do fluxo, o modo de execucao atual e o output consolidado

### Requirement: Interactive Preview
O painel MUST permitir testar uma headline e atualizar o fluxo sem reiniciar a aplicacao.

#### Scenario: User submits a headline
- **WHEN** o usuario envia uma nova headline pelo formulario
- **THEN** o painel requisita o preview do pipeline e atualiza as secoes em tela
