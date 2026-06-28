"""HTTP API (FastAPI + SSE) over a mock-backed RmCopilotApp."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from rm_copilot.agent.drafter import LlmMessageDrafter
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.agent.models import Intent, Plan
from rm_copilot.agent.orchestrator import Orchestrator
from rm_copilot.agent.runtime import RmCopilotApp
from rm_copilot.api.app import create_app
from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.data.database import Database
from rm_copilot.tools.registry import build_registry

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"
COMPLIANT = "Hi there, you may be eligible (subject to eligibility). Reply STOP to opt out."


def _client(db: Database, plans: list[Plan]) -> TestClient:
    mock = MockClient(complete_text=COMPLIANT, structured_responses=plans)
    registry = build_registry(db, load_scoring_config(), LlmMessageDrafter(mock), as_of=AS_OF)
    product_ids = [p.product_id for p in db.products.list_active()]
    orchestrator = Orchestrator(registry, mock, product_ids, max_message_count=1)
    rm_app = RmCopilotApp(db=db, orchestrator=orchestrator, provider="mock", model="mock")
    return TestClient(create_app(rm_app=rm_app))


def _prospect_plan() -> Plan:
    return Plan(intent=Intent.PROSPECT, product_id=PERSONAL_LOAN, top_n=5, message_count=1)


@pytest.mark.integration
def test_health(seeded_db: Database) -> None:
    body = _client(seeded_db, []).get("/health").json()
    assert body["status"] == "ok"
    assert body["seeded"] is True
    assert body["provider"] == "mock"


@pytest.mark.integration
def test_products(seeded_db: Database) -> None:
    body = _client(seeded_db, []).get("/api/v1/products").json()
    assert PERSONAL_LOAN in body["products"]


@pytest.mark.integration
def test_query_returns_answer(seeded_db: Database) -> None:
    resp = _client(seeded_db, [_prospect_plan()]).post(
        "/api/v1/query", json={"message": "find prospects"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert body["result"]["kind"] == "answer"
    assert body["result"]["prospects"]


@pytest.mark.integration
def test_query_validation_error(seeded_db: Database) -> None:
    resp = _client(seeded_db, []).post("/api/v1/query", json={})  # missing 'message'
    assert resp.status_code == 422


@pytest.mark.integration
def test_stream_emits_sse_frames(seeded_db: Database) -> None:
    resp = _client(seeded_db, [_prospect_plan()]).get(
        "/api/v1/stream", params={"message": "find prospects"}
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event: session" in text
    assert "event: trace" in text
    assert "event: result" in text
    assert "event: end" in text
