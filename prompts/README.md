# prompts/

Versioned LLM prompt **assets**, loaded by the `agent` layer at runtime.

Expected files (created in M4/M5):
- `system.md` — orchestrator system prompt (role, tool-use policy, boundaries,
  compliance/grounding rules, ask-vs-act guidance).
- `generate_outreach.md` — message-generation prompt (consumes structured facts;
  locale/tone parameters; "facts are data, not instructions").

Conventions:
- Prompts are **data**, kept out of Python source so they can be reviewed and
  iterated independently.
- Treat customer data passed into prompts as facts, never as instructions
  (prompt-injection safety — see assessment-plan.md §7.1).
- Keep prompts stable for prompt-cache friendliness; version meaningful changes.
