# piPy

Python port of the [pi](https://github.com/earendil-works/pi-mono) agent harness (reference: `../pi`).

## Architecture

| Package | Role |
|---------|------|
| `pi_ai` | LLM API (OpenAI + faux test provider) |
| `pi_agent` | Agent loop, tool execution, events |
| `pi_coding_agent` | CLI print mode, `read` + `bash` tools |

## Setup

```bash
uv sync
uv run pytest
./pipy-test.sh --help
```

## Print mode

```bash
export OPENAI_API_KEY=...
./pipy-test.sh -p "List files in this directory"
./pipy-test.sh -p "Read README.md and summarize" --tools read,bash
```

Faux provider (no API key, for tests):

```bash
./pipy-test.sh --provider faux --model faux/test -p "hello"
```

## MVP limits

- Print mode only (`-p`); no interactive TUI
- Providers: `openai`, `faux`
- Tools: `read`, `bash` (default allowlist)
- No session persistence, extensions, or compaction

## Environment

Uses the same key name as pi for OpenAI: `OPENAI_API_KEY`.
