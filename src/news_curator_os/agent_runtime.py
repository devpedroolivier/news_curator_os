from agno.os import AgentOS

from .app import create_base_app
from .workflow import build_bootstrap_workflow


def build_agent_os_app():
    base_app = create_base_app()
    agent_os = AgentOS(
        name="News Curator OS",
        description="Sistema de curadoria de noticias com painel de monitoramento.",
        base_app=base_app,
        workflows=[build_bootstrap_workflow()],
        auto_provision_dbs=False,
        telemetry=False,
        tracing=False,
        on_route_conflict="preserve_base_app",
    )
    return agent_os.get_app()


app = build_agent_os_app()
