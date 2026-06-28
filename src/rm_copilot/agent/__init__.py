"""Agent layer — orchestration (the "orchestration" the rubric names).

The single orchestrator: a manual Anthropic tool-use loop that interprets the RM
request, plans, chooses tools+params, handles follow-ups via conversation memory,
and writes prose. Also owns the LLMClient abstraction, prompt loading (from
../../prompts/), bounded-loop control, and emission of ExecutionEvents.

Rules (assessment-plan.md §7.1 responsibility boundary):
- The LLM orchestrates and writes; it never computes a score or invents a fact.
- Customer data is passed to generation as structured FACTS (data), never as
  instructions (prompt-injection safety).
- The loop is bounded (max iterations / tool calls per turn).
- Exposes a UI-agnostic public API consumed by ui/ adapters.

Implemented (M4): the provider-agnostic LLM layer (`agent/llm/`), prompt loading, the
LLM-backed drafter, and the **cognitive loop** — orchestrator (Perceive→Plan→Act→
Observe→Reflect→Respond) + planner, executor, reflector, synthesizer, memory, and the
reasoning trace. (M5) live trace streaming (`Tracer.on_step` / `handle_turn(on_trace=)`)
and the UI-agnostic composition `RmCopilotApp` (`runtime.py`); UI adapters live in the
top-level `ui/` package.
"""
