"""
Agentic sampling loop that calls the Anthropic API and local implementation of anthropic-defined computer use tools.
"""

import platform
import os
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, cast, Optional, Dict
import time
import json

import httpx
from anthropic import APIError, APIResponseValidationError, APIStatusError
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

from .providers import (
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
from .tools import (
    TOOL_GROUPS_BY_VERSION,
    ToolCollection,
    ToolResult,
    ToolVersion,
)

from .mcpclient import MCPClient

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

try:
    from evaluator.core.base_evaluator import BaseEvaluator
    from evaluator.core.events import AgentEvent
except ImportError:
    BaseEvaluator = None
    AgentEvent = None


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"
    OPENAI = "openai"


_PROVIDER_REGISTRY = ProviderRegistry()
_PROVIDER_REGISTRY.register(
    APIProvider.ANTHROPIC.value,
    lambda: AnthropicAdapter(APIProvider.ANTHROPIC.value),
)
_PROVIDER_REGISTRY.register(
    APIProvider.BEDROCK.value,
    lambda: AnthropicAdapter(APIProvider.BEDROCK.value),
)
_PROVIDER_REGISTRY.register(
    APIProvider.VERTEX.value,
    lambda: AnthropicAdapter(APIProvider.VERTEX.value),
)
_PROVIDER_REGISTRY.register(
    APIProvider.OPENAI.value,
    lambda: OpenAIAdapter(APIProvider.OPENAI.value),
)


# This system prompt is optimized for the Docker environment in this repository and
# specific tool combinations enabled.
# We encourage modifying this system prompt to ensure the model has context for the
# environment it is running in, and to provide any additional information that may be
# helpful for the task at hand.
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* To open firefox, please just click on the firefox icon.  Note, firefox-esr is what is installed on your system.
* Using bash tool you can start GUI applications, but you need to set export DISPLAY={os.getenv("DISPLAY")} and use a subshell. For example "(DISPLAY={os.getenv("DISPLAY")} xterm &)". GUI apps run with bash tool will appear within your desktop environment, but they may take some time to appear. Take a screenshot to confirm it did.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* When using Firefox, if a startup wizard appears, IGNORE IT.  Do not even click "skip this step".  Instead, click on the address bar where it says "Search or enter address", and enter the appropriate search term or URL there.
* If the item you are looking at is a pdf, if after taking a single screenshot of the pdf it seems that you want to read the entire document instead of trying to continue to read the pdf from your screenshots + navigation, determine the URL, use curl to download the pdf, install and use pdftotext to convert it to a text file, and then read that text file directly with your StrReplaceEditTool.
</IMPORTANT>"""

SYSTEM_PROMPT_API_ONLY = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* If the item you are looking at is a pdf, if after taking a single screenshot of the pdf it seems that you want to read the entire document instead of trying to continue to read the pdf from your screenshots + navigation, determine the URL, use curl to download the pdf, install and use pdftotext to convert it to a text file, and then read that text file directly with your StrReplaceEditTool.
</IMPORTANT>"""

SYSTEM_PROMPT_NO_BASH = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* To open firefox, please just click on the firefox icon.  Note, firefox-esr is what is installed on your system.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* When using Firefox, if a startup wizard appears, IGNORE IT.  Do not even click "skip this step".  Instead, click on the address bar where it says "Search or enter address", and enter the appropriate search term or URL there.
</IMPORTANT>"""

SYSTEM_PROMPT_NO_BASH_API_ONLY = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>
"""


# --- Evaluator Helper Functions ---
def _record_tool_call_start(
    evaluator: Optional[BaseEvaluator],
    task_id: Optional[str],
    tool_name: str,
    tool_input: Dict[str, Any]
):
    start_time = time.time()
    """Records the TOOL_CALL_START event if evaluator is enabled."""
    if evaluator and task_id and AgentEvent:
        try:
            evaluator.record_event(
                AgentEvent.TOOL_CALL_START,
                {
                    "timestamp": start_time,
                    "tool_name": tool_name,
                    "args": tool_input,
                }
            )
        except Exception as rec_e:
            print(f"[Evaluator Error] Failed to record TOOL_CALL_START: {rec_e}")

def _record_tool_call_end(
    evaluator: Optional[BaseEvaluator],
    task_id: Optional[str],
    tool_name: str,
    tool_result: ToolResult,
):
    end_time = time.time()
    """Records the TOOL_CALL_END event if evaluator is enabled."""
    if evaluator and task_id and AgentEvent:
        try:
            tool_success = not tool_result.error
            tool_error = tool_result.error

            event_data = {
                "timestamp": end_time,
                "tool_name": tool_name,
                "success": tool_success,
                "error": tool_error,
                "result": None,
            }

            if tool_success:
                if tool_result.output:
                    output_str = str(tool_result.output)
                    if len(output_str) > 1000:
                        event_data["result"] = output_str[:500] + "... (truncated)"
                    else:
                        event_data["result"] = output_str
                elif tool_result.base64_image:
                    event_data["result"] = "[Screenshot Taken]"
            else:
                event_data["result"] = tool_result.error

            evaluator.record_event(
                AgentEvent.TOOL_CALL_END,
                event_data
            )
        except Exception as rec_e:
            print(f"[Evaluator Error] Failed to record TOOL_CALL_END: {rec_e}")
# --- End Evaluator Helper Functions ---


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[
        [httpx.Request, httpx.Response | object | None, Exception | None], None
    ],
    api_key: str,
    evaluator: Optional[BaseEvaluator] = None,
    evaluator_task_id: Optional[str] = None,
    is_timeout: Callable[[], bool],
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    tool_version: ToolVersion,
    thinking_budget: int | None = None,
    token_efficient_tools_beta: bool = False,
):
    """
    Agentic sampling loop for the assistant/tool interaction of computer use.
    """
    mcp_servers = evaluator.config.get("mcp_servers", [])
    mcp_client = MCPClient()
    try:
        tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
        exec_mode = evaluator.config.get("exec_mode", "mixed")
        if exec_mode == "api":
            for tool in list(tool_group.tools):
                if "computer" in tool.name:
                    tool_group.tools.remove(tool)
        tool_collection = ToolCollection(*(ToolCls() for ToolCls in tool_group.tools))
        tool_specs: list[ToolSpec] = tool_collection.to_specs()
        if exec_mode in ["mixed", "api"]:
            for server in mcp_servers:
                await mcp_client.connect_to_server(server)
            tool_specs.extend(await mcp_client.list_tools())

        if tool_version == "computer_only":
            base_system_prompt = (
                SYSTEM_PROMPT_NO_BASH_API_ONLY
                if exec_mode == "api"
                else SYSTEM_PROMPT_NO_BASH
            )
        else:
            base_system_prompt = (
                SYSTEM_PROMPT_API_ONLY if exec_mode == "api" else SYSTEM_PROMPT
            )
        system_prompt_text = (
            f"{base_system_prompt} {system_prompt_suffix}"
            if system_prompt_suffix
            else base_system_prompt
        )
        system_block = BetaTextBlockParam(type="text", text=system_prompt_text)

        adapter = _PROVIDER_REGISTRY.create(provider.value)

        while not is_timeout():
            enable_prompt_caching = provider == APIProvider.ANTHROPIC
            betas = [tool_group.beta_flag] if tool_group.beta_flag else []
            if token_efficient_tools_beta:
                betas.append("token-efficient-tools-2025-02-19")

            image_truncation_threshold = only_n_most_recent_images or 0

            if enable_prompt_caching:
                betas.append(PROMPT_CACHING_BETA_FLAG)
                _inject_prompt_caching(messages)
                only_n_most_recent_images = 0
                system_block["cache_control"] = {"type": "ephemeral"}  # type: ignore[index]

            if only_n_most_recent_images:
                _maybe_filter_to_n_most_recent_images(
                    messages,
                    only_n_most_recent_images,
                    min_removal_threshold=image_truncation_threshold,
                )

            extra_body: Dict[str, Any] = {}
            if thinking_budget:
                extra_body = {
                    "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
                }

            transcript = _beta_messages_to_transcript(messages)

            provider_extra_options: Dict[str, Any] = {
                "api_response_callback": api_response_callback,
            }

            if provider in {
                APIProvider.ANTHROPIC,
                APIProvider.BEDROCK,
                APIProvider.VERTEX,
            }:
                provider_extra_options.update(
                    {
                        "api_key": api_key,
                        "anthropic_betas": betas,
                        "anthropic_system": [system_block],
                        "beta_messages": messages,
                        "extra_body": extra_body,
                    }
                )
            elif provider == APIProvider.OPENAI:
                openai_api_key = api_key or os.getenv("OPENAI_API_KEY", "")
                base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
                endpoint = os.getenv("OPENAI_ENDPOINT", "/v1/chat/completions")
                tool_choice = os.getenv("OPENAI_TOOL_CHOICE", "auto")
                timeout_env = os.getenv("OPENAI_TIMEOUT")
                response_format = os.getenv("OPENAI_RESPONSE_FORMAT")

                provider_extra_options.update(
                    {
                        "api_key": openai_api_key,
                        "base_url": base_url,
                        "endpoint": endpoint,
                        "system_prompts": [system_prompt_text],
                        "tool_choice": tool_choice,
                    }
                )
                if response_format:
                    provider_extra_options["response_format"] = response_format
                if timeout_env:
                    try:
                        provider_extra_options["timeout"] = float(timeout_env)
                    except ValueError:
                        pass

            options = ProviderOptions(
                model=model,
                temperature=0.0,
                max_output_tokens=max_tokens,
                thinking_budget=thinking_budget,
                extra_options=provider_extra_options,
            )

            request = adapter.prepare_request(transcript, tool_specs, options)
            try:
                provider_response = await adapter.invoke(request)
            except (
                APIStatusError,
                APIResponseValidationError,
                APIError,
                httpx.HTTPError,
                ValueError,
            ):
                return messages

            assistant_message = adapter.parse_response(provider_response)
            assistant_beta = _conversation_message_to_beta(assistant_message)
            messages.append(assistant_beta)

            tool_result_segments: list[ToolResultSegment] = []
            for segment in assistant_message.segments:
                beta_block = _segment_to_beta_block(segment)
                if beta_block is not None:
                    output_callback(beta_block)

                if isinstance(segment, ToolCallSegment):
                    tool_name = segment.tool_name
                    tool_input = cast(dict[str, Any], segment.arguments)
                    result: Optional[ToolResult] = None

                    _record_tool_call_start(
                        evaluator, evaluator_task_id, tool_name, tool_input
                    )

                    if tool_name in tool_collection.tool_map.keys():
                        result = await tool_collection.run(
                            name=tool_name,
                            tool_input=tool_input,
                        )
                    else:
                        result = await mcp_client.call_tool(
                            name=tool_name,
                            tool_input=tool_input,
                        )
                    _record_tool_call_end(
                        evaluator, evaluator_task_id, tool_name, result
                    )

                    tool_result_segment = _make_tool_result_segment(
                        result, segment.call_id
                    )
                    tool_result_segments.append(tool_result_segment)
                    tool_output_callback(result, segment.call_id)

            if not tool_result_segments:
                return messages

            tool_result_blocks: list[BetaToolResultBlockParam] = [
                _tool_result_segment_to_beta(segment)
                for segment in tool_result_segments
            ]
            messages.append({"role": "user", "content": tool_result_blocks})
    finally:
        with open("sample_message_stream.json", "w+") as f:
            json.dump(messages, f)
        await mcp_client.cleanup()


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int,
):
    """
    With the assumption that images are screenshots that are of diminishing value as
    the conversation progresses, remove all but the final `images_to_keep` tool_result
    images in place, with a chunk of min_removal_threshold to reduce the amount we
    break the implicit prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[BetaToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    # for better cache behavior, we want to remove in chunks
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _inject_prompt_caching(
    messages: list[BetaMessageParam],
):
    """
    Set cache breakpoints for the 3 most recent turns
    one cache breakpoint is left for tools/system prompt, to be shared across sessions
    """

    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(
            content := message["content"], list
        ):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                # Use type ignore to bypass TypedDict check until SDK types are updated
                content[-1]["cache_control"] = BetaCacheControlEphemeralParam(  # type: ignore
                    {"type": "ephemeral"}
                )
            else:
                content[-1].pop("cache_control", None)
                # we'll only every have one extra turn per loop
                break


def _make_tool_result_segment(
    result: ToolResult, tool_use_id: str
) -> ToolResultSegment:
    """Convert an agent ToolResult to a provider-agnostic ToolResultSegment."""
    images: list[dict[str, Any]] = []
    if result.base64_image:
        images.append(
            {
                "type": "base64",
                "media_type": "image/png",
                "data": result.base64_image,
            }
        )

    if result.error:
        output_text = _maybe_prepend_system_tool_result(result, result.error)
        is_error = True
    else:
        output_text = (
            _maybe_prepend_system_tool_result(result, result.output)
            if result.output
            else None
        )
        is_error = False

    return ToolResultSegment(
        call_id=tool_use_id,
        output_text=output_text,
        images=images,
        is_error=is_error,
        system_note=result.system,
    )


def _tool_result_segment_to_beta(
    segment: ToolResultSegment,
) -> BetaToolResultBlockParam:
    content: list[dict[str, Any]] | str = []
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


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text


def _segment_to_beta_block(segment: MessageSegment) -> dict[str, Any] | None:
    if isinstance(segment, TextSegment):
        return {"type": "text", "text": segment.text}
    if isinstance(segment, ThinkingSegment):
        block: dict[str, Any] = {"type": "thinking", "thinking": segment.content}
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
        return _tool_result_segment_to_beta(segment)
    return None


def _conversation_message_to_beta(
    message: ConversationMessage,
) -> BetaMessageParam:
    content: list[dict[str, Any]] = []
    for segment in message.segments:
        block = _segment_to_beta_block(segment)
        if block is not None:
            content.append(block)
    return {"role": message.role, "content": content}


def _beta_messages_to_transcript(
    messages: list[BetaMessageParam],
) -> ConversationTranscript:
    transcript = ConversationTranscript()
    for message in messages:
        conv_message = ConversationMessage(role=message["role"])
        content = message.get("content", [])
        for item in content:
            block_type = item.get("type")
            if block_type == "text":
                conv_message.append(TextSegment(text=item.get("text", "")))
            elif block_type == "thinking":
                conv_message.append(
                    ThinkingSegment(
                        content=item.get("thinking", ""),
                        signature=item.get("signature"),
                    )
                )
            elif block_type == "tool_use":
                conv_message.append(
                    ToolCallSegment(
                        tool_name=item.get("name", ""),
                        arguments=item.get("input", {}) or {},
                        call_id=item.get("id", ""),
                    )
                )
            elif block_type == "tool_result":
                content_field = item.get("content", [])
                text_parts: list[str] = []
                images: list[dict[str, Any]] = []
                if isinstance(content_field, str):
                    text_parts.append(content_field)
                elif isinstance(content_field, list):
                    for entry in content_field:
                        entry_type = entry.get("type")
                        if entry_type == "text":
                            text_parts.append(entry.get("text", ""))
                        elif entry_type == "image":
                            images.append(entry.get("source", {}))
                conv_message.append(
                    ToolResultSegment(
                        call_id=item.get("tool_use_id", ""),
                        output_text="\n".join(text_parts) if text_parts else None,
                        images=images,
                        is_error=item.get("is_error", False),
                    )
                )
        transcript.add_message(conv_message)
    return transcript
