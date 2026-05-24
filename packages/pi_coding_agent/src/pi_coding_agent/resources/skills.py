"""Skill loading and system-prompt formatting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pi_ai.config_paths import CONFIG_DIR_NAME

from pi_coding_agent.resources.frontmatter import parse_frontmatter


@dataclass(frozen=True)
class Skill:
    """Loaded skill descriptor."""

    name: str
    description: str
    file_path: str
    base_dir: str
    disable_model_invocation: bool = False


def _bool_value(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_skill_file(path: Path) -> Skill | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_frontmatter(raw)
    description = parsed.frontmatter.get("description", "").strip()
    if not description:
        return None
    name = parsed.frontmatter.get("name", "").strip() or path.parent.name
    return Skill(
        name=name,
        description=description,
        file_path=str(path),
        base_dir=str(path.parent),
        disable_model_invocation=_bool_value(
            parsed.frontmatter.get("disable-model-invocation"),
        ),
    )


def _scan_skill_dir(root: Path) -> list[Skill]:
    if not root.is_dir():
        return []
    found: list[Skill] = []
    for current, dirs, files in _walk(root):
        if "SKILL.md" in files:
            skill = _load_skill_file(current / "SKILL.md")
            if skill is not None:
                found.append(skill)
            dirs[:] = []
            continue
        for file_name in files:
            if file_name.lower().endswith(".md") and current == root:
                skill = _load_skill_file(current / file_name)
                if skill is not None:
                    found.append(skill)
    return found


def _walk(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        dirs: list[Path] = []
        files: list[str] = []
        for item in entries:
            if item.name.startswith("."):
                continue
            if item.name == "node_modules":
                continue
            if item.is_dir():
                dirs.append(item)
            elif item.is_file():
                files.append(item.name)
        yield current, dirs, files
        stack.extend(reversed(dirs))


def _iter_project_agents_dirs(cwd: Path) -> list[Path]:
    results: list[Path] = []
    current = cwd.resolve()
    while True:
        candidate = current / ".agents" / "skills"
        if candidate.is_dir():
            results.insert(0, candidate)
        if current.parent == current:
            break
        current = current.parent
    return results


def load_skills(
    *,
    cwd: Path,
    agent_dir: Path,
    skill_paths: list[str],
    include_defaults: bool,
) -> list[Skill]:
    """Load skills from global/project defaults plus explicit paths."""

    loaded: list[Skill] = []
    if include_defaults:
        loaded.extend(_scan_skill_dir(agent_dir / "skills"))
        loaded.extend(_scan_skill_dir(agent_dir.parent / ".agents" / "skills"))
        loaded.extend(_scan_skill_dir(cwd / CONFIG_DIR_NAME / "skills"))
        for directory in _iter_project_agents_dirs(cwd):
            loaded.extend(_scan_skill_dir(directory))
    for raw in skill_paths:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (cwd / path).resolve()
        if path.is_dir():
            loaded.extend(_scan_skill_dir(path))
        elif path.is_file() and path.suffix.lower() == ".md":
            skill = _load_skill_file(path)
            if skill is not None:
                loaded.append(skill)
    deduped: list[Skill] = []
    seen: set[str] = set()
    for skill in loaded:
        if skill.name in seen:
            continue
        seen.add(skill.name)
        deduped.append(skill)
    return deduped


def format_skills_for_prompt(skills: list[Skill]) -> str:
    """Format skill inventory in Agent Skills XML style."""

    visible = [item for item in skills if not item.disable_model_invocation]
    if not visible:
        return ""
    lines = [
        "",
        "",
        "The following skills provide specialized instructions for specific tasks.",
        "Use the read tool to load a skill file when the task matches.",
        "",
        "<available_skills>",
    ]
    for skill in visible:
        lines.extend(
            [
                "  <skill>",
                f"    <name>{_escape_xml(skill.name)}</name>",
                f"    <description>{_escape_xml(skill.description)}</description>",
                f"    <location>{_escape_xml(skill.file_path)}</location>",
                "  </skill>",
            ]
        )
    lines.append("</available_skills>")
    return "\n".join(lines)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
