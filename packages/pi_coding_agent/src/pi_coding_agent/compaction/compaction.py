"""Context compaction helpers (pi: compaction/compaction.ts subset)."""

from __future__ import annotations

import json

from pi_agent.types import AgentMessage
from pi_ai.stream import complete_simple
from pi_ai.types import (
    AssistantMessage,
    Context,
    Model,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    TextContent,
)

from pi_coding_agent.compaction.utils import (
    FileOperations,
    compute_file_lists,
    extract_file_ops_from_message,
)
from pi_coding_agent.session.types import CompactionResult

SUMMARIZATION_SYSTEM_PROMPT = (
    "You are a context summarization assistant. Your task is to read a "
    "conversation between a user and an AI coding assistant, then produce "
    "a structured summary following the exact format specified.\n\n"
    "Do NOT continue the conversation. Do NOT respond to any questions in "
    "the conversation. ONLY output the structured summary."
)

_SUMMARY_USER_PROMPT = """The messages above are a conversation to summarize.
Create a structured context checkpoint summary that another LLM will use to
continue the work. Be concise about completed work and open issues.

Preserve exact file paths, function names, and error messages when relevant.
"""

_TOOL_RESULT_MAX_CHARS = 2000


def estimate_context_tokens(messages: list[AgentMessage], model: Model) -> int:
    """Rough context size; prefers summed assistant usage.total_tokens."""

    del model

    summed = False
    total = 0
    for message in messages:
        if getattr(message, "role", None) != "assistant":
            continue
        if not isinstance(message, AssistantMessage):
            continue
        if message.stop_reason in ("error", "aborted"):
            continue
        tt = getattr(getattr(message, "usage", None), "total_tokens", 0) or 0
        if tt > 0:
            total += int(tt)
            summed = True
    if summed:
        return total
    return len(str(messages)) // 4


def _session_body(entries: list[dict]) -> list[dict]:
    return [row for row in entries if row.get("type") != "session"]


def _associate_entry_messages(
    entries: list[dict],
    messages: list[AgentMessage],
) -> dict[str, AgentMessage]:
    messages_by_id: dict[str, AgentMessage] = {}
    mq = iter(messages)
    for entry in _session_body(entries):
        if entry.get("type") != "message":
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            continue
        try:
            messages_by_id[entry_id] = next(mq)
        except StopIteration:
            break
    return messages_by_id


