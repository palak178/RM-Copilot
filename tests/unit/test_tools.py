"""Tool registry: schema export, dispatch, validation, and the read tools."""

from datetime import date

from rm_copilot.data.database import Database
from rm_copilot.tools.generate_outreach import DraftContext
from rm_copilot.tools.registry import build_registry

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"


class _StubDrafter:
    """Deterministic grounded + compliant drafter (no LLM)."""

    def draft(self, context: DraftContext) -> str:
        return (
            f"Hi {context.first_name}, you may be eligible for {context.product_name} "
            f"(subject to eligibility). Reply STOP to opt out."
        )


def _registry(db: Database):
    from rm_copilot.config.scoring import load_scoring_config

    return build_registry(db, load_scoring_config(), _StubDrafter(), as_of=AS_OF)


def test_registry_exposes_five_tools(seeded_db: Database) -> None:
    reg = _registry(seeded_db)
    assert reg.names() == sorted(
        [
            "find_and_rank_prospects",
            "get_customer_360",
            "explain_assessment",
            "generate_outreach_message",
            "log_outreach",
        ]
    )


def test_schemas_are_well_formed(seeded_db: Database) -> None:
    schemas = _registry(seeded_db).schemas()
    assert len(schemas) == 5
    for s in schemas:
        assert s["name"] and s["description"]
        assert s["input_schema"]["type"] == "object"
        assert "properties" in s["input_schema"]


def test_find_and_rank_prospects_returns_ranked(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke(
        "find_and_rank_prospects", {"product_id": PERSONAL_LOAN, "top_n": 5}
    )
    assert "is_error" not in result
    assert result["count"] >= 1
    assert all(p["reason_codes"] for p in result["prospects"])  # reason-coded


def test_invalid_arguments_returns_structured_error(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke(
        "find_and_rank_prospects", {"top_n": 5}
    )  # missing product_id
    assert result["is_error"] is True
    assert result["error"] == "invalid_arguments"


def test_unknown_product_returns_not_found(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke("find_and_rank_prospects", {"product_id": "PROD_NOPE"})
    assert result["error"] == "not_found"


def test_unknown_tool_returns_error(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke("teleport", {})
    assert result["error"] == "unknown_tool"


def test_get_customer_360(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke("get_customer_360", {"customer_id": "CUST000001"})
    assert "is_error" not in result
    assert result["customer_id"] == "CUST000001"
    assert result["holdings"]
    assert "ABCDE" not in (result["masked_pan"] or "")  # masked only


def test_get_customer_360_unknown(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke("get_customer_360", {"customer_id": "CUST999999"})
    assert result["error"] == "not_found"


def test_explain_assessment(seeded_db: Database) -> None:
    result = _registry(seeded_db).invoke(
        "explain_assessment", {"customer_id": "CUST000001", "product_id": PERSONAL_LOAN}
    )
    assert "is_error" not in result
    assert result["value"]["factors"]
    assert "eligible" in result["eligibility"]
    assert result["recommendation"]["recommended_product_id"] == PERSONAL_LOAN
