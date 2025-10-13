"""Collection classes for managing multiple tools."""

from typing import Any

from anthropic.types.beta import BetaToolUnionParam

from computer_use_demo.providers import ToolSpec

from .base import (
    BaseAnthropicTool,
    ToolError,
    ToolFailure,
    ToolResult,
)


class ToolCollection:
    """A collection of anthropic-defined tools."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = tools
        self.tool_map = {tool.to_params()["name"]: tool for tool in tools}

    def to_params(
        self,
    ) -> list[BetaToolUnionParam]:
        return [tool.to_params() for tool in self.tools]

    def to_specs(self) -> list[ToolSpec]:
        """Return provider-agnostic tool specifications."""
        specs: list[ToolSpec] = []
        for tool in self.tools:
            params = tool.to_params()
            name = params["name"]
            if name == "computer":
                tool_type = "computer_use"
            elif name == "bash":
                tool_type = "bash"
            elif name == "str_replace_editor":
                tool_type = "edit"
            else:
                tool_type = "generic"

            specs.append(
                ToolSpec(
                    name=name,
                    description=params.get("description", ""),
                    input_schema=params.get("input_schema", {}),
                    tool_type=tool_type,
                    metadata={"anthropic_params": params},
                )
            )
        return specs

    async def run(self, *, name: str, tool_input: dict[str, Any]) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            return await tool(**tool_input)
        except ToolError as e:
            return ToolFailure(error=e.message)
