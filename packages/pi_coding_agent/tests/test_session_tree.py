import json

from pi_coding_agent.interactive_mode import format_session_tree
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.session.tree import build_session_tree, clone_branch_entries


def test_build_tree_from_entries() -> None:
    entries = [
        {"type": "session", "id": "sess"},
        {"id": "u1", "type": "message", "role": "user"},
        {"id": "a1", "type": "message", "role": "assistant", "parentId": "u1"},
    ]
    tree = build_session_tree(entries)
    assert tree.root_ids == ["u1"]
    assert tree.children["u1"] == ["a1"]


def test_clone_branch_preserves_path_order() -> None:
    entries = [
        {"type": "session", "id": "sess"},
        {"id": "u1", "type": "message"},
        {"id": "a1", "type": "message", "parentId": "u1"},
        {"id": "u2", "type": "message", "parentId": "a1"},
        {"id": "a2", "type": "message", "parentId": "u2"},
        {"id": "u3", "type": "message", "parentId": "a1"},
    ]
    branch = clone_branch_entries(entries, leaf_id="u3")
    assert [item["id"] for item in branch] == ["u1", "a1", "u3"]


def test_format_session_tree_shows_active_leaf() -> None:
    entries = [
        {"type": "session", "id": "sess"},
        {"id": "u1", "type": "message"},
        {"id": "a1", "type": "message", "parentId": "u1"},
    ]
    rendered = format_session_tree(entries)
    assert "Session tree:" in rendered
    assert "u1 (message)" in rendered
    assert "a1 (message) <active>" in rendered
    assert "Active leaf: a1" in rendered


def test_fork_from_clones_selected_branch(tmp_path, monkeypatch) -> None:
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    source = SessionManager.create(tmp_path)
    source_entries = [
        {"type": "message", "id": "u1", "parentId": None},
        {"type": "message", "id": "a1", "parentId": "u1"},
        {"type": "message", "id": "u2", "parentId": "a1"},
        {"type": "message", "id": "u3", "parentId": "a1"},
    ]
    with source.path.open("a", encoding="utf-8") as handle:
        for entry in source_entries:
            handle.write(json.dumps(entry) + "\n")

    cloned = SessionManager.fork_from(source.path, tmp_path, leaf_id="u3")
    body_ids = [
        row["id"]
        for row in cloned.load_entries()
        if isinstance(row, dict) and row.get("type") == "message"
    ]
    assert body_ids == ["u1", "a1", "u3"]
