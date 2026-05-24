"""Write file tool (pi: write.ts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.path_utils import resolve_under_cwd

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to write (relative or absolute)",
        },
        "content": {
            "type": "string",
            "description": "Content to write to the file",
        },
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}


@dataclass
class WriteTool:
    cwd: str
    name: str = "write"
    description: str = "Write content to a file (creates or overwrites)."
    parameters: dict = field(default_factory=lambda: dict(WRITE_SCHEMA))
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
        resolved = resolve_under_cwd(Path(self.cwd), path_arg)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(str(args["content"]), encoding="utf-8")
        return AgentToolResult(
            content=[TextContent(text=f"Wrote {path_arg}")],
            details={"path": str(resolved)},
        )


def create_write_tool(cwd: str) -> WriteTool:
    return WriteTool(cwd=cwd)
