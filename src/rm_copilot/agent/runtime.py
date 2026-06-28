"""Application composition — the UI-agnostic public entry point.

`RmCopilotApp` wires the database, scoring config, provider-agnostic LLM client, tool
registry, and the cognitive-loop orchestrator from settings. Both the CLI and the
Streamlit app build on this; neither imports a provider SDK or touches the loop's
internals.
"""

from collections.abc import Callable
from dataclasses import dataclass

from rm_copilot.agent.drafter import LlmMessageDrafter
from rm_copilot.agent.llm.base import LLMClient
from rm_copilot.agent.llm.factory import LLMFactory
from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import AgentResult
from rm_copilot.agent.orchestrator import Orchestrator
from rm_copilot.agent.trace import TraceStep
from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.config.settings import Settings, get_settings
from rm_copilot.data.database import Database
from rm_copilot.tools.registry import build_registry


@dataclass
class RmCopilotApp:
    """Holds the live database + orchestrator and runs conversational turns."""

    db: Database
    orchestrator: Orchestrator
    provider: str
    model: str

    def new_session(self) -> SessionMemory:
        return SessionMemory()

    def ask(
        self,
        message: str,
        memory: SessionMemory,
        on_trace: Callable[[TraceStep], None] | None = None,
    ) -> AgentResult:
        return self.orchestrator.handle_turn(message, memory, on_trace=on_trace)

    @property
    def is_seeded(self) -> bool:
        return self.db.customers.count() > 0

    def close(self) -> None:
        self.db.close()


def build_app(settings: Settings | None = None, client: LLMClient | None = None) -> RmCopilotApp:
    """Construct the app from settings. Pass `client` to inject a provider (e.g. MockClient)."""
    settings = settings or get_settings()
    db = Database.connect(settings.db_path)
    db.create_schema()  # safe if absent; no-op if present
    config = load_scoring_config(settings.scoring_config_path)
    client = client or LLMFactory.from_settings(settings)
    registry = build_registry(db, config, LlmMessageDrafter(client))
    product_ids = [p.product_id for p in db.products.list_active()]
    orchestrator = Orchestrator(registry, client, product_ids)
    return RmCopilotApp(
        db=db, orchestrator=orchestrator, provider=settings.llm_provider, model=settings.llm_model
    )
