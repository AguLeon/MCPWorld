import json
from dataclasses import dataclass

import httpx
from anthropic.types.beta import (
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolUnionParam,
    BetaUsage,
)

# from ..system_prompt import SYSTEM_PROMPT


@dataclass
class LocalLLMClient:
    """
    Adapter for local LLMs with OpenAI-compatible APIs.
    Works with Ollama, LM Studio, vLLM, llama.cpp, etc.
    """

    base_url: str = "http://localhost:11434"
    api_key: str = "dummy"
    model: str = "tinyllama"
    client: httpx.Client = httpx.Client(timeout=300.0)

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")

    def _convert_messages_to_openai(
        self, messages: list[BetaMessageParam], system_prompt: str
    ) -> list[dict]:
        """Convert Anthropic message format to OpenAI format."""
        openai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                openai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Handle complex content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            # Convert tool results to text
                            tool_content = block.get("content", "")
                            if isinstance(tool_content, list):
                                for item in tool_content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type") == "text"
                                    ):
                                        text_parts.append(
                                            f"Tool result: {item.get('text', '')}"
                                        )
                            else:
                                text_parts.append(f"Tool result: {tool_content}")
                        elif block.get("type") == "tool_use":
                            # Convert tool use to text description
                            text_parts.append(
                                f"Using tool: {block.get('name')} with input: {json.dumps(block.get('input', {}))}"
                            )

                if text_parts:
                    openai_messages.append(
                        {"role": role, "content": "\n".join(text_parts)}
                    )

        return openai_messages

    def _convert_tools_to_openai(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI function format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
            )
        return openai_tools

    # def beta_messages_create(
    #     self,
    #     max_tokens: int,
    #     messages: list[BetaMessageParam],
    #     model: str,
    #     system: list,
    #     tools: list[dict],
    #     **kwargs,
    # ):
    #     """
    #     Mimics Anthropic's beta.messages.create API but calls local LLM.
    #     """
    #     # Extract system prompt
    #     system_prompt = (
    #         system[0]["text"]
    #         if system and isinstance(system[0], dict)
    #         else SYSTEM_PROMPT
    #     )
    #
    #     # Convert messages and tools
    #     openai_messages = self._convert_messages_to_openai(messages, system_prompt)
    #     openai_tools = self._convert_tools_to_openai(tools) if tools else None
    #
    #     # Build request payload
    #     payload = {
    #         "model": self.model,
    #         "messages": openai_messages,
    #         "max_tokens": max_tokens,
    #         "temperature": 0.0,
    #     }
    #
    #     if openai_tools:
    #         payload["tools"] = openai_tools
    #         payload["tool_choice"] = "auto"
    #
    #     # Make API call
    #     try:
    #         response = self.client.post(
    #             f"{self.base_url}/chat/completions",
    #             json=payload,
    #             headers={
    #                 "Authorization": f"Bearer {self.api_key}",
    #                 "Content-Type": "application/json",
    #             },
    #         )
    #         response.raise_for_status()
    #         result = response.json()
    #     except httpx.HTTPError as e:
    #         raise e
    #
    #     # Convert response to Anthropic format
    #     return self._convert_response_to_anthropic(result)

    def _convert_response_to_anthropic(self, openai_response: dict):
        """Convert OpenAI response format to Anthropic format."""
        choice = openai_response["choices"][0]
        message = choice["message"]

        content_blocks = []

        # Handle text content
        if message.get("content"):
            content_blocks.append({"type": "text", "text": message["content"]})

        # Handle tool calls
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "input": json.loads(tool_call["function"]["arguments"]),
                    }
                )

        # Create mock response object
        class MockResponse:
            def __init__(self, content, stop_reason):
                self.content = content
                self.stop_reason = stop_reason
                self.id = openai_response.get("id", "local-llm")
                self.model = openai_response.get("model", "local")
                self.role = "assistant"
                self.type = "message"
                self.usage = openai_response.get("usage", {})

        class MockContentBlock:
            def __init__(self, block_dict):
                self.type = block_dict["type"]
                if self.type == "text":
                    self.text = block_dict["text"]
                elif self.type == "tool_use":
                    self.id = block_dict["id"]
                    self.name = block_dict["name"]
                    self.input = block_dict["input"]

            def model_dump(self):
                if self.type == "text":
                    return {"type": "text", "text": self.text}
                elif self.type == "tool_use":
                    return {
                        "type": "tool_use",
                        "id": self.id,
                        "name": self.name,
                        "input": self.input,
                    }

        mock_content = [MockContentBlock(block) for block in content_blocks]
        stop_reason = choice.get("finish_reason", "end_turn")
        if stop_reason == "tool_calls":
            stop_reason = "tool_use"

        return MockResponse(mock_content, stop_reason)

    def _convert_messages_to_ollama(
        self,
        messages: list[BetaMessageParam],
    ) -> list[dict]:
        """Convert Anthropic message format to Ollama format."""
        ollama_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                ollama_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Combine text and image content
                text_parts = []
                images = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image":
                            # Extract base64 image data
                            source = block.get("source", {})
                            if source.get("type") == "base64":  # pyright: ignore
                                images.append(source.get("data", ""))  # pyright: ignore
                        elif block.get("type") == "tool_result":
                            # Handle tool results
                            tool_content = block.get("content", [])
                            if isinstance(tool_content, str):
                                text_parts.append(f"Tool result: {tool_content}")
                            elif isinstance(tool_content, list):
                                for item in tool_content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type") == "text"
                                    ):
                                        text_parts.append(
                                            f"Tool result: {item.get('text', '')}"
                                        )

                combined_text = "\n".join(text_parts)
                msg_dict = {"role": role, "content": combined_text}
                if images:
                    msg_dict["images"] = images  # pyright: ignore
                ollama_messages.append(msg_dict)

        return ollama_messages

    def _convert_tools_to_ollama(
        self, tools: list[dict] | list[BetaToolUnionParam]
    ) -> list[dict]:
        """Convert Anthorpic tool format to Ollama Format"""
        ollama_tools = []
        for tool in tools:
            ollama_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            ollama_tools.append(ollama_tool)

        return ollama_tools

    def beta_messages_create(
        self,
        messages: list[BetaMessageParam],
        system_prompt: str | BetaTextBlockParam,
        tools: list[dict] | list[BetaToolUnionParam],
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict:
        """Create message using Ollama API"""
        ollama_messages = self._convert_messages_to_ollama(messages)

        # Add system prompt
        if system_prompt:
            ollama_messages.insert(0, {"role": "system", "content": system_prompt})

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Add tools if provided (note: tool support varies by model)
        # Tool Support varies by model
        if tools:
            payload["tools"] = self._convert_tools_to_ollama(tools)

        # Request to Ollama
        response = self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )

        response.raise_for_status()

        return response.json()

    def _parse_ollama_response(self, response: dict) -> BetaMessage:
        """Ollama Response to Anthorpic BetaMessage format"""
        message = response.get("message", {})
        content_text = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        content_blocks = []

        # Text Content
        if content_text:
            content_blocks.append(BetaTextBlock(type="text", text=content_text))

        # Tool Calls
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tool_call.get("id", f"tool_{len(content_blocks)}"),
                    "name": function.get("name", ""),
                    "input": function.get("arguments", {}),
                }
            )

        mock_output = BetaMessage(
            id=response.get("created_at", ""),
            type="message",
            role="assistant",
            content=content_blocks,
            model=response.get("model", self.model),
            stop_reason="end_turn" if not tool_calls else "tool_use",
            usage=BetaUsage(
                input_tokens=response.get("prompt_eval_count", 0),
                output_tokens=response.get("eval_count", 0),
            ),
        )

        return mock_output

    def close(self):
        """Close HTTPX client"""
        self.client.close()
