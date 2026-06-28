"""Agent Console — Streamlit UI for RM Copilot (thin adapter over the public runtime).

Run: `make ui` (or `streamlit run ui/streamlit_app.py`).

This is not a chatbot skin: it visualizes the agent's **cognition** — the live
Perceive → Plan → Act → Observe → Reflect → Respond loop, the generated execution plan,
a tool-execution timeline with durations, the reflection decision, conversational
memory, and runtime metrics — alongside the grounded answer and explainable prospect
cards. It only renders observable runtime events (trace, plan, memory, metrics) from the
public API; no chain-of-thought, no business logic, no duplicated data.

The LLM provider/model is selectable in the sidebar (Gemini or Anthropic/Claude); the
selection just sets config and the app is rebuilt via the provider-agnostic LLMFactory.
"""

import streamlit as st

from rm_copilot.agent.runtime import RmCopilotApp, build_app
from rm_copilot.config.settings import get_settings
from rm_copilot.observability.render import (
    COGNITIVE_LOOP,
    TOOL_PURPOSE,
    console_metrics,
    loop_stage,
    loop_state,
    step_durations,
    tool_status,
)

st.set_page_config(page_title="RM Copilot — Agent Console", page_icon="🏦", layout="wide")

_DEFAULT_MODEL = {"gemini": get_settings().llm_model, "anthropic": "claude-opus-4-8"}
_KEY_ENV_HINT = {
    "gemini": "RM_COPILOT_LLM_API_KEY or GEMINI_API_KEY",
    "anthropic": "RM_COPILOT_LLM_API_KEY or ANTHROPIC_API_KEY",
}
_LOOP_GLYPH = {
    "perceive": "👁",
    "plan": "🧭",
    "act": "⚙",
    "observe": "🔍",
    "reflect": "↻",
    "respond": "🗣",
}
_LOOP_LABEL = {s: s.capitalize() for s in COGNITIVE_LOOP}


# --- app construction -----------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _build_app(provider: str, model: str, api_key: str) -> RmCopilotApp:
    """Build (and cache) an app per (provider, model, key). Cache miss → rebuild.

    A blank sidebar key must NOT erase the configured key: fall back to the .env
    `RM_COPILOT_LLM_API_KEY` when the selected provider matches the configured one,
    otherwise leave it unset so the provider's own SDK env var (GEMINI_API_KEY /
    ANTHROPIC_API_KEY) is used.
    """
    base = get_settings()
    resolved_key = api_key or (base.llm_api_key if provider == base.llm_provider else None)
    settings = base.model_copy(
        update={"llm_provider": provider, "llm_model": model, "llm_api_key": resolved_key}
    )
    return build_app(settings)


# --- cognitive-loop bar ---------------------------------------------------------------
def _loop_bar_md(state: dict[str, str]) -> str:
    parts: list[str] = []
    for stage in COGNITIVE_LOOP:
        glyph, label, status = _LOOP_GLYPH[stage], _LOOP_LABEL[stage], state[stage]
        if status == "done":
            parts.append(f":green[{glyph} {label} ✓]")
        elif status == "active":
            parts.append(f":blue[**{glyph} {label} ●**]")
        else:
            parts.append(f":gray[{glyph} {label}]")
    return "  →  ".join(parts)


def _live_line(step) -> str:
    """A friendly streaming line for one trace step (live timeline)."""
    if step.stage == "tool":
        glyph, label = tool_status(step.data.get("result", {}))
        return f"🔧 `{step.summary}()` — {glyph} {label}"
    if step.stage == "plan":
        return f"🧭 Planned · intent = `{step.data.get('intent', '?')}`"
    if step.stage == "reflect":
        return f"🤔 Reflection: {step.data.get('note') or step.summary}"
    glyph = _LOOP_GLYPH.get(loop_stage(step.stage), "•")
    return f"{glyph} {step.stage.capitalize()}: {step.summary}"


# --- panels ---------------------------------------------------------------------------
def _plan_panel(plan) -> None:
    st.markdown(f"**Goal / intent:** `{plan.intent.value}`")
    if plan.rationale:
        st.caption(plan.rationale)
    params = {
        "product": plan.product_id,
        "customer": plan.customer_id,
        "city": plan.city,
        "top_n": plan.top_n,
        "generate_messages": plan.generate_messages,
        "messages": plan.message_count if plan.generate_messages else 0,
        "locale": plan.locale,
        "tone": plan.tone,
    }
    st.markdown(" · ".join(f"**{k}:** `{v}`" for k, v in params.items() if v not in (None, "")))
    st.markdown("**Execution plan:**")
    if plan.tool_plan:
        for i, tool in enumerate(plan.tool_plan, 1):
            st.markdown(f"{i}. `{tool}` — {TOOL_PURPOSE.get(tool, 'tool call')}")
    else:
        st.caption("(planner proceeded without enumerating tools)")
    if plan.assumptions:
        st.markdown("**Assumptions:** " + "; ".join(plan.assumptions))
    if plan.clarification_question:
        st.info(f"Clarification: {plan.clarification_question}")


