"""Path resolution relative to session cwd."""

from __future__ import annotations

from pathlib import Path


def resolve_under_cwd(cwd: Path, path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    resolved = candidate.resolve()
    cwd_resolved = cwd.resolve()
    if resolved != cwd_resolved and cwd_resolved not in resolved.parents:
        raise ValueError(f"Path escapes working directory: {path}")
    return resolved
