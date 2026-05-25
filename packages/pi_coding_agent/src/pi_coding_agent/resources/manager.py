"""Resource manager for skills, prompts, and extensions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pi_coding_agent.resources.diagnostics import ResourceDiagnostic
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
from pi_coding_agent.resources.source_info import SourceInfo


@dataclass(frozen=True)
class CommandInfo:
    name: str
    source: str
    description: str | None
    path: str
    source_info: SourceInfo | None = None


@dataclass
class ResourceManager:
    """Runtime resource inventory and expansion helpers."""

    prompt_templates: list[PromptTemplate]
    skills: list[Skill]
    extension_runtime: ExtensionRuntime
    diagnostics: list[ResourceDiagnostic]
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
                    source_info=command.source_info,
                )
            )
        for template in self.prompt_templates:
            commands.append(
                CommandInfo(
                    name=template.name,
                    source="prompt",
                    description=template.description,
                    path=template.file_path,
                    source_info=template.source_info,
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
                        source_info=skill.source_info,
                    )
                )
        return commands

    def get_diagnostics(self) -> list[dict[str, object]]:
        return [item.to_dict() for item in self.diagnostics]

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


async def create_resource_manager(
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
    reason: str = "startup",
) -> ResourceManager:
    """Build all runtime resources with pi-style precedence."""

    extension_paths_resolved = (
        []
        if no_extensions
        else discover_extension_paths(cwd, agent_dir, extension_paths)
    )
    extension_load = load_extensions(
        cwd,
        extension_paths_resolved,
        agent_dir=agent_dir,
    )
    extension_runtime = ExtensionRuntime(
        cwd=cwd,
        load_result=extension_load,
    )
    await extension_runtime.emit_session_start(reason=reason)
    discovered = await extension_runtime.emit_resources_discover(reason=reason)
    merged_skill_paths = [
        *skill_paths,
        *discovered.get("skillPaths", []),
    ]
    merged_prompt_paths = [
        *prompt_paths,
        *discovered.get("promptPaths", []),
    ]
    skills_result = (
        None
        if no_skills
        else load_skills(
            cwd=cwd,
            agent_dir=agent_dir,
            skill_paths=merged_skill_paths,
            include_defaults=True,
        )
    )
    prompts_result = (
        None
        if no_prompt_templates
        else load_prompt_templates(
            cwd=cwd,
            agent_dir=agent_dir,
            prompt_paths=merged_prompt_paths,
            include_defaults=True,
        )
    )
    diagnostics: list[ResourceDiagnostic] = []
    if skills_result is not None:
        diagnostics.extend(skills_result.diagnostics)
    if prompts_result is not None:
        diagnostics.extend(prompts_result.diagnostics)
    for error in extension_load.errors:
        diagnostics.append(
            ResourceDiagnostic(
                type="error",
                message=error,
                path="<extension>",
            ),
        )
    return ResourceManager(
        prompt_templates=[] if prompts_result is None else prompts_result.prompts,
        skills=[] if skills_result is None else skills_result.skills,
        extension_runtime=extension_runtime,
        diagnostics=diagnostics,
        enable_skill_commands=enable_skill_commands,
    )
