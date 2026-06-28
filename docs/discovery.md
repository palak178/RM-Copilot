# Problem Understanding & Discovery — RM Copilot

*The thinking that preceded the code: what the problem really is, the discoveries that
shaped the design, the high-value scoring framework in detail, and what was deliberately
deferred.*

Companion documents: [`solution.md`](solution.md) (how it was solved) ·
[`architecture.md`](architecture.md) (how it works internally).

---

# Part 1 — Understanding the Problem

## 1.1 Problem statement
Turn a single natural-language request from a bank **Relationship Manager (RM)** —

> *"Find high-value customers likely to convert for a personal loan this month and
> generate personalized WhatsApp messages."*

— into an **explainable workflow**: a ranked shortlist of high-potential customers, a
per-customer product recommendation, and personalized, compliant outreach, each backed by
**reason codes**. The system must hold a conversation (follow-ups), and the WhatsApp send is
**simulated** (dry-run + audit log).

## 1.2 Business context
A retail-banking RM owns hundreds of customers and is measured on cross-sell, while bound by
compliance. The skill is **timing and fit**: offering the right product to the right
customer at the moment a life event creates need or capacity — without making promises the
bank can't keep. The hard part isn't any single calculation; it's *fusing* many weak signals
(balances, holdings, repayment behavior, life-stage, recent events) into a decision the RM —
and a compliance officer — can trust and audit.

## 1.3 Functional scope & required capabilities
1. Interpret an open-ended NL request and decide what to do.
2. Identify and **rank** high-potential customers for a product.
3. **Recommend** an eligible product per customer.
4. **Generate** a personalized, compliant outreach message.
5. Attach **reason codes** to every score, recommendation, and figure.
6. Support **multi-turn** follow-ups (explain a customer, redraft in another language, filter the set).
7. Expose the agent's **reasoning** so it can be inspected.

## 1.4 Non-functional requirements
Explainability · reliability/safety (bounded work, unbypassable guardrails) ·
reproducibility (fixed seed → identical scores) · testability (no network in tests) ·
extensibility (add a product / tune scoring without touching the orchestrator) ·
provider independence (no LLM vendor lock-in) · interactive latency.

## 1.5 Hidden requirements (implied by the brief, not stated)
These separate a literal reading from a deep one:

| Hidden requirement | Consequence in the design |
|---|---|
| **"High-value" is ambiguous** — *worth pursuing* ≠ *likely to convert now* | **Two separate scores: Value and Propensity** (the major discovery, §2.3). |
| **"This month" implies an event**, not a static profile | A **temporal trigger engine** (§3.3). |
| **Outreach is a regulated artifact** | Deterministic **compliance + groundedness**, *internal to generation* (§ solution.md). |
| **The LLM will hallucinate numbers** | A **groundedness** check: every figure must trace to real facts. |
| **Money needs exactness** | **Integer paise** end-to-end; round only at display. |
| **Eligibility ≠ contactability** | Hard eligibility gates *and* consent suppression (DND / opt-out). |
| **Reviewers grade the reasoning** | Make the **cognitive loop** the primary, observable abstraction. |

## 1.6 Initial open questions (and the answers adopted)
| Question | Answer adopted |
|---|---|
| What does "high-value" mean precisely? | A configurable composite of **Value** and **Propensity** (§2.3, §3.4). |
| Where do hard rules end and ranking begin? | **Hard filters gate; soft scores rank** (§2.4). |
| Heuristics or ML? | **Transparent heuristics** — no labels exist; explainability is graded (§2.5). |
| Which LLM? | **Provider-agnostic**; Gemini default, Anthropic selectable (§2.9). |
| How is data accessed? | **Repository pattern over SQLite**, money in paise (§2.6). |
| How is correctness shown without real data? | **Deterministic synthetic data with embedded ground-truth signals** (§2.8). |

