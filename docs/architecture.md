# Architecture — RM Copilot

*The technical design: how the system works internally.*

This document is diagram-led. For the problem understanding and discovery see
[`discovery.md`](discovery.md); for what each subsystem does see [`solution.md`](solution.md).

---

## 1. System architecture (layered)

Dependencies point **inward** toward the pure `domain`. The LLM lives only in the `agent`
layer; `services` and `domain` never call it. `config` feeds every layer; `observability`
is a cross-cutting sink.

```mermaid
flowchart TD
    subgraph SURFACES["Surfaces (outside the package)"]
        ST["Streamlit Agent Console"]
        CLI["Rich CLI"]
        API["FastAPI + SSE"]
    end

    subgraph AGENT["agent — cognition"]
        ORCH["Orchestrator (cognitive loop)"]
        PLAN["Planner"]; REFL["Reflector"]; SYN["Synthesizer"]
        MEM["Memory"]; DRA["Drafter"]
        LLM["llm/ — LLMClient + LLMFactory"]
    end

    REG["tools — registry (5 typed tools)"]
    SVC["services — scoring · eligibility · recommend · rank · compliance · groundedness"]
    DATA["data — repositories · schema · synthetic seed · catalog"]
    DOM["domain — entities · enums · money (pure, no I/O)"]
    CFG["config — settings · scoring.yaml · playbooks"]
    OBS["observability — trace · render"]

    ST --> ORCH; CLI --> ORCH; API --> ORCH
    ORCH --> PLAN & REFL & SYN & MEM & DRA
    PLAN & REFL & SYN & DRA --> LLM
    ORCH --> REG
    REG --> SVC --> DOM
    REG --> DATA --> DOM
    SVC --> DATA
    CFG -.feeds.-> SVC & AGENT & DATA
    ORCH -.trace.-> OBS
    classDef pure fill:#eef,stroke:#88a
    class DOM pure
```

**Rule enforced in code:** nothing in `domain`/`services` imports `agent`/`tools`/`data`
against the arrow, and no provider SDK is imported outside `agent/llm/`.

## 2. Component diagram

```mermaid
flowchart LR
    subgraph Cognition["LLM — cognition"]
        P["Planner<br/>structured: Plan"]
        R["Reflector<br/>structured: ReflectDecision"]
        S["Synthesizer<br/>grounded prose"]
        D["Drafter<br/>message text"]
    end
    subgraph Execution["Deterministic — execution"]
        T1["find_and_rank_prospects"]
        T2["get_customer_360"]
        T3["explain_assessment"]
        T4["generate_outreach_message<br/>(groundedness + compliance inside)"]
        T5["log_outreach"]
        VS["value_scorer"]; PS["propensity_scorer (+triggers)"]
        EL["eligibility"]; RK["ranker"]; RC["recommender"]
        GR["groundedness"]; CO["compliance"]
        REPO["repositories → SQLite"]
    end
    O["Orchestrator"] --> P & R & S
    O --> T1 & T2 & T3 & T4 & T5
    T4 --> D
    T1 --> VS & PS & EL & RC & RK
    T4 --> GR & CO
    T1 & T2 & T3 & T5 --> REPO
```

## 3. Runtime architecture

```mermaid
flowchart TD
    REQ["RM request (string) + SessionMemory"] --> O["Orchestrator.handle_turn()"]
    O --> TR["Tracer (emits TraceStep + at_ms; optional on_step callback → live UI stream)"]
    O --> LF["LLMFactory.from_settings → LLMClient (Gemini | Anthropic | Mock)"]
    O --> RG["ToolRegistry.build_registry(db, config, drafter)"]
    RG --> DB[("SQLite (seeded)")]
    O --> AR["AgentResult: reply · plan · prospects · explanation · trace · metrics"]
    AR --> REQ
```

`RmCopilotApp` (in `agent/runtime.py`) is the UI-agnostic composition root: it wires the
database, scoring config, the provider-agnostic client, the tool registry, and the
orchestrator from settings. Every surface (Streamlit, CLI, FastAPI) is a thin adapter over
`app.ask(message, memory, on_trace=…)`.

## 4. The cognitive loop

```mermaid
stateDiagram-v2
    [*] --> Perceive
    Perceive --> Plan: request + memory
    Plan --> Clarify: underspecified
    Plan --> Decline: out of scope
    Plan --> Act: proceed
    Act --> Observe: tool results
    Observe --> Reflect: empty / ineligible
    Observe --> Respond: sufficient
    Reflect --> Act: one bounded re-plan
    Reflect --> Respond: accept
    Respond --> [*]
    Clarify --> [*]
    Decline --> [*]
```

Bounded by design: at most one reflect-driven re-plan and a hard cap on tool calls per
turn. Reflection may re-query or annotate but **never overwrites a deterministic score**.

