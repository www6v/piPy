"""Bash execution tool."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pi_agent.types import AgentToolResult, ToolExecutionMode
from pi_ai.types import TextContent

from pi_coding_agent.tools.truncate import truncate_tail

BASH_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Bash command to execute",
        },
        "timeout": {
            "type": "number",
            "description": "Timeout in seconds (optional)",
        },
    },
    "required": ["command"],
    "additionalProperties": False,
}


class BashOperations(Protocol):
    async def exec(
        self,
        command: str,
        cwd: str,
        *,
        on_data,
        signal,
        timeout: float | None,
    ) -> int | None: ...


@dataclass
class LocalBashOperations:
    async def exec(
        self,
        command: str,
        cwd: str,
        *,
        on_data,
        signal,
        timeout: float | None,
    ) -> int | None:
        if not Path(cwd).is_dir():
            raise FileNotFoundError(f"Working directory does not exist: {cwd}")

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=os.environ.copy(),
        )
        chunks: list[bytes] = []

        async def read_output() -> None:
            assert process.stdout is not None
            while True:
                data = await process.stdout.read(4096)
                if not data:
                    break
                chunks.append(data)
                if on_data is not None:
                    on_data(data)

        read_task = asyncio.create_task(read_output())
        if signal is not None and getattr(signal, "is_set", lambda: False)():
            process.kill()
            await process.wait()
            raise RuntimeError("aborted")
        try:
            if timeout is not None and timeout > 0:
                exit_code = await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                exit_code = await process.wait()
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise RuntimeError(f"timeout:{timeout}") from exc
        finally:
            await read_task

        return exit_code


async def _default_exec(
    command: str,
    cwd: str,
    *,
    on_data,
    signal,
    timeout: float | None,
) -> tuple[int | None, str]:
    ops = LocalBashOperations()
    return await ops.exec(
        command,
        cwd,
        on_data=on_data,
        signal=signal,
        timeout=timeout,
    )


@dataclass
class BashTool:
    cwd: str
    operations: BashOperations | None = None
    name: str = "bash"
    description: str = (
        "Execute a bash command in the current working directory. "
        "Returns stdout and stderr combined."
    )
    parameters: dict = field(default_factory=lambda: BASH_SCHEMA)
    execution_mode: ToolExecutionMode = "parallel"

    async def execute(
        self,
        tool_call_id: str,
        args: dict,
        signal=None,
        on_update=None,
    ) -> AgentToolResult:
        del tool_call_id, on_update
        command = args["command"]
        timeout = args.get("timeout")
        timeout_val = float(timeout) if timeout is not None else None
        cwd = str(Path(self.cwd).resolve())
        if not Path(cwd).is_dir():
            raise FileNotFoundError(f"Working directory does not exist: {cwd}")

        chunks: list[bytes] = []

        def on_data(data: bytes) -> None:
            chunks.append(data)

        try:
            if self.operations is not None:
                exit_code = await self.operations.exec(
                    command,
                    cwd,
                    on_data=on_data,
                    signal=signal,
                    timeout=timeout_val,
                )
                output = b"".join(chunks).decode("utf-8", errors="replace")
            else:
                exit_code = await _default_exec(
                    command,
                    cwd,
                    on_data=on_data,
                    signal=signal,
                    timeout=timeout_val,
                )
                output = b"".join(chunks).decode("utf-8", errors="replace")
        except RuntimeError as exc:
            output = b"".join(chunks).decode("utf-8", errors="replace")
            snapshot = truncate_tail(output)
            text = snapshot.content
            if str(exc) == "aborted":
                raise RuntimeError(
                    f"{text}\n\nCommand aborted" if text else "Command aborted"
                ) from exc
            if str(exc).startswith("timeout:"):
                secs = str(exc).split(":", 1)[1]
                raise RuntimeError(
                    f"{text}\n\nCommand timed out after {secs} seconds"
                    if text
                    else f"Command timed out after {secs} seconds"
                ) from exc
            raise

        snapshot = truncate_tail(output)
        text = snapshot.content or "(no output)"
        details = {"truncation": snapshot} if snapshot.truncated else None
        if exit_code not in (0, None):
            raise RuntimeError(
                f"{text}\n\nCommand exited with code {exit_code}"
            )
        return AgentToolResult(
            content=[TextContent(text=text)],
            details=details,
        )


def create_bash_tool(cwd: str, operations: BashOperations | None = None) -> BashTool:
    return BashTool(cwd=cwd, operations=operations)
