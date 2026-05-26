"""Demo extension for piPy resource + reload workflows."""

from __future__ import annotations


def register(pi):
    """Register demo command and discovery hooks."""

    def on_resources_discover(event, ctx):
        del event
        return {"promptPaths": [f"{ctx.cwd}/.pi/demo-prompts"]}

    def on_tool_call(event, ctx):
        del ctx
        if event.get("toolName") != "bash":
            return None
        cmd = event.get("input", {}).get("command", "")
        if isinstance(cmd, str) and "rm -rf" in cmd:
            return {"block": True, "reason": "demo_extension blocked dangerous bash"}
        return None

    def command_demo_mode(args, ctx):
        del args
        ctx.session.set_thinking_level("high")

    pi.on("resources_discover", on_resources_discover)
    pi.on("tool_call", on_tool_call)
    pi.register_command(
        "demo-mode",
        description="Set thinking level to high (demo)",
        handler=command_demo_mode,
    )
