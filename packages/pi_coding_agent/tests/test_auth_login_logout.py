from pi_coding_agent.auth.storage import AuthStorage
from pi_coding_agent.interactive_mode import _handle_auth_command
from pi_coding_agent.modes.rpc_mode import _handle_auth_rpc_command


def test_login_logout_roundtrip(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")
    storage.set_api_key("openai", "sk-test")
    assert storage.get_api_key("openai") == "sk-test"
    removed = storage.logout("openai")
    assert removed is True
    assert storage.get_api_key("openai") is None


def test_logout_missing_provider_is_safe(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")
    storage.set_api_key("openai", "sk-test")
    removed = storage.logout("anthropic")
    assert removed is False
    assert storage.get_api_key("openai") == "sk-test"


def test_interactive_login_logout_commands(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")

    handled, message, is_error = _handle_auth_command(
        "/login openai sk-live",
        storage,
    )
    assert handled is True
    assert is_error is False
    assert "Stored API key" in message
    assert storage.get_api_key("openai") == "sk-live"

    handled, message, is_error = _handle_auth_command("/logout openai", storage)
    assert handled is True
    assert is_error is False
    assert "Removed API key" in message
    assert storage.get_api_key("openai") is None


def test_interactive_command_usage_errors(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")

    handled, message, is_error = _handle_auth_command("/login", storage)
    assert handled is True
    assert is_error is True
    assert message == "Usage: /login <provider> <key>"

    handled, message, is_error = _handle_auth_command("/logout", storage)
    assert handled is True
    assert is_error is True
    assert message == "Usage: /logout <provider>"


def test_rpc_login_logout_commands(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")

    login = _handle_auth_rpc_command(
        {"id": "r1", "type": "login", "provider": "openai", "key": "sk-rpc"},
        "r1",
        storage,
    )
    assert login is not None
    assert login["type"] == "response"
    assert login["command"] == "login"
    assert login["success"] is True
    assert storage.get_api_key("openai") == "sk-rpc"

    logout = _handle_auth_rpc_command(
        {"id": "r2", "type": "logout", "provider": "openai"},
        "r2",
        storage,
    )
    assert logout is not None
    assert logout["type"] == "response"
    assert logout["command"] == "logout"
    assert logout["success"] is True
    assert logout["data"]["removed"] is True
    assert storage.get_api_key("openai") is None


def test_rpc_command_validation_errors(tmp_path) -> None:
    storage = AuthStorage(path=tmp_path / "auth.json")

    login = _handle_auth_rpc_command({"id": "r1", "type": "login"}, "r1", storage)
    assert login is not None
    assert login["success"] is False
    assert login["error"] == "provider is required"

    logout = _handle_auth_rpc_command({"id": "r2", "type": "logout"}, "r2", storage)
    assert logout is not None
    assert logout["success"] is False
    assert logout["error"] == "provider is required"
