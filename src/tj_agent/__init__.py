"""
TJ Agent - ReAct-based autonomous AI agent system.

Core data structures and models for the agent system.
"""

from .models import (
    Message,
    ToolCall, 
    ToolResult,
    AgentState,
    AgentConfig,
    SkillManifest,
    Skill,
    ToolDefinition,
    ToolRegistry,
    TOOL_REGISTRY,
)
from .app import app
from .main import main

__all__ = [
    "Message",
    "ToolCall", 
    "ToolResult",
    "AgentState",
    "AgentConfig",
    "SkillManifest",
    "Skill",
    "ToolDefinition",
    "ToolRegistry",
    "TOOL_REGISTRY",
    "app",
    "main",
]
