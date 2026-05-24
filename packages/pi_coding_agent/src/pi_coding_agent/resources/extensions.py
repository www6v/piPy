"""Minimal Python extension runtime for piPy."""

from __future__ import annotations

import importlib.util
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi_agent.types import AgentMessage, AgentTool, AgentToolResult
from pi_ai.types import TextContent


InputAction = dict[str, Any]
CommandHandler = Callable[[str, "ExtensionCommandContext"], Any]
InputHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]
BeforeAgentStartHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]
SessionStartHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]
ContextHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]
ToolCallHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]
ToolResultHandler = Callable[[dict[str, Any], "ExtensionContext"], Any]


@dataclass(frozen=True)
class ExtensionCommand:
    name: str
    description: str | None
    handler: CommandHandler
    extension_path: str


@dataclass(frozen=True)
class ResolvedExtensionCommand:
    name: str
    invocation_name: str
    description: str | None
    handler: CommandHandler
    extension_path: str


class ExtensionContext:
    """Context object passed to extension callbacks."""

    def __init__(self, *, cwd: Path) -> None:
        self.cwd = str(cwd.resolve())


class ExtensionCommandContext(ExtensionContext):
    """Command context for extension slash handlers."""

    def __init__(self, *, cwd: Path, session: Any) -> None:
        super().__init__(cwd=cwd)
        self.session = session

    async def wait_for_idle(self) -> None:
        await self.session.wait_for_idle()


class ExtensionAPI:
    """Registration API exposed to Python extension modules."""

    def __init__(self, extension_path: str) -> None:
        self._extension_path = extension_path
        self.commands: list[ExtensionCommand] = []
        self.tools: list[AgentTool] = []
        self.input_handlers: list[InputHandler] = []
        self.before_agent_start_handlers: list[BeforeAgentStartHandler] = []
        self.session_start_handlers: list[SessionStartHandler] = []
        self.context_handlers: list[ContextHandler] = []
        self.tool_call_handlers: list[ToolCallHandler] = []
        self.tool_result_handlers: list[ToolResultHandler] = []

    def register_command(
        self,
        name: str,
        *,
        handler: CommandHandler,
        description: str | None = None,
    ) -> None:
        self.commands.append(
            ExtensionCommand(
                name=name,
                description=description,
                handler=handler,
                extension_path=self._extension_path,
            )
        )

    def register_tool(self, tool: AgentTool) -> None:
        self.tools.append(tool)

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        if event == "input":
            self.input_handlers.append(handler)
            return
        if event == "before_agent_start":
            self.before_agent_start_handlers.append(handler)
            return
        if event == "session_start":
            self.session_start_handlers.append(handler)
            return
        if event == "context":
            self.context_handlers.append(handler)
            return
        if event == "tool_call":
            self.tool_call_handlers.append(handler)
            return
        if event == "tool_result":
            self.tool_result_handlers.append(handler)
            return
        raise ValueError(f"Unsupported extension event: {event}")


@dataclass
class ExtensionLoadResult:
    command_overrides: list[ExtensionCommand]
    tools: list[AgentTool]
    input_handlers: list[InputHandler]
    before_agent_start_handlers: list[BeforeAgentStartHandler]
    session_start_handlers: list[SessionStartHandler]
    context_handlers: list[ContextHandler]
    tool_call_handlers: list[ToolCallHandler]
    tool_result_handlers: list[ToolResultHandler]
    errors: list[str]


