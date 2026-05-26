"""Session tree helpers for branch-aware navigation and cloning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionTree:
    """Deterministic parent/child index built from session entries."""

    root_ids: list[str]
    children: dict[str, list[str]]
    parent_by_id: dict[str, str | None]
    entries_by_id: dict[str, dict]


def _body_entries(entries: list[dict]) -> list[dict]:
    return [entry for entry in entries if entry.get("type") != "session"]


def build_session_tree(entries: list[dict]) -> SessionTree:
    """Build a deterministic tree using entry id/parentId relationships."""

    ordered_entries = _body_entries(entries)
    ordered_ids: list[str] = []
    entries_by_id: dict[str, dict] = {}
    parent_by_id: dict[str, str | None] = {}

    for entry in ordered_entries:
        raw_id = entry.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            continue
        ordered_ids.append(raw_id)
        entries_by_id[raw_id] = entry
        raw_parent = entry.get("parentId")
        if isinstance(raw_parent, str) and raw_parent:
            parent_by_id[raw_id] = raw_parent
        else:
            parent_by_id[raw_id] = None

    children: dict[str, list[str]] = {entry_id: [] for entry_id in ordered_ids}
    root_ids: list[str] = []
    for entry_id in ordered_ids:
        parent_id = parent_by_id.get(entry_id)
        if parent_id is None or parent_id not in entries_by_id or parent_id == entry_id:
            root_ids.append(entry_id)
            continue
        children[parent_id].append(entry_id)

    return SessionTree(
        root_ids=root_ids,
        children=children,
        parent_by_id=parent_by_id,
        entries_by_id=entries_by_id,
    )


def infer_active_leaf_id(entries: list[dict]) -> str | None:
    """Infer the active leaf id using the latest body entry id."""

    for row in reversed(_body_entries(entries)):
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id:
            return row_id
    return None


def branch_entry_ids(tree: SessionTree, leaf_id: str) -> list[str]:
    """Return ids on the root->leaf path for a selected leaf."""

    if leaf_id not in tree.entries_by_id:
        raise ValueError(f"Unknown entry id: {leaf_id}")

    path_rev: list[str] = []
    visited: set[str] = set()
    cur: str | None = leaf_id
    while cur is not None:
        if cur in visited:
            raise ValueError(f"Cycle detected while resolving path for {leaf_id}")
        visited.add(cur)
        path_rev.append(cur)
        parent_id = tree.parent_by_id.get(cur)
        if parent_id is None or parent_id not in tree.entries_by_id:
            break
        cur = parent_id

    path_rev.reverse()
    return path_rev


def clone_branch_entries(entries: list[dict], leaf_id: str | None = None) -> list[dict]:
    """Clone branch entries in path order from root to selected leaf."""

    tree = build_session_tree(entries)
    selected_leaf = leaf_id or infer_active_leaf_id(entries)
    if selected_leaf is None:
        return []
    path_ids = branch_entry_ids(tree, selected_leaf)
    return [dict(tree.entries_by_id[item_id]) for item_id in path_ids]