def _estimate_message_tokens(message: AgentMessage) -> int:
    chars = 0
    if isinstance(message, UserMessage):
        if isinstance(message.content, str):
            chars = len(message.content)
        elif isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, TextContent):
                    chars += len(block.text)
        return max(1, (chars + 3) // 4)
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if block.type == "text":
                chars += len(block.text)
            elif isinstance(block, ToolCall):
                chars += len(block.name) + len(json.dumps(block.arguments))
        return max(1, (chars + 3) // 4)
    if isinstance(message, ToolResultMessage):
        for block in message.content:
            if block.type == "text":
                chars += len(block.text)
        return max(1, (chars + 3) // 4)
    return 1


class _CutPointDetail:
    __slots__ = ("first_kept_index", "turn_start_index", "is_split_turn")

    def __init__(
        self,
        first_kept_index: int,
        turn_start_index: int | None,
        is_split_turn: bool,
    ) -> None:
        self.first_kept_index = first_kept_index
        self.turn_start_index = turn_start_index
        self.is_split_turn = is_split_turn


def _find_valid_cut_indices(
    entries: list[dict],
    start_index: int,
    end_index: int,
) -> list[int]:
    cut_points: list[int] = []
    for idx in range(start_index, end_index):
        row = entries[idx]
        if row.get("type") != "message":
            continue
        payload = row.get("message")
        if not isinstance(payload, dict):
            continue
        role = payload.get("role")
        if role in ("user", "assistant"):
            cut_points.append(idx)
    return cut_points


def _find_turn_start_index(
    entries: list[dict],
    entry_index: int,
    start_index: int,
) -> int | None:
    for idx in range(entry_index, start_index - 1, -1):
        row = entries[idx]
        if row.get("type") != "message":
            continue
        payload = row.get("message")
        if not isinstance(payload, dict):
            continue
        if payload.get("role") == "user":
            return idx
    return None


def _find_cut_point_detail(
    entries: list[dict],
    start_index: int,
    end_index: int,
    keep_recent_tokens: int,
    messages_by_id: dict[str, AgentMessage],
) -> _CutPointDetail | None:
    """Mirror pi findCutPoint; indices are relative to ``entries`` slice."""

    cut_points = _find_valid_cut_indices(entries, start_index, end_index)
    if not cut_points:
        return None

    cut_index = cut_points[0]
    accumulated_tokens = 0

    for idx in range(end_index - 1, start_index - 1, -1):
        row = entries[idx]
        if row.get("type") != "message":
            continue
        entry_id_raw = row.get("id")
        entry_id = entry_id_raw if isinstance(entry_id_raw, str) else None
        if not entry_id:
            continue
        msg = messages_by_id.get(entry_id)
        if msg is None:
            continue
        accumulated_tokens += _estimate_message_tokens(msg)
        if accumulated_tokens >= keep_recent_tokens:
            chosen = cut_index
            for cut_candidate in cut_points:
                if cut_candidate >= idx:
                    chosen = cut_candidate
                    break
            cut_index = chosen
            break

    while cut_index > start_index:
        prev_entry = entries[cut_index - 1]
        if prev_entry.get("type") == "compaction":
            break
        if prev_entry.get("type") == "message":
            break
        cut_index -= 1

    cut_row = entries[cut_index]
    payload_dict = cut_row.get("message")
    payload_dict = payload_dict if isinstance(payload_dict, dict) else {}
    role = payload_dict.get("role")
    is_user = cut_row.get("type") == "message" and role == "user"
    if is_user:
        turn_start: int | None = None
        is_split_turn = False
    else:
        turn_start = _find_turn_start_index(entries, cut_index, start_index)
        is_split_turn = turn_start is not None
    return _CutPointDetail(
        first_kept_index=cut_index,
        turn_start_index=turn_start,
        is_split_turn=is_split_turn,
    )


def find_cut_point(
    entries: list[dict],
    keep_recent_tokens: int,
    messages_by_id: dict[str, AgentMessage],
) -> str | None:
    """Return the entry id after which conversation is kept unchanged."""

    body = _session_body(entries)
    if not body:
        return None

    if body[-1].get("type") == "compaction":
        return None

    boundary_start = 0
    for idx in range(len(body) - 1, -1, -1):
        if body[idx].get("type") == "compaction":
            prev = body[idx]
            fk_raw = prev.get("firstKeptEntryId") or prev.get(
                "first_kept_entry_id",
            )
            if isinstance(fk_raw, str) and fk_raw:
                found = next(
                    (
                        j
                        for j, row in enumerate(body)
                        if row.get("id") == fk_raw
                    ),
                    None,
                )
                boundary_start = found if found is not None else idx + 1
            else:
                boundary_start = idx + 1
            break

    end_index = len(body)
    detail = _find_cut_point_detail(
        body,
        boundary_start,
        end_index,
        keep_recent_tokens,
        messages_by_id,
    )
    if detail is None:
        return None
    rid = body[detail.first_kept_index].get("id")
    return str(rid) if isinstance(rid, str) else None


def serialize_conversation(messages: list[AgentMessage]) -> str:
    """Flatten messages into tagged text for summarization."""

    lines: list[str] = []

    for message in messages:
        if isinstance(message, UserMessage):
            chunk = ""
            if isinstance(message.content, str):
                chunk = message.content
            elif isinstance(message.content, list):
                chunk = "".join(
                    blk.text for blk in message.content if blk.type == "text"
                )
            if chunk:
                lines.append(f"[User]: {chunk}")
            continue

        if isinstance(message, AssistantMessage):
            texts: list[str] = []
            tools: list[str] = []
            for block in message.content:
                if block.type == "text":
                    texts.append(block.text)
                elif isinstance(block, ToolCall):
                    args_repr = ", ".join(
                        f"{key}={json.dumps(val)}"
                        for key, val in block.arguments.items()
                    )
                    tools.append(f"{block.name}({args_repr})")
            if texts:
                lines.append("[Assistant]: {}".format("\n".join(texts)))
            if tools:
                lines.append("[Assistant tool calls]: {}".format("; ".join(tools)))
            continue

        if isinstance(message, ToolResultMessage):
            body = "".join(
                blk.text for blk in message.content if blk.type == "text"
            )
            if len(body) > _TOOL_RESULT_MAX_CHARS:
                extra = len(body) - _TOOL_RESULT_MAX_CHARS
                body = (
                    f"{body[:_TOOL_RESULT_MAX_CHARS]}\n\n"
                    f"[... {extra} more characters truncated]"
                )
            if body:
                lines.append(f"[Tool result]: {body}")

    return "\n\n".join(lines)


def _compaction_boundary_start(body: list[dict]) -> int:
    """First index after the previous compaction envelope."""

    boundary_start = 0
    for idx in range(len(body) - 1, -1, -1):
        if body[idx].get("type") != "compaction":
            continue
        prev = body[idx]
        fk_raw = prev.get("firstKeptEntryId") or prev.get("first_kept_entry_id")
        if isinstance(fk_raw, str) and fk_raw:
            found = next(
                (j for j, row in enumerate(body) if row.get("id") == fk_raw),
                None,
            )
            boundary_start = found if found is not None else idx + 1
        else:
            boundary_start = idx + 1
        break
    return boundary_start


def _collect_messages_for_summarization(
    body: list[dict],
    detail: _CutPointDetail,
    boundary_start: int,
    messages_by_id: dict[str, AgentMessage],
) -> tuple[list[AgentMessage], FileOperations]:
    history_end = (
        detail.turn_start_index
        if detail.is_split_turn and detail.turn_start_index is not None
        else detail.first_kept_index
    )
    summarized: list[AgentMessage] = []
    ops = FileOperations()
    for idx in range(boundary_start, history_end):
        row = body[idx]
        if row.get("type") != "message":
            continue
        rid = row.get("id")
        if not isinstance(rid, str):
            continue
        msg = messages_by_id.get(rid)
        if msg is None:
            continue
        summarized.append(msg)
        merged = extract_file_ops_from_message(msg)
        ops.read.update(merged.read)
        ops.edited.update(merged.edited)
        ops.written.update(merged.written)

    if detail.is_split_turn and detail.turn_start_index is not None:
        for idx in range(detail.turn_start_index, detail.first_kept_index):
            row = body[idx]
            if row.get("type") != "message":
                continue
            rid = row.get("id")
            if not isinstance(rid, str):
                continue
            prefix_msg = messages_by_id.get(rid)
            if prefix_msg is None:
                continue
            summarized.append(prefix_msg)
            merged = extract_file_ops_from_message(prefix_msg)
            ops.read.update(merged.read)
            ops.edited.update(merged.edited)
            ops.written.update(merged.written)
    return summarized, ops


async def compact_session(
    *,
    entries: list[dict],
    messages: list[AgentMessage],
    model: Model,
    api_key: str | None,
    request_headers: dict[str, str] | None = None,
    custom_instructions: str | None = None,
    keep_recent_tokens: int = 20_000,
) -> CompactionResult:
    """Summarize prefix messages via ``complete_simple`` and return metadata."""

    body = _session_body(entries)
    if not body:
        raise ValueError("Session has no entries to compact.")

    if body[-1].get("type") == "compaction":
        raise ValueError("Latest entry is already a compaction record.")

    messages_by_id = _associate_entry_messages(entries, messages)
    boundary_start = _compaction_boundary_start(body)

    detail_opt = _find_cut_point_detail(
        body,
        boundary_start,
        len(body),
        keep_recent_tokens,
        messages_by_id,
    )
    if detail_opt is None:
        raise ValueError("No valid compaction cut points.")
    detail = detail_opt

    first_kept_id_raw = body[detail.first_kept_index].get("id")
    if not isinstance(first_kept_id_raw, str) or not first_kept_id_raw:
        raise ValueError("Compaction target entry has no stable id.")

    to_summarize, file_ops = _collect_messages_for_summarization(
        body,
        detail,
        boundary_start,
        messages_by_id,
    )
    conversation = serialize_conversation(to_summarize)
    user_body = (
        f"<conversation>\n{conversation}\n</conversation>\n\n"
        f"{_SUMMARY_USER_PROMPT}"
    )
    if custom_instructions:
        user_body += (
            f"\n\nAdditional focus requested by caller:\n"
            f"{custom_instructions}\n"
        )

    user_message = UserMessage(content=user_body)

    ctx = Context(
        system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
        messages=[user_message],
    )

    assistant = await complete_simple(
        model,
        ctx,
        api_key=api_key,
        request_headers=request_headers,
    )
    if assistant.stop_reason == "error":
        err = assistant.error_message or "Unknown summarization error"
        raise RuntimeError(f"Summarization failed: {err}")

    summary_text_parts = [
        block.text for block in assistant.content if block.type == "text"
    ]

    tokens_before = estimate_context_tokens(messages, model)

    return CompactionResult(
        summary="\n".join(summary_text_parts).strip(),
        first_kept_entry_id=first_kept_id_raw,
        tokens_before=tokens_before,
        details=dict(compute_file_lists(file_ops)),
    )
