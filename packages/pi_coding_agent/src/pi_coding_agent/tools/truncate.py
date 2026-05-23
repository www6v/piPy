"""Shared truncation utilities for tool outputs."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024


@dataclass
class TruncationResult:
    content: str
    truncated: bool
    truncated_by: str | None
    total_lines: int
    total_bytes: int
    output_lines: int
    output_bytes: int


def truncate_tail(
    text: str,
    *,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    lines = text.splitlines()
    total_lines = len(lines)
    total_bytes = len(text.encode("utf-8"))
    if total_lines <= max_lines and total_bytes <= max_bytes:
        return TruncationResult(
            content=text,
            truncated=False,
            truncated_by=None,
            total_lines=total_lines,
            total_bytes=total_bytes,
            output_lines=total_lines,
            output_bytes=total_bytes,
        )
    selected = lines
    truncated_by = None
    if total_lines > max_lines:
        selected = lines[-max_lines:]
        truncated_by = "lines"
    content = "\n".join(selected)
    output_bytes = len(content.encode("utf-8"))
    if output_bytes > max_bytes:
        encoded = content.encode("utf-8")
        content = encoded[-max_bytes:].decode("utf-8", errors="ignore")
        truncated_by = "bytes"
        output_bytes = len(content.encode("utf-8"))
        selected = content.splitlines()
    return TruncationResult(
        content=content,
        truncated=True,
        truncated_by=truncated_by,
        total_lines=total_lines,
        total_bytes=total_bytes,
        output_lines=len(selected),
        output_bytes=output_bytes,
    )
