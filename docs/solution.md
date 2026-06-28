# Solution — RM Copilot

*How the problem was solved, subsystem by subsystem, with the reasoning behind each choice.*

For the problem understanding, discovery, and the **high-value scoring framework in detail**
see [`discovery.md`](discovery.md); for diagrams and internal mechanics see
[`architecture.md`](architecture.md). This document sits in between: **what each part does
and why it is built that way.**

---

## 1. Solution overview

RM Copilot is a **single agent** that turns one natural-language request into an
explainable workflow. The design is governed by one principle:

> **Cognition vs execution.** The LLM *reasons* (understand intent, plan, choose tools,
> adapt, clarify, reflect, write prose). Deterministic code *computes* (scoring,
> eligibility, ranking, compliance, groundedness, persistence). The LLM never computes a
> score, applies a rule, or invents a fact.

Everything below is an application of that split. The agent decides *what to do*; the
deterministic layers guarantee *it is done correctly and explainably*.

## 2. End-to-end workflow

```
RM request
  → Perceive (intent + memory)
  → Plan        [LLM]      decide intent, parameters, generate-or-not, clarify-or-proceed
  → Act         [tools]    agent-decided sequence over deterministic services
  → Observe                interpret results / empty / ineligible / errors
  → Reflect     [LLM]      does this answer the request? one bounded re-plan if not
  → Respond     [LLM]      grounded markdown synthesized over reason codes
  → Memory                 store result set for follow-ups
```

A turn touches only the tools the plan calls for. *"List the top 20"* ranks and lists with
**no drafting**; *"…and message them"* additionally drafts the top few; *"why her?"* reads
memory and explains without re-ranking; *"only those in Indore"* filters the prior set in
place. The sequence is **never** a fixed pipeline.

## 3. Agent workflow & the cognitive loop

The orchestrator runs six stages per turn; each stage emits a structured, logged,
mockable trace event (the **reasoning trace** — observable decisions, never raw
chain-of-thought):

| Stage | Who | What it does |
|---|---|---|
| **Perceive** | code | Read the request + conversational memory; resolve follow-up references. |
| **Plan** | **LLM** | Structured output: intent, parameters, `generate_messages`, filters, assumptions, and **clarify-vs-proceed**. The planner *owns the workflow shape*. |
| **Act** | tools | Invoke deterministic tools via the registry, in the agent-decided order. |
| **Observe** | code | Interpret results: empty set, all-ineligible, low-confidence, tool error. |
| **Reflect** | **LLM** | Does the observation answer the request? Trigger **one** bounded re-plan if not (e.g. relax `eligible_only`). Never overwrites a deterministic score. |
| **Respond** | **LLM** | Synthesize grounded markdown strictly over the reason codes and facts. |

**Why a planner-owned loop:** the brief grades reasoning. Making the loop explicit and
bounded (caps on tool calls and a single re-plan) keeps the agent transparent and reliable
— adaptive where it should be, predictable where it must be.

## 4. Tool registry — the agent's execution primitives

Five typed tools form the agent's entire action space. Each is a class with a Pydantic
input/output model and a JSON schema, registered in one place; adding a tool is a new class
+ one registry entry, and the orchestrator does not change.

| Tool | Purpose | Det/LLM |
|---|---|---|
| `find_and_rank_prospects` | retrieve → score (Value & Propensity + triggers) → eligibility → recommend → rank | Deterministic |
| `get_customer_360` | full profile, holdings, transactions, interactions | Deterministic |
| `explain_assessment` | factor/trigger breakdown + reason codes for one (customer, product) | Deterministic |
| `generate_outreach_message` | personalized draft, grounded in facts; **guardrails internal** | LLM (gated) |
| `log_outreach` | persist the decision + message (the simulated send); idempotent | Deterministic |

Tools return a **structured `is_error` result** instead of raising, so the orchestrator can
observe failures and self-correct. Analytics (scoring, ranking, eligibility) stay *internal
services*, not tools — keeping the agent surface small and the cognition focused.