class ExtensionRuntime:
    """Loaded extension metadata and callback dispatch."""

    def __init__(self, *, cwd: Path, load_result: ExtensionLoadResult) -> None:
        self.cwd = cwd.resolve()
        self.commands = load_result.command_overrides
        self.tools = load_result.tools
        self.input_handlers = load_result.input_handlers
        self.before_agent_start_handlers = load_result.before_agent_start_handlers
        self.session_start_handlers = load_result.session_start_handlers
        self.context_handlers = load_result.context_handlers
        self.tool_call_handlers = load_result.tool_call_handlers
        self.tool_result_handlers = load_result.tool_result_handlers
        self.errors = load_result.errors

    def _resolve_commands(self) -> list[ResolvedExtensionCommand]:
        counts: dict[str, int] = {}
        for command in self.commands:
            counts[command.name] = counts.get(command.name, 0) + 1
        seen: dict[str, int] = {}
        resolved: list[ResolvedExtensionCommand] = []
        for command in self.commands:
            index = seen.get(command.name, 0) + 1
            seen[command.name] = index
            invocation = (
                f"{command.name}:{index}"
                if counts.get(command.name, 0) > 1
                else command.name
            )
            resolved.append(
                ResolvedExtensionCommand(
                    name=command.name,
                    invocation_name=invocation,
                    description=command.description,
                    handler=command.handler,
                    extension_path=command.extension_path,
                )
            )
        return resolved

    def list_command_entries(self) -> list[ResolvedExtensionCommand]:
        return self._resolve_commands()

    def get_command(self, name: str) -> ResolvedExtensionCommand | None:
        return next(
            (cmd for cmd in self._resolve_commands() if cmd.invocation_name == name),
            None,
        )

    async def run_command(self, name: str, args: str, session: Any) -> bool:
        command = self.get_command(name)
        if command is None:
            return False
        ctx = ExtensionCommandContext(cwd=self.cwd, session=session)
        out = command.handler(args, ctx)
        if isinstance(out, Awaitable):
            await out
        return True

    async def emit_session_start(self) -> None:
        if not self.session_start_handlers:
            return
        ctx = ExtensionContext(cwd=self.cwd)
        event = {"type": "session_start", "reason": "startup"}
        for handler in self.session_start_handlers:
            out = handler(event, ctx)
            if isinstance(out, Awaitable):
                await out

    async def emit_input(self, text: str, source: str) -> InputAction:
        current_text = text
        ctx = ExtensionContext(cwd=self.cwd)
        for handler in self.input_handlers:
            out = handler({"type": "input", "text": current_text, "source": source}, ctx)
            result = await out if isinstance(out, Awaitable) else out
            if not isinstance(result, dict):
                continue
            action = result.get("action")
            if action == "handled":
                return {"action": "handled"}
            if action == "transform" and isinstance(result.get("text"), str):
                current_text = str(result["text"])
        if current_text != text:
            return {"action": "transform", "text": current_text}
        return {"action": "continue"}

    async def emit_before_agent_start(self, prompt: str, system_prompt: str) -> dict[str, str] | None:
        if not self.before_agent_start_handlers:
            return None
        ctx = ExtensionContext(cwd=self.cwd)
        current_prompt = system_prompt
        changed = False
        for handler in self.before_agent_start_handlers:
            out = handler(
                {
                    "type": "before_agent_start",
                    "prompt": prompt,
                    "systemPrompt": current_prompt,
                },
                ctx,
            )
            result = await out if isinstance(out, Awaitable) else out
            if isinstance(result, dict) and isinstance(result.get("systemPrompt"), str):
                current_prompt = result["systemPrompt"]
                changed = True
        if not changed:
            return None
        return {"systemPrompt": current_prompt}

    async def emit_context(
        self,
        messages: list[AgentMessage],
    ) -> list[AgentMessage]:
        if not self.context_handlers:
            return messages
        ctx = ExtensionContext(cwd=self.cwd)
        current = list(messages)
        for handler in self.context_handlers:
            out = handler({"type": "context", "messages": current}, ctx)
            result = await out if isinstance(out, Awaitable) else out
            if isinstance(result, dict) and isinstance(result.get("messages"), list):
                current = result["messages"]
        return current

    async def emit_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.tool_call_handlers:
            return None
        ctx = ExtensionContext(cwd=self.cwd)
        current_args = dict(args)
        blocked_reason: str | None = None
        for handler in self.tool_call_handlers:
            out = handler(
                {
                    "type": "tool_call",
                    "toolName": tool_name,
                    "toolCallId": tool_call_id,
                    "input": current_args,
                },
                ctx,
            )
            result = await out if isinstance(out, Awaitable) else out
            if not isinstance(result, dict):
                continue
            if result.get("block"):
                blocked_reason = str(result.get("reason") or "Blocked by extension")
                break
            if isinstance(result.get("args"), dict):
                current_args = dict(result["args"])
        if blocked_reason is not None:
            return {"block": True, "reason": blocked_reason}
        if current_args != args:
            return {"args": current_args}
        return None

    async def emit_tool_result(
        self,
        tool_name: str,
        tool_call_id: str,
        args: dict[str, Any],
        result: AgentToolResult,
    ) -> AgentToolResult:
        if not self.tool_result_handlers:
            return result
        ctx = ExtensionContext(cwd=self.cwd)
        current = result
        for handler in self.tool_result_handlers:
            out = handler(
                {
                    "type": "tool_result",
                    "toolName": tool_name,
                    "toolCallId": tool_call_id,
                    "input": args,
                    "content": [
                        {"type": "text", "text": block.text}
                        for block in current.content
                    ],
                    "isError": current.is_error,
                    "details": current.details,
                },
                ctx,
            )
            patch = await out if isinstance(out, Awaitable) else out
            if not isinstance(patch, dict):
                continue
            if isinstance(patch.get("content"), list):
                content_blocks: list[TextContent] = []
                for item in patch["content"]:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        content_blocks.append(
                            TextContent(text=str(item["text"])),
                        )
                if content_blocks:
                    current = AgentToolResult(
                        content=content_blocks,
                        details=current.details,
                        is_error=current.is_error,
                        terminate=current.terminate,
                    )
            details = current.details
            if "details" in patch:
                details = patch["details"]
            is_error = current.is_error
            if "isError" in patch and isinstance(patch["isError"], bool):
                is_error = bool(patch["isError"])
            terminate = current.terminate
            if "terminate" in patch and isinstance(patch["terminate"], bool):
                terminate = bool(patch["terminate"])
            current = AgentToolResult(
                content=current.content,
                details=details,
                is_error=is_error,
                terminate=terminate,
            )
        return current


