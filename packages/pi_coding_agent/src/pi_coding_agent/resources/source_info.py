"""Resource source metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceInfo:
    """Resource provenance metadata."""

    path: str
    source: str
    scope: str
    origin: str
    base_dir: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "path": self.path,
            "source": self.source,
            "scope": self.scope,
            "origin": self.origin,
        }
        if self.base_dir:
            payload["baseDir"] = self.base_dir
        return payload


def classify_source_info(
    *,
    path: Path,
    cwd: Path,
    agent_dir: Path,
    fallback_base_dir: Path | None = None,
) -> SourceInfo:
    """Classify a resource path into user/project/temporary scope."""

    resolved = path.resolve()
    resolved_cwd = cwd.resolve()
    resolved_agent = agent_dir.resolve()
    agent_roots = [
        resolved_agent / "skills",
        resolved_agent / "prompts",
        resolved_agent / "extensions",
        resolved_agent.parent / ".agents" / "skills",
    ]
    project_roots = [
        resolved_cwd / ".pi" / "skills",
        resolved_cwd / ".pi" / "prompts",
        resolved_cwd / ".pi" / "extensions",
    ]
    for root in agent_roots:
        if _is_under(resolved, root):
            return SourceInfo(
                path=str(path),
                source="local",
                scope="user",
                origin="top-level",
                base_dir=str(root),
            )
    for root in project_roots:
        if _is_under(resolved, root):
            return SourceInfo(
                path=str(path),
                source="local",
                scope="project",
                origin="top-level",
                base_dir=str(root),
            )
    if _is_under(resolved, resolved_cwd):
        return SourceInfo(
            path=str(path),
            source="local",
            scope="project",
            origin="top-level",
            base_dir=str(resolved_cwd),
        )
    base_dir = (
        str(fallback_base_dir.resolve())
        if fallback_base_dir is not None
        else str(resolved.parent)
    )
    return SourceInfo(
        path=str(path),
        source="local",
        scope="temporary",
        origin="top-level",
        base_dir=base_dir,
    )


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
