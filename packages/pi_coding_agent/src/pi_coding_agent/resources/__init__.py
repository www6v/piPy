"""Resource loading utilities for prompts, skills, and extensions."""

from pi_coding_agent.resources.manager import (
    CommandInfo,
    ResourceManager,
    create_resource_manager,
)
from pi_coding_agent.resources.prompt_templates import (
    LoadPromptTemplatesResult,
    PromptTemplate,
    expand_prompt_template,
    parse_command_args,
    substitute_args,
)
from pi_coding_agent.resources.skills import LoadSkillsResult, Skill, format_skills_for_prompt
from pi_coding_agent.resources.source_info import SourceInfo

__all__ = [
    "CommandInfo",
    "LoadPromptTemplatesResult",
    "LoadSkillsResult",
    "PromptTemplate",
    "ResourceManager",
    "Skill",
    "SourceInfo",
    "create_resource_manager",
    "expand_prompt_template",
    "format_skills_for_prompt",
    "parse_command_args",
    "substitute_args",
]
