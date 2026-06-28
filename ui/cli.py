"""Conversational CLI for RM Copilot (thin adapter over the agent's public API).

Run: `make run` (or `python ui/cli.py`). Multi-turn; streams the reasoning trace live.
Provider is config-driven (Gemini default — set GEMINI_API_KEY or RM_COPILOT_LLM_API_KEY).
Commands: `:reset` (new conversation), `:quit`.
"""

import sys

from rm_copilot.agent.runtime import build_app
from rm_copilot.agent.trace import TraceStep


def _print_step(step: TraceStep) -> None:
    glyph = {"plan": "🧭", "tool": "🔧", "observe": "🔍", "reflect": "↻", "respond": "🗣"}.get(
        step.stage, "·"
    )
    print(f"   {glyph} {step.stage}: {step.summary}", flush=True)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹/Hindi safe on Windows consoles

    try:
        app = build_app()
    except Exception as exc:
        print(f"Failed to start: {exc}")
        return

    if not app.is_seeded:
        print("No data found. Run `make seed` first.")
        app.close()
        return

    print(f"RM Copilot — provider={app.provider} model={app.model}")
    print('Ask e.g. "Find high-value personal-loan prospects this month and draft messages".')
    print("Commands: :reset  :quit\n")

    memory = app.new_session()
    try:
        while True:
            try:
                message = input("RM> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not message:
                continue
            if message == ":quit":
                break
            if message == ":reset":
                memory = app.new_session()
                print("(new conversation)\n")
                continue

            try:
                result = app.ask(message, memory, on_trace=_print_step)
            except Exception as exc:
                print(f"   ⚠ {exc}\n   (If this is an auth error, set GEMINI_API_KEY.)\n")
                continue

            print()
            print(result.reply)
            print()
    finally:
        app.close()


if __name__ == "__main__":
    main()
