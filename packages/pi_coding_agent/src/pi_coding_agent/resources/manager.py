"""Resource manager for skills, prompts, and extensions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pi_coding_agent.resources.extensions import (
    ExtensionRuntime,
    discover_extension_paths,
    load_extensions,
)
from pi_coding_agent.resources.prompt_templates import (
    PromptTemplate,
    expand_prompt_template,
    load_prompt_templates,
)
from pi_coding_agent.resources.skills import Skill, load_skills


@dataclass(frozen=True)
class CommandInfo:
    name: str
    source: str
    description: str | None
    path: str


@dataclass
class ResourceManager:
    """Runtime resource inventory and expansion helpers."""

    prompt_templates: list[PromptTemplate]
    skills: list[Skill]
    extension_runtime: ExtensionRuntime
    enable_skill_commands: bool = True

    def expand_text(self, text: str) -> str:
        """Expand ``/skill:name`` and ``/template`` input text."""

        expanded = text
        if self.enable_skill_commands:
            expanded = self._expand_skill_command(expanded)
        expanded = expand_prompt_template(expanded, self.prompt_templates)
        return expanded

    def _expand_skill_command(self, text: str) -> str:
        if not text.startswith("/skill:"):
            return text
        command = text[7:]
        if not command:
            return text
        parts = command.split(maxsplit=1)
        skill_name = parts[0].strip()
        args = parts[1].strip() if len(parts) > 1 else ""
        skill = next((item for item in self.skills if item.name == skill_name), None)
        if skill is None:
            return text
        try:
            payload = Path(skill.file_path).read_text(encoding="utf-8")
        except OSError:
            return text
        if args:
            payload = f"{payload}\n\nUser: {args}"
        return payload

    def list_commands(self) -> list[CommandInfo]:
        commands: list[CommandInfo] = []
        for command in self.extension_runtime.list_command_entries():
            commands.append(
                CommandInfo(
                    name=command.invocation_name,
                    source="extension",
                    description=command.description,
                    path=command.extension_path,
                )
            )
        for template in self.prompt_templates:
            commands.append(
                CommandInfo(
                    name=template.name,
                    source="prompt",
                    description=template.description,
                    path=template.file_path,
                )
            )
        if self.enable_skill_commands:
            for skill in self.skills:
                commands.append(
                    CommandInfo(
                        name=f"skill:{skill.name}",
                        source="skill",
                        description=skill.description,
                        path=skill.file_path,
                    )
                )
        return commands

    async def try_run_extension_command(self, text: str, session: object) -> bool:
        if not text.startswith("/"):
            return False
        command = text[1:]
        if not command:
            return False
        parts = command.split(maxsplit=1)
        name = parts[0].strip()
        args = parts[1] if len(parts) > 1 else ""
        return await self.extension_runtime.run_command(name, args, session)


def create_resource_manager(
    *,
    cwd: Path,
    agent_dir: Path,
    skill_paths: list[str],
    prompt_paths: list[str],
    extension_paths: list[str],
    no_skills: bool,
    no_prompt_templates: bool,
    no_extensions: bool,
    enable_skill_commands: bool,
) -> ResourceManager:
    """Build all runtime resources with pi-style precedence."""

    skills = (
        []
        if no_skills
        else load_skills(
            cwd=cwd,
            agent_dir=agent_dir,
            skill_paths=skill_paths,
            include_defaults=True,
        )
    )
    prompts = (
        []
        if no_prompt_templates
        else load_prompt_templates(
            cwd=cwd,
            agent_dir=agent_dir,
            prompt_paths=prompt_paths,
            include_defaults=True,
        )
    )
    extension_runtime = ExtensionRuntime(
        cwd=cwd,
        load_result=load_extensions(
            cwd,
            [] if no_extensions else discover_extension_paths(cwd, agent_dir, extension_paths),
        ),
    )
    return ResourceManager(
        prompt_templates=prompts,
        skills=skills,
        extension_runtime=extension_runtime,
        enable_skill_commands=enable_skill_commands,
    )
