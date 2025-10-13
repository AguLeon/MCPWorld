"""
Provider abstractions for the computer-use demo.

This module exposes the provider-agnostic data models and registry helpers
used to integrate multiple LLM backends (Anthropic, OpenAI-compatible, etc.).
"""

from .base import (
    ConversationMessage,
    ConversationTranscript,
    MessageSegment,
    TextSegment,
    ThinkingSegment,
    ToolCallSegment,
    ToolResultSegment,
    ToolSpec,
    ProviderOptions,
    BaseProviderAdapter,
    ProviderRegistry,
)
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter

__all__ = [
    "ConversationMessage",
    "ConversationTranscript",
    "MessageSegment",
    "TextSegment",
    "ThinkingSegment",
    "ToolCallSegment",
    "ToolResultSegment",
    "ToolSpec",
    "ProviderOptions",
    "BaseProviderAdapter",
    "ProviderRegistry",
    "AnthropicAdapter",
    "OpenAIAdapter",
]