## 5. Sequence — a full prospecting + outreach turn

```mermaid
sequenceDiagram
    actor RM
    participant UI as UI adapter
    participant O as Orchestrator
    participant LLM as LLMClient
    participant Reg as ToolRegistry
    participant Svc as Deterministic services
    participant DB as SQLite

    RM->>UI: "Find personal-loan prospects this month and message them"
    UI->>O: handle_turn(msg, memory, on_trace)
    O->>O: Perceive (read memory)
    O->>LLM: structured(plan)  %% intent=prospect, generate_messages=true, top_n
    LLM-->>O: Plan
    O->>Reg: find_and_rank_prospects(product, top_n)
    Reg->>Svc: value + propensity(+triggers) + eligibility + recommend + rank
    Svc->>DB: read customers/holdings/txns (parameterized SQL)
    DB-->>Svc: rows
    Svc-->>Reg: ranked prospects + reason codes
    Reg-->>O: prospects
    loop top message_count (bounded)
        O->>Reg: generate_outreach_message(customer)
        Reg->>LLM: draft (facts as data)
        LLM-->>Reg: draft text
        Reg->>Reg: groundedness + compliance (regenerate or suppress)
        O->>Reg: log_outreach (dry-run send + audit)
    end
    O->>O: Observe
    O->>LLM: synthesize (grounded over reason codes)
    LLM-->>O: markdown reply
    O-->>UI: AgentResult (reply, prospects, trace, metrics)
    UI-->>RM: answer + live reasoning trace
```

## 6. Tool invocation flow

```mermaid
flowchart LR
    PL["Plan (intent + params)"] --> EX["Executor (deterministic interpreter)"]
    EX -->|prospect| F["find_and_rank_prospects"]
    EX -->|generate_messages?| G{"draft top N?"}
    G -->|"top message_count"| GEN["generate_outreach_message → log_outreach"]
    G -->|"beyond cap"| LIST["ranked-only card (NOT_DRAFTED)"]
    EX -->|explain| E["explain_assessment (memory)"]
    EX -->|redraft| RD["generate_outreach_message (memory)"]
    EX -->|filter| FL["filter current set in memory (no re-rank)"]
    F & GEN & E & RD & FL --> OBS["Observation"]
```

The **planner owns** which branch runs (intent), *whether* to draft (`generate_messages`),
*how many* (`message_count`, capped per turn and the cap surfaced), and any `city` filter.
The executor only realizes those decisions over deterministic tools — there is no fixed
`retrieve → draft → respond` pipeline.

## 7. Conversation lifecycle (multi-turn memory)

```mermaid
sequenceDiagram
    participant RM
    participant O as Orchestrator
    participant M as SessionMemory
    RM->>O: "Find personal-loan prospects this month"
    O->>M: store_results(ranked prospects, product)
    O-->>RM: ranked list (+ drafts)
    RM->>O: "Why CUST000003?"
    O->>M: snapshot() → resolve reference
    O-->>RM: explain_assessment (no re-rank, no draft)
    RM->>O: "Redo that message in Hindi"
    O->>M: last customer/product
    O-->>RM: re-draft only (guardrails re-run)
    RM->>O: "Show only the ones from Indore"
    O->>M: last result set
    O-->>RM: filtered in place (no re-rank)
```

## 8. Data flow

```mermaid
flowchart LR
    SEED["Faker seed (fixed)"] --> DB[("SQLite: customers · products · holdings · transactions · interactions · outreach_log")]
    DB --> FE["feature extraction"] --> SC["scorers (value/propensity + triggers)"]
    SC --> RCODES["reason codes (real values)"]
    SC --> EL["eligibility + recommend + rank"]
    RCODES --> FACTS["facts (data)"]
    EL --> FACTS
    FACTS --> DRAFT["drafter (LLM)"]
    DRAFT --> GRD["groundedness: every figure ∈ facts?"]
    GRD -->|fail| DRAFT
    GRD -->|pass| CMP["compliance"]
    CMP --> LOG["outreach_log (dry-run + audit)"]
```

Money is integer **paise** end-to-end (rounded only at display). **Scores are derived, not
stored** — they cannot drift from `scoring.yaml`.

## 9. Entity model

```mermaid
erDiagram
    CUSTOMER ||--o{ PRODUCT_HOLDING : holds
    CUSTOMER ||--o{ TRANSACTION : has
    CUSTOMER ||--o{ INTERACTION : has
    CUSTOMER ||--o{ OUTREACH_LOG : targeted_by
    PRODUCT  ||--o{ PRODUCT_HOLDING : instantiated_as
    PRODUCT  ||--o{ OUTREACH_LOG : about
    CUSTOMER {
        string customer_id PK
        string first_name
        string city
        string masked_pan
        bool   do_not_disturb
        bool   marketing_opt_in
        bool   fraud_flag
        date   last_default_date
    }
    PRODUCT_HOLDING {
        string product_id FK
        int    balance_paise
        date   maturity_or_end_date
    }
    TRANSACTION { int amount_paise; string direction; date txn_date }
    OUTREACH_LOG { string status; bool grounded; bool compliant }
```

