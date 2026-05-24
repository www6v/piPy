"""Edit file tool (pi: edit.ts)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.path_utils import resolve_under_cwd

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to edit (relative or absolute)",
        },
        "edits": {
            "type": "array",
            "description": "Targeted replacements (matched against original file).",
            "items": {
                "type": "object",
                "properties": {
                    "oldText": {"type": "string"},
                    "newText": {"type": "string"},
                },
                "required": ["oldText", "newText"],
                "additionalProperties": False,
            },
        },
        "oldText": {
            "type": "string",
            "description": "Legacy single replacement: text to find.",
        },
        "newText": {
            "type": "string",
            "description": "Legacy single replacement: replacement text.",
        },
    },
    "required": ["path"],
    "additionalProperties": False,
}


def _normalize_edits(args: dict) -> list[dict[str, str]]:
    edits = args.get("edits")
    if isinstance(edits, str):
        try:
            edits = json.loads(edits)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid edits JSON: {exc}") from exc
    if isinstance(edits, list) and edits:
        return [
            {"oldText": str(item["oldText"]), "newText": str(item["newText"])}
            for item in edits
        ]
    old_text = args.get("oldText")
    new_text = args.get("newText")
    if isinstance(old_text, str) and isinstance(new_text, str):
        return [{"oldText": old_text, "newText": new_text}]
    raise ValueError("edit requires edits[] or oldText/newText")


def _apply_edits(content: str, edits: list[dict[str, str]]) -> str:
    result = content
    for edit in edits:
        old = edit["oldText"]
        new = edit["newText"]
        count = result.count(old)
        if count == 0:
            raise ValueError("oldText not found in file")
        if count > 1:
            raise ValueError(
                f"oldText is not unique ({count} matches); merge into one edit"
            )
        result = result.replace(old, new, 1)
    return result


@dataclass
class EditTool:
    cwd: str
    name: str = "edit"
    description: str = (
        "Edit a file by replacing exact oldText with newText. "
        "Use edits[] for multiple non-overlapping replacements."
    )
    parameters: dict = field(default_factory=lambda: dict(EDIT_SCHEMA))
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
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path_arg}")
        edits = _normalize_edits(args)
        original = resolved.read_text(encoding="utf-8")
        updated = _apply_edits(original, edits)
        resolved.write_text(updated, encoding="utf-8")
        return AgentToolResult(
            content=[TextContent(text=f"Edited {path_arg}")],
            details={"path": str(resolved)},
        )


def create_edit_tool(cwd: str) -> EditTool:
    return EditTool(cwd=cwd)
