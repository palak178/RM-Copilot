"""generate_outreach_message guardrail orchestration + log_outreach idempotency."""

from datetime import date

from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.data.database import Database
from rm_copilot.domain.enums import OutreachStatus
from rm_copilot.services.assessment import AssessmentService
from rm_copilot.tools.generate_outreach import DraftContext, GenerateOutreachMessageTool
from rm_copilot.tools.log_outreach import LogOutreachTool

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"


class _GroundedDrafter:
    def draft(self, context: DraftContext) -> str:
        return (
            f"Hi {context.first_name}, you may be eligible for {context.product_name} "
            f"(subject to eligibility). Reply STOP to opt out."
        )


class _NonCompliantDrafter:
    def draft(self, context: DraftContext) -> str:
        return f"Hi {context.first_name}, you have guaranteed approval! Reply STOP to opt out."


class _UngroundedDrafter:
    def draft(self, context: DraftContext) -> str:
        return "You can borrow ₹9,99,999 right now. Reply STOP to opt out."


def _gen_tool(db: Database, drafter) -> GenerateOutreachMessageTool:
    config = load_scoring_config()
    service = AssessmentService(db, config, AS_OF)
    return GenerateOutreachMessageTool(db, service, drafter, config)


def test_ready_when_grounded_and_compliant(seeded_db: Database) -> None:
    result = _gen_tool(seeded_db, _GroundedDrafter()).invoke(
        {"customer_id": "CUST000001", "product_id": PERSONAL_LOAN}
    )
    assert result["status"] == OutreachStatus.READY.value
    assert result["message"]
    assert result["grounded"] and result["compliant"]


def test_do_not_disturb_is_suppressed(seeded_db: Database) -> None:
    # CUST000004 is the seeded suppression customer (do_not_disturb).
    result = _gen_tool(seeded_db, _GroundedDrafter()).invoke(
        {"customer_id": "CUST000004", "product_id": PERSONAL_LOAN}
    )
    assert result["status"] == OutreachStatus.SUPPRESSED.value
    assert result["suppressed_reason"] == "do_not_disturb"
    assert result["message"] is None


def test_non_compliant_message_fails_after_regeneration(seeded_db: Database) -> None:
    result = _gen_tool(seeded_db, _NonCompliantDrafter()).invoke(
        {"customer_id": "CUST000001", "product_id": PERSONAL_LOAN}
    )
    assert result["status"] == OutreachStatus.COMPLIANCE_FAILED.value
    assert result["message"] is None
    assert result["violations"]
    assert result["regeneration_count"] == 2  # default max


def test_ungrounded_number_fails(seeded_db: Database) -> None:
    result = _gen_tool(seeded_db, _UngroundedDrafter()).invoke(
        {"customer_id": "CUST000001", "product_id": PERSONAL_LOAN}
    )
    assert result["status"] == OutreachStatus.COMPLIANCE_FAILED.value
    assert result["unsupported_claims"]


def test_log_outreach_is_idempotent(seeded_db: Database) -> None:
    tool = LogOutreachTool(seeded_db)
    args = {
        "customer_id": "CUST000001",
        "product_id": PERSONAL_LOAN,
        "run_id": "run-1",
        "status": "DRY_RUN_SENT",
        "message": "Hi Priya, ... Reply STOP to opt out.",
        "locale": "en_IN",
        "assessment_snapshot": {"value": 80},
    }
    first = tool.invoke(args)
    second = tool.invoke(args)
    assert first["created"] is True
    assert second["created"] is False
    assert first["outreach_id"] == second["outreach_id"]
    assert seeded_db.outreach.count() == 1


def test_log_outreach_persists_record(seeded_db: Database) -> None:
    LogOutreachTool(seeded_db).invoke(
        {
            "customer_id": "CUST000002",
            "product_id": PERSONAL_LOAN,
            "run_id": "run-2",
            "status": "SUPPRESSED",
            "suppressed_reason": "do_not_disturb",
        }
    )
    records = seeded_db.outreach.list_for_customer("CUST000002")
    assert len(records) == 1
    assert records[0].status == OutreachStatus.SUPPRESSED
    assert records[0].suppressed_reason == "do_not_disturb"