## 1.7 Assumptions & constraints
**Assumptions:** synthetic data stands in for the warehouse; WhatsApp send is simulated;
single RM / single tenant; no labeled conversions (→ heuristics); Indian retail context
(₹, en/Hindi/Hinglish, festival seasonality).
**Constraints:** the LLM never computes a score, applies a rule, or invents a fact;
deterministic logic stays deterministic and reason-coded; bounded tool calls / re-plans per
turn; parameterized SQL; PII masked in logs; secrets via env; no provider SDK outside the
LLM layer; agent surface kept to 5 tools.

---

# Part 2 — Discovery

## 2.1 Why an agent (not a pipeline or a chatbot)
A fixed `retrieve → rank → draft → respond` pipeline can't handle *"why her?"*, *"redo in
Hindi"*, *"only those in Indore"*, or *"just list them, don't message"* — each needs a
*different* sequence. A pure chatbot, conversely, would be unsafe (it would compute and
fabricate). The fit is an **agent**: the LLM decides *what to do* each turn; deterministic
code guarantees *it is done correctly*. The agent **owns the workflow** and adapts; it is not
a script.

## 2.2 Architecture shape — the cognitive loop + cognition/execution split
The agent runs an explicit per-turn loop with conversational memory:

**Perceive → Plan → Act → Observe → Reflect → Respond**

and the load-bearing split is **cognition vs execution**:

- **LLM (cognition):** understand intent, plan, choose tools, adapt, clarify, reflect, write prose.
- **Deterministic code (execution):** scoring, eligibility, ranking, compliance, groundedness, persistence, audit.

This is what makes the system explainable, testable without a model, and safe by
construction. (Mechanics and diagrams: [`architecture.md`](architecture.md).)

## 2.3 The major discovery — defining "high-value"
Plain English fuses two distinct ideas. A customer with ₹2 Cr in deposits is **valuable**
but may have **zero propensity** for a personal loan; a young salaried customer with an
ending car EMI may be **moderately valuable** but **highly likely** to convert *now*.
Collapsing these into one number would mis-rank and would not be explainable.

**Decision: two separate, independently reason-coded scores.**

| Score | Question it answers | Nature |
|---|---|---|
| **Value** | Is this relationship worth pursuing? | Product-independent, "universal" signals |
| **Propensity** | Is this customer likely to convert for *this product*, *now*? | Product-specific fit **+ temporal triggers** |

They are combined by a **configurable** ranking weight (§3.4) — so "high-value" is a defined,
tunable composite, not a vague label. This is the centerpiece of the framework (Part 3).

## 2.4 Hard filters vs soft ranking
A critical separation: some rules are **binary and non-negotiable** (eligibility), others are
**graded** (desirability). Conflating them produces both unsafe and un-explainable output.

- **Hard filters (gate, before scoring matters):** age, KYC, minimum income, delinquency/DPD,
  unsecured-facility caps, and **fraud-flag / recent-default hard-exclusions** on new credit.
  Fail any → the customer is *excluded* with a `failed_rules` reason. No score can buy back
  ineligibility.
- **Soft ranking (order the eligible):** Value × Propensity composite. This only ever runs on
  customers who already passed the gate.

This mirrors how a bank actually works (policy first, then prioritization) and keeps the
"why excluded" vs "why ranked here" explanations distinct.

## 2.5 Scoring methodology
Heuristic, **config-driven**, fully deterministic:
- Each factor maps a raw feature onto a normalized 0–1 contribution (banded or capped), then is
  weighted; weights sum to 1.0 and live in [`config/scoring.yaml`](../config/scoring.yaml).
- **No weight or threshold is hardcoded**; the LLM is never in this path.
- Each factor and trigger emits a **reason code** filled with the customer's real values.
- **Confidence** is data-completeness driven, so the system never shows false precision on thin data.

Why not ML? No labeled conversions exist, and the brief rewards explainability. Heuristics are
transparent and testable now; an ML scorer slots in later behind the same `Assessment`
contract with feature-attribution reason codes.

## 2.6 Data access pattern
**SQLite + the repository pattern.** Repositories expose typed, parameterized queries; the
rest of the system never sees SQL. Money is stored as **integer paise** (no floats). This is
zero-config and reproducible for a take-home, and Postgres is an isolated swap behind the
repositories. **Scores are derived, never stored**, so they can never drift from config.

