"""JSONL session manager (pi: session-manager.ts subset)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pi_agent.agent_loop import prompt_text
from pi_agent.types import AgentMessage

from pi_ai.config_paths import get_sessions_dir
from pi_coding_agent.session.serialize import message_from_dict, message_to_dict
from pi_coding_agent.session.tree import (
    SessionTree,
    build_session_tree,
    clone_branch_entries,
    infer_active_leaf_id,
)
from pi_coding_agent.session.types import CompactionResult

CURRENT_SESSION_VERSION = 3

_SUMMARY_PREFIX = "Previous conversation summary:\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cwd_key(cwd: Path) -> str:
    digest = hashlib.sha256(str(cwd.resolve()).encode("utf-8")).hexdigest()[:16]
    return digest


def build_messages_from_entries(entries: list[dict]) -> list[AgentMessage]:
    """Rebuild LLM-visible messages honoring the newest compaction on the leaf path."""
    body = _session_body(entries)
    if not body:
        return []
    leaf_id = _infer_leaf_id(entries)
    if leaf_id is None:
        return []
    by_id = _entries_by_id(body)
    if not by_id:
        return []

    path = _leaf_path(leaf_id, by_id)
    if not path:
        return []

    compaction = _latest_compaction_on_path(path)
    if compaction is None:
        return _append_message_entries([], path)

    summary_text = compaction.get("summary", "")
    outgoing: list[AgentMessage] = [
        prompt_text(f"{_SUMMARY_PREFIX}{summary_text}"),
    ]

    compaction_idx = next(
        (
            idx
            for idx, row in enumerate(path)
            if row.get("type") == "compaction"
            and row.get("id") == compaction.get("id")
        ),
        None,
    )
    if compaction_idx is None:
        return _append_message_entries(outgoing, path)

    first_kept_raw = compaction.get("firstKeptEntryId") or compaction.get(
        "first_kept_entry_id",
    )
    first_kept = first_kept_raw if isinstance(first_kept_raw, str) else None

    found_first = False
    for idx in range(compaction_idx):
        row = path[idx]
        if first_kept is not None and row.get("id") == first_kept:
            found_first = True
        if found_first:
            outgoing = _append_message_row(outgoing, row)

    for idx in range(compaction_idx + 1, len(path)):
        outgoing = _append_message_row(outgoing, path[idx])

    return outgoing


def _session_body(entries: list[dict]) -> list[dict]:
    """Return session entries excluding the optional leading session header."""
    return [entry for entry in entries if entry.get("type") != "session"]


def _entries_by_id(body: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for row in body:
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id:
            by_id[row_id] = row
    return by_id


def _leaf_path(leaf_id: str | None, by_id: dict[str, dict]) -> list[dict]:
    if leaf_id is None:
        return []
    path_rev: list[dict] = []
    cur: str | None = leaf_id
    visited: set[str] = set()
    while cur is not None:
        if cur in visited:
            break
        visited.add(cur)
        row = by_id.get(cur)
        if row is None:
            break
        path_rev.append(row)
        parent_raw = row.get("parentId")
        cur = (
            None
            if parent_raw is None
            else (str(parent_raw) if isinstance(parent_raw, str) else None)
        )

    path_rev.reverse()
    return path_rev


def _latest_compaction_on_path(path: list[dict]) -> dict | None:
    for idx in range(len(path) - 1, -1, -1):
        if path[idx].get("type") == "compaction":
            return path[idx]
    return None


def _append_message_entries(
    base: list[AgentMessage],
    path: list[dict],
) -> list[AgentMessage]:
    outgoing = list(base)
    for row in path:
        outgoing = _append_message_row(outgoing, row)
    return outgoing


def _append_message_row(
    messages: list[AgentMessage],
    row: dict,
) -> list[AgentMessage]:
    if row.get("type") != "message":
        return messages
    payload = row.get("message")
    if isinstance(payload, dict):
        messages.append(message_from_dict(payload))
    return messages


def _infer_leaf_id(entries: list[dict]) -> str | None:
    """Pick the persisted leaf id using the chronologically last body entry."""
    return infer_active_leaf_id(entries)


class SessionManager:
    """Append-only JSONL sessions with compaction-aware replay."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._leaf_id: str | None = None
        if self.path.is_file():
            self._sync_leaf_from_disk()

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
        files = cls.list_paths_for_cwd(cwd_path)
        if not files:
            return None
        return cls(files[0])

    @classmethod
    def list_paths_for_cwd(cls, cwd: str | Path) -> list[Path]:
        cwd_path = Path(cwd).resolve()
        session_dir = get_sessions_dir() / _cwd_key(cwd_path)
        if not session_dir.is_dir():
            return []
        return sorted(
            session_dir.glob("*.jsonl"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    @classmethod
    def resolve_session_reference(
        cls,
        cwd: str | Path,
        reference: str,
    ) -> Path | None:
        raw = reference.strip()
        if not raw:
            return None
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        if candidate.suffix != ".jsonl":
            by_id = (get_sessions_dir() / _cwd_key(Path(cwd).resolve())) / (
                f"{raw}.jsonl"
            )
            if by_id.is_file():
                return by_id.resolve()
        return None

    @classmethod
    def fork_from(
        cls,
        source_path: str | Path,
        cwd: str | Path,
        leaf_id: str | None = None,
    ) -> SessionManager:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            msg = f"Session not found: {source}"
            raise FileNotFoundError(msg)
        target = cls.create(cwd)
        source_entries = cls(source).load_entries()
        if leaf_id is None:
            payload = [
                json.dumps(item, ensure_ascii=False)
                for item in source_entries
                if item.get("type") != "session"
            ]
        else:
            payload_entries = clone_branch_entries(source_entries, leaf_id=leaf_id)
            payload = [json.dumps(item, ensure_ascii=False) for item in payload_entries]
        if payload:
            with target.path.open("a", encoding="utf-8") as handle:
                for line in payload:
                    if line.strip():
                        handle.write(line + "\n")
        target._sync_leaf_from_disk()
        return target

    def load_entries(self) -> list[dict]:
        """Parse JSONL lines into dictionaries (skip invalid lines)."""
        if not self.path.is_file():
            return []
        parsed: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    parsed.append(obj)
            except json.JSONDecodeError:
                continue
        return parsed

    def load_messages(self) -> list[AgentMessage]:
        return build_messages_from_entries(self.load_entries())

    def load_tree(self) -> SessionTree:
        return build_session_tree(self.load_entries())

    def append_messages(self, new_messages: list[AgentMessage]) -> None:
        if not new_messages:
            return
        lines: list[str] = []
        for message in new_messages:
            entry = {
                "type": "message",
                "id": str(uuid.uuid4()),
                "parentId": self._leaf_id,
                "timestamp": _utc_now_iso(),
                "message": message_to_dict(message),
            }
            self._leaf_id = entry["id"]
            lines.append(json.dumps(entry, ensure_ascii=False))
        with self.path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")

    def append_compaction(self, result: CompactionResult) -> str:
        """Write a compaction record and advance the leaf to it."""
        entry_id = str(uuid.uuid4())
        entry = {
            "type": "compaction",
            "id": entry_id,
            "parentId": self._leaf_id,
            "timestamp": _utc_now_iso(),
            "summary": result.summary,
            "firstKeptEntryId": result.first_kept_entry_id,
            "tokensBefore": result.tokens_before,
        }
        if result.details:
            entry["details"] = result.details
        self._leaf_id = entry_id
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry_id

    def _sync_leaf_from_disk(self) -> None:
        self._leaf_id = _infer_leaf_id(self.load_entries())
