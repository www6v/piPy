"""CLI entry point for pi-coding-agent."""

from __future__ import annotations

import argparse
import asyncio
import sys

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
    parser.add_argument("prompt", nargs="?", help="User prompt for print mode")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{APP_NAME} {VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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
