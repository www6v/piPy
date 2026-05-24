"""Auto-retry helpers (pi: agent-session.ts _isRetryableError subset)."""

from __future__ import annotations

import re
from typing import Final

from pi_ai.types import AssistantMessage

_CONTEXT_OVERFLOW_FRAGMENT: Final = re.compile(
    r"context.{0,40}overflow|overflow.{0,40}context|"
    r"maximum\s+context|too\s+many\s+tokens|"
    r"context\s+(length|window)\s+exceeded|"
    r"prompt\s+is\s+too\s+long|"
    r"tokens?\s*\(?exceed|\bmaximum\s+tokens\b",
    re.IGNORECASE,
)

_RETRYABLE_FRAGMENT: Final = re.compile(
    r"\b529\b|"  # Anthropic overloaded
    r"\b429\b|"
    r"rate\s*limit|requests?\s*per|throttl(?:e|ed|ing)|"
    r"\boverload(?:ed)?\b|"  # overloaded / overload
    r"\b(?:5\d{2})\b|"  # HTTP 500-599 status codes as token
    r"\bECONNRESET\b|\bECONNREFUSED\b|"
    r"connection\s+(?:closed|reset|refused)|"
    r"\btimed?\s*out\b|timeout\b|socket\s+(?:timed?\s*)?out|"
    r"network\b.*\b(?:error|unreachable)|"
    r"unexpected\s+eof|"  # common stream drops
    r"RESOURCE_EXHAUSTED",
    re.IGNORECASE,
)


def is_retryable_error(
    message: AssistantMessage,
    context_window: int,
) -> bool:
    """Return True when a failed assistant turn should trigger auto-retry."""

    del context_window  # Reserved for callers; overflow uses error text matches.
    if message.stop_reason != "error":
        return False
    err_raw = message.error_message
    if err_raw is None or not str(err_raw).strip():
        return False
    err_lower = err_raw.casefold()

    # Context / token overrun is handled via compaction instead of retries.
    if _CONTEXT_OVERFLOW_FRAGMENT.search(err_lower) is not None:
        return False
    if (
        ("context" in err_lower or "prompt" in err_lower or "tokens" in err_lower)
        and "overflow" in err_lower
    ):
        return False

    return _RETRYABLE_FRAGMENT.search(err_lower) is not None


def compute_retry_delay_ms(attempt: int, base_delay_ms: int) -> int:
    """Exponential backoff in milliseconds from zero-based retry attempt."""

    if base_delay_ms < 1:
        base_delay_ms = 1
    if attempt < 0:
        attempt = 0
    delay = base_delay_ms * (2**attempt)
    return min(delay, 60 * 60 * 1000)
