"""App composition: build_app wiring, live-trace streaming, and locale flow."""

from datetime import date
from pathlib import Path

import pytest

from rm_copilot.agent.drafter import LlmMessageDrafter
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.agent.memory import SessionMemory
from rm_copilot.agent.models import Intent, Plan
from rm_copilot.agent.orchestrator import Orchestrator
from rm_copilot.agent.runtime import build_app
from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.config.settings import Settings
from rm_copilot.data.database import Database
from rm_copilot.data.seed import seed_database
from rm_copilot.tools.generate_outreach import DraftContext
from rm_copilot.tools.registry import build_registry

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"
COMPLIANT = "Hi there, you may be eligible (subject to eligibility). Reply STOP to opt out."


def _orchestrator(db: Database, plans, drafter=None, *, max_messages=1):
    client = MockClient(complete_text=COMPLIANT, structured_responses=plans)
    registry = build_registry(
        db, load_scoring_config(), drafter or LlmMessageDrafter(client), as_of=AS_OF
    )
    product_ids = [p.product_id for p in db.products.list_active()]
    return Orchestrator(registry, client, product_ids, max_message_count=max_messages)


@pytest.mark.integration
def test_build_app_runs_a_turn(tmp_path: Path) -> None:
    db_path = tmp_path / "rm.db"
    seeder = Database.connect(str(db_path))
    seed_database(seeder, seed=7, customer_count=20, as_of=AS_OF)
    seeder.close()

    plan = Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=5, message_count=2)
    client = MockClient(complete_text=COMPLIANT, structured_responses=[plan])
    app = build_app(
        Settings(db_path=str(db_path), llm_provider="mock", llm_model="mock"), client=client
    )
    try:
        assert app.is_seeded
        result = app.ask("find personal-loan prospects this month", app.new_session())
        assert result.kind == "answer"
        assert result.prospects
    finally:
        app.close()


def test_on_trace_streams_steps_in_order(seeded_db: Database) -> None:
    plan = Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=5, message_count=1)
    orch = _orchestrator(seeded_db, [plan])
    captured = []
    result = orch.handle_turn("find prospects", SessionMemory(), on_trace=captured.append)

    assert captured  # streamed live
    assert [s.seq for s in captured] == list(range(1, len(captured) + 1))  # ordered
    assert captured == result.trace  # what streamed == what's returned


def test_locale_flows_to_drafter(seeded_db: Database) -> None:
    class _CapturingDrafter:
        def __init__(self) -> None:
            self.last: DraftContext | None = None

        def draft(self, context: DraftContext) -> str:
            self.last = context
            return COMPLIANT

    drafter = _CapturingDrafter()
    plan = Plan(
        intent=Intent.REDRAFT, customer_id="CUST000001", product_id=PERSONAL_LOAN, locale="hi_IN"
    )
    orch = _orchestrator(seeded_db, [plan], drafter=drafter)
    orch.handle_turn("redo CUST000001's message in Hindi", SessionMemory())

    assert drafter.last is not None
    assert drafter.last.locale == "hi_IN"  # localization plumbed end-to-end
