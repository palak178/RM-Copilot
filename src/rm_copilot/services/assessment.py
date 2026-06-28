"""Assessment service — composes the deterministic services over the database.

This is the analytics entry point that runs WITHOUT the agent (milestone M2
acceptance). It is the only service that touches repositories; the pure scorers it
calls operate on domain objects. Milestone M3 wraps this as a typed agent tool.
"""

from datetime import date

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.data.database import Database
from rm_copilot.domain.assessment import Assessment, RankedCandidate
from rm_copilot.services import eligibility, propensity_scorer, ranker, recommender, value_scorer
from rm_copilot.services.features import extract_features
from rm_copilot.services.triggers import detect_triggers


class CustomerNotFoundError(LookupError):
    """Raised when an assessment is requested for an unknown customer."""


class ProductNotFoundError(LookupError):
    """Raised when an assessment is requested for an unknown product."""


class AssessmentService:
    """Fetches a customer's data and produces reason-coded assessments."""

    def __init__(self, db: Database, config: ScoringConfig, as_of: date | None = None) -> None:
        self._db = db
        self._config = config
        self._as_of = as_of or date.today()
        self._products = {p.product_id: p for p in db.products.list_active()}

    def assess(self, customer_id: str, product_id: str) -> Assessment:
        """Compute the full assessment of one customer for one product."""
        customer = self._db.customers.get(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        product = self._products.get(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        holdings = self._db.holdings.list_for_customer(customer_id)
        transactions = self._db.transactions.list_for_customer(customer_id)

        features = extract_features(
            customer, holdings, transactions, self._products, self._as_of, self._config
        )
        triggers = detect_triggers(
            holdings, transactions, features.monthly_income_paise, self._config, self._as_of
        )
        value = value_scorer.score_value(features, self._config)
        propensity = propensity_scorer.score_propensity(features, triggers, product, self._config)
        elig = eligibility.check_eligibility(customer, features, product)
        recommendation = recommender.recommend(
            customer, features, product, elig, propensity, self._products.values()
        )
        return Assessment(
            customer_id=customer_id,
            product_id=product_id,
            value=value,
            propensity=propensity,
            eligibility=elig,
            recommendation=recommendation,
            aum_paise=features.aum_paise,
            tenure_months=features.tenure_months,
            monthly_income_paise=features.monthly_income_paise,
        )

    def rank_prospects(
        self,
        product_id: str,
        candidate_ids: list[str] | None = None,
        top_n: int = 10,
        eligible_only: bool = True,
    ) -> list[RankedCandidate]:
        """Assess a candidate set for a product and return the top-N ranked prospects."""
        ids = candidate_ids if candidate_ids is not None else self._db.customers.list_ids()
        assessments = [self.assess(cid, product_id) for cid in ids]
        if eligible_only:
            assessments = [a for a in assessments if a.eligibility.eligible]
        return ranker.rank(assessments, self._config)[:top_n]
