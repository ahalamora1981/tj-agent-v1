from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional
import yaml
from loguru import logger

from ..models import Skill, SkillManifest


FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL
)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter from SKILL.md content.
    
    Args:
        content: Full SKILL.md file content
    
    Returns:
        Tuple of (frontmatter dict, remaining markdown content)
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        logger.warning("No YAML frontmatter found in SKILL.md")
        return {}, content
    
    frontmatter_yaml = match.group(1)
    markdown_content = content[match.end():]
    
    try:
        frontmatter = yaml.safe_load(frontmatter_yaml) or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML frontmatter: {e}")
        return {}, content
    
    return frontmatter, markdown_content


def parse_skill_manifest(frontmatter: dict[str, Any]) -> SkillManifest:
    """
    Create SkillManifest from parsed YAML frontmatter.
    
    Args:
        frontmatter: Parsed YAML dictionary
    
    Returns:
        SkillManifest object
    """
    return SkillManifest(
        name=frontmatter.get("name", "unknown"),
        description=frontmatter.get("description", ""),
        version=frontmatter.get("version"),
        author=frontmatter.get("author"),
        tags=frontmatter.get("tags", []),
        triggers=frontmatter.get("triggers", [])
    )


def load_skill_from_path(skill_path: Path) -> Optional[Skill]:
    """
    Load a complete skill from a directory containing SKILL.md.
    
    Args:
        skill_path: Path to the skill directory
    
    Returns:
        Skill object or None if loading failed
    """
    skill_file = skill_path / "SKILL.md"
    
    if not skill_file.exists():
        logger.error(f"SKILL.md not found in {skill_path}")
        return None
    
    try:
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, full_content = parse_frontmatter(content)
        manifest = parse_skill_manifest(frontmatter)
        
        scripts_path = None
        assets_path = None
        
        scripts_dir = skill_path / "scripts"
        if scripts_dir.exists() and scripts_dir.is_dir():
            scripts_path = str(scripts_dir)
        
        assets_dir = skill_path / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            assets_path = str(assets_dir)
        
        return Skill(
            manifest=manifest,
            full_content=full_content,
            skill_path=str(skill_path),
            scripts_path=scripts_path,
            assets_path=assets_path
        )
        
    except Exception as e:
        logger.exception(f"Failed to load skill from {skill_path}")
        return None


def get_discovery_prompt(skills: list[Skill]) -> str:
    """
    Generate a discovery prompt for skills.
    
    Args:
        skills: List of discovered skills
    
    Returns:
        Formatted string for system prompt injection
    """
    if not skills:
        return ""
    
    lines = ["<skills>"]
    for skill in skills:
        lines.append(f"  <skill>")
        lines.append(f"    <name>{skill.manifest.name}</name>")
        lines.append(f"    <description>{skill.manifest.description}</description>")
        lines.append(f"  </skill>")
    lines.append("</skills>")
    
    return "\n".join(lines)
