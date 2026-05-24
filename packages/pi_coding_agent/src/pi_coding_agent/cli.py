"""CLI entry point for pi-coding-agent."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from pi_ai.model_registry import get_registry

from pi_coding_agent.config import APP_NAME, VERSION
from pi_coding_agent.interactive_mode import InteractiveOptions, run_interactive_mode
from pi_coding_agent.model_resolver import parse_model_pattern
from pi_coding_agent.print_mode import PrintModeOptions, run_print_mode
from pi_coding_agent.session.manager import SessionManager
from pi_coding_agent.settings import load_settings


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
        default=None,
        help="Model as provider/modelId or pattern (e.g. sonnet:high)",
    )
    parser.add_argument("--api-key", help="API key override")
    parser.add_argument("--system", default=None, help="System prompt override")
    parser.add_argument(
        "-nc",
        "--no-context-files",
        dest="no_context_files",
        action="store_true",
        help="Skip loading AGENTS.md / CLAUDE.md into the system prompt",
    )
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
        "--thinking",
        dest="thinking_level",
        default=None,
        help="Thinking level: off|minimal|low|medium|high|xhigh",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log agent events to stderr (text mode only)",
    )
    parser.add_argument(
        "--mode",
        choices=["text", "json", "rpc"],
        default="text",
        help="Output mode: text, json, or rpc (JSONL protocol on stdin/stdout)",
    )
    parser.add_argument(
        "--no-session",
        action="store_true",
        help="Disable session persistence (RPC / SDK)",
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
        "-r",
        "--resume",
        dest="resume_picker",
        action="store_true",
        help="Pick a recent session for this cwd",
    )
    parser.add_argument(
        "--fork",
        dest="fork_session",
        metavar="PATH_OR_ID",
        help="Fork from a session path or id in current cwd",
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


def _resolve_default_model(cli_model: str | None) -> str:
    settings = load_settings(os.getcwd())
    if cli_model:
        return cli_model
    if settings.default_model:
        provider = settings.default_provider
        if provider and "/" not in settings.default_model:
            return f"{provider}/{settings.default_model}"
        return settings.default_model
    if settings.default_provider:
        registry = get_registry()
        for model in registry.get_all():
            if model.provider == settings.default_provider:
                return f"{model.provider}/{model.id}"
    return "anthropic/claude-sonnet-4-5"


def _resolve_thinking(
    cli_level: str | None,
    model_pattern: str,
) -> str | None:
    settings = load_settings(os.getcwd())
    registry = get_registry()
    parsed = parse_model_pattern(model_pattern, registry)
    if parsed and parsed.thinking_level:
        return parsed.thinking_level
    if cli_level:
        return cli_level
    return settings.default_thinking_level


def _pick_resume_session_path(cwd: Path) -> str | None:
    sessions = SessionManager.list_paths_for_cwd(cwd)
    if not sessions:
        print("No sessions found for current directory.", file=sys.stderr)
        return None
    if not sys.stdin.isatty() or len(sessions) == 1:
        return str(sessions[0])
    print("Select a session:")
    for idx, path in enumerate(sessions, start=1):
        print(f"  {idx}. {path.name}")
    raw = input("Enter number (blank=latest): ").strip()
    if not raw:
        return str(sessions[0])
    try:
        selected = int(raw)
    except ValueError:
        print("Invalid selection; using latest session.", file=sys.stderr)
        return str(sessions[0])
    if selected < 1 or selected > len(sessions):
        print("Selection out of range; using latest session.", file=sys.stderr)
        return str(sessions[0])
    return str(sessions[selected - 1])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_models:
        return _list_models()

    model_pattern = _resolve_default_model(args.model)
    thinking_level = _resolve_thinking(args.thinking_level, model_pattern)
    tools_raw = args.tools
    tools = [name.strip() for name in tools_raw.split(",") if name.strip()]
    cwd = Path(os.getcwd()).resolve()
    selected_session_path: str | None = args.session_path
    if args.resume_picker:
        selected_session_path = _pick_resume_session_path(cwd)
        if selected_session_path is None:
            return 1

    if args.mode == "rpc":
        from pi_coding_agent.modes.rpc_mode import RpcModeOptions, run_rpc_mode

        rpc_options = RpcModeOptions(
            model=model_pattern,
            tools=tools,
            api_key=args.api_key,
            provider=args.provider,
            thinking_level=thinking_level,
            no_session=args.no_session,
            continue_session=args.continue_session,
            session_path=selected_session_path,
            no_context_files=args.no_context_files,
            fork_session=args.fork_session,
        )
        try:
            return asyncio.run(run_rpc_mode(rpc_options))
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.print_mode:
        if not args.prompt:
            parser.error("print mode requires a prompt argument")
        options = PrintModeOptions(
            prompt=args.prompt,
            model=model_pattern,
            system_prompt=args.system,
            tools=tools,
            api_key=args.api_key,
            provider=args.provider,
            thinking_level=thinking_level,
            verbose=args.verbose,
            mode=args.mode,
            continue_session=args.continue_session,
            session_path=selected_session_path,
            fork_session=args.fork_session,
            no_context_files=args.no_context_files,
        )
        try:
            return asyncio.run(run_print_mode(options))
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.prompt is not None:
        options = PrintModeOptions(
            prompt=args.prompt,
            model=model_pattern,
            system_prompt=args.system,
            tools=tools,
            api_key=args.api_key,
            provider=args.provider,
            thinking_level=thinking_level,
            verbose=args.verbose,
            mode=args.mode,
            continue_session=args.continue_session,
            session_path=selected_session_path,
            fork_session=args.fork_session,
            no_context_files=args.no_context_files,
        )
        try:
            return asyncio.run(run_print_mode(options))
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    interactive = InteractiveOptions(
        model_pattern=model_pattern,
        system_prompt=args.system,
        tools=tools,
        api_key=args.api_key,
        provider=args.provider,
        thinking_level=thinking_level,
        verbose=args.verbose,
        continue_session=args.continue_session,
        session_path=selected_session_path,
        fork_session=args.fork_session,
        no_context_files=args.no_context_files,
    )
    try:
        return asyncio.run(run_interactive_mode(interactive))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
