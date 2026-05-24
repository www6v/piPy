"""Resource loading utilities for prompts, skills, and extensions."""

from pi_coding_agent.resources.manager import (
    CommandInfo,
    ResourceManager,
    create_resource_manager,
)
from pi_coding_agent.resources.prompt_templates import (
    PromptTemplate,
    expand_prompt_template,
    parse_command_args,
    substitute_args,
)
from pi_coding_agent.resources.skills import Skill, format_skills_for_prompt

__all__ = [
    "CommandInfo",
    "PromptTemplate",
    "ResourceManager",
    "Skill",
    "create_resource_manager",
    "expand_prompt_template",
    "format_skills_for_prompt",
    "parse_command_args",
    "substitute_args",
]
