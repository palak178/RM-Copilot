"""log_outreach — persist the decision + message (the dry-run 'send') + audit.

Deterministic write. Idempotent on a deterministic outreach_id derived from
(customer, product, session, run) so a retried call returns the existing record
rather than creating a duplicate.
"""

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel

from rm_copilot.data.database import Database
from rm_copilot.domain.entities import OutreachLog
from rm_copilot.domain.enums import OutreachStatus
from rm_copilot.tools.base import Tool


class LogOutreachInput(BaseModel):
    customer_id: str
    product_id: str
    run_id: str
    status: OutreachStatus
    message: str | None = None
    locale: str | None = None
    tone: str | None = None
    recommended_product_id: str | None = None
    session_id: str | None = None
    value_score: int | None = None
    propensity_score: int | None = None
    confidence: str | None = None
    assessment_snapshot: dict | None = None
    groundedness_passed: bool | None = None
    compliance_passed: bool | None = None
    regeneration_count: int | None = None
    suppressed_reason: str | None = None


class LogOutreachOutput(BaseModel):
    outreach_id: str
    status: str
    created: bool  # False if an identical record already existed (idempotent)


def _deterministic_id(
    customer_id: str, product_id: str, session_id: str | None, run_id: str
) -> str:
    key = "|".join([customer_id, product_id, session_id or "", run_id])
    return "OUT_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


class LogOutreachTool(Tool):
    name = "log_outreach"
    description = (
        "Record an outreach decision (and simulate the WhatsApp send) in the audit log. "
        "Idempotent per (customer, product, session, run)."
    )
    input_model = LogOutreachInput

    def __init__(self, db: Database) -> None:
        self._db = db

    def execute(self, args: LogOutreachInput) -> LogOutreachOutput:
        outreach_id = _deterministic_id(
            args.customer_id, args.product_id, args.session_id, args.run_id
        )
        existing = self._db.outreach.get(outreach_id)
        if existing is not None:
            return LogOutreachOutput(
                outreach_id=outreach_id, status=existing.status.value, created=False
            )

        record = OutreachLog(
            outreach_id=outreach_id,
            customer_id=args.customer_id,
            product_id=args.product_id,
            recommended_product_id=args.recommended_product_id,
            session_id=args.session_id,
            run_id=args.run_id,
            value_score=args.value_score,
            propensity_score=args.propensity_score,
            confidence=args.confidence,
            assessment_snapshot=json.dumps(args.assessment_snapshot)
            if args.assessment_snapshot is not None
            else None,
            message_text=args.message,
            message_locale=args.locale,
            message_tone=args.tone,
            groundedness_passed=args.groundedness_passed,
            compliance_passed=args.compliance_passed,
            regeneration_count=args.regeneration_count,
            status=args.status,
            suppressed_reason=args.suppressed_reason,
            created_at=datetime.now(),
        )
        with self._db.transaction():
            self._db.outreach.add(record)
        return LogOutreachOutput(outreach_id=outreach_id, status=args.status.value, created=True)
