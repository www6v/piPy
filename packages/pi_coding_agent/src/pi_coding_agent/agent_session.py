"""High-level agent session (pi: AgentSession subset)."""

from __future__ import annotations

import asyncio
import html
import json
import subprocess
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi_agent.agent import Agent, AgentBusyError
from pi_agent.message_queue import QueueMode
from pi_agent.types import AgentEvent, AgentMessage
from pi_ai.model_registry import ModelRegistry
from pi_ai.types import AssistantMessage, Model, UserMessage

from pi_coding_agent.auth.resolve import resolve_auth_for_model
from pi_coding_agent.compaction import compact_session, estimate_context_tokens
from pi_coding_agent.model_resolver import resolve_model_reference
from pi_coding_agent.defaults import DEFAULT_SYSTEM
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.session.serialize import model_to_dict
from pi_coding_agent.session.types import CompactionResult
from pi_coding_agent.retry import compute_retry_delay_ms, is_retryable_error
from pi_coding_agent.resources.manager import ResourceManager
from pi_coding_agent.settings import Settings, load_settings
from pi_coding_agent.tools.registry import create_tools_for_names


@dataclass
class SessionBackend:
    """Persistence backend for a session."""

    manager: SessionManager | None
    session_id: str
    session_file: str | None

    def load_messages(self) -> list[AgentMessage]:
        if self.manager is None:
            return []
        return self.manager.load_messages()

    def append_messages(self, messages: list[AgentMessage]) -> None:
        if self.manager is not None:
            self.manager.append_messages(messages)

    def load_entries(self) -> list[dict]:
        if self.manager is None:
            return []
        return self.manager.load_entries()

    def append_compaction(self, result: CompactionResult) -> str:
        if self.manager is None:
            msg = (
                "Compaction requires a persisted session (SessionManager); "
                "in-memory backends cannot compact."
            )
            raise RuntimeError(msg)
        return self.manager.append_compaction(result)


class InMemorySessionBackend(SessionBackend):
    """In-memory session (pi: SessionManager.inMemory())."""

    def __init__(self) -> None:
        self._messages: list[AgentMessage] = []
        session_id = str(uuid.uuid4())
        super().__init__(manager=None, session_id=session_id, session_file=None)

    def load_messages(self) -> list[AgentMessage]:
        return list(self._messages)

    def append_messages(self, messages: list[AgentMessage]) -> None:
        self._messages.extend(messages)


def _read_session_id(path: Path) -> str:
    if not path.is_file():
        return str(uuid.uuid4())
    first = path.read_text(encoding="utf-8").splitlines()[:1]
    if not first:
        return str(uuid.uuid4())
    header = json.loads(first[0])
    return str(header.get("id") or uuid.uuid4())


def _coerce_queue_mode(raw: str) -> QueueMode:
    if raw in ("all", "one-at-a-time"):
        return raw  # type: ignore[return-value]
    return "one-at-a-time"


def _ensure_faux_retry_test_model() -> None:
    """Register ``faux/retry-test``: first completion errors, second succeeds."""

    from pi_ai.providers.faux import (
        faux_assistant_message,
        faux_text,
        register_faux_provider,
    )
    from pi_ai.types import Context

    attempts = {"n": 0}

    def handler(_ctx: Context) -> AssistantMessage:
        idx = attempts["n"]
        attempts["n"] = idx + 1
        if idx == 0:
            return faux_assistant_message(
                [faux_text("")],
                stop_reason="error",
                error_message="HTTP 529 overloaded upstream",
            )
        return faux_assistant_message([faux_text("recovery-ok")])

    register_faux_provider(
        models=[{"id": "retry-test", "name": "retry-test"}],
        handler=handler,
    )


def _ensure_faux_model(model_id: str) -> None:
    from pi_ai.providers import faux as faux_mod
    from pi_ai.providers.faux import (
        faux_assistant_message,
        faux_text,
        register_faux_provider,
    )

    if model_id == "retry-test":
        _ensure_faux_retry_test_model()
        return
    if faux_mod.get_faux_model(model_id) is None:
        register_faux_provider(
            models=[{"id": model_id, "name": model_id}],
            handler=lambda _ctx: faux_assistant_message([faux_text("ok")]),
        )


