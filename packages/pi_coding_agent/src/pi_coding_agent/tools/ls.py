"""List directory contents (pi: ls.ts)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.path_utils import resolve_under_cwd
from pi_coding_agent.tools.truncate import DEFAULT_MAX_BYTES, truncate_tail

LS_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Directory to list (default: cwd)",
        },
        "limit": {
            "type": "number",
            "description": "Maximum entries (default: 500)",
        },
    },
    "additionalProperties": False,
}

DEFAULT_LIMIT = 500


@dataclass
class LsTool:
    name: str
    description: str
    parameters: dict
    execution_mode: ToolExecutionMode
    _cwd: Path

    async def execute(
        self,
        tool_call_id: str,
        args: dict,
        signal=None,
        on_update=None,
    ) -> AgentToolResult:
        dir_path = resolve_under_cwd(self._cwd, str(args.get("path") or "."))
        limit = int(args.get("limit") or DEFAULT_LIMIT)
        if not dir_path.exists():
            return AgentToolResult(
                content=[TextContent(text=f"Path not found: {dir_path}")],
                is_error=True,
            )
        if not dir_path.is_dir():
            return AgentToolResult(
                content=[TextContent(text=f"Not a directory: {dir_path}")],
                is_error=True,
            )
        entries = sorted(
            dir_path.iterdir(),
            key=lambda entry: entry.name.lower(),
        )
        lines: list[str] = []
        entry_limit_reached = False
        for entry in entries:
            if len(lines) >= limit:
                entry_limit_reached = True
                break
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        if not lines:
            return AgentToolResult(
                content=[TextContent(text="(empty directory)")],
            )
        output = "\n".join(lines)
        truncated = truncate_tail(
            output,
            max_lines=limit,
            max_bytes=DEFAULT_MAX_BYTES,
        )
        text = truncated.content
        notices: list[str] = []
        if entry_limit_reached:
            notices.append(f"{limit} entries limit reached")
        if truncated.truncated:
            notices.append(f"{DEFAULT_MAX_BYTES // 1024}KB limit reached")
        if notices:
            text += f"\n\n[{'. '.join(notices)}]"
        return AgentToolResult(content=[TextContent(text=text)])


def create_ls_tool(cwd: str) -> LsTool:
    root = Path(cwd)
    return LsTool(
        name="ls",
        description=(
            "List directory contents sorted alphabetically. "
            f"Directories end with '/'. Default limit {DEFAULT_LIMIT} entries."
        ),
        parameters=LS_SCHEMA,
        execution_mode="parallel",
        _cwd=root,
    )
