<artifact id="proposal" change="integrate-search-agents-audit">

<problem>
O bootstrap inicial mostrou o fluxo editorial, mas ainda faltavam tres capacidades centrais para uso operacional: busca real por noticias, agentes especializados para analise/verificacao/qualificacao e persistencia das execucoes com evidencias e auditoria.
</problem>

<success_criteria>
- O sistema aceita um provider real configuravel para busca de noticias.
- O pipeline passa a usar agentes especializados com OpenAI/Agno quando a chave estiver disponivel, com fallback local seguro.
- Cada execucao persistida registra run, evidencias, score e trilha de auditoria.
- O painel exibe historico recente e evidencias recuperadas.
</success_criteria>

<unlocks>
  <capability name="operational-news-curation">
    <description>Execucao auditavel e mais proxima do fluxo real de curadoria editorial.</description>
    <requirement>O sistema deve registrar cada rodada em SQLite com score e evidencias.</requirement>
    <requirement>O sistema deve permitir busca real e qualificar o uso de fallback quando nao houver integracoes ativas.</requirement>
  </capability>
</unlocks>

</artifact>
