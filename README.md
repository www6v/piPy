# piPy

Python port of the [pi](https://github.com/earendil-works/pi-mono) agent harness (reference: `../pi`).

## Architecture

| Package | Role |
|---------|------|
| `pi_ai` | LLM API + `models.json` registry |
| `pi_agent` | Agent loop, tool execution, events |
| `pi_coding_agent` | CLI print mode, `read` + `bash` tools |

## Setup

```bash
uv sync
uv run pytest
./pipy-test.sh --help
```

## models.json (same as pi)

piPy reads **`~/.pi/agent/models.json`** — the same file as pi. You can copy
[docs/models.json.example](docs/models.json.example) or share your existing pi config.

Config directory override (same env as pi):

```bash
export PI_CODING_AGENT_DIR=~/.pi/agent   # optional; default is ~/.pi/agent
```

Features aligned with pi MVP:

- JSON with `//` comments and trailing commas
- Custom providers (`baseUrl`, `api`, `apiKey`, `models`)
- Built-in provider overrides (`baseUrl`, `compat`, `modelOverrides`)
- `apiKey` as env var name, literal, or `!shell command`
- `compat.thinkingFormat: "qwen"` for DashScope
- APIs: `openai-completions`, `anthropic-messages`

Built-in models (without models.json): `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-5`, `anthropic/claude-haiku-4-5`.

## Print mode

### Claude

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./pipy-test.sh --model anthropic/claude-sonnet-4-5 -p "List files here"
```

### Qwen (DashScope) via models.json

```bash
mkdir -p ~/.pi/agent
cp docs/models.json.example ~/.pi/agent/models.json
export DASHSCOPE_API_KEY=sk-...

./pipy-test.sh --model dashscope/qwen-plus -p "List files here"
```

### Faux (tests)

```bash
./pipy-test.sh --provider faux --model faux/test -p "hello"
```

### Verbose event log (stderr)

Matches pi MVP acceptance: `agent_start` → `turn_start` → `message_*` → `tool_execution_*`:

```bash
./pipy-test.sh -v -p "List files" --provider faux --model faux/test
```

## P1 features (implemented)

| Feature | Usage |
|---------|--------|
| Tools `edit`, `write`, `grep` | `--tools read,edit,write,grep,bash` |
| Session JSONL | auto per cwd; `-c` continue; `--session path.jsonl` |
| `auth.json` | `~/.pi/agent/auth.json` (same format as [pi](https://pi.dev/docs/latest)) |
| `--mode json` | JSONL events on stdout ([JSON mode](https://pi.dev/docs/latest)) |
| `--list-models` | List built-in + models.json models |

```bash
# Edit a file
./pipy-test.sh -p "Add a header comment to README.md" --tools read,edit

# Continue last session in this directory
./pipy-test.sh -c -p "What did we discuss?"

# JSON event stream
./pipy-test.sh --mode json -p "hi" --provider faux --model faux/test
```

## Roadmap

Further work: [docs/superpowers/plans/2026-05-23-pipy-p1.md](docs/superpowers/plans/2026-05-23-pipy-p1.md) §8（glob/find/ls、REPL、compaction、RPC）。

## Limits

- Print mode only (`-p`); no interactive TUI
- OAuth `/login` not implemented (use `auth.json` `api_key` or env vars)
- APIs: `openai-completions`, `anthropic-messages` only
- Default tools: `read`, `bash` (also available: `edit`, `write`, `grep`)

## Environment

| Provider | Env var(s) |
|----------|------------|
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_OAUTH_TOKEN` |
| OpenAI | `OPENAI_API_KEY` |
| Custom (e.g. DashScope) | Set in models.json `apiKey` (e.g. `DASHSCOPE_API_KEY`) |
