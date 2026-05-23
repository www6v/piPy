from pi_coding_agent.cli import build_parser, main


def test_help_exits_zero() -> None:
    assert main([]) == 0


def test_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["-p", "hello"])
    assert args.print_mode is True
    assert args.prompt == "hello"
    assert args.tools == "read,bash"