## 2.7 Service shape
Deterministic logic is decomposed into small, single-responsibility services —
`features → triggers → value_scorer / propensity_scorer → eligibility → recommender →
ranker`, plus `compliance` and `groundedness` — composed by an `AssessmentService`. Each is
unit-testable in isolation; the agent reaches them only through **5 typed tools** (analytics
stay internal services, not agent tools, to keep the action space small).

## 2.8 Synthetic data strategy
Real correctness must be demonstrable without real data, so the generator:
- is **deterministic** (fixed Faker seed → identical dataset and scores every run);
- **embeds ground-truth signals** — customers engineered to have a maturing FD, an ending EMI,
  a large outflow, or a salary hike, so triggers and scores are observable and assertable;
- plants **role populations** — clear "hero" prospects, plus **fraud-flagged**,
  **recently-defaulted**, and **DND / opted-out** customers — so every guardrail and exclusion
  is demonstrable;
- writes **append-only transactions** with realistic categories/channels so the trigger
  window and confidence (transaction count) are meaningful.

## 2.9 Provider-agnostic LLM (discovery decision)
Calling a vendor SDK throughout the code would create lock-in and make business logic
untestable offline. **Decision:** an `LLMClient` abstraction (`complete` / `generate` /
`structured`) with an `LLMFactory` selecting the provider from config. Gemini is the default;
Anthropic/Claude is a fully implemented alternative (selectable in the UI); a `MockClient`
makes the whole system testable with **zero token spend**. Only one package imports a provider
SDK — so swapping the model never changes a score.

---

# Part 3 — The High-Value Framework in Detail

All values below are the live defaults in [`config/scoring.yaml`](../config/scoring.yaml);
changing them is a config edit, not a code change.

## 3.1 Layer A — Universal value signals (the **Value** score)
*Product-independent: how much is this relationship worth?* Weighted contributions (sum = 1.0):

| Signal | Weight | How it's measured | Reason-code example |
|---|---:|---|---|
| **AUM** | 0.40 | Total assets under management, banded at ₹2L / ₹10L / ₹25L (4 bands) | *"AUM ₹99.76L (Top band)"* |
| **Income** | 0.25 | Monthly income proxy, capped at ₹3,00,000/mo | *"Income proxy ~₹5.90L/mo"* |
| **Product depth** | 0.20 | Distinct products held, capped at 4 | *"Holds 4 product(s)"* |
| **Tenure** | 0.15 | Relationship length, capped at 96 months (8 yrs) | *"5-year relationship"* |

## 3.2 Layer B — Product-specific signals (the **Propensity** score)
*Will this customer convert for **this** product, **now**?* Static fit (sum = 1.0) **plus**
additive temporal trigger boosts (§3.3):

| Signal | Weight | Intuition |
|---|---:|---|
| **Affordability** | 0.30 | Income clears the product minimum with headroom (×2.0) |
| **Debt burden** | 0.25 | EMI-to-income (FOIR) below the 0.50 ceiling |
| **Utilization** | 0.20 | Card utilization below the 0.40 "unhealthy" mark |
| **Delinquency** | 0.15 | Clean repayment (DPD) history |
| **Life-stage fit** | 0.10 | Age within the product's ideal band (e.g. personal loan 25–50) |

## 3.3 Temporal triggers — the "why now" engine
Computed over a **31-day** window; each detected trigger adds points to Propensity. This is
what makes *"this month"* meaningful rather than a static profile:

| Trigger | Boost | Fires when |
|---|---:|---|
| **EMI ending** | +12 | A loan EMI ends soon → repayment capacity frees up |
| **FD maturing** | +10 | A deposit matures soon → funds free up |
| **Large outflow** | +8 | A debit ≥ 1.5× monthly income → possible liquidity need |
| **Salary hike** | +6 | Latest salary ≥ +10% vs trailing median → higher capacity |
| **Festival window** | +4 | Sep–Nov festival season |

## 3.4 The composite definition (ranking)
The shortlist is ordered by a **configurable** composite:

```
rank_score = 0.40 × Value  +  0.60 × Propensity      # config/scoring.yaml → ranking
```