## 5. Deterministic business logic

All scoring/eligibility logic is pure, unit-tested code driven by
[`config/scoring.yaml`](../config/scoring.yaml) — **no weights or thresholds are hardcoded**,
and the LLM is never involved. The framework in full detail (every factor, weight, trigger,
the composite, confidence, playbook format, and edge cases) is in
[`discovery.md` Part 3](discovery.md#part-3--the-high-value-framework-in-detail); the
reasoning, in brief:

- **Two separate scores** — *Value* (worth pursuing, product-independent) and *Propensity*
  (likely to convert now, product-specific fit **+ temporal triggers**) — combined by a
  configurable ranking weight. Keeping them separate is more correct *and* more explainable
  than one blended "high-value" number.
- **Hard filters gate; soft scores rank.** Eligibility (age, KYC, income, delinquency, unsecured
  caps, **fraud-flag / recent-default exclusions**) is binary and runs first; ranking only ever
  orders the eligible set. No score buys back ineligibility.
- **Temporal triggers** answer *"why now"* (FD maturing, EMI ending, large outflow, salary
  hike, festival window) — the mechanism that makes "this month" meaningful.
- **Confidence** (HIGH/MEDIUM/LOW) is data-completeness driven, so thin data never looks
  precise. Money is integer **paise**; rounding only at display.
- **Reason codes** — every factor and trigger emits a templated string filled with the
  customer's *actual* values (e.g. *"FD of ₹59.80L matures on 2026-06-30 — funds freeing up"*).
  These flow into the message and are exactly what the groundedness check verifies.

## 6. Provider-agnostic LLM layer

Business logic depends only on an `LLMClient` abstraction with three capabilities:
`complete` (text), `generate` (one tool-use turn), `structured` (schema-valid JSON for the
planner/reflector). An `LLMFactory` selects the concrete provider **from configuration**:

- **GeminiClient** (`google-genai`, default `gemini-3.1-flash-lite`) — runtime default.
- **AnthropicClient** (`anthropic`, e.g. `claude-opus-4-8`) — selectable at runtime / in the UI sidebar; uses the Messages API with forced `tool_choice` for structured output.
- **MockClient** — deterministic, scripted; powers all tests with zero token spend.
- **OpenAIClient** — declared stub extension point.

**Only the `agent/llm/` layer imports a provider SDK.** Swapping providers is a config
change; adding one is a client class + a factory entry. Because the deterministic core is
identical across providers, the *scores never change* when the model does — proven by
switching Gemini ↔ Anthropic and observing identical rankings.

## 7. Memory

In-process conversational memory holds the recent dialogue, the **last result set**, and
the last product discussed. Follow-ups ("why her?", "redo in Hindi", "only those in
Indore") are resolved against this prior context rather than re-fabricated — the planner
reads a compact memory snapshot and resolves references to a concrete `customer_id` / city.
Durable business facts and the outreach audit log live in SQLite; session memory is
ephemeral by default (JSON persistence is an easy add).

## 8. Explainability

Explainability is not a feature bolted on — it is the architecture:
- **Every score and recommendation carries reason codes** with real values.
- **Every cognitive step is a structured trace event** (stage, summary, tool args/result summary, durations) — surfaced live in the Agent Console as a loop bar, execution-plan panel, tool timeline, reflection panel, and memory panel.
- **No raw chain-of-thought is exposed** — only observable decisions and execution events.

A reviewer (or a compliance officer) can answer *"why this customer, why this product, why
this number"* from the UI alone.

## 9. Guardrails

Two deterministic checks are **internal to `generate_outreach_message`**, so they cannot be
bypassed by the agent:

- **Groundedness** — every monetary figure, date, product, and attribute in the draft must
  appear in the structured facts passed to the generator. Any untraceable number →
  regenerate (bounded), else suppress. This neutralizes hallucination.
- **Compliance** — no guaranteed/assured-approval phrases; a mandatory opt-out line;
  indicative framing of rates/amounts; first-name + city PII only (a PAN-shaped token is
  rejected); length cap.

Plus **consent suppression**: customers on `do_not_disturb` or with `marketing_opt_in =
false` are never drafted to. Customer facts are passed to the generator **as data, never as
instructions** (prompt-injection safety). The status of every attempt (READY / SUPPRESSED /
COMPLIANCE_FAILED) is logged.

## 10. Data model overview

Six durable tables, all money in integer paise; **scores are derived, never stored** (so
they can never drift from the config):

`customers · products · product_holdings · transactions · interactions · outreach_log`

`ProductHolding` deliberately unifies accounts, deposits, loans, and cards (no separate
`Account` entity). Products are **YAML playbooks** — a new product is a new file, with the
`Product` entity and all eligibility/scoring logic unchanged. The synthetic generator plants
ground-truth value/trigger signals and a small population of fraud-flagged /
recently-defaulted / DND customers so every rule is demonstrable. See
[`architecture.md`](architecture.md) for the entity diagram and data flow.

## 11. Testing strategy

**120 tests, no network, no token spend.**
- **Deterministic services & tools** — unit-tested directly; fixed seed → stable scores; edge cases (no transactions, ties, ineligible, empty set, fraud/default exclusion, a fabricated number caught by groundedness).
- **The agent** — tested **by trajectory** with a scripted `MockClient`: asserts the plan, the tool sequence, clarification, multi-turn memory, redraft, planner-owned generate-vs-list, in-place filtering, and bounded reflect/adapt.
- **API** — FastAPI `TestClient` over a real seeded SQLite.
- **Reproducibility** — the same seed yields identical data and scores, so trajectory tests are stable.

## 12. Security considerations

- **No secrets in the repo** — keys via environment only; `.env` gitignored.
- **PII discipline** — only a masked PAN ever exists; logs carry first-name/token only; the compliance check blocks PAN-shaped tokens from any outgoing message.
- **SQL injection** — parameterized queries only.
- **Prompt injection** — customer data reaches the generator as structured facts, not instructions; output is gated by groundedness + compliance before it is shown or logged.
- **No real outreach** — the WhatsApp send is simulated and audited; there is no network dispatch path.
- **Provider boundary** — no vendor SDK is imported outside `agent/llm/`.

## 13. Trade-offs

| Decision | Gain | Cost (accepted) |
|---|---|---|
| Heuristic scoring (not ML) | Explainable, testable, no labels needed | Less adaptive than a trained model |
| Single agent (not multi-agent) | Transparent, simple, less overhead | A future, broader scope may want decomposition |
| Manual loop (no framework) | Full control, gradable reasoning | More orchestration code to own |
| SQLite (not Postgres) | Zero-config, reproducible | Single-writer; not for production scale |
| Bounded per-turn drafting | Cost/latency control, reviewable | Large batches need a "continue" turn (surfaced explicitly) |
| In-process memory | Simple, fast | Not durable across processes (JSON persistence is additive) |

## 14. Limitations

Synthetic data; simulated send; single RM / single tenant; no credit-bureau score (internal
risk band + DPD only); English/Hindi/Hinglish messaging; schema changes need a fresh
`make seed` (no migration framework); the demo API shares one SQLite connection across
threads. Token/cost metering is not yet wired through the provider clients.

## 15. Future improvements

- **ML propensity model** once labeled conversions exist — behind the same `Assessment` contract, with feature-attribution reason codes.
- **Postgres + a connection pool**; offline/batch scoring; a vector store for similar-customer retrieval.
- **Real WhatsApp** via a messaging provider behind the existing tool interface.
- **Multi-tenant + RBAC**, immutable audit, field-level PII encryption, secrets vault.
- **Token/cost metrics** surfaced per turn; archetype personas for richer drafting.
- **Multi-agent evolution** if scope broadens (see [`architecture.md`](architecture.md)).
