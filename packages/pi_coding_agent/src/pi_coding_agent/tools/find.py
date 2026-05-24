"""Find files by glob pattern (pi: find.ts)."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.path_utils import resolve_under_cwd
from pi_coding_agent.tools.truncate import DEFAULT_MAX_BYTES, truncate_tail

FIND_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Glob pattern, e.g. '*.py' or '**/*.json'",
        },
        "path": {
            "type": "string",
            "description": "Directory to search (default: cwd)",
        },
        "limit": {
            "type": "number",
            "description": "Maximum results (default: 1000)",
        },
    },
    "required": ["pattern"],
    "additionalProperties": False,
}

DEFAULT_LIMIT = 1000
_SKIP_DIRS = {".git", "node_modules"}


@dataclass
class FindTool:
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
        pattern = str(args["pattern"])
        search_dir = resolve_under_cwd(
            self._cwd,
            str(args.get("path") or "."),
        )
        limit = int(args.get("limit") or DEFAULT_LIMIT)
        if not search_dir.is_dir():
            return AgentToolResult(
                content=[TextContent(text=f"Path not found: {search_dir}")],
                is_error=True,
            )
        results = await asyncio.to_thread(
            _find_files,
            pattern,
            search_dir,
            limit,
        )
        if not results:
            return AgentToolResult(
                content=[TextContent(text="No files found matching pattern")],
            )
        output = "\n".join(results)
        truncated = truncate_tail(
            output,
            max_lines=limit,
            max_bytes=DEFAULT_MAX_BYTES,
        )
        text = truncated.content
        notices: list[str] = []
        if len(results) >= limit:
            notices.append(f"{limit} results limit reached")
        if truncated.truncated:
            notices.append(f"{DEFAULT_MAX_BYTES // 1024}KB limit reached")
        if notices:
            text += f"\n\n[{'. '.join(notices)}]"
        return AgentToolResult(content=[TextContent(text=text)])


def _find_with_fd(pattern: str, search_dir: Path, limit: int) -> list[str] | None:
    fd = shutil.which("fd")
    if fd is None:
        return None
    cmd = [
        fd,
        "--glob",
        pattern,
        "--max-results",
        str(limit),
        ".",
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(search_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in (0, 1):
        return None
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[:limit]


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIRS or name.startswith(".")


def _walk_glob(pattern: str, search_dir: Path, limit: int) -> list[str]:
    results: list[str] = []
    normalized = pattern.replace("\\", "/")
    use_rglob = "**" in normalized

    def matches(path: Path) -> bool:
        rel = path.relative_to(search_dir).as_posix()
        if use_rglob:
            return fnmatch.fnmatch(rel, normalized)
        return fnmatch.fnmatch(path.name, normalized.split("/")[-1])

    for root, dirs, files in os.walk(search_dir):
        dirs[:] = [name for name in dirs if not _should_skip_dir(name)]
        root_path = Path(root)
        for filename in files:
            full = root_path / filename
            if matches(full):
                results.append(full.relative_to(search_dir).as_posix())
                if len(results) >= limit:
                    return results
    return results


def _find_files(pattern: str, search_dir: Path, limit: int) -> list[str]:
    fd_results = _find_with_fd(pattern, search_dir, limit)
    if fd_results is not None:
        return fd_results
    return _walk_glob(pattern, search_dir, limit)


def create_find_tool(cwd: str) -> FindTool:
    root = Path(cwd)
    return FindTool(
        name="find",
        description=(
            "Search for files by glob pattern. Returns paths relative to the "
            f"search directory. Output truncated to {DEFAULT_LIMIT} results."
        ),
        parameters=FIND_SCHEMA,
        execution_mode="parallel",
        _cwd=root,
    )
