"""Tool base contract + structured error result.

Every tool validates its arguments against a Pydantic input model and returns a
JSON-serializable dict. Failures (bad args, unknown entity) are returned as a
structured ``is_error`` result so the orchestrator can self-correct — tools do not
raise across the agent boundary (CLAUDE.md).
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ValidationError


class ToolError(BaseModel):
    """Structured, correctable error returned to the orchestrator."""

    is_error: bool = True
    error: str
    detail: str | None = None


def _format_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}" for err in exc.errors()
    )


class Tool(ABC):
    """A typed, schema-validated unit of work the agent can invoke."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]

    @abstractmethod
    def execute(self, args: BaseModel) -> BaseModel:
        """Run the tool on validated arguments. May raise LookupError for unknown entities."""

    def invoke(self, raw_args: dict) -> dict:
        """Validate raw arguments, execute, and return a JSON-serializable result/error."""
        try:
            parsed = self.input_model.model_validate(raw_args)
        except ValidationError as exc:
            return ToolError(
                error="invalid_arguments", detail=_format_validation_error(exc)
            ).model_dump()
        try:
            result = self.execute(parsed)
        except LookupError as exc:
            return ToolError(error="not_found", detail=str(exc)).model_dump()
        return result.model_dump(mode="json")
