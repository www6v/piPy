"""RPC steer / follow_up / queue modes (subprocess harness)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pi_coding_agent.rpc_client import RpcClient


def _read_json_line(proc) -> dict | None:
    if proc.stdout is None:
        return None
    raw = proc.stdout.readline()
    if not raw:
        return None
    line = raw.rstrip("\n").rstrip("\r")
    return json.loads(line)


def test_rpc_steering_and_state(tmp_path: Path) -> None:
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
        "faux/rpc_steering_smoke",
        "--tools",
        "read",
    ]

    client = RpcClient(command=cli_cmd, cwd=tmp_path)
    client.start()

    try:
        assert client._process is not None
        assert client._process.stdin is not None
        steer_cmd = (
            json.dumps(
                {"id": "rq-steer", "type": "steer", "message": "watch"},
                ensure_ascii=False,
            )
            + "\n"
        )
        client._process.stdin.write(steer_cmd)
        client._process.stdin.flush()

        saw_queue = False
        response = None

        while response is None:
            payload = _read_json_line(client._process)
            assert payload is not None
            if payload.get("type") == "queue_update":
                saw_queue = True
                steer_list = payload.get("steering", [])
                if steer_list == ["watch"]:
                    pass  # Preferred snapshot; tolerate extra updates.
                continue
            if payload.get("type") == "response" and payload.get("id") == "rq-steer":
                response = payload

        assert response is not None
        assert response.get("success") is True

        client.send({"id": "rq-state", "type": "get_state"})
        state_response = None
        while state_response is None:
            payload = _read_json_line(client._process)
            assert payload is not None
            if (
                payload.get("type") == "response"
                and payload.get("id") == "rq-state"
            ):
                state_response = payload

        pending = state_response["data"]["pendingMessageCount"]
        assert isinstance(pending, int)
        assert pending >= 1

        client.send(
            {
                "id": "rq-mode",
                "type": "set_steering_mode",
                "mode": "all",
            }
        )

        mode_response = None
        while mode_response is None:
            payload = _read_json_line(client._process)
            assert payload is not None
            if (
                payload.get("type") == "response"
                and payload.get("id") == "rq-mode"
            ):
                mode_response = payload

        assert mode_response["success"] is True

        if not saw_queue:
            pytest.fail("Never observed queue_update on stdout")

    finally:
        client.close()