`PRODUCT_HOLDING` unifies accounts, deposits, loans, and cards (no separate `Account`).
Products are defined by **YAML playbooks** loaded into the catalog — adding a product is a
new file, not a code change.

## 10. LLM abstraction

```mermaid
classDiagram
    class LLMClient {
        <<abstract>>
        +complete(system, prompt) str
        +generate(system, messages, tools) LLMResponse
        +structured(system, prompt, schema) BaseModel
    }
    class LLMFactory { +from_settings(settings) LLMClient }
    LLMClient <|-- GeminiClient
    LLMClient <|-- AnthropicClient
    LLMClient <|-- MockClient
    LLMClient <|-- OpenAIClient
    LLMFactory ..> LLMClient : creates
```

Business logic depends only on `LLMClient`. `LLMFactory` selects the provider from config
(`RM_COPILOT_LLM_*`). `GeminiClient` and `AnthropicClient` are real; `MockClient` is
deterministic for tests; `OpenAIClient` is a declared stub. **Only this package imports a
provider SDK** — so the deterministic core (and its scores) are identical regardless of the
model, and the whole system is testable with zero token spend.

## 11. Why deterministic services are separated from cognition

Cognition is probabilistic and non-reproducible; banking computation must be exact,
explainable, and auditable. Separating them yields:

- **Explainability** — every score/figure traces to deterministic code + real data.
- **Testability** — the core is unit-tested without a model; the agent is trajectory-tested with a mock.
- **Safety** — guardrails are deterministic and *internal to generation*, so the agent cannot bypass them; a hallucinated number fails groundedness.
- **Stability** — swapping the LLM provider cannot change a score or a ranking.

The model contributes judgment (intent, sequencing, adaptation, prose); the deterministic
layers contribute correctness. Neither does the other's job.

## 12. Why a single cognitive agent

The workflow is sequential, shares one context, and is bounded. A single agent running an
explicit loop is the simplest design that fully satisfies it, and it keeps the reasoning
**transparent and gradable**. "Researcher / scorer / writer" are *roles within one loop*,
not separate agents — modeling them as agents would add message-passing, more failure
modes, and less observability for no capability gain.

## 13. Future evolution toward multi-agent

The single-agent boundary is deliberately a clean seam, not a ceiling. Multi-agent is
warranted only if scope grows to where it pays for its overhead — e.g. **parallel,
independent sub-tasks** (campaign generation across many segments at once), **long-running /
durable** workflows needing checkpointing, or **specialized policies** (a separate
compliance/agent-of-record). The graduation path is additive:

```mermaid
flowchart LR
    subgraph now["Today — single agent"]
        A["Orchestrator (one loop)"] --> Tools
    end
    subgraph later["If scope grows — supervisor + specialists"]
        SUP["Supervisor agent"] --> A1["Prospecting agent"]
        SUP --> A2["Outreach agent"]
        SUP --> A3["Compliance agent"]
        A1 & A2 & A3 --> Tools2["same tool registry + deterministic services"]
    end
    now --> later
```

Because the loop is isolated behind the `agent` layer and all computation lives in
deterministic services + the tool registry, introducing a supervisor and specialist agents
later would reuse the entire execution substrate unchanged — `domain`, `services`, `tools`,
and `data` would not move.

## 14. Repository structure

```
src/rm_copilot/
  domain/         entities.py · enums.py · money.py · assessment.py        (pure, no I/O)
  data/           connection · schema · mappers · repositories · database · catalog · synthetic · seed
  services/       features · triggers · value_scorer · propensity_scorer · eligibility
                  recommender · ranker · compliance · groundedness · assessment
  tools/          base · find_prospects · customer_360 · explain_assessment
                  generate_outreach · log_outreach · registry
  agent/          models · trace · memory · planner · executor · reflector
                  synthesizer · orchestrator · drafter · prompts · runtime
    llm/          base · factory · gemini · anthropic · mock · openai
  api/            schemas · app                                            (FastAPI + SSE)
  observability/  render
  config/         settings · scoring · playbooks
ui/               streamlit_app.py · cli.py                                (thin adapters)
config/           scoring.yaml · playbooks/*.yaml
prompts/          plan · reflect · respond · generate_outreach            (versioned)
tests/            unit/ · integration/ (mocked LLM, real SQLite)
```
