from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
import yaml
from loguru import logger


class AgentTemplate:
    """Agent template loaded from YAML file."""
    
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        system_prompt: str,
        tools: list[str],
        skills: list[str]
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools
        self.skills = skills
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "skills": self.skills,
        }


class AgentLoader:
    """Loads and manages Agent templates from YAML files."""
    
    def __init__(self, agents_dir: Optional[str] = None) -> None:
        self._agents_dir = Path(agents_dir) if agents_dir else Path("agents")
        self._agents: dict[str, AgentTemplate] = {}
        self._loaded = False
    
    @property
    def agents(self) -> dict[str, AgentTemplate]:
        return self._agents
    
    @property
    def is_loaded(self) -> bool:
        return self._loaded
    
    def load(self, agents_dir: Optional[str] = None) -> int:
        """
        Load all agent templates from YAML files.
        
        Args:
            agents_dir: Override the agents directory path
        
        Returns:
            Number of agents loaded
        """
        if agents_dir:
            self._agents_dir = Path(agents_dir)
        
        if not self._agents_dir.exists():
            logger.warning(f"Agents directory not found: {self._agents_dir}")
            return 0
        
        logger.info(f"Loading agents from: {self._agents_dir}")
        
        loaded_count = 0
        
        for yaml_file in self._agents_dir.glob("*.yaml"):
            agent = self._load_agent(yaml_file)
            if agent:
                self._agents[agent.id] = agent
                loaded_count += 1
                logger.debug(f"Loaded agent: {agent.id}")
        
        for yaml_file in self._agents_dir.glob("*.yml"):
            agent = self._load_agent(yaml_file)
            if agent:
                self._agents[agent.id] = agent
                loaded_count += 1
                logger.debug(f"Loaded agent: {agent.id}")
        
        self._loaded = True
        logger.info(f"Loaded {loaded_count} agents")
        
        return loaded_count
    
    def _load_agent(self, yaml_path: Path) -> Optional[AgentTemplate]:
        """Load a single agent from YAML file."""
        try:
            content = yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            
            if not data:
                logger.warning(f"Empty YAML file: {yaml_path}")
                return None
            
            required_fields = ["id", "name"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field '{field}' in {yaml_path}")
                    return None
            
            return AgentTemplate(
                id=data["id"],
                name=data.get("name", data["id"]),
                description=data.get("description", ""),
                system_prompt=data.get("system_prompt", ""),
                tools=data.get("tools", []),
                skills=data.get("skills", [])
            )
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML {yaml_path}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Failed to load agent from {yaml_path}")
            return None
    
    def get_agent(self, agent_id: str) -> Optional[AgentTemplate]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> list[dict[str, str]]:
        """List all available agents (summary)."""
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
            }
            for agent in self._agents.values()
        ]
    
    def reload(self) -> int:
        """Reload all agents."""
        self._agents.clear()
        self._loaded = False
        return self.load()


class GlobalAgentLoader:
    """Singleton agent loader."""
    
    _instance: Optional[AgentLoader] = None
    
    @classmethod
    def get_instance(cls, agents_dir: Optional[str] = None) -> AgentLoader:
        if cls._instance is None:
            cls._instance = AgentLoader(agents_dir)
        return cls._instance
    
    @classmethod
    def load(cls, agents_dir: Optional[str] = None) -> int:
        """Convenience method to load agents."""
        loader = cls.get_instance(agents_dir)
        return loader.load()
    
    @classmethod
    def get_agent(cls, agent_id: str) -> Optional[AgentTemplate]:
        """Convenience method to get an agent."""
        loader = cls.get_instance()
        return loader.get_agent(agent_id)
    
    @classmethod
    def list_agents(cls) -> list[dict[str, str]]:
        """Convenience method to list agents."""
        loader = cls.get_instance()
        return loader.list_agents()
