import json

from pi_coding_agent.auth.storage import AuthStorage


def test_auth_storage_reads_api_key(tmp_path):
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps({"anthropic": {"type": "api_key", "key": "secret-key"}}),
        encoding="utf-8",
    )
    storage = AuthStorage(path)
    assert storage.get_api_key("anthropic") == "secret-key"
    assert storage.get_api_key("openai") is None
