import json

import httpx
import pytest

from computer_use_demo.providers import (
    ConversationMessage,
    ConversationTranscript,
    TextSegment,
    ToolCallSegment,
    ToolSpec,
    ProviderOptions,
)
from computer_use_demo.providers.openai_adapter import (
    OpenAIAdapter,
    OpenAIProviderRequest,
    OpenAIProviderResponse,
)


def _build_transcript() -> ConversationTranscript:
    transcript = ConversationTranscript(system_prompts=["System prompt"])
    user_message = ConversationMessage(role="user")
    user_message.append(TextSegment(text="Hello"))
    transcript.add_message(user_message)
    return transcript


def _tool_spec() -> ToolSpec:
    return ToolSpec(
        name="example_tool",
        description="Example tool",
        input_schema={"type": "object", "properties": {}},
        tool_type="generic",
    )


def test_prepare_request():
    adapter = OpenAIAdapter()
    transcript = _build_transcript()
    options = ProviderOptions(
        model="gpt-4o",
        temperature=0.2,
        max_output_tokens=512,
        extra_options={
            "api_key": "test-key",
            "base_url": "https://example.com",
            "endpoint": "/v1/chat/completions",
            "system_prompts": ["Injected system"],
            "tool_choice": "auto",
            "timeout": 15.0,
        },
    )

    request = adapter.prepare_request(
        transcript=transcript,
        tools=[_tool_spec()],
        options=options,
    )

    assert isinstance(request, OpenAIProviderRequest)
    assert request.url == "https://example.com/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.payload["model"] == "gpt-4o"
    assert request.payload["temperature"] == 0.2
    assert request.payload["max_tokens"] == 512
    assert request.payload["tool_choice"] == "auto"

    messages = request.payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "Injected system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello"

    assert request.payload["tools"][0]["function"]["name"] == "example_tool"


@pytest.mark.asyncio
async def test_invoke_and_parse_response(monkeypatch):
    adapter = OpenAIAdapter()
    transcript = _build_transcript()
    options = ProviderOptions(
        model="gpt-4o",
        extra_options={
            "api_key": "test-key",
        },
    )
    request = adapter.prepare_request(transcript, [_tool_spec()], options)

    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hi there!",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "example_tool", "arguments": json.dumps({"arg": 1})},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    response = httpx.Response(200, json=payload)
    provider_response = OpenAIProviderResponse(http_response=response, payload=payload)
    message = adapter.parse_response(provider_response)

    assert message.role == "assistant"
    assert isinstance(message.segments[0], ToolCallSegment)
    assert message.segments[0].tool_name == "example_tool"
    assert message.segments[0].arguments == {"arg": 1}
    assert isinstance(message.segments[1], TextSegment)
    assert message.segments[1].text == "Hi there!"
    assert message.metadata["finish_reason"] == "tool_calls"
