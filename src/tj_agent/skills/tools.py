from __future__ import annotations

from loguru import logger

from ..tools.registry import tj_tool
from ..models import AgentState
from .loader import GlobalSkillLoader


@tj_tool(
    name="load_skill_instructions",
    description="Load the full instructions for a specific skill. Use this when a task matches a skill's description."
)
async def load_skill_instructions(skill_name: str) -> str:
    """
    Activate a skill and load its full instructions.
    
    This is the Progressive Disclosure mechanism:
    1. On startup, only skill names/descriptions are injected into system prompt
    2. When the agent determines a task matches a skill, it calls this tool
    3. Full SKILL.md content is returned for the agent to follow
    
    Args:
        skill_name: Name of the skill to activate
    
    Returns:
        Full skill instructions (SKILL.md content) or error message
    """
    logger.info(f"Loading skill instructions: {skill_name}")
    
    loader = GlobalSkillLoader.get_instance()
    
    skill = loader.get_skill(skill_name)
    if not skill:
        available = loader.list_skill_names()
        available_str = ", ".join(available) if available else "none"
        return f"[ERROR] Skill not found: {skill_name}. Available skills: {available_str}"
    
    state = get_agent_state()
    if state is None:
        logger.warning("No agent state set for skill loader")
        return skill.full_content
    
    full_content = loader.activate_skill(skill_name, state)
    
    if full_content:
        return full_content
    
    return f"[ERROR] Failed to activate skill: {skill_name}"


_current_agent_state: AgentState | None = None


def set_agent_state(state: AgentState) -> None:
    """Set the current agent state for skill activation."""
    global _current_agent_state
    _current_agent_state = state


def get_agent_state() -> AgentState | None:
    """Get the current agent state for skill activation."""
    return _current_agent_state