Propensity is weighted higher because the brief asks for customers *likely to convert now*;
the weighting is a single config knob, not code. Value and Propensity remain visible
separately on every card.

## 3.5 Confidence (data-completeness)
A score on thin data must not look precise. Confidence is driven by transaction count:
**HIGH ≥ 40**, **MEDIUM ≥ 15**, else **LOW**. It is surfaced on every prospect so the RM knows
how much to trust the number.

## 3.6 Reason codes
Every factor and trigger emits a templated string filled with the customer's **actual** values
at compute time — e.g. *"Loan EMI ends 2026-07-10 → ~₹1.75L/mo repayment capacity frees up"*.
These flow into the outreach message and are exactly what the **groundedness** check verifies,
so no figure can appear that doesn't trace to real data.

## 3.7 Per-product playbooks
Eligibility parameters and recommendation/outreach metadata are **not** in code — each product
is a **YAML playbook** in `config/playbooks/<product>.yaml`. The catalog is built from these;
the `Product` entity and the eligibility/scoring services are unchanged. **Adding a product is
a new file.** Eight ship by default (savings, current, FD, RD, personal/auto/home loan, credit
card).

## 3.8 Playbook format
Validated by a typed `Playbook` schema at load time (a malformed file fails fast). Monetary
thresholds are written in rupees for readability and converted to paise downstream:

```yaml
product_id: PROD_PERSONAL_LOAN
name: Personal Loan
product_type: PERSONAL_LOAN
product_class: LENDING
is_active: true
# Eligibility gates (hard filters)
min_age: 21
max_age: 60
min_monthly_income_rupees: 25000
requires_kyc: true
max_active_unsecured_loans: 2
# Recommendation / outreach metadata
typical_ticket_size_rupees: 500000
indicative_interest_rate_pct: 11.5
talking_points:
  - Quick disbursal for planned expenses
  - Flexible tenure; no collateral
```

## 3.9 Edge-case handling
| Edge case | Behavior |
|---|---|
| **No transactions** | Triggers can't fire; **LOW** confidence; the score is still computed and labeled. |
| **Ties in rank** | Deterministic, stable ordering (fixed seed → reproducible). |
| **Ineligible customer** | Excluded with a `failed_rules` reason; never ranked. |
| **Fraud flag / recent default** | **Hard-excluded** from new credit regardless of score. |
| **Empty eligible set** | The agent **observes** the empty result, **reflects**, and adapts (e.g. relaxes a soft filter) or answers honestly — it does not fabricate prospects. |
| **DND / opted-out** | Eligible but **never messaged**; outreach is suppressed with a reason. |
| **Hallucinated figure in a draft** | Caught by **groundedness**; regenerate (bounded) or suppress. |
| **Thin / missing fields** | Capped contributions + confidence prevent false precision. |

---

# Part 4 — Deferred (and why)

Scope was bounded to what best demonstrates the agentic capability the brief asks for.
Everything deferred is designed to be **additive** — no rework of the core:

| Deferred | Why deferred | How it slots in later |
|---|---|---|
| **ML propensity model** | No labeled conversions; explainability is graded | Behind the same `Assessment` contract, with feature-attribution reason codes |
| **Postgres + pooling** | SQLite is zero-config & reproducible for a take-home | Isolated swap behind the repository interface |
| **Real WhatsApp send** | Out of scope; safety | Behind the existing `log_outreach` / messaging seam |
| **Multi-tenant + RBAC, encryption, secrets vault** | Single-RM scope | Additive at the API/auth boundary |
| **Vector store / semantic retrieval** | Not needed for structured scoring | Optional retrieval service feeding features |
| **Token/cost metrics & archetype personas** | Needs provider-usage plumbing / generator rework | Per-turn metrics + richer drafting context |
| **Multi-agent topology** | Roles ≠ agents; single agent is simpler and more transparent for this scope | Supervisor + specialists reusing the same tools/services (see [`architecture.md`](architecture.md)) |

> The single-agent boundary, the deterministic-service core, and the provider-agnostic LLM
> layer are deliberately clean seams — each deferred item plugs into one of them without
> disturbing the rest.
