"""LLM-backed drafter wired through the provider-agnostic LLMClient (via MockClient)."""

from datetime import date

from rm_copilot.agent.drafter import LlmMessageDrafter
from rm_copilot.agent.llm.mock import MockClient
from rm_copilot.config.scoring import load_scoring_config
from rm_copilot.data.database import Database
from rm_copilot.domain.enums import OutreachStatus
from rm_copilot.services.assessment import AssessmentService
from rm_copilot.tools.generate_outreach import DraftContext, GenerateOutreachMessageTool

AS_OF = date(2026, 6, 15)
PERSONAL_LOAN = "PROD_PERSONAL_LOAN"

# A compliant, grounded (no numeric claims) message the mock "LLM" returns.
_COMPLIANT = "Hi there, you may be eligible for a Personal Loan (subject to eligibility). Reply STOP to opt out."


def test_drafter_uses_llm_client() -> None:
    drafter = LlmMessageDrafter(MockClient(complete_text=_COMPLIANT))
    context = DraftContext(
        first_name="Priya",
        product_id=PERSONAL_LOAN,
        product_name="Personal Loan",
        locale="en_IN",
        tone="friendly",
        facts=["AUM ₹8.20L (Top band)"],
        reason_codes=["AUM ₹8.20L (Top band)"],
        trigger_reasons=[],
    )
    assert drafter.draft(context) == _COMPLIANT


def test_generate_tool_with_llm_drafter_is_ready(seeded_db: Database) -> None:
    config = load_scoring_config()
    service = AssessmentService(seeded_db, config, AS_OF)
    drafter = LlmMessageDrafter(MockClient(complete_text=_COMPLIANT))
    tool = GenerateOutreachMessageTool(seeded_db, service, drafter, config)

    result = tool.invoke({"customer_id": "CUST000001", "product_id": PERSONAL_LOAN})
    assert result["status"] == OutreachStatus.READY.value
    assert result["message"] == _COMPLIANT
    assert result["grounded"] and result["compliant"]
