"""Shared utilities for compaction (pi: compaction/utils.ts subset)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pi_ai.types import AssistantMessage

from pi_agent.types import AgentMessage


@dataclass
class FileOperations:
    """Tracked file paths touched during a turn."""

    read: set[str] = field(default_factory=set)
    edited: set[str] = field(default_factory=set)
    written: set[str] = field(default_factory=set)


def extract_file_ops_from_message(message: AgentMessage) -> FileOperations:
    """Extract read/write/edit paths from assistant tool calls."""
    ops = FileOperations()
    if message.role != "assistant":
        return ops
    if not isinstance(message, AssistantMessage):
        return ops
    for block in message.content:
        if block.type != "toolCall":
            continue
        raw_path = dict(block.arguments).get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = raw_path
        if block.name == "read":
            ops.read.add(path)
        elif block.name == "write":
            ops.written.add(path)
        elif block.name == "edit":
            ops.edited.add(path)
    return ops


def compute_file_lists(
    file_ops: FileOperations,
) -> dict[str, list[str]]:
    """Compute read-only and modified file lists."""
    modified = file_ops.edited | file_ops.written
    read_only = sorted(f for f in file_ops.read if f not in modified)
    modified_files = sorted(modified)
    return {"readFiles": read_only, "modifiedFiles": modified_files}
