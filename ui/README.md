# ui/

Presentation **adapters** — intentionally kept *outside* the `rm_copilot`
package so the core engine stays importable and testable on its own. Both
adapters depend only on the agent's public API (one-way: `ui/ -> rm_copilot`).

Files (M5, **implemented**):
- `streamlit_app.py` — primary demo surface: chat, **live reasoning-trace timeline**,
  ranked prospect cards (scores, reason codes, triggers, drafted message), multi-turn
  follow-ups. Run: `make ui` (needs `pip install '.[ui]'` + `GEMINI_API_KEY`).
- `cli.py` — conversational REPL streaming the trace live. Run: `make run`.

Both are thin adapters over `rm_copilot.agent.runtime.RmCopilotApp`; rendering uses the
pure helpers in `rm_copilot.observability.render`. They import the package only.

> Realizes the plan's `interface/` layer. Orchestrator is UI-agnostic; swapping or
> adding a UI must not require changes in `agent/`.
