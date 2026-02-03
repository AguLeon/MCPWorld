from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional, Protocol


ConversationRole = Literal["system", "user", "assistant", "tool"]
SegmentType = Literal["text", "thinking", "tool_call", "tool_result"]


@dataclass(slots=True)
class MessageSegment:
    """Base segment type used in conversation messages."""

    type: SegmentType


@dataclass(slots=True)
class TextSegment(MessageSegment):
    text: str
    annotations: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        text: str,
        *,
        annotations: Optional[Dict[str, Any]] = None,
    ) -> None:
        MessageSegment.__init__(self, type="text")
        self.text = text
        self.annotations = annotations


@dataclass(slots=True)
class ThinkingSegment(MessageSegment):
    content: str
    signature: Optional[str] = None

    def __init__(
        self,
        content: str,
        *,
        signature: Optional[str] = None,
    ) -> None:
        MessageSegment.__init__(self, type="thinking")
        self.content = content
        self.signature = signature


@dataclass(slots=True)
class ToolCallSegment(MessageSegment):
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        MessageSegment.__init__(self, type="tool_call")
        self.tool_name = tool_name
        self.arguments = arguments
        self.call_id = call_id
        self.metadata = metadata or {}


@dataclass(slots=True)
class ToolResultSegment(MessageSegment):
    call_id: str
    output_text: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    system_note: Optional[str] = None

    def __init__(
        self,
        *,
        call_id: str,
        output_text: Optional[str] = None,
        images: Optional[Iterable[Dict[str, Any]]] = None,
        is_error: bool = False,
        system_note: Optional[str] = None,
    ) -> None:
        MessageSegment.__init__(self, type="tool_result")
        self.call_id = call_id
        self.output_text = output_text
        self.images = list(images) if images else []
        self.is_error = is_error
        self.system_note = system_note


@dataclass(slots=True)
class ConversationMessage:
    role: ConversationRole
    segments: List[MessageSegment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def append(self, segment: MessageSegment) -> None:
        self.segments.append(segment)


@dataclass(slots=True)
class ConversationTranscript:
    """Wrapper that contains all messages exchanged so far."""

    messages: List[ConversationMessage] = field(default_factory=list)
    system_prompts: List[str] = field(default_factory=list)

    def add_message(self, message: ConversationMessage) -> None:
        self.messages.append(message)


ToolType = Literal["computer_use", "bash", "edit", "generic"]


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    tool_type: ToolType = "generic"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderOptions:
    model: str
    temperature: float = 0.0
    max_output_tokens: int = 4096
    thinking_budget: Optional[int] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


ProviderRequest = Any
ProviderResponse = Any


class BaseProviderAdapter(ABC):
    """Interface for provider-specific request/response handling."""

    provider_id: str

    @abstractmethod
    def prepare_request(
        self,
        transcript: ConversationTranscript,
        tools: List[ToolSpec],
        options: ProviderOptions,
    ) -> ProviderRequest:
        ...

    @abstractmethod
    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        ...

    @abstractmethod
    def parse_response(
        self,
        response: ProviderResponse,
    ) -> ConversationMessage:
        ...

    @property
    def supports_thinking(self) -> bool:
        return False

    @property
    def supports_image_outputs(self) -> bool:
        return True


class ProviderFactory(Protocol):
    def __call__(self) -> BaseProviderAdapter:
        ...


class ProviderRegistry:
    """Runtime registry mapping provider identifiers to adapter factories."""

    def __init__(self) -> None:
        self._registry: Dict[str, ProviderFactory] = {}

    def register(self, provider_id: str, factory: ProviderFactory) -> None:
        if provider_id in self._registry:
            raise ValueError(f"Provider '{provider_id}' already registered")
        self._registry[provider_id] = factory

    def create(self, provider_id: str) -> BaseProviderAdapter:
        try:
            factory = self._registry[provider_id]
        except KeyError as exc:
            raise KeyError(f"Provider '{provider_id}' not registered") from exc
        adapter = factory()
        if adapter.provider_id != provider_id:
            raise ValueError(
                f"Adapter for '{provider_id}' reported provider_id '{adapter.provider_id}'"
            )
        return adapter

    def available_providers(self) -> List[str]:
        return list(self._registry.keys())
