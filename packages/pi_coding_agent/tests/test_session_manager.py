import json

from pi_agent.agent_loop import prompt_text
from pi_agent.types import AgentMessage
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.session.types import CompactionResult


def _user_text(message: AgentMessage) -> str:
    assert message.role == "user"
    body = getattr(message, "content", "")
    if isinstance(body, str):
        return body
    return "".join(block.text for block in body)


def test_session_round_trip(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    manager = SessionManager.create(tmp_path)
    user = prompt_text("hello")
    manager.append_messages([user])
    loaded = manager.load_messages()
    assert len(loaded) == 1
    assert loaded[0].role == "user"
    lines = manager.path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["type"] == "session"
    assert header["cwd"] == str(tmp_path.resolve())


def test_latest_for_cwd(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    first = SessionManager.create(tmp_path)
    second = SessionManager.create(tmp_path)
    latest = SessionManager.latest_for_cwd(tmp_path)
    assert latest is not None
    assert latest.path == second.path


def test_compaction_load_messages_keeps_suffix(tmp_path, monkeypatch):
    sessions_root = tmp_path / "sessions"
    monkeypatch.setattr(
        "pi_coding_agent.session.manager.get_sessions_dir",
        lambda: sessions_root,
    )
    manager = SessionManager.create(tmp_path)
    for marker in ["m1", "m2", "m3", "m4", "m5"]:
        manager.append_messages([prompt_text(marker)])
    parsed = manager.load_entries()
    message_rows = [
        row for row in parsed if isinstance(row, dict) and row.get("type") == "message"
    ]
    fourth_id = message_rows[3]["id"]
    manager.append_compaction(
        CompactionResult(
            summary="Compact note.",
            first_kept_entry_id=fourth_id,
            tokens_before=420,
            details={"readFiles": ["x.py"], "modifiedFiles": ["y.py"]},
        ),
    )
    msgs = manager.load_messages()
    assert len(msgs) == 3
    assert msgs[0].role == "user"
    summary_text = _user_text(msgs[0])
    assert summary_text.startswith("Previous conversation summary:")
    assert "Compact note." in summary_text
    assert _user_text(msgs[1]) == "m4"
    assert _user_text(msgs[2]) == "m5"
