from pi_coding_agent.cli import build_parser, main


def test_help_exits_zero() -> None:
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["-p", "hello"])
    assert args.print_mode is True
    assert args.prompt == "hello"
    assert args.tools == "read,bash"
    assert args.verbose is False


def test_parser_verbose_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["-p", "hello", "-v"])
    assert args.verbose is True


def test_parser_json_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(["-p", "hello", "--mode", "json"])
    assert args.mode == "json"


def test_parser_rpc_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(["--mode", "rpc", "--no-session"])
    assert args.mode == "rpc"
    assert args.no_session is True


def test_parser_resume_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["-r"])
    assert args.resume_picker is True


def test_parser_fork_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--fork", "abc123"])
    assert args.fork_session == "abc123"


def test_parser_resource_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--no-skills",
            "--no-prompt-templates",
            "--no-extensions",
            "--skill",
            "/tmp/skills",
            "--prompt-template",
            "/tmp/prompts",
            "--extension",
            "/tmp/ext.py",
        ]
    )
    assert args.no_skills is True
    assert args.no_prompt_templates is True
    assert args.no_extensions is True
    assert args.skill_paths == ["/tmp/skills"]
    assert args.prompt_paths == ["/tmp/prompts"]
    assert args.extension_paths == ["/tmp/ext.py"]
