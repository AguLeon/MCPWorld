from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import httpx
from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    DefaultHttpxClient,
)
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from .base import (
    BaseProviderAdapter,
    ConversationMessage,
    ConversationTranscript,
    ProviderOptions,
    ProviderRequest,
    ProviderResponse,
    TextSegment,
    ThinkingSegment,
    ToolCallSegment,
    ToolResultSegment,
    ToolSpec,
)


@dataclass(slots=True)
class AnthropicProviderRequest:
    client: Any
    request_kwargs: Dict[str, Any]
    api_response_callback: Optional[
        Callable[[httpx.Request, httpx.Response | object | None, Exception | None], None]
    ] = None


@dataclass(slots=True)
class AnthropicProviderResponse:
    raw_response: Any
    beta_messages: BetaMessage


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter that delegates to the Anthropic Python SDK."""

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def prepare_request(
        self,
        transcript: ConversationTranscript,
        tools: List[ToolSpec],
        options: ProviderOptions,
    ) -> ProviderRequest:
        messages = options.extra_options.get("beta_messages")
        if messages is None:
            messages = _transcript_to_beta_messages(transcript)

        system_blocks: List[BetaTextBlockParam] = options.extra_options.get("anthropic_system", [])
        tool_params = [
            spec.metadata.get("anthropic_params")
            for spec in tools
            if spec.metadata.get("anthropic_params")
        ]

        request_kwargs: Dict[str, Any] = dict(
            model=options.model,
            messages=messages,
            system=system_blocks,
            tools=tool_params,
            betas=options.extra_options.get("anthropic_betas", []),
            extra_body=options.extra_options.get("extra_body", {}),
            temperature=options.temperature,
            max_tokens=options.max_output_tokens,
        )

        client = self._create_client(options)

        return AnthropicProviderRequest(
            client=client,
            request_kwargs=request_kwargs,
            api_response_callback=options.extra_options.get("api_response_callback"),
        )

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        assert isinstance(request, AnthropicProviderRequest)
        callback = request.api_response_callback
        try:
            raw_response = request.client.beta.messages.with_raw_response.create(
                **request.request_kwargs
            )
        except (APIStatusError, APIResponseValidationError) as err:
            if callback:
                callback(err.request, err.response, err)
            raise
        except APIError as err:
            if callback:
                callback(err.request, err.body, err)
            raise

        if callback:
            callback(
                raw_response.http_response.request,
                raw_response.http_response,
                None,
            )

        parsed = raw_response.parse()
        return AnthropicProviderResponse(raw_response=raw_response, beta_messages=parsed)

    def parse_response(
        self,
        response: ProviderResponse,
    ) -> ConversationMessage:
        assert isinstance(response, AnthropicProviderResponse)
        content_blocks = _response_to_params(response.beta_messages)
        message = ConversationMessage(role="assistant")
        for block in content_blocks:
            segment = _content_block_to_segment(block)
            if segment:
                message.append(segment)
        message.metadata["beta_content_blocks"] = content_blocks

        # Extract usage data from the response
        if hasattr(response.beta_messages, 'usage'):
            usage = response.beta_messages.usage
            message.metadata["usage"] = {
                "input_tokens": getattr(usage, 'input_tokens', 0),
                "output_tokens": getattr(usage, 'output_tokens', 0),
            }

        return message

    def _create_client(self, options: ProviderOptions) -> Any:
        api_key = options.extra_options.get("api_key")
        if self.provider_id == "anthropic":
            return Anthropic(api_key=api_key, max_retries=4, http_client=DefaultHttpxClient())
        if self.provider_id == "bedrock":
            return AnthropicBedrock()
        if self.provider_id == "vertex":
            return AnthropicVertex()
        raise ValueError(f"Unsupported Anthropic provider '{self.provider_id}'")


def _transcript_to_beta_messages(transcript: ConversationTranscript) -> List[BetaMessageParam]:
    messages: List[BetaMessageParam] = []
    for message in transcript.messages:
        content = []
        for segment in message.segments:
            block = _segment_to_beta_content(segment)
            if block is not None:
                content.append(block)
        messages.append({"role": message.role, "content": content})
    return messages


def _segment_to_beta_content(segment) -> Dict[str, Any] | None:
    if isinstance(segment, TextSegment):
        return {"type": "text", "text": segment.text}
    if isinstance(segment, ThinkingSegment):
        block: Dict[str, Any] = {"type": "thinking", "thinking": segment.content}
        if segment.signature:
            block["signature"] = segment.signature
        return block
    if isinstance(segment, ToolCallSegment):
        return {
            "type": "tool_use",
            "name": segment.tool_name,
            "input": segment.arguments,
            "id": segment.call_id,
        }
    if isinstance(segment, ToolResultSegment):
        content: List[Dict[str, Any]] | str = []
        if segment.output_text:
            content.append({"type": "text", "text": segment.output_text})
        for image in segment.images:
            content.append({"type": "image", "source": image})
        if not content:
            content = ""
        return {
            "type": "tool_result",
            "tool_use_id": segment.call_id,
            "content": content,
            "is_error": segment.is_error,
        }
    return None


def _content_block_to_segment(block: Dict[str, Any]):
    block_type = block.get("type")
    if block_type == "text":
        return TextSegment(text=block.get("text", ""))
    if block_type == "thinking":
        return ThinkingSegment(
            content=block.get("thinking", ""),
            signature=block.get("signature"),
        )
    if block_type == "tool_use":
        return ToolCallSegment(
            tool_name=block.get("name", ""),
            arguments=block.get("input", {}) or {},
            call_id=block.get("id", ""),
        )
    if block_type == "tool_result":
        content = block.get("content", [])
        text_parts: List[str] = []
        images: List[Dict[str, Any]] = []
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    images.append(item.get("source", {}))
        return ToolResultSegment(
            call_id=block.get("tool_use_id", ""),
            output_text="\n".join(text_parts) if text_parts else None,
            images=images,
            is_error=block.get("is_error", False),
        )
    return None


def _response_to_params(
    response: BetaMessage,
) -> List[BetaContentBlockParam]:
    res: list[BetaContentBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            if block.text:
                res.append(BetaTextBlockParam(type="text", text=block.text))
            elif getattr(block, "type", None) == "thinking":
                thinking_block = {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", None),
                }
                if hasattr(block, "signature"):
                    thinking_block["signature"] = getattr(block, "signature", None)
                res.append(thinking_block)  # type: ignore[arg-type]
        else:
            res.append(block.model_dump())  # type: ignore[attr-defined]
    return res