def _timeline_panel(trace, total_ms) -> None:
    durations = step_durations(trace, total_ms)
    for step, dur in zip(trace, durations, strict=False):
        if step.stage == "tool":
            res = step.data.get("result", {})
            glyph, label = tool_status(res)
            obs = ", ".join(f"{k}={v}" for k, v in res.items() if k != "is_error") or "—"
            st.markdown(
                f"🔧 **{step.summary}** · `{dur} ms` · {glyph} {label}  \n"
                f"&nbsp;&nbsp;&nbsp;{TOOL_PURPOSE.get(step.summary, '')}  \n"
                f"&nbsp;&nbsp;&nbsp;↳ {obs}"
            )
        else:
            glyph = _LOOP_GLYPH.get(loop_stage(step.stage), "•")
            st.markdown(f"{glyph} **{step.stage.capitalize()}** — {step.summary} · `{dur} ms`")


def _reflection_panel(result) -> None:
    reflects = [s for s in result.trace if s.stage == "reflect"]
    if result.kind == "clarification":
        st.warning(
            "Needs clarification from the user.\n\n"
            f"{result.plan.clarification_question or 'Request underspecified.'}"
        )
    elif result.kind == "declined":
        st.warning("Request is out of scope — the agent declined rather than guess.")
    elif reflects:
        for s in reflects:
            st.markdown(f"🤔 {s.data.get('note') or s.summary}")
        st.info("Re-planned and retried once (bounded — never overwrites a deterministic score).")
    else:
        st.success(
            "✓ Enough information collected.\n\n✓ No clarification required.\n\n✓ Ready to answer."
        )


def _metrics_row(result, turn_no: int, provider: str, model: str) -> None:
    # A single subtle caption — no large numeric tiles (st.metric is too prominent here).
    m = console_metrics(result, turn_no)
    time_s = f"{m['elapsed_ms']} ms" if m["elapsed_ms"] is not None else "—"
    st.caption(
        f"provider `{provider}` · model `{model}` · {m['tool_calls']} tool calls · "
        f"{m['reflection_cycles']} reflections · {m['cognition_steps']} LLM cognition · {time_s}"
    )


def _why_recommendation(card) -> str:
    bits = [
        f"**{card.first_name}** ranks **{card.rank_score:.0f}** "
        f"(value {card.value_score}/100 · propensity {card.propensity_score}/100 · "
        f"{card.confidence} confidence)."
    ]
    if card.recommended_product_id:
        bits.append(f"Recommended: `{card.recommended_product_id}`.")
    if card.triggers:
        bits.append("Why now: " + ", ".join(card.triggers) + ".")
    return " ".join(bits)


def _prospect(card) -> None:
    city = f" · {card.city}" if card.city else ""
    with st.expander(
        f"{card.first_name} · {card.customer_id}{city} — rank {card.rank_score:.0f} "
        f"(value {card.value_score} / propensity {card.propensity_score}, {card.confidence})"
    ):
        st.markdown(f"**Why this recommendation?** {_why_recommendation(card)}")
        st.markdown(f"**Status:** `{card.message_status}`")
        if card.reason_codes:
            st.markdown("**Reason codes:**")
            for rc in card.reason_codes:
                st.markdown(f"- {rc}")
        if card.message:
            st.markdown("**Drafted outreach:**")
            st.info(card.message)
        elif card.message_status == "NOT_DRAFTED":
            st.caption(
                "Ranked candidate — outreach not drafted (drafting is limited to the top few)."
            )
        elif card.message_status and card.message_status != "READY":
            st.caption(f"No message sent — guardrail outcome: `{card.message_status}`.")


def _explanation_panel(explanation: dict) -> None:
    st.markdown("**Assessment explanation**")
    for key in ("reason_codes", "triggers"):
        items = explanation.get(key)
        if items:
            st.markdown(f"_{key.replace('_', ' ').title()}_:")
            for it in items:
                st.markdown(f"- {it}")
    st.json(explanation, expanded=False)


# --- sidebar --------------------------------------------------------------------------
def _llm_controls() -> tuple[str, str, str]:
    st.header("LLM")
    provider = st.selectbox(
        "Provider", ["gemini", "anthropic"], help="Provider-agnostic via LLMFactory."
    )
    model = st.text_input("Model", value=_DEFAULT_MODEL[provider], key=f"model_{provider}")
    api_key = st.text_input(
        "API key (optional)",
        type="password",
        key=f"key_{provider}",
        help=f"Overrides the env key. If blank, uses {_KEY_ENV_HINT[provider]}.",
    )
    return provider, model.strip(), api_key.strip()


