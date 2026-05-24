import json

from pi_agent.agent_loop import prompt_text
from pi_coding_agent.session.manager import SessionManager


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