class AgentSession:
    """SDK-facing session wrapping Agent + persistence."""

    def __init__(
        self,
        *,
        agent: Agent,
        model: Model,
        thinking_level: str | None,
        backend: SessionBackend,
        cwd: Path,
        registry: ModelRegistry,
        api_key: str | None,
        request_headers: dict[str, str] | None,
        settings: Settings,
        resources: ResourceManager | None = None,
        provider_override: str | None = None,
    ) -> None:
        self._agent = agent
        self._model = model
        self._thinking_level = thinking_level
        self._backend = backend
        self.cwd = cwd
        self._registry = registry
        self._api_key = api_key
        self._request_headers = request_headers
        self._provider_override = provider_override
        self._settings = settings
        self._resources = resources
        self._auto_compaction_enabled = settings.compaction.enabled
        self._reserve_tokens = settings.compaction.reserve_tokens
        self._keep_recent_tokens = settings.compaction.keep_recent_tokens
        self._is_compacting = False
        retry_cfg = settings.retry
        self._auto_retry_enabled = retry_cfg.enabled
        self._retry_max_retries = retry_cfg.max_retries
        self._retry_base_delay_ms = retry_cfg.base_delay_ms
        self._retry_attempt = 0
        self._retry_abort_event = asyncio.Event()
        self._session_event_listeners: list[
            Callable[[AgentEvent | dict[str, Any]], None | Awaitable[None]]
        ] = []

        async def queue_sync(event: AgentEvent) -> None:
            if (
                event.type == "message_start"
                and isinstance(event.message, UserMessage)
            ):
                await self._emit_queue_update()

        self._agent.subscribe(queue_sync)

    def _compaction_result_to_dict(self, result: CompactionResult) -> dict[str, Any]:
        return {
            "summary": result.summary,
            "firstKeptEntryId": result.first_kept_entry_id,
            "tokensBefore": result.tokens_before,
            "details": dict(result.details),
        }

    async def _emit_session_event(self, payload: dict[str, Any]) -> None:
        for listener in list(self._session_event_listeners):
            out = listener(payload)
            if asyncio.iscoroutine(out):
                await out

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def model(self) -> Model:
        return self._model

    @property
    def thinking_level(self) -> str | None:
        return self._thinking_level

    @property
    def messages(self) -> list[AgentMessage]:
        return list(self._agent.state.messages)

    @property
    def is_streaming(self) -> bool:
        return self._agent.state.is_streaming

    @property
    def session_id(self) -> str:
        return self._backend.session_id

    @property
    def session_file(self) -> str | None:
        return self._backend.session_file

    def subscribe(
        self,
        listener: Callable[[AgentEvent], None | Awaitable[None]],
    ) -> Callable[[], None]:
        return self._agent.subscribe(listener)

    def subscribe_all(
        self,
        listener: Callable[
            [AgentEvent | dict[str, Any]],
            None | Awaitable[None],
        ],
    ) -> Callable[[], None]:
        """Subscribe to AgentEvent stream plus session dict events."""

        listeners = self._session_event_listeners

        async def forward_agent(ev: AgentEvent) -> None:
            res = listener(ev)
            if asyncio.iscoroutine(res):
                await res

        unsub_agent = self._agent.subscribe(forward_agent)
        listeners.append(listener)

        def cleanup() -> None:
            unsub_agent()
            listeners.remove(listener)

        return cleanup

    def _queue_update_dict(self) -> dict[str, Any]:
        steer = list(self._agent.steering_queue.peek_texts())
        follow_up = list(self._agent.follow_up_queue.peek_texts())
        return {"type": "queue_update", "steering": steer, "followUp": follow_up}

    def _find_last_assistant(self) -> AssistantMessage | None:
        """Return newest assistant transcript message, if any."""

        for candidate in reversed(self._agent._messages):
            if isinstance(candidate, AssistantMessage):
                return candidate
        return None

    async def _interruptible_retry_sleep(self, delay_ms: int) -> bool:
        """Wait for backoff; returns False when :meth:`abort_retry` fires."""

        delay_s = max(0.0, delay_ms / 1000.0)
        sleeper = asyncio.create_task(asyncio.sleep(delay_s))
        aborted = asyncio.create_task(self._retry_abort_event.wait())
        _done, pending = await asyncio.wait(
            {sleeper, aborted},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return not self._retry_abort_event.is_set()

    async def _handle_post_run(
        self,
        accumulated: list[AgentMessage],
    ) -> list[AgentMessage]:
        """Apply bounded auto-retries after a transcript-producing run."""

        if not self._auto_retry_enabled:
            self._retry_attempt = 0
            return accumulated

        merged = list(accumulated)
        retry_round = 0
        try:
            while True:
                assistant = self._find_last_assistant()
                if assistant is None:
                    return merged

                ok_error = assistant.stop_reason == "error"
                ok_msg = bool(
                    assistant.error_message
                    and str(assistant.error_message).strip(),
                )
                if not ok_error or not ok_msg:
                    return merged

                if not is_retryable_error(
                    assistant,
                    self._model.context_window,
                ):
                    return merged

                if retry_round >= self._retry_max_retries:
                    return merged

                self._retry_attempt = retry_round
                delay_ms = compute_retry_delay_ms(
                    retry_round,
                    self._retry_base_delay_ms,
                )
                await self._emit_session_event({
                    "type": "auto_retry_start",
                    "attempt": retry_round,
                    "maxRetries": self._retry_max_retries,
                    "delayMs": delay_ms,
                })
                recovered = assistant
                last_agent = self._agent._messages[-1]
                if last_agent is not recovered:
                    return merged
                self._agent._messages.pop()
                self._retry_abort_event.clear()
                if not await self._interruptible_retry_sleep(delay_ms):
                    self._agent._messages.append(recovered)
                    await self._emit_session_event({
                        "type": "auto_retry_end",
                        "success": False,
                        "cancelled": True,
                    })
                    return merged

                try:
                    more = await self._agent.continue_run()
                except Exception:
                    self._agent._messages.append(recovered)
                    raise

                retry_round += 1
                if merged and merged[-1] is recovered:
                    merged = merged[:-1]
                merged.extend(more)
                await self._emit_session_event({
                    "type": "auto_retry_end",
                    "success": True,
                    "attempt": retry_round - 1,
                })
        finally:
            self._retry_attempt = 0

    def set_auto_retry(self, enabled: bool) -> None:
        """Enable or disable automatic retries for retryable provider errors."""

        self._auto_retry_enabled = enabled

    def abort_retry(self) -> None:
        """Abort an in-progress retry backoff wait (see :meth:`set_auto_retry`)."""

        self._retry_abort_event.set()

    async def _emit_queue_update(self) -> None:
        await self._emit_session_event(self._queue_update_dict())

    async def flush_queue_broadcast(self) -> None:
        """Deliver a ``queue_update`` snapshot to subscribe_all listeners."""

        await self._emit_queue_update()

    def steer(self, message: str) -> None:
        """Enqueue steering text while or before a run (see Agent.steer)."""

        self._agent.steer(message)

    def follow_up(self, message: str) -> None:
        """Enqueue follow-up text (see Agent.follow_up)."""

        self._agent.follow_up(message)

    def set_steering_mode(self, mode: str) -> None:
        """Set steering queue discard mode (``all`` or ``one-at-a-time``)."""

        coerced = _coerce_queue_mode(mode)
        self._agent.steering_queue.mode = coerced

    def set_follow_up_mode(self, mode: str) -> None:
        """Set follow-up queue discard mode (``all`` or ``one-at-a-time``)."""

        coerced = _coerce_queue_mode(mode)
        self._agent.follow_up_queue.mode = coerced

    async def prompt(
        self,
        text: str,
        streaming_behavior: str | None = None,
        input_source: str = "interactive",
    ) -> list[AgentMessage]:
        if self.is_streaming:
            if streaming_behavior is None:
                raise AgentBusyError(
                    "Agent is streaming; pass streaming_behavior "
                    "'steer' or 'followUp', or use steer()/follow_up().",
                )
            key = streaming_behavior.strip()
            if key == "steer":
                self._agent.steer(text)
                await self._emit_queue_update()
                return []
            if key == "followUp":
                self._agent.follow_up(text)
                await self._emit_queue_update()
                return []
            msg = (
                f"streaming_behavior must be 'steer' or 'followUp', "
                f"got {streaming_behavior!r}"
            )
            raise ValueError(msg)

        if self._resources is not None:
            handled = await self._resources.try_run_extension_command(text, self)
            if handled:
                return []
            input_result = await self._resources.extension_runtime.emit_input(
                text,
                input_source,
            )
            if input_result.get("action") == "handled":
                return []
            if (
                input_result.get("action") == "transform"
                and isinstance(input_result.get("text"), str)
            ):
                text = str(input_result["text"])
            text = self._resources.expand_text(text)

        original_system_prompt = self._agent._system_prompt
        if self._resources is not None:
            before_start = await self._resources.extension_runtime.emit_before_agent_start(
                text,
                original_system_prompt,
            )
            if before_start and isinstance(before_start.get("systemPrompt"), str):
                self._agent._system_prompt = before_start["systemPrompt"]

        snapshot_before = len(self._agent._messages)
        self._retry_abort_event.clear()
        try:
            new_messages = await self._agent.prompt(text)
            _reconciled = await self._handle_post_run(new_messages)
            appended = list(self._agent._messages[snapshot_before:])
            self._backend.append_messages(appended)
            await self._maybe_auto_compact()
            return appended
        finally:
            self._agent._system_prompt = original_system_prompt


    async def compact(
        self,
        custom_instructions: str | None = None,
    ) -> CompactionResult:
        if self._backend.manager is None:
            msg = (
                "Compaction requires a persisted SessionManager-backed session."
            )
            raise RuntimeError(msg)
        return await self._run_compaction(
            reason="manual",
            custom_instructions=custom_instructions,
        )

    async def _maybe_auto_compact(self) -> None:
        if (
            not self._auto_compaction_enabled
            or self._backend.manager is None
            or self._is_compacting
        ):
            return
        messages_now = list(self._agent._messages)
        estimate = estimate_context_tokens(messages_now, self._model)
        budget = max(0, self._model.context_window - self._reserve_tokens)
        if estimate <= budget:
            return
        try:
            await self._run_compaction(
                reason="threshold",
                custom_instructions=None,
            )
        except Exception:
            return

    async def _run_compaction(
        self,
        *,
        reason: str,
        custom_instructions: str | None,
    ) -> CompactionResult:
        if self._is_compacting:
            msg = "Compaction already in progress"
            raise RuntimeError(msg)
        mgr = self._backend.manager
        if mgr is None:
            msg = (
                "Compaction requires a persisted SessionManager-backed session."
            )
            raise RuntimeError(msg)
        entries = mgr.load_entries()
        self._is_compacting = True
        try:
            await self._emit_session_event({
                "type": "compaction_start",
                "reason": reason,
            })
            result = await compact_session(
                entries=entries,
                messages=list(self._agent._messages),
                model=self._model,
                api_key=self._api_key,
                request_headers=self._request_headers,
                custom_instructions=custom_instructions,
                keep_recent_tokens=self._keep_recent_tokens,
            )
            self._backend.append_compaction(result)
            self._agent._messages = self._backend.load_messages()
            await self._emit_session_event({
                "type": "compaction_end",
                "reason": reason,
                "result": self._compaction_result_to_dict(result),
            })
            return result
        finally:
            self._is_compacting = False

    def abort(self) -> None:
        self._agent.abort()

    async def wait_for_idle(self) -> None:
        await self._agent.wait_for_idle()

    async def set_model(self, provider: str, model_id: str) -> Model:
        pattern = f"{provider}/{model_id}"
        resolved = resolve_model_reference(
            pattern,
            self._registry,
            provider_override=self._provider_override,
        )
        if resolved.provider == "faux":
            _ensure_faux_model(resolved.model_id)
        api_key, request_headers = resolve_auth_for_model(
            self._registry,
            resolved.model,
            api_key_override=self._api_key,
        )
        self._model = resolved.model
        self._agent._model = resolved.model
        self._agent._api_key = api_key
        self._agent._request_headers = request_headers
        if resolved.thinking_level:
            self.set_thinking_level(resolved.thinking_level)
        return self._model

    def set_thinking_level(self, level: str | None) -> None:
        self._thinking_level = level
        self._agent._thinking_level = level

    def set_auto_compaction(self, enabled: bool) -> None:
        """Enable or disable automatic compaction on context overrun."""

        self._auto_compaction_enabled = enabled

    async def run_bash_command(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute a shell command and append its output as user context."""

        cwd = str(self.cwd.resolve())
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                command,
                cwd=cwd,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
            output = completed.stdout or ""
            exit_code = int(completed.returncode)
            cancelled = False
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            exit_code = 124
            cancelled = False
        formatted = (
            f"Ran `{command}`\n```\n{output}\n```"
            if output
            else f"Ran `{command}`\n```\n(no output)\n```"
        )
        msg = UserMessage(content=formatted)
        self._agent._messages.append(msg)
        self._backend.append_messages([msg])
        return {
            "output": output,
            "exitCode": exit_code,
            "cancelled": cancelled,
            "truncated": False,
        }

    def get_session_stats(self) -> dict[str, Any]:
        """Compute basic session statistics for RPC clients."""

        user_messages = 0
        assistant_messages = 0
        tool_results = 0
        tool_calls = 0
        token_input = 0
        token_output = 0
        token_cache_read = 0
        token_cache_write = 0
        cost_total = 0.0
        for msg in self._agent._messages:
            if isinstance(msg, UserMessage):
                user_messages += 1
                continue
            if isinstance(msg, AssistantMessage):
                assistant_messages += 1
                for block in msg.content:
                    if getattr(block, "type", "") == "toolCall":
                        tool_calls += 1
                usage = msg.usage
                token_input += int(usage.input)
                token_output += int(usage.output)
                token_cache_read += int(usage.cache_read)
                token_cache_write += int(usage.cache_write)
                cost_total += float(usage.cost.total)
                continue
            tool_results += 1

        total_tokens = token_input + token_output + token_cache_read + token_cache_write
        context_usage: dict[str, Any] | None = None
        if self._model.context_window > 0:
            percent = (total_tokens / self._model.context_window) * 100
            context_usage = {
                "tokens": total_tokens,
                "contextWindow": self._model.context_window,
                "percent": round(percent, 2),
            }
        payload: dict[str, Any] = {
            "sessionFile": self.session_file,
            "sessionId": self.session_id,
            "userMessages": user_messages,
            "assistantMessages": assistant_messages,
            "toolCalls": tool_calls,
            "toolResults": tool_results,
            "totalMessages": len(self._agent._messages),
            "tokens": {
                "input": token_input,
                "output": token_output,
                "cacheRead": token_cache_read,
                "cacheWrite": token_cache_write,
                "total": total_tokens,
            },
            "cost": round(cost_total, 6),
        }
        if context_usage is not None:
            payload["contextUsage"] = context_usage
        return payload

    def export_html(self, output_path: str | None = None) -> str:
        """Export current transcript to a standalone HTML file."""

        if output_path:
            target = Path(output_path).expanduser()
        else:
            base = Path(self.session_file) if self.session_file else (self.cwd / "session")
            target = base.with_suffix(".html")
        target.parent.mkdir(parents=True, exist_ok=True)

        rows: list[str] = []
        for msg in self._agent._messages:
            role = msg.role
            if isinstance(msg, UserMessage):
                content = msg.content if isinstance(msg.content, str) else "".join(
                    block.text for block in msg.content
                )
            elif isinstance(msg, AssistantMessage):
                content = "".join(
                    block.text
                    for block in msg.content
                    if getattr(block, "type", "") == "text"
                )
            else:
                content = "\n".join(block.text for block in msg.content)
            rows.append(
                "<div class='msg'>"
                f"<div class='role'>{html.escape(role)}</div>"
                f"<pre>{html.escape(content)}</pre>"
                "</div>"
            )
        body = "\n".join(rows)
        doc = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>piPy session export</title>"
            "<style>body{font-family:ui-monospace,monospace;padding:16px}"
            ".msg{border:1px solid #ddd;border-radius:8px;margin:10px 0;padding:10px}"
            ".role{font-weight:700;margin-bottom:6px}pre{white-space:pre-wrap}</style>"
            "</head><body>"
            f"<h1>Session {html.escape(self.session_id)}</h1>{body}</body></html>"
        )
        target.write_text(doc, encoding="utf-8")
        return str(target.resolve())

    def get_rpc_state(self) -> dict[str, Any]:
        pending = (
            len(self._agent.steering_queue)
            + len(self._agent.follow_up_queue)
        )
        return {
            "model": model_to_dict(self._model),
            "thinkingLevel": self._thinking_level or "off",
            "isStreaming": self.is_streaming,
            "isCompacting": self._is_compacting,
            "steeringMode": self._agent.steering_queue.mode,
            "followUpMode": self._agent.follow_up_queue.mode,
            "sessionFile": self.session_file,
            "sessionId": self.session_id,
            "autoCompactionEnabled": self._auto_compaction_enabled,
            "messageCount": len(self.messages),
            "pendingMessageCount": pending,
            "autoRetryEnabled": self._auto_retry_enabled,
            "retryAttempt": self._retry_attempt,
            "retryMaxRetries": self._retry_max_retries,
        }

    def get_messages_json(self) -> list[dict[str, Any]]:
        from pi_coding_agent.session.serialize import message_to_dict

        return [message_to_dict(message) for message in self.messages]

    def get_commands(self) -> list[dict[str, Any]]:
        if self._resources is None:
            return []
        return [
            {
                "name": item.name,
                "source": item.source,
                "description": item.description,
                "path": item.path,
            }
            for item in self._resources.list_commands()
        ]

    async def new_session(self, *, cwd: Path | None = None) -> None:
        target = cwd or self.cwd
        manager = SessionManager.create(target)
        backend = SessionBackend(
            manager=manager,
            session_id=_read_session_id(manager.path),
            session_file=str(manager.path),
        )
        self._backend = backend
        self._agent._messages = []
        self.cwd = target

    @classmethod
    def build(
        cls,
        *,
        cwd: Path,
        model: Model,
        tools: list[str],
        system_prompt: str,
        thinking_level: str | None,
        backend: SessionBackend,
        registry: ModelRegistry,
        api_key: str | None,
        request_headers: dict[str, str] | None,
        settings: Settings | None = None,
        resources: ResourceManager | None = None,
        provider_override: str | None = None,
    ) -> AgentSession:
        resolved_settings = settings or load_settings(cwd)
        steering_mode_q = _coerce_queue_mode(resolved_settings.steering_mode)
        follow_up_mode_q = _coerce_queue_mode(resolved_settings.follow_up_mode)
        builtins = create_tools_for_names(str(cwd), tools)
        extension_tools = (
            list(resources.extension_runtime.tools)
            if resources is not None
            else []
        )

        async def on_context(messages: list[AgentMessage]) -> list[AgentMessage] | None:
            if resources is None:
                return None
            return await resources.extension_runtime.emit_context(messages)

        async def on_tool_call(
            tool_name: str,
            tool_call_id: str,
            args: dict[str, Any],
        ) -> dict[str, Any] | None:
            if resources is None:
                return None
            return await resources.extension_runtime.emit_tool_call(
                tool_name,
                tool_call_id,
                args,
            )

        async def on_tool_result(
            tool_name: str,
            tool_call_id: str,
            args: dict[str, Any],
            result: Any,
        ) -> Any:
            if resources is None:
                return result
            return await resources.extension_runtime.emit_tool_result(
                tool_name,
                tool_call_id,
                args,
                result,
            )

        agent = Agent(
            system_prompt=system_prompt,
            model=model,
            tools=[*builtins, *extension_tools],
            api_key=api_key,
            request_headers=request_headers,
            initial_messages=backend.load_messages(),
            thinking_level=thinking_level,
            steering_mode=steering_mode_q,
            follow_up_mode=follow_up_mode_q,
            on_context=on_context if resources is not None else None,
            on_tool_call=on_tool_call if resources is not None else None,
            on_tool_result=on_tool_result if resources is not None else None,
        )
        return cls(
            agent=agent,
            model=model,
            thinking_level=thinking_level,
            backend=backend,
            cwd=cwd,
            registry=registry,
            api_key=api_key,
            request_headers=request_headers,
            provider_override=provider_override,
            settings=resolved_settings,
            resources=resources,
        )
