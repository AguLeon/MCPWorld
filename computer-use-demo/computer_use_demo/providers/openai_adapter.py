from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

import httpx

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
class OpenAIProviderRequest:
    url: str
    headers: Dict[str, str]
    payload: Dict[str, Any]
    api_response_callback: Optional[
        Callable[[httpx.Request, httpx.Response | object | None, Exception | None], None]
    ] = None
    timeout: Optional[float] = None


@dataclass(slots=True)
class OpenAIProviderResponse:
    http_response: httpx.Response
    payload: Dict[str, Any]


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter targeting OpenAI-compatible chat completion endpoints."""

    def __init__(self, provider_id: str = "openai"):
        self.provider_id = provider_id

    def prepare_request(
        self,
        transcript: ConversationTranscript,
        tools: List[ToolSpec],
        options: ProviderOptions,
    ) -> ProviderRequest:
        base_url: str = options.extra_options.get(
            "base_url", "https://api.openai.com"
        )
        endpoint: str = options.extra_options.get(
            "endpoint", "/v1/chat/completions"
        )
        url = f"{base_url.rstrip('/')}{endpoint}"

        system_prompts = options.extra_options.get(
            "system_prompts", transcript.system_prompts
        )
        if system_prompts and isinstance(system_prompts, str):
            system_prompts = [system_prompts]

        messages_payload: List[Dict[str, Any]] = []
        if system_prompts:
            for prompt in system_prompts:
                if prompt:
                    messages_payload.append(
                        {"role": "system", "content": prompt}
                    )

        messages_payload.extend(
            _transcript_to_openai_messages(transcript.messages)
        )

        tools_payload = [
            _tool_spec_to_openai(tool_spec) for tool_spec in tools
        ]
        payload: Dict[str, Any] = {
            "model": options.model,
            "messages": messages_payload,
            "temperature": options.temperature,
            "max_tokens": options.max_output_tokens,
        }
        if tools_payload:
            payload["tools"] = tools_payload
            payload["tool_choice"] = options.extra_options.get(
                "tool_choice", "auto"
            )

        response_format = options.extra_options.get("response_format")
        if response_format:
            payload["response_format"] = response_format

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
        }
        api_key = options.extra_options.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        extra_headers: Dict[str, str] = options.extra_options.get(
            "headers", {}
        )
        headers.update(extra_headers or {})

        timeout = options.extra_options.get("timeout")

        return OpenAIProviderRequest(
            url=url,
            headers=headers,
            payload=payload,
            api_response_callback=options.extra_options.get(
                "api_response_callback"
            ),
            timeout=timeout,
        )

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        assert isinstance(request, OpenAIProviderRequest)
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                response = await client.post(
                    request.url,
                    headers=request.headers,
                    json=request.payload,
                )
        except httpx.HTTPError as err:
            callback = request.api_response_callback
            req = getattr(err, "request", None)
            res = getattr(err, "response", None)
            if callback:
                callback(req, res, err)
            raise

        callback = request.api_response_callback
        if callback:
            callback(response.request, response, None)

        response.raise_for_status()
        payload = response.json()
        return OpenAIProviderResponse(http_response=response, payload=payload)

    def parse_response(
        self,
        response: ProviderResponse,
    ) -> ConversationMessage:
        assert isinstance(response, OpenAIProviderResponse)
        choices: List[Dict[str, Any]] = response.payload.get("choices", [])
        if not choices:
            raise ValueError("OpenAI response missing choices")
        message_payload = choices[0].get("message") or {}

        segments: List[Any] = []

        content = message_payload.get("content")
        if isinstance(content, str):
            if content:
                segments.append(TextSegment(text=content))
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        segments.append(TextSegment(text=text))

        tool_calls = message_payload.get("tool_calls", [])
        for call in tool_calls or []:
            function = call.get("function", {})
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {"raw": raw_args}
            segments.append(
                ToolCallSegment(
                    tool_name=function.get("name", ""),
                    arguments=arguments or {},
                    call_id=call.get("id") or str(uuid4()),
                )
            )

        function_call = message_payload.get("function_call")
        if function_call:
            raw_args = function_call.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {"raw": raw_args}
            segments.append(
                ToolCallSegment(
                    tool_name=function_call.get("name", ""),
                    arguments=arguments or {},
                    call_id=str(uuid4()),
                )
            )

        assistant_message = ConversationMessage(role="assistant")
        for segment in segments:
            assistant_message.append(segment)

        assistant_message.metadata["finish_reason"] = choices[0].get(
            "finish_reason"
        )
        assistant_message.metadata["raw_response"] = response.payload
        return assistant_message

    @property
    def supports_thinking(self) -> bool:
        return False


def _transcript_to_openai_messages(
    messages: Iterable[ConversationMessage],
) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for message in messages:
        if message.role == "assistant":
            payload.extend(_assistant_segments_to_messages(message))
        elif message.role == "user":
            payload.extend(_user_segments_to_messages(message))
        elif message.role == "system":
            text = _collect_text_segments(message.segments)
            if text:
                payload.append({"role": "system", "content": text})
        elif message.role == "tool":
            payload.extend(_tool_role_segments(message))
    return payload


def _assistant_segments_to_messages(
    message: ConversationMessage,
) -> List[Dict[str, Any]]:
    text = _collect_text_segments(message.segments)
    tool_calls = [
        _tool_call_to_openai(segment)
        for segment in message.segments
        if isinstance(segment, ToolCallSegment)
    ]
    if not text and not tool_calls:
        return []
    msg: Dict[str, Any] = {"role": "assistant"}
    msg["content"] = text or ""
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return [msg]


def _user_segments_to_messages(
    message: ConversationMessage,
) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    text = _collect_text_segments(message.segments)
    if text:
        payload.append({"role": "user", "content": text})
    for segment in message.segments:
        if isinstance(segment, ToolResultSegment):
            payload.append(_tool_result_to_message(segment))
    return payload


def _tool_role_segments(
    message: ConversationMessage,
) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for segment in message.segments:
        if isinstance(segment, ToolResultSegment):
            payload.append(_tool_result_to_message(segment))
    return payload


def _collect_text_segments(
    segments: Iterable[Any],
) -> str:
    parts: List[str] = []
    for segment in segments:
        if isinstance(segment, TextSegment):
            if segment.text:
                parts.append(segment.text)
        elif isinstance(segment, ThinkingSegment):
            # Skip thinking content for OpenAI providers (not supported)
            continue
    return "\n\n".join(parts).strip()


def _tool_result_to_message(segment: ToolResultSegment) -> Dict[str, Any]:
    call_id = segment.call_id or str(uuid4())
    content_parts: List[str] = []
    if segment.system_note:
        content_parts.append(f"<system>{segment.system_note}</system>")
    if segment.output_text:
        content_parts.append(segment.output_text)
    if segment.images:
        content_parts.append(f"[{len(segment.images)} image(s) omitted]")
    content = "\n".join(content_parts).strip()
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": content or "",
    }


def _tool_call_to_openai(segment: ToolCallSegment) -> Dict[str, Any]:
    arguments = segment.arguments or {}
    try:
        arguments_json = json.dumps(arguments)
    except (TypeError, ValueError):
        arguments_json = json.dumps({"raw": str(arguments)})
    return {
        "id": segment.call_id or str(uuid4()),
        "type": "function",
        "function": {
            "name": segment.tool_name,
            "arguments": arguments_json,
        },
    }


def _tool_spec_to_openai(spec: ToolSpec) -> Dict[str, Any]:
    parameters = spec.input_schema or {"type": "object", "properties": {}}
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description or "",
            "parameters": parameters,
        },
    }

