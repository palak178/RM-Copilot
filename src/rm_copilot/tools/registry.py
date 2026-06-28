"""Tool registry — the agent's action space.

Holds the tool instances, exposes JSON schemas (Anthropic tool definitions for the
M4 orchestrator), and dispatches a validated invocation. Adding a tool = register
one instance here; the orchestrator does not change.
"""

from datetime import date

from rm_copilot.config.scoring import ScoringConfig
from rm_copilot.data.database import Database
from rm_copilot.services.assessment import AssessmentService
from rm_copilot.tools.base import Tool, ToolError
from rm_copilot.tools.customer_360 import GetCustomer360Tool
from rm_copilot.tools.explain_assessment import ExplainAssessmentTool
from rm_copilot.tools.find_prospects import FindAndRankProspectsTool
from rm_copilot.tools.generate_outreach import GenerateOutreachMessageTool, MessageDrafter
from rm_copilot.tools.log_outreach import LogOutreachTool


class ToolRegistry:
    """A name -> Tool registry with schema export and validated dispatch."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict]:
        """Anthropic-style tool definitions (name, description, input JSON schema)."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_model.model_json_schema(),
            }
            for tool in self._tools.values()
        ]

    def invoke(self, name: str, raw_args: dict) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return ToolError(error="unknown_tool", detail=name).model_dump()
        return tool.invoke(raw_args)


def build_registry(
    db: Database, config: ScoringConfig, drafter: MessageDrafter, as_of: date | None = None
) -> ToolRegistry:
    """Wire the five tools over a database, scoring config, and message drafter."""
    service = AssessmentService(db, config, as_of)
    registry = ToolRegistry()
    registry.register(FindAndRankProspectsTool(db, service))
    registry.register(GetCustomer360Tool(db))
    registry.register(ExplainAssessmentTool(service))
    registry.register(GenerateOutreachMessageTool(db, service, drafter, config))
    registry.register(LogOutreachTool(db))
    return registry
