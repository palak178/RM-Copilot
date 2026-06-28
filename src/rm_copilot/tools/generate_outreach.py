"""generate_outreach_message — personalized, grounded, compliant draft (plan §14).

The deterministic orchestration lives here (M3): suppression (DND / opt-out) ->
build grounded facts from the assessment -> draft via an injected MessageDrafter ->
groundedness check -> compliance check -> bounded regenerate. The actual LLM drafter
is supplied in M4; the guardrails are unskippable because they wrap drafting here.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.data.database import Database
from rm_copilot.domain.enums import OutreachStatus
from rm_copilot.domain.money import format_inr
from rm_copilot.services.assessment import AssessmentService, CustomerNotFoundError
from rm_copilot.services.compliance import check_compliance
from rm_copilot.services.groundedness import check_groundedness
from rm_copilot.tools.base import Tool

_DEFAULT_MAX_REGENERATIONS = 2


class DraftContext(BaseModel):
    """Everything a drafter may use — facts are data, never instructions."""

    first_name: str
    product_id: str
    product_name: str
    locale: str
    tone: str
    facts: list[str]
    reason_codes: list[str]
    trigger_reasons: list[str]


class MessageDrafter(Protocol):
    """Produces message text from a DraftContext. LLM implementation arrives in M4."""

    def draft(self, context: DraftContext) -> str: ...


class GenerateInput(BaseModel):
    customer_id: str
    product_id: str
    locale: str | None = Field(
        default=None, description="en_IN | hi_IN | hi_en; defaults to the customer's preference"
    )
    tone: str = Field(default="friendly")


class GenerateOutput(BaseModel):
    status: str
    customer_id: str
    product_id: str
    message: str | None
    locale: str
    tone: str
    grounded: bool
    compliant: bool
    violations: list[str]
    unsupported_claims: list[str]
    regeneration_count: int
    suppressed_reason: str | None
    facts_used: list[str]


class GenerateOutreachMessageTool(Tool):
    name = "generate_outreach_message"
    description = (
        "Draft a personalized, compliant WhatsApp message for a customer about a product, "
        "grounded strictly in the customer's real facts. Suppresses do-not-disturb / opted-out "
        "customers and regenerates until groundedness and compliance pass."
    )
    input_model = GenerateInput

    def __init__(
        self,
        db: Database,
        service: AssessmentService,
        drafter: MessageDrafter,
        config: ScoringConfig,
        max_regenerations: int = _DEFAULT_MAX_REGENERATIONS,
    ) -> None:
        self._db = db
        self._service = service
        self._drafter = drafter
        self._config = config
        self._max_regenerations = max_regenerations

    def execute(self, args: GenerateInput) -> GenerateOutput:
        customer = self._db.customers.get(args.customer_id)
        if customer is None:
            raise CustomerNotFoundError(args.customer_id)
        locale = args.locale or customer.preferred_language.value

        suppressed = self._suppression_reason(customer.do_not_disturb, customer.marketing_opt_in)
        if suppressed is not None:
            return self._result(
                OutreachStatus.SUPPRESSED,
                args,
                locale,
                message=None,
                grounded=False,
                compliant=False,
                violations=[],
                unsupported=[],
                regenerations=0,
                suppressed_reason=suppressed,
                facts=[],
            )

        assessment = self._service.assess(args.customer_id, args.product_id)
        product = self._db.products.get(args.product_id)
        facts = self._build_facts(customer.first_name, product, assessment)
        context = DraftContext(
            first_name=customer.first_name,
            product_id=args.product_id,
            product_name=product.name if product else args.product_id,
            locale=locale,
            tone=args.tone,
            facts=facts,
            reason_codes=list(assessment.reason_codes),
            trigger_reasons=[t.reason for t in assessment.propensity.triggers],
        )

        grounded_ok = compliant_ok = False
        violations: list[str] = []
        unsupported: list[str] = []
        message: str | None = None
        attempts = 0
        while attempts <= self._max_regenerations:
            message = self._drafter.draft(context)
            g = check_groundedness(message, facts)
            c = check_compliance(message, self._config)
            grounded_ok, compliant_ok = g.grounded, c.passed
            violations, unsupported = list(c.violations), list(g.unsupported_claims)
            if grounded_ok and compliant_ok:
                return self._result(
                    OutreachStatus.READY,
                    args,
                    locale,
                    message=message,
                    grounded=True,
                    compliant=True,
                    violations=[],
                    unsupported=[],
                    regenerations=attempts,
                    suppressed_reason=None,
                    facts=facts,
                )
            attempts += 1

        return self._result(
            OutreachStatus.COMPLIANCE_FAILED,
            args,
            locale,
            message=None,
            grounded=grounded_ok,
            compliant=compliant_ok,
            violations=violations,
            unsupported=unsupported,
            regenerations=attempts - 1,
            suppressed_reason=None,
            facts=facts,
        )

    @staticmethod
    def _suppression_reason(do_not_disturb: bool, marketing_opt_in: bool) -> str | None:
        if do_not_disturb:
            return "do_not_disturb"
        if not marketing_opt_in:
            return "marketing_opt_in_false"
        return None

    @staticmethod
    def _build_facts(first_name, product, assessment) -> list[str]:
        facts = list(assessment.reason_codes)
        facts += [t.reason for t in assessment.propensity.triggers]
        if product is not None:
            if product.indicative_interest_rate_pct is not None:
                facts.append(f"indicative rate {product.indicative_interest_rate_pct}%")
            if product.typical_ticket_size_paise is not None:
                facts.append(
                    f"indicative amount up to {format_inr(product.typical_ticket_size_paise)}"
                )
            facts.append(f"product {product.name}")
        facts.append(f"customer first name {first_name}")
        return facts

    def _result(
        self,
        status,
        args,
        locale,
        *,
        message,
        grounded,
        compliant,
        violations,
        unsupported,
        regenerations,
        suppressed_reason,
        facts,
    ) -> GenerateOutput:
        return GenerateOutput(
            status=status.value,
            customer_id=args.customer_id,
            product_id=args.product_id,
            message=message,
            locale=locale,
            tone=args.tone,
            grounded=grounded,
            compliant=compliant,
            violations=violations,
            unsupported_claims=unsupported,
            regeneration_count=regenerations,
            suppressed_reason=suppressed_reason,
            facts_used=facts,
        )
