"""Read file tool."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.truncate import truncate_tail

READ_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to read (relative or absolute)",
        },
    },
    "required": ["path"],
    "additionalProperties": False,
}


def _resolve_under_cwd(cwd: Path, path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    resolved = candidate.resolve()
    cwd_resolved = cwd.resolve()
    if resolved != cwd_resolved and cwd_resolved not in resolved.parents:
        raise ValueError(f"Path escapes working directory: {path}")
    return resolved


@dataclass
class ReadTool:
    cwd: str
    name: str = "read"
    description: str = (
        "Read a file from the filesystem. Returns file contents as text."
    )
    parameters: dict = field(default_factory=lambda: READ_SCHEMA)
    execution_mode: ToolExecutionMode = "parallel"

    async def execute(
        self,
        tool_call_id: str,
        args: dict,
        signal=None,
        on_update=None,
    ) -> AgentToolResult:
        del tool_call_id, signal, on_update
        path_arg = args["path"]
        resolved = _resolve_under_cwd(Path(self.cwd), path_arg)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path_arg}")
        text = resolved.read_text(encoding="utf-8", errors="replace")
        snapshot = truncate_tail(text)
        details = {"truncation": snapshot} if snapshot.truncated else None
        return AgentToolResult(
            content=[TextContent(text=snapshot.content)],
            details=details,
        )


def create_read_tool(cwd: str) -> ReadTool:
    return ReadTool(cwd=cwd)