def _memory_panel(memory) -> None:
    st.subheader("🧠 Agent memory")
    st.markdown(f"**Current product:** `{memory.last_product_id or '—'}`")
    selected = memory.last_prospects
    st.markdown(f"**Selected customers:** {len(selected)}")
    if selected:
        st.caption(", ".join(f"{p.first_name} ({p.customer_id})" for p in selected[:5]))
    last_goal = next((t for r, t in reversed(memory.history) if r == "user"), None)
    if last_goal:
        st.markdown(f"**Last goal:** {last_goal}")
    st.markdown(f"**History turns:** {len(memory.history)}")


def _architecture_view() -> None:
    with st.expander("🏗 Runtime architecture (cognition vs execution)"):
        st.markdown(
            "```\n"
            "Conversation Agent  (cognitive loop)\n"
            "        ↓\n"
            "Planner / Reflector / Synthesizer   ← LLM (provider-agnostic)\n"
            "        ↓\n"
            "Tool Registry        (5 typed tools)\n"
            "        ↓\n"
            "Deterministic Services  (scoring · eligibility · rank · compliance · groundedness)\n"
            "        ↓\n"
            "Repositories  →  SQLite (seeded)\n"
            "```\n"
            "The **LLM does cognition** (plan / reflect / synthesize); the **deterministic "
            "layers do execution** (scoring, eligibility, ranking, guardrails). The active "
            "stage is shown live in the loop bar above each answer."
        )


# --- turn rendering -------------------------------------------------------------------
def _render_turn(result, turn_no: int, provider: str, model: str) -> None:
    st.markdown(_loop_bar_md(loop_state(result.trace, final=True)))
    st.markdown(result.reply)
    if result.prospects:
        st.markdown(f"**{len(result.prospects)} prospect(s):**")
        for card in result.prospects:
            _prospect(card)
    elif result.explanation:
        _explanation_panel(result.explanation)
    _metrics_row(result, turn_no, provider, model)
    with st.expander("🔬 Reasoning & tools"):
        tab_plan, tab_tl, tab_ref, tab_trace = st.tabs(
            ["🧭 Plan", "⏱ Timeline", "↻ Reflection", "🧾 Trace"]
        )
        with tab_plan:
            _plan_panel(result.plan)
        with tab_tl:
            _timeline_panel(result.trace, result.metrics.get("elapsed_ms"))
        with tab_ref:
            _reflection_panel(result)
        with tab_trace:
            for step in result.trace:
                detail = f" — `{step.data}`" if step.data else ""
                st.markdown(
                    f"`{step.seq}` **{step.stage}** ({step.at_ms} ms): {step.summary}{detail}"
                )


def main() -> None:
    with st.sidebar:
        provider, model, api_key = _llm_controls()
        st.divider()
        new_chat = st.button("🔄 New conversation")
        st.markdown(
            "Try:\n"
            "- *Find high-value personal-loan prospects this month*\n"
            "- *Why CUST000003?*\n"
            "- *Redo that message in Hindi*"
        )

    app = _build_app(provider, model, api_key)

    st.title("🏦 RM Copilot — Agent Console")
    st.caption(
        f"A single agent running a transparent cognitive loop · provider `{app.provider}` · "
        f"model `{app.model}`"
    )
    _architecture_view()

    if not app.is_seeded:
        st.error("No data found. Run `make seed` first.")
        return

    if "memory" not in st.session_state or new_chat:
        st.session_state.memory = app.new_session()
        st.session_state.turns = []  # list of dicts: {user, result, provider, model}

    with st.sidebar:
        st.divider()
        _memory_panel(st.session_state.memory)

    for i, turn in enumerate(st.session_state.turns, start=1):
        with st.chat_message("user"):
            st.markdown(turn["user"])
        with st.chat_message("assistant"):
            _render_turn(turn["result"], i, turn["provider"], turn["model"])

    prompt = st.chat_input("Ask the assistant…")
    if not prompt:
        return

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        loop_ph = st.empty()
        loop_ph.markdown(_loop_bar_md(dict.fromkeys(COGNITIVE_LOOP, "pending")))
        timeline = st.status("Reasoning…", expanded=True)
        seen: list = []

        def _on_trace(step) -> None:
            seen.append(step)
            loop_ph.markdown(_loop_bar_md(loop_state(seen, final=False)))
            timeline.write(_live_line(step))

        try:
            result = app.ask(prompt, st.session_state.memory, on_trace=_on_trace)
        except Exception as exc:
            timeline.update(label="Error", state="error")
            st.error(
                f"{exc}\n\nIf this is an auth/quota error, check the API key for "
                f"`{provider}` (sidebar) or set {_KEY_ENV_HINT[provider]}."
            )
            return
        timeline.update(label="Done", state="complete")
        loop_ph.markdown(_loop_bar_md(loop_state(result.trace, final=True)))
        _render_turn(result, len(st.session_state.turns) + 1, app.provider, app.model)

    st.session_state.turns.append(
        {"user": prompt, "result": result, "provider": app.provider, "model": app.model}
    )


main()