def discover_extension_paths(cwd: Path, agent_dir: Path, explicit_paths: list[str]) -> list[Path]:
    """Discover extension files from default locations and explicit paths."""

    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        found.append(resolved)

    def scan_dir(dir_path: Path) -> None:
        if not dir_path.is_dir():
            return
        for item in sorted(dir_path.iterdir(), key=lambda entry: entry.name):
            if item.is_file() and item.suffix == ".py":
                add(item)
            elif item.is_dir():
                entry = item / "index.py"
                if entry.is_file():
                    add(entry)

    scan_dir(agent_dir / "extensions")
    scan_dir(cwd / ".pi" / "extensions")
    for raw in explicit_paths:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (cwd / path).resolve()
        if path.is_file():
            add(path)
            continue
        if path.is_dir():
            scan_dir(path)
    return found


def load_extensions(cwd: Path, extension_paths: list[Path]) -> ExtensionLoadResult:
    """Load Python extension modules."""

    commands: list[ExtensionCommand] = []
    tools: list[AgentTool] = []
    input_handlers: list[InputHandler] = []
    before_agent_start_handlers: list[BeforeAgentStartHandler] = []
    session_start_handlers: list[SessionStartHandler] = []
    context_handlers: list[ContextHandler] = []
    tool_call_handlers: list[ToolCallHandler] = []
    tool_result_handlers: list[ToolResultHandler] = []
    errors: list[str] = []

    for index, ext_path in enumerate(extension_paths):
        module_name = f"_pipy_extension_{index}"
        spec = importlib.util.spec_from_file_location(module_name, str(ext_path))
        if spec is None or spec.loader is None:
            errors.append(f"Failed to load extension spec: {ext_path}")
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Extension import failed ({ext_path}): {exc}")
            continue
        factory = getattr(module, "register", None) or getattr(module, "setup", None)
        if factory is None or not callable(factory):
            errors.append(
                f"Extension must export register(api) or setup(api): {ext_path}",
            )
            continue
        api = ExtensionAPI(str(ext_path))
        try:
            maybe = factory(api)
            if isinstance(maybe, Awaitable):
                errors.append(
                    f"Async extension factories are not supported yet: {ext_path}",
                )
                continue
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Extension setup failed ({ext_path}): {exc}")
            continue
        commands.extend(api.commands)
        tools.extend(api.tools)
        input_handlers.extend(api.input_handlers)
        before_agent_start_handlers.extend(api.before_agent_start_handlers)
        session_start_handlers.extend(api.session_start_handlers)
        context_handlers.extend(api.context_handlers)
        tool_call_handlers.extend(api.tool_call_handlers)
        tool_result_handlers.extend(api.tool_result_handlers)

    return ExtensionLoadResult(
        command_overrides=commands,
        tools=tools,
        input_handlers=input_handlers,
        before_agent_start_handlers=before_agent_start_handlers,
        session_start_handlers=session_start_handlers,
        context_handlers=context_handlers,
        tool_call_handlers=tool_call_handlers,
        tool_result_handlers=tool_result_handlers,
        errors=errors,
    )
