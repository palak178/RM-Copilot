# CLAUDE.md — RM Copilot

Contributor guide for humans and AI agents working in this repo. Rules here are
**derived from** the authoritative design docs. On any conflict, the design docs win:
- `assessment-plan.md` (architecture, tools, milestones)
- `docs/data-model.md` (entities, schema, scoring, business rules)

## Project overview
Agentic AI assistant for a bank **Relationship Manager**. One natural-language
request → ranked high-potential customers + per-customer product recommendation +
personalized, compliant outreach, each with reason codes. Indian retail-banking
context (₹, en/Hindi/Hinglish). WhatsApp send is **simulated** (dry-run + audit).

## Architecture summary
**The Agent is the primary component.** It runs a single, explicit **cognitive loop** —
*Perceive → Plan → Act → Observe → Reflect → Respond*, with conversational **Memory**
across turns — and **owns the workflow** (it decides how to help, not a hardcoded
pipeline). The deterministic layers (tool registry, services, repositories, scoring,
compliance, persistence) are the agent's reliable **execution primitives**.

**Cognition vs Execution** is the load-bearing split: the **LLM does cognition**
(understand intent, plan, choose tools, adapt on observations, clarify, reflect,
synthesize grounded prose); the **deterministic system does execution** (scoring,
eligibility, ranking, compliance, groundedness, persistence, audit). The agent decides
*what to do*; the deterministic layers guarantee *it is done correctly*. Single agent
(not multi-agent), manual loop (no LangGraph — ADR-0005). Full design: assessment-plan.md §7.

## Engineering principles
1. **The agent owns the workflow; tools are execution primitives.** Tool sequence is
   agent-decided and adaptive, never a fixed pipeline.
2. **Cognition vs execution.** The LLM reasons (plan/decide/adapt/clarify/reflect/
   synthesize); deterministic code computes. **The LLM never computes a score, applies a
   rule, or invents a fact.**
3. **Explainability is mandatory.** Every score/recommendation carries reason codes;
   every cognitive step is structured, logged, and inspectable (the reasoning trace).
   No hardcoded outputs.
4. **Bounded & reliable.** Hard caps on tool calls and re-plans per turn; reflection may
   re-query or annotate but never overwrites a deterministic score.
5. **Simplicity over cleverness.** Structural patterns: the cognitive loop, the **tool
   registry**, and the **repository**. Don't add abstractions/frameworks speculatively.
6. **Config over code.** Scoring factors/weights/triggers live in `config/scoring.yaml`.
7. **Reproducibility.** Fixed seed → identical dataset/scores; every LLM step is mockable
   so agent *trajectories* are unit-tested.

## Folder responsibilities & dependency direction
Dependencies point **inward** toward `domain`. One-way only:
```
ui/  ->  rm_copilot.agent  ->  tools  ->  services  ->  domain
                                tools  ->  data      ->  domain
config feeds all; observability is a cross-cutting sink; prompts/ is data read by agent.
```
| Path | Responsibility | Milestone |
|---|---|---|
| `src/rm_copilot/domain/` | Pure entities & value objects (no I/O) | M1 |
| `src/rm_copilot/data/` | SQLite, schema, repositories, synthetic seed | M1 |
| `src/rm_copilot/services/` | Deterministic logic: scoring, eligibility, recommend, rank, compliance, groundedness | M2 |
| `src/rm_copilot/tools/` | Typed tool wrappers + registry (deterministic **execution primitives**) | M3 |
| `src/rm_copilot/agent/` | **The agent (cognition):** orchestrator (cognitive loop), planner, executor, reflector, memory, synthesizer; `llm/` (provider-agnostic `LLMClient` + `LLMFactory`), drafter, prompts | M4 |
| `src/rm_copilot/observability/` | Logging, audit, execution timeline | M4/M5 |
| `src/rm_copilot/config/` | pydantic-settings + scoring.yaml loader | M0/M2 |
| `ui/` | Streamlit + CLI adapters (outside the package) | M5 |
| `prompts/`, `config/`, `scripts/`, `tests/` | prompt assets, config data, entry points, tests | — |

