"""JSONL session manager (pi: session-manager.ts subset)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pi_agent.types import AgentMessage

from pi_ai.config_paths import get_sessions_dir
from pi_coding_agent.session.serialize import message_from_dict, message_to_dict

CURRENT_SESSION_VERSION = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cwd_key(cwd: Path) -> str:
    digest = hashlib.sha256(str(cwd.resolve()).encode("utf-8")).hexdigest()[:16]
    return digest


class SessionManager:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def create(cls, cwd: str | Path) -> SessionManager:
        cwd_path = Path(cwd).resolve()
        session_dir = get_sessions_dir() / _cwd_key(cwd_path)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(uuid.uuid4())
        path = session_dir / f"{session_id}.jsonl"
        header = {
            "type": "session",
            "version": CURRENT_SESSION_VERSION,
            "id": session_id,
            "timestamp": _utc_now_iso(),
            "cwd": str(cwd_path),
        }
        path.write_text(json.dumps(header) + "\n", encoding="utf-8")
        return cls(path)

    @classmethod
    def open(cls, path: str | Path) -> SessionManager:
        return cls(Path(path))

    @classmethod
    def latest_for_cwd(cls, cwd: str | Path) -> SessionManager | None:
        cwd_path = Path(cwd).resolve()
        session_dir = get_sessions_dir() / _cwd_key(cwd_path)
        if not session_dir.is_dir():
            return None
        files = sorted(
            session_dir.glob("*.jsonl"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return None
        return cls(files[0])

    def load_messages(self) -> list[AgentMessage]:
        if not self.path.is_file():
            return []
        messages: list[AgentMessage] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("type") != "message":
                continue
            payload = entry.get("message")
            if isinstance(payload, dict):
                messages.append(message_from_dict(payload))
        return messages

    def append_messages(self, new_messages: list[AgentMessage]) -> None:
        if not new_messages:
            return
        lines: list[str] = []
        for message in new_messages:
            entry = {
                "type": "message",
                "id": str(uuid.uuid4()),
                "parentId": None,
                "timestamp": _utc_now_iso(),
                "message": message_to_dict(message),
            }
            lines.append(json.dumps(entry, ensure_ascii=False))
        with self.path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
