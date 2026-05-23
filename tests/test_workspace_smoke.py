"""Smoke tests for the uv workspace installs."""

from __future__ import annotations


def test_import_workspace_packages() -> None:
    """Ensure editable workspace members resolve on PYTHONPATH."""
    import pi_ai
    import pi_agent
    import pi_coding_agent

    assert pi_ai.__doc__ is not None
    assert pi_agent.__doc__ is not None
    assert pi_coding_agent.__doc__ is not None
