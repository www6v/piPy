"""RPC mode unit tests."""

import json
import sys
from pathlib import Path

from pi_ai.types import AssistantMessage, TextContent, Usage, UserMessage

from pi_coding_agent.modes.rpc_mode import _error, _success
from pi_coding_agent.rpc_client import RpcClient
from pi_coding_agent.session.manager import SessionManager


def test_rpc_response_success() -> None:
    payload = _success("r1", "prompt")
    assert payload["type"] == "response"
    assert payload["success"] is True
    assert payload["id"] == "r1"
    assert payload["command"] == "prompt"


def test_rpc_response_error() -> None:
    payload = _error("r2", "prompt", "failed")
    assert payload["success"] is False
    assert payload["error"] == "failed"


def test_rpc_command_json_roundtrip() -> None:
    line = json.dumps({"id": "1", "type": "get_state"})
    command = json.loads(line.rstrip("\n").rstrip("\r"))
    assert command["type"] == "get_state"


def test_rpc_compact_subprocess_returns_summary_and_metadata(
    tmp_path: Path,
) -> None:
    """Compaction via RPC returns summary tokens and cut id (faux backend)."""

    (tmp_path / ".pi").mkdir(parents=True, exist_ok=True)
    settings_payload = {"compaction": {"keepRecentTokens": 220}}
    (tmp_path / ".pi" / "settings.json").write_text(
        json.dumps(settings_payload),
        encoding="utf-8",
    )

    manager = SessionManager.create(tmp_path)
    filler = "x" * 200
    blob: list[UserMessage | AssistantMessage] = []
    for turn in range(4):
        blob.append(UserMessage(content=f"{filler} user-{turn} {filler}"))
        blob.append(
            AssistantMessage(
                content=[
                    TextContent(text=f"{filler} reply-{turn} {filler}")
                ],
                api="openai-completions",
                provider="faux",
                model="stub",
                usage=Usage(),
                stop_reason="stop",
            )
        )
    manager.append_messages(blob)

    cli_cmd = [
        sys.executable,
        "-m",
        "pi_coding_agent.cli",
        "--mode",
        "rpc",
        "--session",
        str(manager.path.resolve()),
        "--no-context-files",
        "--provider",
        "faux",
        "--model",
        "faux/compact_rpc_integration",
        "--tools",
        "read",
    ]
    client = RpcClient(command=cli_cmd, cwd=tmp_path)
    client.start()
    try:
        response, events = client.request({"id": "c1", "type": "compact"})
    finally:
        client.close()

    assert any(e.get("type") == "compaction_start" for e in events)
    assert response["success"] is True
    assert response["command"] == "compact"
    data = response["data"]
    assert data["summary"] == "ok"
    assert isinstance(data["firstKeptEntryId"], str)
    assert data["firstKeptEntryId"]
    assert isinstance(data["tokensBefore"], int)


def test_rpc_bash_get_stats_and_export_html(tmp_path: Path) -> None:
    cli_cmd = [
        sys.executable,
        "-m",
        "pi_coding_agent.cli",
        "--mode",
        "rpc",
        "--no-context-files",
        "--provider",
        "faux",
        "--model",
        "faux/rpc_bash_stats",
        "--tools",
        "read,bash",
    ]
    client = RpcClient(command=cli_cmd, cwd=tmp_path)
    client.start()
    try:
        bash_resp, _ = client.request(
            {"id": "b1", "type": "bash", "command": "printf hello"},
        )
        stats_resp, _ = client.request({"id": "s1", "type": "get_session_stats"})
        export_path = tmp_path / "rpc-export.html"
        export_resp, _ = client.request(
            {
                "id": "e1",
                "type": "export_html",
                "outputPath": str(export_path),
            },
        )
    finally:
        client.close()

    assert bash_resp["success"] is True
    assert bash_resp["command"] == "bash"
    assert bash_resp["data"]["exitCode"] == 0
    assert "hello" in bash_resp["data"]["output"]

    assert stats_resp["success"] is True
    assert stats_resp["command"] == "get_session_stats"
    assert stats_resp["data"]["totalMessages"] >= 1
    assert stats_resp["data"]["sessionId"]

    assert export_resp["success"] is True
    assert export_resp["command"] == "export_html"
    html_path = Path(export_resp["data"]["path"])
    assert html_path.is_file()
    content = html_path.read_text(encoding="utf-8")
    assert "piPy session export" in content


def test_rpc_get_commands_includes_prompt_template(tmp_path: Path) -> None:
    prompts_dir = tmp_path / ".pi" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "quick.md").write_text(
        "---\n"
        "description: quick helper\n"
        "---\n"
        "Say hi.\n",
        encoding="utf-8",
    )
    cli_cmd = [
        sys.executable,
        "-m",
        "pi_coding_agent.cli",
        "--mode",
        "rpc",
        "--no-session",
        "--no-context-files",
        "--provider",
        "faux",
        "--model",
        "faux/rpc_get_commands",
        "--tools",
        "read",
    ]
    client = RpcClient(command=cli_cmd, cwd=tmp_path)
    client.start()
    try:
        response, _events = client.request({"id": "gc1", "type": "get_commands"})
    finally:
        client.close()
    assert response["success"] is True
    commands = response["data"]["commands"]
    assert any(item["name"] == "quick" and item["source"] == "prompt" for item in commands)
