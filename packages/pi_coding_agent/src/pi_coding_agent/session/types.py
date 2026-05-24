"""Typed session records for compaction and JSONL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class CompactionDetails(TypedDict, total=False):
    """Optional compaction metadata stored beside the session entry."""

    readFiles: list[str]
    modifiedFiles: list[str]


@dataclass(frozen=True)
class CompactionResult:
    """Arguments for recording a compaction in the JSONL session."""

    summary: str
    first_kept_entry_id: str
    tokens_before: int
    details: dict[str, object] = field(default_factory=dict)


class CompactionEntry(TypedDict, total=False):
    """Compaction record shape as serialized in JSONL (pi-compatible)."""

    type: str
    id: str
    parentId: str | None
    timestamp: str
    summary: str
    firstKeptEntryId: str
    tokensBefore: int
    details: dict[str, object]
    fromHook: bool
