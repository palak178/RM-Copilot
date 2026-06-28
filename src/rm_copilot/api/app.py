"""FastAPI application — endpoints over RmCopilotApp, with SSE trace streaming.

Endpoints: GET /health, GET /api/v1/products, POST /api/v1/query (synchronous),
GET /api/v1/stream (Server-Sent Events: live trace frames + final result). OpenAPI at
/docs. Sessions are an in-memory dict (a store can back this in production).
"""

import json
import queue
import threading
import uuid
from collections.abc import Callable, Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from rm_copilot.agent.runtime import RmCopilotApp, build_app
from rm_copilot.agent.trace import TraceStep
from rm_copilot.api.schemas import HealthResponse, ProductsResponse, QueryRequest, QueryResponse


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def create_app(
    rm_app: RmCopilotApp | None = None,
    app_builder: Callable[[], RmCopilotApp] = build_app,
) -> FastAPI:
    """Build the FastAPI app. Pass `rm_app` to inject a backend (e.g. mock-backed) for tests."""
    api = FastAPI(title="RM Copilot API", version="0.0.0")
    state: dict = {"app": rm_app, "sessions": {}}

    def get_app() -> RmCopilotApp:
        if state["app"] is None:
            state["app"] = app_builder()
        return state["app"]

    def get_memory(session_id: str):
        sessions = state["sessions"]
        if session_id not in sessions:
            sessions[session_id] = get_app().new_session()
        return sessions[session_id]

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        app = get_app()
        return HealthResponse(
            status="ok", provider=app.provider, model=app.model, seeded=app.is_seeded
        )

    @api.get("/api/v1/products", response_model=ProductsResponse)
    def products() -> ProductsResponse:
        app = get_app()
        return ProductsResponse(products=[p.product_id for p in app.db.products.list_active()])

    @api.post("/api/v1/query", response_model=QueryResponse)
    def query(req: QueryRequest) -> QueryResponse:
        app = get_app()
        session_id = req.session_id or uuid.uuid4().hex
        result = app.ask(req.message, get_memory(session_id))
        return QueryResponse(session_id=session_id, result=result)

    @api.get("/api/v1/stream")
    def stream(message: str, session_id: str | None = None) -> StreamingResponse:
        app = get_app()
        sid = session_id or uuid.uuid4().hex
        memory = get_memory(sid)
        return StreamingResponse(
            _run_stream(app, message, memory, sid), media_type="text/event-stream"
        )

    return api


def _run_stream(app: RmCopilotApp, message: str, memory, session_id: str) -> Iterator[str]:
    """Run a turn in a worker thread; stream trace frames live, then the final result."""
    events: queue.Queue = queue.Queue()
    box: dict = {}

    def worker() -> None:
        try:
            box["result"] = app.ask(message, memory, on_trace=lambda s: events.put(("trace", s)))
        except Exception as exc:
            box["error"] = str(exc)
        finally:
            events.put(("end", None))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    yield _sse("session", json.dumps({"session_id": session_id}))
    while True:
        kind, payload = events.get()
        if kind == "trace":
            step: TraceStep = payload
            yield _sse("trace", step.model_dump_json())
        else:
            break
    thread.join()

    if "result" in box:
        yield _sse("result", box["result"].model_dump_json())
    else:
        yield _sse("error", json.dumps({"error": box.get("error", "unknown")}))
    yield _sse("end", "")
