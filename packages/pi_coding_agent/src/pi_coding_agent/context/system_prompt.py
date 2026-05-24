"""Build the composite system prompt (default or custom), with project context."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from pi_coding_agent.context.loader import ContextFile
from pi_coding_agent.defaults import DEFAULT_SYSTEM


def _normalized_cwd(cwd: str | Path) -> str:
    return str(cwd).replace("\\", "/")


def _today_iso() -> str:
    """Return today's date as ``YYYY-MM-DD``."""
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}-{today.day:02d}"


def _format_project_context(files: Iterable[ContextFile]) -> str:
    """Return the pi-style ``project_context`` XML block or empty string."""
    file_list = list(files)
    if not file_list:
        return ""

    parts: list[str] = [
        "",
        "",
        "<project_context>",
        "",
        "Project-specific instructions and guidelines:",
        "",
    ]
    for ctx in file_list:
        parts.append(
            f'<project_instructions path="{ctx.path}">\n'
            f"{ctx.content}\n"
            f"</project_instructions>\n"
            ""
        )
    parts.append("</project_context>\n")
    return "\n".join(parts)


def _format_tools_section(tool_names: list[str]) -> str:
    if not tool_names:
        return ""
    lines = "\n".join(f"- {name}" for name in tool_names)
    return f"\n\nAvailable tools:\n{lines}"


def build_system_prompt(
    *,
    cwd: str | Path,
    tools: list[str],
    context_files: list[ContextFile],
    custom_prompt: str | None = None,
    append_sections: list[str] | None = None,
    default_base: str | None = None,
) -> str:
    """Assemble the system prompt with optional custom base and project context.

    When ``custom_prompt`` is set, its text is used as the base. Optional
    ``append_sections`` are appended first, then a ``<project_context>`` block
    for ``context_files`` (pi format). Date and working directory lines are
    always added last.

    When ``custom_prompt`` is omitted, ``default_base`` is used if provided,
    otherwise :data:`pi_coding_agent.defaults.DEFAULT_SYSTEM`. Tool names are
    listed when ``tools`` is non-empty; then append sections (if any), project
    context, date, and working directory follow.

    Args:
        cwd: Current working directory (shown at end of prompt).
        tools: Tool names for the non-custom default branch.
        context_files: Files loaded by :func:`load_project_context_files`.
        custom_prompt: If set, replaces the default template entirely.
        append_sections: Extra paragraphs appended before ``project_context``.
        default_base: Override for the built-in default when not using custom.

    Returns:
        Full system prompt string.
    """
    prompt_cwd = _normalized_cwd(cwd)
    today = _today_iso()
    appends_list = append_sections if append_sections is not None else []
    append_blob = ""
    if appends_list:
        append_blob = "\n\n" + "\n\n".join(appends_list)

    context_block = _format_project_context(context_files)
    footer = (
        f"\nCurrent date: {today}"
        f"\nCurrent working directory: {prompt_cwd}"
    )

    if custom_prompt is not None:
        prompt = custom_prompt
        if append_blob:
            prompt += append_blob
        if context_block:
            prompt += context_block
        prompt += footer
        return prompt

    base = default_base if default_base is not None else DEFAULT_SYSTEM
    prompt = base
    prompt += _format_tools_section(tools)
    if append_blob:
        prompt += append_blob
    if context_block:
        prompt += context_block
    prompt += footer
    return prompt
