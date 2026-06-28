"""HTTP API surface — a thin FastAPI + SSE adapter over the agent's public API.

Production-shaped (validated request/response, OpenAPI at /docs, SSE streaming of the
cognitive-loop trace) and UI-agnostic: it wraps `RmCopilotApp` and changes nothing in
the agent or below. Optional dependency group: `pip install '.[api]'`.
"""
