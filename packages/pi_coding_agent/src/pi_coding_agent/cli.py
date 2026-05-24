"""CLI entry point for pi-coding-agent."""

from __future__ import annotations

import argparse
import asyncio
import sys

from pi_ai.model_registry import get_registry

from pi_coding_agent.config import APP_NAME, VERSION
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="piPy coding agent",
    )
    parser.add_argument(
        "-p",
        "--print",
        dest="print_mode",
        action="store_true",
        help="Print mode (single-shot prompt)",
    )
    parser.add_argument(
        "--model",
        default="anthropic/claude-sonnet-4-5",
        help="Model as provider/modelId (default: anthropic/claude-sonnet-4-5)",
    )
    parser.add_argument("--api-key", help="API key override")
    parser.add_argument("--system", help="System prompt override")
    parser.add_argument(
        "--tools",
        default="read,bash",
        help="Comma-separated tool allowlist (default: read,bash)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Force provider id (e.g. faux for tests)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log agent events to stderr (text mode only)",
    )
    parser.add_argument(
        "--mode",
        choices=["text", "json"],
        default="text",
        help="Output mode: text (default) or json (JSONL events on stdout)",
    )
    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_session",
        action="store_true",
        help="Continue the latest session for this cwd",
    )
    parser.add_argument(
        "--session",
        dest="session_path",
        help="Path to a session .jsonl file",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List registered models and exit",
    )
    parser.add_argument("prompt", nargs="?", help="User prompt for print mode")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{APP_NAME} {VERSION}",
    )
    return parser


def _list_models() -> int:
    registry = get_registry()
    if registry.load_error:
        print(f"Warning: {registry.load_error}", file=sys.stderr)
    for model in registry.get_all():
        print(f"{model.provider}/{model.id}\t{model.name}\t{model.api}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_models:
        return _list_models()
    if not args.print_mode and args.prompt is None:
        parser.print_help()
        return 0
    if args.print_mode and not args.prompt:
        parser.error("print mode requires a prompt argument")
    if not args.print_mode:
        parser.error("only print mode (-p) is implemented in MVP")
    tools = [name.strip() for name in args.tools.split(",") if name.strip()]
    options = PrintModeOptions(
        prompt=args.prompt,
        model=args.model,
        system_prompt=args.system or "",
        tools=tools,
        api_key=args.api_key,
        provider=args.provider,
        verbose=args.verbose,
        mode=args.mode,
        continue_session=args.continue_session,
        session_path=args.session_path,
    )
    try:
        return asyncio.run(run_print_mode(options))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
