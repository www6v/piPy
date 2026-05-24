"""Minimal Markdown frontmatter parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrontmatterDocument:
    """Parsed frontmatter document."""

    frontmatter: dict[str, str]
    body: str


def parse_frontmatter(raw: str) -> FrontmatterDocument:
    """Parse YAML-like frontmatter from markdown text.

    The parser intentionally supports only simple ``key: value`` pairs because
    piPy currently needs lightweight metadata extraction for prompts/skills.
    """

    if not raw.startswith("---\n"):
        return FrontmatterDocument(frontmatter={}, body=raw)

    end_marker = "\n---\n"
    end_index = raw.find(end_marker, 4)
    if end_index == -1:
        return FrontmatterDocument(frontmatter={}, body=raw)

    head = raw[4:end_index]
    body = raw[end_index + len(end_marker) :]
    parsed: dict[str, str] = {}
    for line in head.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return FrontmatterDocument(frontmatter=parsed, body=body)
