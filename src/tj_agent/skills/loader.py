from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from ..models import Skill, AgentState
from .parser import load_skill_from_path, get_discovery_prompt


class SkillLoader:
    """
    Manages skill discovery and activation.
    Implements the Progressive Disclosure mechanism:
    1. Discovery: On startup, parse all SKILL.md YAML frontmatter
    2. Activation: load_skill_instructions loads full content
    """
    
    def __init__(self, skills_dir: Optional[str] = None) -> None:
        self._skills_dir: Optional[Path] = Path(skills_dir) if skills_dir else None
        self._skills: dict[str, Skill] = {}
        self._discovered = False
    
    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills
    
    @property
    def is_discovered(self) -> bool:
        return self._discovered
    
    async def discover(self, skills_dir: Optional[str] = None) -> int:
        """
        Discover all skills in the given directory.
        Parses YAML frontmatter only (for token efficiency).
        
        Args:
            skills_dir: Path to skills directory (optional, uses cached if not provided)
        
        Returns:
            Number of skills discovered
        """
        if skills_dir:
            self._skills_dir = Path(skills_dir)
        
        if not self._skills_dir or not self._skills_dir.exists():
            logger.warning(f"Skills directory not found: {self._skills_dir}")
            return 0
        
        logger.info(f"Discovering skills in: {self._skills_dir}")
        
        discovered_count = 0
        
        for item in self._skills_dir.iterdir():
            if not item.is_dir():
                continue
            
            skill = load_skill_from_path(item)
            if skill:
                self._skills[skill.manifest.name] = skill
                discovered_count += 1
                logger.debug(f"Discovered skill: {skill.manifest.name}")
        
        self._discovered = True
        logger.info(f"Discovered {discovered_count} skills")
        
        return discovered_count
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def get_discovery_prompt(self) -> str:
        """Get the prompt fragment for skill discovery (injects into system prompt)."""
        return get_discovery_prompt(list(self._skills.values()))
    
    def activate_skill(self, name: str, state: AgentState) -> Optional[str]:
        """
        Activate a skill by loading its full instructions.
        
        Args:
            name: Skill name to activate
            state: Current agent state
        
        Returns:
            Full skill content if successful, None otherwise
        """
        skill = self._skills.get(name)
        if not skill:
            logger.warning(f"Skill not found: {name}")
            return None
        
        if name not in state.active_skills:
            state.add_skill(name)
            logger.info(f"Activated skill: {name}")
        
        return skill.full_content
    
    def list_skill_names(self) -> list[str]:
        """List all available skill names."""
        return list(self._skills.keys())


class GlobalSkillLoader:
    """Singleton skill loader instance."""
    
    _instance: Optional[SkillLoader] = None
    
    @classmethod
    def get_instance(cls) -> SkillLoader:
        if cls._instance is None:
            cls._instance = SkillLoader()
        return cls._instance
    
    @classmethod
    async def discover(cls, skills_dir: str) -> int:
        """Convenience method to discover skills."""
        loader = cls.get_instance()
        return await loader.discover(skills_dir)
    
    @classmethod
    def activate(cls, name: str, state: AgentState) -> Optional[str]:
        """Convenience method to activate a skill."""
        loader = cls.get_instance()
        return loader.activate_skill(name, state)
