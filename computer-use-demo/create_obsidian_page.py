from enum import StrEnum
import asyncio
import sys
import os
from typing import cast, Any

from computer_use_demo.providers import (
    ConversationMessage,
    ConversationTranscript,
    MessageSegment,
    TextSegment,
    ThinkingSegment,
    ToolCallSegment,
    ToolResultSegment,
    ToolSpec,
    ProviderOptions,
    ProviderRegistry,
    AnthropicAdapter,
    OpenAIAdapter,
)

from computer_use_demo.loop import _beta_messages_to_transcript, _conversation_message_to_beta, _make_tool_result_segment, _segment_to_beta_block

sys.path.insert(0, '/workspace/computer-use-demo')
from computer_use_demo.mcpclient import MCPClient

class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"
    OPENAI = "openai"


_PROVIDER_REGISTRY = ProviderRegistry()
_PROVIDER_REGISTRY.register(
    APIProvider.OPENAI.value,
    lambda: OpenAIAdapter(APIProvider.OPENAI.value),
)


prompt = """
Create a new paragraph title called 'AI Generated Page'
under active open
Add a paragraph with text: 'Hello from Ollama!'.
"""

async def create_page():
    print("Creating MCP Client...")
    client = MCPClient()
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
        }
    ]

    transcript = _beta_messages_to_transcript(messages)
    try:

        print("Connecting to Notion MCP server...")
        await client.connect_to_server({
            'command': 'uvx',
            'args': ['mcp-obsidian'],
            'env': {
                "OBSIDIAN_API_KEY": "1234",
                "OBSIDIAN_HOST": "http://127.0.0.1",
                "OBSIDIAN_PORT": "27123"
            }
        })
        print("Connected!")
        
        # available tools
        tools = await client.list_tools()
        print("\nAvailable tools:")
        for tool in tools:
            print(f"  - {tool.name} \t {tool.description} {tool.input_schema}")
        return 
        # Connect to LocalLLM
        provider = APIProvider.OPENAI
        adapter = _PROVIDER_REGISTRY.create(provider.value)
        provider_extra_options = {
            "api_key": "1234",
            "base_url": "http://host.docker.internal:11434",
            "system_prompts": [""],
            "endpoint": "/v1/chat/completions",
            "tool_choice": "auto",
        }

        options = ProviderOptions(
            model="qwen3-vl:32b",
            temperature=0.0,
            extra_options=provider_extra_options,
        )

        request = adapter.prepare_request(
            transcript, tools, options
        )

        # Calling LLM
        provider_response = await adapter.invoke(request)
        assistant_message = adapter.parse_response(provider_response)

        assistant_beta = _conversation_message_to_beta(assistant_message)
        print(assistant_beta)

        # Create a new page with Lorem Ipsum
        print("\nCreating new page with Lorem Ipsum...")
        for segment in assistant_message.segments:
            beta_block = _segment_to_beta_block(segment)

            if isinstance(segment, ToolCallSegment):
                tool_name = segment.tool_name
                tool_input = cast(dict[str, Any], segment.arguments)
                result: Optional[ToolResult] = None

                print("*" * 100)
                print(tool_name)
                print("*" * 100)
                print(tool_input)
                result = await client.call_tool(
                    name=tool_name,
                    tool_input=tool_input,
                )
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(create_page())
