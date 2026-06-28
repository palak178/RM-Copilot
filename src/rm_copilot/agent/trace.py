"""Reasoning trace — the inspectable record of the cognitive loop.

Each cognitive step and each tool call appends a `TraceStep`. An optional `on_step`
callback lets a UI stream the trace live (the demo centerpiece). No raw chain-of-thought
— only stage, a short summary, structured data, and a wall-clock offset so the UI can
show per-step durations (an execution timeline). `at_ms` is the elapsed time since the
turn started; the gap to the previous step is how long that step's work took.
"""

import time
from collections.abc import Callable

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    seq: int
    stage: str  # perceive | plan | act | observe | reflect | respond | tool
    summary: str
    data: dict = Field(default_factory=dict)
    at_ms: int = 0  # ms since the turn started (observability; default 0 keeps it optional)


class Tracer:
    """Accumulates ordered trace steps for one turn; optionally streams them live."""

    def __init__(self, on_step: Callable[[TraceStep], None] | None = None) -> None:
        self._steps: list[TraceStep] = []
        self._on_step = on_step
        self._t0 = time.perf_counter()

    def add(self, stage: str, summary: str, **data: object) -> None:
        at_ms = round((time.perf_counter() - self._t0) * 1000)
        step = TraceStep(
            seq=len(self._steps) + 1, stage=stage, summary=summary, data=dict(data), at_ms=at_ms
        )
        self._steps.append(step)
        if self._on_step is not None:
            self._on_step(step)

    @property
    def steps(self) -> list[TraceStep]:
        return list(self._steps)
