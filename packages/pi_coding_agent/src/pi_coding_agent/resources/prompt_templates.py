"""Prompt template loading and expansion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pi_ai.config_paths import CONFIG_DIR_NAME

from pi_coding_agent.resources.diagnostics import ResourceDiagnostic
from pi_coding_agent.resources.frontmatter import parse_frontmatter
from pi_coding_agent.resources.source_info import SourceInfo, classify_source_info


@dataclass(frozen=True)
class PromptTemplate:
    """Prompt template resource."""

    name: str
    description: str
    content: str
    file_path: str
    argument_hint: str | None = None
    source_info: SourceInfo | None = None


@dataclass(frozen=True)
class LoadPromptTemplatesResult:
    prompts: list[PromptTemplate]
    diagnostics: list[ResourceDiagnostic]


def parse_command_args(args_string: str) -> list[str]:
    """Split command arguments with basic quote handling."""

    args: list[str] = []
    current = ""
    quote: str | None = None
    for char in args_string:
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current += char
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char.isspace():
            if current:
                args.append(current)
                current = ""
            continue
        current += char
    if current:
        args.append(current)
    return args


def substitute_args(content: str, args: list[str]) -> str:
    """Substitute pi-style prompt template placeholders."""

    out = content
    for idx, value in enumerate(args, start=1):
        out = out.replace(f"${idx}", value)
    all_args = " ".join(args)
    out = out.replace("$ARGUMENTS", all_args).replace("$@", all_args)

    # Support ${@:N} and ${@:N:L}
    while True:
        start = out.find("${@:")
        if start == -1:
            break
        end = out.find("}", start)
        if end == -1:
            break
        token = out[start + 4 : end]
        parts = token.split(":")
        try:
            start_pos = max(1, int(parts[0])) - 1
        except ValueError:
            break
        if len(parts) == 2 and parts[1]:
            try:
                length = int(parts[1])
            except ValueError:
                break
            replacement = " ".join(args[start_pos : start_pos + length])
        else:
            replacement = " ".join(args[start_pos:])
        out = f"{out[:start]}{replacement}{out[end + 1:]}"
    return out


def expand_prompt_template(text: str, templates: list[PromptTemplate]) -> str:
    """Expand ``/name ...`` prompt template commands."""

    if not text.startswith("/"):
        return text
    command = text[1:]
    if not command:
        return text
    parts = command.split(maxsplit=1)
    name = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    template = next((item for item in templates if item.name == name), None)
    if template is None:
        return text
    parsed_args = parse_command_args(args)
    return substitute_args(template.content, parsed_args)


def _load_template_file(
    path: Path,
    *,
    cwd: Path,
    agent_dir: Path,
    fallback_base_dir: Path | None = None,
) -> PromptTemplate | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_frontmatter(raw)
    body = parsed.body
    description = parsed.frontmatter.get("description", "").strip()
    if not description:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped:
                description = stripped[:60] + ("..." if len(stripped) > 60 else "")
                break
    return PromptTemplate(
        name=path.stem,
        description=description,
        content=body,
        file_path=str(path),
        argument_hint=parsed.frontmatter.get("argument-hint"),
        source_info=classify_source_info(
            path=path,
            cwd=cwd,
            agent_dir=agent_dir,
            fallback_base_dir=fallback_base_dir,
        ),
    )


def _load_templates_from_dir(
    dir_path: Path,
    *,
    cwd: Path,
    agent_dir: Path,
    fallback_base_dir: Path | None = None,
) -> list[PromptTemplate]:
    if not dir_path.is_dir():
        return []
    loaded: list[PromptTemplate] = []
    for child in sorted(dir_path.iterdir()):
        if child.is_file() and child.suffix.lower() == ".md":
            tpl = _load_template_file(
                child,
                cwd=cwd,
                agent_dir=agent_dir,
                fallback_base_dir=fallback_base_dir,
            )
            if tpl is not None:
                loaded.append(tpl)
    return loaded


def load_prompt_templates(
    *,
    cwd: Path,
    agent_dir: Path,
    prompt_paths: list[str],
    include_defaults: bool,
) -> LoadPromptTemplatesResult:
    """Load prompt templates from defaults plus explicit paths."""

    templates: list[PromptTemplate] = []
    diagnostics: list[ResourceDiagnostic] = []
    if include_defaults:
        templates.extend(
            _load_templates_from_dir(
                agent_dir / "prompts",
                cwd=cwd,
                agent_dir=agent_dir,
            ),
        )
        templates.extend(
            _load_templates_from_dir(
                cwd / CONFIG_DIR_NAME / "prompts",
                cwd=cwd,
                agent_dir=agent_dir,
            ),
        )
    for raw in prompt_paths:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (cwd / path).resolve()
        if path.is_dir():
            templates.extend(
                _load_templates_from_dir(
                    path,
                    cwd=cwd,
                    agent_dir=agent_dir,
                    fallback_base_dir=path,
                ),
            )
            continue
        if path.is_file() and path.suffix.lower() == ".md":
            tpl = _load_template_file(
                path,
                cwd=cwd,
                agent_dir=agent_dir,
                fallback_base_dir=path.parent,
            )
            if tpl is not None:
                templates.append(tpl)
    deduped: list[PromptTemplate] = []
    seen: dict[str, PromptTemplate] = {}
    for template in templates:
        if template.name in seen:
            winner = seen[template.name]
            diagnostics.append(
                ResourceDiagnostic(
                    type="collision",
                    message=f'name "/{template.name}" collision',
                    path=template.file_path,
                    collision={
                        "resourceType": "prompt",
                        "name": template.name,
                        "winnerPath": winner.file_path,
                        "loserPath": template.file_path,
                    },
                ),
            )
            continue
        seen[template.name] = template
        deduped.append(template)
    return LoadPromptTemplatesResult(prompts=deduped, diagnostics=diagnostics)
