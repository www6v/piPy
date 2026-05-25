"""Smoke test for shipped extension example."""

from __future__ import annotations

import sys
from pathlib import Path

from pi_coding_agent.rpc_client import RpcClient


def test_demo_extension_smoke_via_rpc_reload(tmp_path: Path) -> None:
    demo_prompts = tmp_path / ".pi" / "demo-prompts"
    demo_prompts.mkdir(parents=True, exist_ok=True)
    (demo_prompts / "demo_template.md").write_text(
        "---\n"
        "description: demo template\n"
        "---\n"
        "Demo template body.\n",
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[3]
    extension_path = repo_root / "examples" / "extensions" / "demo_extension.py"
    assert extension_path.is_file()

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
        "faux/demo-extension-smoke",
        "--tools",
        "read,bash",
        "--extension",
        str(extension_path),
    ]
    client = RpcClient(command=cli_cmd, cwd=tmp_path)
    client.start()
    try:
        commands, _events = client.request({"id": "gc", "type": "get_commands"})
        names = {item["name"] for item in commands["data"]["commands"]}
        assert "demo-mode" in names
        assert "demo_template" in names

        # Update discovered prompt and verify reload reflects changes.
        (demo_prompts / "new_prompt.md").write_text(
            "---\n"
            "description: new prompt\n"
            "---\n"
            "New prompt body.\n",
            encoding="utf-8",
        )
        reloaded, _events = client.request({"id": "reload", "type": "reload"})
        assert reloaded["success"] is True
        reloaded_names = {item["name"] for item in reloaded["data"]["commands"]}
        assert "new_prompt" in reloaded_names
    finally:
        client.close()
