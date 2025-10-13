from unittest import mock

import pytest

from anthropic.types.beta import BetaMessageParam, BetaTextBlockParam

from computer_use_demo.loop import APIProvider, sampling_loop
from computer_use_demo.providers import (
    ConversationMessage,
    TextSegment,
    ToolCallSegment,
    ToolSpec,
)
from computer_use_demo.tools import ToolResult


class StubToolCollection:
    def __init__(self):
        self.tool_map = {"computer": mock.AsyncMock(return_value=None)}

    def to_specs(self):
        return [
            ToolSpec(
                name="computer",
                description="Computer tool",
                input_schema={},
                tool_type="computer_use",
                metadata={"anthropic_params": {"name": "computer"}},
            )
        ]

    async def run(self, *, name, tool_input):
        return ToolResult(output="Tool output")


class StubMCPClient:
    def __init__(self):
        self.list_tools = mock.AsyncMock(return_value=[])
        self.connect_to_server = mock.AsyncMock()
        self.cleanup = mock.AsyncMock()


@pytest.mark.asyncio
async def test_sampling_loop_with_adapter(monkeypatch):
    adapter = mock.Mock()
    adapter.prepare_request.return_value = "request"
    adapter.invoke = mock.AsyncMock(return_value="response")
    adapter.parse_response.return_value = ConversationMessage(
        role="assistant",
        segments=[
            ToolCallSegment(
                tool_name="computer", arguments={"action": "test"}, call_id="1"
            ),
            TextSegment(text="Done!"),
        ],
    )

    monkeypatch.setattr(
        "computer_use_demo.loop._PROVIDER_REGISTRY.create",
        mock.Mock(return_value=adapter),
    )
    monkeypatch.setattr("computer_use_demo.loop.ToolCollection", lambda *args: StubToolCollection())
    monkeypatch.setattr("computer_use_demo.loop.MCPClient", lambda: StubMCPClient())

    messages: list[BetaMessageParam] = [{"role": "user", "content": "Test message"}]
    output_callback = mock.Mock()
    tool_output_callback = mock.Mock()
    api_response_callback = mock.Mock()

    evaluator = mock.Mock()
    evaluator.config = {"mcp_servers": [], "exec_mode": "mixed"}

    result = await sampling_loop(
        model="test-model",
        provider=APIProvider.ANTHROPIC,
        system_prompt_suffix="",
        messages=messages,
        output_callback=output_callback,
        tool_output_callback=tool_output_callback,
        api_response_callback=api_response_callback,
        api_key="test-key",
        tool_version="computer_use_20250124",
        evaluator=evaluator,
        evaluator_task_id="task-1",
        is_timeout=lambda: False,
    )

    assert len(result) == 3
    assert result[0] == {"role": "user", "content": "Test message"}
    assert result[1]["role"] == "assistant"
    assert result[2]["role"] == "user"

    adapter.prepare_request.assert_called_once()
    adapter.invoke.assert_awaited()
    adapter.parse_response.assert_called_once_with("response")
    tool_output_callback.assert_called_once()
    output_callback.assert_any_call(
        BetaTextBlockParam(type="text", text="Done!")
    )
