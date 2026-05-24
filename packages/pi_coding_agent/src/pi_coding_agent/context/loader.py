"""Load project context files (AGENTS.md / CLAUDE.md) and system prompt files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PI_DIR_NAME = ".pi"

_CONTEXT_FILENAMES = ("AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD")


@dataclass(frozen=True)
class ContextFile:
    """A single discovered context markdown file."""

    path: str
    content: str


def load_context_file_from_dir(dir_path: Path) -> ContextFile | None:
    """Return the first existing context file in ``dir_path``, or ``None``."""
    resolved = dir_path.resolve()
    for name in _CONTEXT_FILENAMES:
        candidate = resolved / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                return None
            return ContextFile(path=str(candidate), content=text)
    return None


def load_project_context_files(cwd: Path, agent_dir: Path) -> list[ContextFile]:
    """Load global context plus ancestor chain contexts (deduped by path).

    Order matches pi ``loadProjectContextFiles``: global agent dir first,
    then directories from filesystem root toward ``cwd`` (outer ancestors
    before inner).

    Args:
        cwd: Working directory for the agent run.
        agent_dir: Global agent directory (e.g. ``~/.pi/agent``).

    Returns:
        Ordered list of context files.
    """
    resolved_cwd = cwd.resolve()
    resolved_agent_dir = agent_dir.resolve()

    context_files: list[ContextFile] = []
    seen_paths: set[str] = set()

    global_ctx = load_context_file_from_dir(resolved_agent_dir)
    if global_ctx is not None:
        context_files.append(global_ctx)
        seen_paths.add(global_ctx.path)

    ancestor_files: list[ContextFile] = []
    current = resolved_cwd
    while True:
        ctx = load_context_file_from_dir(current)
        if ctx is not None and ctx.path not in seen_paths:
            ancestor_files.insert(0, ctx)
            seen_paths.add(ctx.path)

        if current.parent == current:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    context_files.extend(ancestor_files)
    return context_files


def load_system_prompt_files(
    cwd: Path,
    agent_dir: Path,
) -> tuple[str | None, list[str]]:
    """Load ``SYSTEM.md`` (replaces default) and ``APPEND_SYSTEM.md`` sections.

    ``SYSTEM.md`` is taken from ``{cwd}/.pi/SYSTEM.md`` if present, otherwise
    ``{agent_dir}/SYSTEM.md``. This matches pi project-over-global precedence.

    ``APPEND_SYSTEM.md`` is read from both ``{agent_dir}/APPEND_SYSTEM.md`` and
    ``{cwd}/.pi/APPEND_SYSTEM.md`` when present, returning a list of sections
    in that order (global first, then project).

    Args:
        cwd: Project root / working directory.
        agent_dir: Global agent directory.

    Returns:
        ``(system_text_or_none, append_sections)``.
    """
    resolved_cwd = cwd.resolve()
    resolved_agent_dir = agent_dir.resolve()

    project_system = resolved_cwd / PI_DIR_NAME / "SYSTEM.md"
    global_system = resolved_agent_dir / "SYSTEM.md"

    system_text: str | None = None
    if project_system.is_file():
        try:
            system_text = project_system.read_text(encoding="utf-8")
        except OSError:
            system_text = None
    if system_text is None and global_system.is_file():
        try:
            system_text = global_system.read_text(encoding="utf-8")
        except OSError:
            system_text = None

    append_sections: list[str] = []
    global_append = resolved_agent_dir / "APPEND_SYSTEM.md"
    project_append = resolved_cwd / PI_DIR_NAME / "APPEND_SYSTEM.md"
    for path in (global_append, project_append):
        if path.is_file():
            try:
                append_sections.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue

    return system_text, append_sections
