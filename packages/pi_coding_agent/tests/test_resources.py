"""Skills / prompts / extensions integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pi_ai.providers.faux import (
    faux_assistant_message,
    faux_text,
    register_faux_provider,
    set_faux_responses,
)
from pi_ai.types import ToolCall

from pi_coding_agent.sdk import CreateAgentSessionOptions, create_agent_session


@pytest.mark.asyncio
async def test_prompt_template_expansion(tmp_path: Path) -> None:
    prompts_dir = tmp_path / ".pi" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "review.md").write_text(
        "---\n"
        "description: review helper\n"
        "---\n"
        "Please review $1 and also $ARGUMENTS.\n",
        encoding="utf-8",
    )

    register_faux_provider(
        models=[{"id": "resources-test", "name": "resources-test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    set_faux_responses([faux_assistant_message([faux_text("ok")])])
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=tmp_path,
            model="faux/resources-test",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    session = result.session
    await session.prompt('/review src/app.py "extra checks"')
    await session.wait_for_idle()
    first = session.messages[0]
    assert first.role == "user"
    assert "src/app.py" in str(first.content)
    assert "extra checks" in str(first.content)


@pytest.mark.asyncio
async def test_skill_command_expansion_and_system_prompt_skills_xml(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / ".pi" / "skills" / "deploy-check"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: deploy-check\n"
        "description: Validate deploy prerequisites\n"
        "---\n"
        "# Deploy check\n"
        "Run deployment validations.\n",
        encoding="utf-8",
    )
    register_faux_provider(
        models=[{"id": "skills-test", "name": "skills-test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    set_faux_responses([faux_assistant_message([faux_text("ok")])])
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=tmp_path,
            model="faux/skills-test",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    session = result.session
    assert "<available_skills>" in session.agent.state.system_prompt
    assert "deploy-check" in session.agent.state.system_prompt
    await session.prompt("/skill:deploy-check prod")
    await session.wait_for_idle()
    first = session.messages[0]
    assert first.role == "user"
    assert "Deploy check" in str(first.content)
    assert "User: prod" in str(first.content)


@pytest.mark.asyncio
async def test_extension_command_and_get_commands(tmp_path: Path) -> None:
    ext_dir = tmp_path / ".pi" / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "mode_ext.py").write_text(
        "def register(pi):\n"
        "    def _handler(args, ctx):\n"
        "        ctx.session.set_thinking_level('high')\n"
        "    pi.register_command('set-high', description='set thinking high', handler=_handler)\n",
        encoding="utf-8",
    )

    register_faux_provider(
        models=[{"id": "extensions-test", "name": "extensions-test"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    set_faux_responses([faux_assistant_message([faux_text("ok")])])
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=tmp_path,
            model="faux/extensions-test",
            provider="faux",
            tools=[],
            in_memory=True,
            thinking_level="off",
        )
    )
    session = result.session
    before_count = len(session.messages)
    await session.prompt("/set-high")
    await session.wait_for_idle()
    assert session.thinking_level == "high"
    assert len(session.messages) == before_count
    commands = session.get_commands()
    assert any(item["name"] == "set-high" and item["source"] == "extension" for item in commands)


@pytest.mark.asyncio
async def test_extension_duplicate_command_suffix_and_invocation(tmp_path: Path) -> None:
    ext_dir = tmp_path / ".pi" / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "ext_a.py").write_text(
        "def register(pi):\n"
        "    def _handler(args, ctx):\n"
        "        ctx.session.set_thinking_level('low')\n"
        "    pi.register_command('set-level', description='set low', handler=_handler)\n",
        encoding="utf-8",
    )
    (ext_dir / "ext_b.py").write_text(
        "def register(pi):\n"
        "    def _handler(args, ctx):\n"
        "        ctx.session.set_thinking_level('high')\n"
        "    pi.register_command('set-level', description='set high', handler=_handler)\n",
        encoding="utf-8",
    )
    register_faux_provider(
        models=[{"id": "ext-collision", "name": "ext-collision"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    set_faux_responses([faux_assistant_message([faux_text("ok")])])
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=tmp_path,
            model="faux/ext-collision",
            provider="faux",
            tools=[],
            in_memory=True,
            thinking_level="off",
        )
    )
    session = result.session
    commands = session.get_commands()
    names = {item["name"] for item in commands if item["source"] == "extension"}
    assert "set-level:1" in names
    assert "set-level:2" in names
    await session.prompt("/set-level:2")
    assert session.thinking_level == "high"


@pytest.mark.asyncio
async def test_extension_tool_call_and_tool_result_hooks(tmp_path: Path) -> None:
    ext_dir = tmp_path / ".pi" / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "tool_hooks.py").write_text(
        "from pi_agent.types import AgentToolResult\n"
        "from pi_ai.types import TextContent\n"
        "\n"
        "class EchoExtTool:\n"
        "    name = 'echo_ext'\n"
        "    description = 'echo ext'\n"
        "    parameters = {\n"
        "        'type': 'object',\n"
        "        'properties': {'text': {'type': 'string'}},\n"
        "        'required': ['text'],\n"
        "    }\n"
        "    execution_mode = 'parallel'\n"
        "\n"
        "    async def execute(self, tool_call_id, args, signal=None, on_update=None):\n"
        "        del tool_call_id, signal, on_update\n"
        "        return AgentToolResult(content=[TextContent(text=args['text'])])\n"
        "\n"
        "def register(pi):\n"
        "    pi.register_tool(EchoExtTool())\n"
        "\n"
        "    def _on_tool_call(event, ctx):\n"
        "        del ctx\n"
        "        if event.get('toolName') == 'echo_ext':\n"
        "            text = event.get('input', {}).get('text', '')\n"
        "            return {'args': {'text': f'{text}-call'}}\n"
        "\n"
        "    def _on_tool_result(event, ctx):\n"
        "        del ctx\n"
        "        if event.get('toolName') == 'echo_ext':\n"
        "            content = event.get('content', [])\n"
        "            if content:\n"
        "                text = content[0].get('text', '')\n"
        "                return {'content': [{'type': 'text', 'text': f'{text}-result'}]}\n"
        "\n"
        "    pi.on('tool_call', _on_tool_call)\n"
        "    pi.on('tool_result', _on_tool_result)\n",
        encoding="utf-8",
    )
    register_faux_provider(
        models=[{"id": "ext-tool-hooks", "name": "ext-tool-hooks"}],
        handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
    )
    set_faux_responses(
        [
            faux_assistant_message(
                [ToolCall(id="t1", name="echo_ext", arguments={"text": "base"})],
                stop_reason="toolUse",
            ),
            faux_assistant_message([faux_text("done")]),
        ]
    )
    result = await create_agent_session(
        CreateAgentSessionOptions(
            cwd=tmp_path,
            model="faux/ext-tool-hooks",
            provider="faux",
            tools=[],
            in_memory=True,
        )
    )
    session = result.session
    await session.prompt("run ext tool")
    await session.wait_for_idle()
    tool_results = [msg for msg in session.messages if msg.role == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0].content[0].text == "base-call-result"
