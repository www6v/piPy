"""Grep tool via ripgrep (pi: grep.ts)."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.path_utils import resolve_under_cwd
from pi_coding_agent.tools.truncate import truncate_tail

GREP_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Search pattern (regex)",
        },
        "path": {
            "type": "string",
            "description": "Directory or file to search (default: cwd)",
        },
        "glob": {
            "type": "string",
            "description": "Filter files by glob, e.g. '*.py'",
        },
        "ignoreCase": {"type": "boolean"},
        "literal": {"type": "boolean"},
        "limit": {
            "type": "number",
            "description": "Maximum matches (default 100)",
        },
    },
    "required": ["pattern"],
    "additionalProperties": False,
}

DEFAULT_LIMIT = 100


@dataclass
class GrepTool:
    cwd: str
    name: str = "grep"
    description: str = "Search file contents with ripgrep (rg)."
    parameters: dict = field(default_factory=lambda: dict(GREP_SCHEMA))
    execution_mode: ToolExecutionMode = "parallel"

    async def execute(
        self,
        tool_call_id: str,
        args: dict,
        signal=None,
        on_update=None,
    ) -> AgentToolResult:
        del tool_call_id, on_update
        if signal is not None and getattr(signal, "is_set", lambda: False)():
            raise asyncio.CancelledError("aborted")

        rg = shutil.which("rg")
        if rg is None:
            raise RuntimeError("ripgrep (rg) not found in PATH")

        search_path = args.get("path") or "."
        resolved = resolve_under_cwd(Path(self.cwd), str(search_path))
        limit = int(args.get("limit") or DEFAULT_LIMIT)

        cmd = [
            rg,
            "--line-number",
            "--no-heading",
            "--color=never",
            "-m",
            str(limit),
        ]
        if args.get("ignoreCase"):
            cmd.append("-i")
        if args.get("literal"):
            cmd.append("-F")
        glob = args.get("glob")
        if glob:
            cmd.extend(["--glob", str(glob)])
        cmd.extend([str(args["pattern"]), str(resolved)])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode not in (0, 1):
            err = (stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(err or f"rg exited with {proc.returncode}")

        text = (stdout or b"").decode("utf-8", errors="replace")
        if not text.strip():
            return AgentToolResult(content=[TextContent(text="No matches found.")])
        snapshot = truncate_tail(text)
        details: dict = {}
        if snapshot.truncated:
            details["truncation"] = {
                "truncated": True,
                "truncated_by": snapshot.truncated_by,
            }
        return AgentToolResult(
            content=[TextContent(text=snapshot.content)],
            details=details or None,
        )


def create_grep_tool(cwd: str) -> GrepTool:
    return GrepTool(cwd=cwd)
