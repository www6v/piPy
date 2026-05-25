"""Resource diagnostics models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResourceDiagnostic:
    """Non-fatal resource warning/error/collision."""

    type: str
    message: str
    path: str
    collision: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "message": self.message,
            "path": self.path,
        }
        if self.collision is not None:
            payload["collision"] = dict(self.collision)
        return payload
