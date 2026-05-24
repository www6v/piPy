"""RPC subprocess client (pi: RpcClient subset)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class RpcClient:
    """Spawn pipy --mode rpc and exchange JSONL messages."""

    def __init__(
        self,
        *,
        command: list[str] | None = None,
        extra_args: list[str] | None = None,
        cwd: str | Path | None = None,
    ) -> None:
        base = command or ["pipy", "--mode", "rpc", "--no-session"]
        if extra_args:
            base = [*base, *extra_args]
        self._command = base
        self._cwd = Path(cwd).resolve() if cwd is not None else None
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        popen_kw: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "bufsize": 1,
        }
        if self._cwd is not None:
            popen_kw["cwd"] = str(self._cwd)
        self._process = subprocess.Popen(
            self._command,
            **popen_kw,
        )

    def close(self) -> None:
        if self._process is None:
            return
        if self._process.stdin:
            self._process.stdin.close()
        self._process.terminate()
        self._process.wait(timeout=10)
        self._process = None

    def send(self, command: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("RpcClient not started")
        line = json.dumps(command, ensure_ascii=False) + "\n"
        self._process.stdin.write(line)
        self._process.stdin.flush()

    def read_lines(self) -> Iterator[dict[str, Any]]:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("RpcClient not started")
        while True:
            raw = self._process.stdout.readline()
            if not raw:
                break
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            yield json.loads(line)

    def request(
        self,
        command: dict[str, Any],
        *,
        timeout_events: int = 10_000,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Send a command and return (response, trailing events until idle)."""
        self.send(command)
        response: dict[str, Any] | None = None
        events: list[dict[str, Any]] = []
        request_id = command.get("id")
        for _ in range(timeout_events):
            for payload in self.read_lines():
                if payload.get("type") == "response":
                    if request_id is None or payload.get("id") == request_id:
                        response = payload
                        return response, events
                else:
                    events.append(payload)
        raise TimeoutError("RPC response not received")

    def prompt(self, message: str, *, request_id: str = "req-1") -> None:
        self.send({"id": request_id, "type": "prompt", "message": message})
