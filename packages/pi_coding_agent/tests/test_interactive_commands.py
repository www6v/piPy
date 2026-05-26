"""Interactive slash-command behavior tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pi_ai.types import AssistantMessage, TextContent, Usage

from pi_coding_agent import interactive_mode
from pi_coding_agent.interactive_mode import InteractiveOptions, run_interactive_mode
from pi_coding_agent.session.manager import SessionManager


class _DummyState:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt


class _DummyAgent:
    def __init__(self, system_prompt: str = "system") -> None:
        self.state = _DummyState(system_prompt)


class _DummyModel:
    provider = "faux"
    id = "interactive-cmd"


class _DummySession:
    def __init__(self, cwd: Path, session_file: str | None) -> None:
        self.model = _DummyModel()
        self.thinking_level = None
        self.cwd = cwd
        self.session_file = session_file
        self.is_streaming = False
        self.agent = _DummyAgent()
        self.messages = []
        self.new_session_calls = 0
        self.export_calls: list[str | None] = []

    async def new_session(self, *, cwd: Path | None = None) -> None:
        self.new_session_calls += 1
        target = cwd or self.cwd
        manager = SessionManager.create(target)
        self.session_file = str(manager.path)
        self.messages = []

    def export_html(self, output_path: str | None = None) -> str:
        self.export_calls.append(output_path)
        return str((self.cwd / (output_path or "session.html")).resolve())


class _CreateResult:
    def __init__(self, session: _DummySession) -> None:
        self.session = session
        self.warning = None


def _build_options() -> InteractiveOptions:
    return InteractiveOptions(
        model_pattern="faux/interactive-cmd",
        system_prompt=None,
        tools=["read"],
        api_key=None,
        provider="faux",
        thinking_level=None,
        verbose=False,
        continue_session=False,
        session_path=None,
    )


def _feed_lines(lines: list[str]):
    async def _pump(queue: asyncio.Queue[str | None]) -> None:
        for line in lines:
            await queue.put(line)
        await queue.put(None)

    return _pump


@pytest.mark.asyncio
async def test_name_usage_message(monkeypatch, tmp_path: Path, capsys) -> None:
    session = _DummySession(tmp_path, str(SessionManager.create(tmp_path).path))

    async def _create_bundle(_options):
        return session

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/name", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    captured = capsys.readouterr()
    assert code == 0
    assert "Usage: /name <name>" in captured.err


@pytest.mark.asyncio
async def test_new_command_creates_new_persisted_session(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session = _DummySession(tmp_path, str(SessionManager.create(tmp_path).path))
    original_session_file = session.session_file

    async def _create_bundle(_options):
        return session

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/new", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    captured = capsys.readouterr()
    assert code == 0
    assert session.new_session_calls == 1
    assert session.session_file is not None
    assert session.session_file != original_session_file
    assert "Started new session:" in captured.out


@pytest.mark.asyncio
async def test_name_command_persists_header(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    manager = SessionManager.create(tmp_path)
    session = _DummySession(tmp_path, str(manager.path))

    async def _create_bundle(_options):
        return session

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/name sprint-demo", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    assert code == 0
    captured = capsys.readouterr()
    assert "Session name set to 'sprint-demo'." in captured.out
    header = json.loads(manager.path.read_text(encoding="utf-8").splitlines()[0])
    assert header["name"] == "sprint-demo"


@pytest.mark.asyncio
async def test_copy_command_handles_missing_clipboard(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session = _DummySession(tmp_path, str(SessionManager.create(tmp_path).path))
    session.messages = [
        AssistantMessage(
            content=[TextContent(text="copy me")],
            api="openai-completions",
            provider="faux",
            model="interactive-cmd",
            usage=Usage(),
            stop_reason="stop",
        )
    ]

    async def _create_bundle(_options):
        return session

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(
        interactive_mode,
        "_copy_text_to_clipboard",
        lambda _text: (False, "Clipboard unavailable (test)."),
    )
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/copy", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    captured = capsys.readouterr()
    assert code == 0
    assert "Clipboard unavailable (test)." in captured.err


@pytest.mark.asyncio
async def test_export_command_passes_optional_path(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session = _DummySession(tmp_path, str(SessionManager.create(tmp_path).path))

    async def _create_bundle(_options):
        return session

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/export out.html", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    captured = capsys.readouterr()
    assert code == 0
    assert session.export_calls == ["out.html"]
    assert "Exported:" in captured.out
    assert "out.html" in captured.out


@pytest.mark.asyncio
async def test_resume_command_uses_picker_and_switches_session(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    session = _DummySession(tmp_path, str(SessionManager.create(tmp_path).path))
    resumed_manager = SessionManager.create(tmp_path)
    resumed = _DummySession(tmp_path, str(resumed_manager.path))
    create_calls = []

    async def _create_bundle(_options):
        return session

    async def _create_agent_session(options):
        create_calls.append(options.session_path)
        return _CreateResult(resumed)

    async def _pick(_cwd: Path, _line_queue):
        return str(resumed_manager.path)

    monkeypatch.setattr(interactive_mode, "create_agent_session_bundle", _create_bundle)
    monkeypatch.setattr(interactive_mode, "create_agent_session", _create_agent_session)
    monkeypatch.setattr(interactive_mode, "_pick_resume_session_path", _pick)
    monkeypatch.setattr(
        interactive_mode,
        "_pump_stdin_lines",
        _feed_lines(["/resume", "/quit"]),
    )

    code = await run_interactive_mode(_build_options())
    captured = capsys.readouterr()
    assert code == 0
    assert create_calls == [str(resumed_manager.path)]
    assert f"Resumed: {resumed_manager.path}" in captured.out


@pytest.mark.asyncio
async def test_pick_resume_session_path_non_tty_uses_latest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first = SessionManager.create(tmp_path)
    second = SessionManager.create(tmp_path)
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    class _FakeStdin:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(interactive_mode.sys, "stdin", _FakeStdin())

    selected = await interactive_mode._pick_resume_session_path(tmp_path, queue)
    assert selected == str(second.path)
    assert selected != str(first.path)