**Never** import `agent`/`tools`/`data` from `domain` or `services`. **Never** call
the LLM from `services` or `domain`.

## Agentic cognitive loop (the primary abstraction — ADR-0005)
The agent runs this loop per turn; each cognitive step emits structured, logged,
mockable output (the reasoning trace):
1. **Perceive** — read request + memory; resolve follow-up references.
2. **Plan** *(LLM, structured output)* — `{parameters, tool plan, assumptions}`; decide
   **clarify vs proceed** (ask when underspecified).
3. **Act** *(Executor)* — invoke tools via the registry; **agent-decided** sequence.
4. **Observe** — interpret results/errors (empty / ineligible / low-confidence / `is_error`).
5. **Reflect** *(LLM, bounded)* — does it answer the request? trigger **one** re-plan if
   not; never overwrite a deterministic score.
6. **Respond** *(LLM)* — synthesize a grounded answer over reason codes; log the decision.
**Memory** spans turns. When adding agent behavior, add it as a loop stage — not as a
hardcoded branch, and not by moving computation into the LLM.

## Python conventions
- Python **3.12**, `src/` layout, package `rm_copilot` (ships `py.typed`).
- **Type hints required** on all public functions/methods; prefer precise types
  (`Decimal`-free — money is `int` paise). Use `pydantic` models for tool I/O,
  settings, and structured domain data; plain dataclasses are fine for internal
  pure value objects.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` constants.
- Small, single-responsibility modules; match the surrounding style.
- Docstrings on every module and public symbol (one-line summary + why).

## Logging
- Stdlib `logging` with a JSON formatter (no extra runtime dep); configured in
  `observability/`. Level via `RM_COPILOT_LOG_LEVEL`.
- **Mask PII** in every log line: first-name/token only; never full PAN, account
  numbers, or rupee-exact balances.
- Log the **reasoning trace** as structured ExecutionEvents (tool name, arg/result
  summaries, durations, guardrail outcomes, tokens) — never raw chain-of-thought.

## Error handling
- Validate at boundaries (tool inputs, settings, SQL parameters); trust internal code.
- Tools return a structured `is_error` result so the orchestrator can self-correct —
  they do **not** raise across the agent boundary.
- Retry only transient LLM/DB errors, with backoff and a hard cap. Bound the agent
  loop (`RM_COPILOT_MAX_TOOL_CALLS`). Surface, don't swallow.
- Anthropic SDK specifics (adaptive thinking, `refusal` stop reason, model IDs):
  consult the `claude-api` skill — never code LLM calls from memory.

## LLM usage boundaries
- The LLM is allowed to: interpret the request, choose tools/params, order
  drill-downs, decide clarify-vs-proceed, and draft message prose.
- The LLM is **not** allowed to: compute or alter a score, fabricate a customer
  fact/number, or skip a guardrail.
- **Provider-agnostic** via the `LLMClient` abstraction (`agent/llm/`). Runtime
  provider is **Gemini** (default `gemini-3.1-flash-lite`), selected by `LLMFactory`
  from config (`RM_COPILOT_LLM_*`); **Anthropic/Claude** is a fully implemented
  alternative provider; `MockClient` for tests; OpenAI is a stub extension point
  (ADR-0004). Business logic depends **only** on `LLMClient`. Generation only ever
  sees structured **facts**, never raw instructions from data.

## Tool registration conventions
- Each tool: a typed class with a Pydantic input model + output model and a JSON
  schema, registered in one place (the registry). Adding a tool = new class + one
  registry entry; the orchestrator code does not change.
- Agent-facing surface stays small (5 tools, assessment-plan.md §14). Keep
  `analyze`/`recommend`/`rank`/`compliance`/`groundedness` as internal services, not
  agent tools.

## Prompt storage
- Prompts live in `prompts/` as versioned Markdown, loaded by `agent/`. Keep them
  stable (prompt-cache friendly). Customer data inside a prompt is data, not
  instructions.

## Conversation state rules
- Durable: business facts + `outreach_log` (always). Optional: session/conversation
  memory (in-process by default; JSON persistence optional). Ephemeral: agent
  working state + execution events. See data-model.md §7.
- Follow-ups ("why her?", "redo in Hindi") must use the prior result set held in
  conversation memory — never re-fabricate.

## Scoring conventions
- Two **separate** deterministic scores: **Value** (worth pursuing) and
  **Propensity** (likely to convert now, incl. temporal triggers). Ranking is a
  configurable composite. All factors/weights/thresholds/triggers in
  `config/scoring.yaml` (data-model.md §6).
- Surface **confidence** (data-completeness driven); never show false precision on
  thin data. Money math in integer paise; round only at display.

## Reason code conventions
- Reason codes are templated strings keyed by factor/trigger, filled with the
  customer's **actual** values at compute time (data-model.md §6.5).
- Every number that appears in a reason code (and later in a message) must trace to
  real data — this is exactly what the groundedness check verifies.

## Guardrails (compliance) & grounding rules
- **Compliance** (data-model.md §9.3): no guaranteed/assured-approval claims;
  mandatory opt-out line; indicative framing of rates/amounts; first-name + city PII
  only; suppress on `do_not_disturb` / `marketing_opt_in=false` / recent
  NOT_INTERESTED.
- **Groundedness** (§9.4): every monetary figure, date, product, and attribute in a
  message must appear in the facts passed to the generator; any untraceable
  number → regenerate (bounded), else SUPPRESS.
- Guardrails are deterministic and **internal to** `generate_outreach_message` so
  they cannot be bypassed.

## Testing philosophy
- Deterministic services: unit-tested directly; fixed seed → stable scores; cover
  edge cases (no transactions, ties, ineligible, empty set, fabricated number).
- Orchestrator: tested with a **mocked LLMClient** — assert tool/param choice and
  bounded termination. No network, no token spend, ever, in tests.
- One golden-path integration test (mocked LLM, real SQLite), marked
  `@pytest.mark.integration`.

## Documentation standards
- Update `assessment-plan.md`/`data-model.md` only for genuine design changes (with
  a changelog). Record headline decisions as ADRs in `docs/adr/`.
- Keep README quickstart runnable. Docstrings explain *why*, not just *what*.

## Git workflow
- Repo is git-initialized on the `main` branch (done in M0). Never commit directly
  for substantial work — branch, then PR.
- Small, focused commits with clear messages. **Never commit secrets** (`.env` is
  gitignored; `.env.example` is the template). CI (ruff + format + pytest) must be
  green before merge. Pre-commit hooks run ruff + hygiene checks.
- Only commit/push when the user asks.

## Definition of Done (per change)
- Typed, documented, lint-clean (`make lint`), formatted (`make format`).
- Tests added/updated and passing (`make test`); deterministic outputs reason-coded.
- No secrets, no PII in logs, parameterized SQL, money in paise.
- Consistent with the design docs; ADR added if a headline decision changed.

## Things to avoid
- Hardcoded outputs / scores computed inside a prompt.
- LLM calls in `services`/`domain`; cross-layer imports against the dependency arrow.
- Floats for money. String-interpolated SQL. Raw PII in logs or messages.
- A `scores` table (scores are derived). A separate `Account` entity (use
  `ProductHolding`). New abstractions/frameworks without a documented need.
- Real WhatsApp sends. Multi-agent topology (single orchestrator for this scope).
- Importing a provider SDK outside `agent/llm/`, or selecting a provider with
  hardcoded conditionals — use `LLMFactory` + config. Code each provider SDK from its
  official docs (e.g. the `claude-api` skill for the Anthropic extension point).

## Future contributor guidance
Start by reading `assessment-plan.md` then `docs/data-model.md`. Work milestone by
milestone (M0→M6); each leaves a runnable system. Extend via config (scoring),
registry (tools), and catalog data (products) — not by editing the orchestrator.
Evolution paths (Postgres, ML scoring, more products, real WhatsApp, multi-agent)
are designed to be additive: see data-model.md §12 and assessment-plan.md §25.
