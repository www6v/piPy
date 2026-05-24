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

## P3a (implemented)

Compaction, `.pi`/project context injection, steer/follow-up queues, and
bounded auto-retries mirror core pi agent-session behavior.

| Area | Notes |
|------|--------|
| Compaction | Auto when tokens exceed ``contextWindow - reserveTokens``; manual CLI/RPC/SDK |
| Context files | `AGENTS.md`, `CLAUDE.md`, `.pi/SYSTEM.md`; ``--no-context-files`` skips |
| Queues | `steer` / `follow_up` (+ streaming `prompt` with `streamingBehavior`) |
| Retry | Overload/rate-limit/5xx-ish errors; backoff via ``settings.retry`` |

```json
{
  "retry": {"enabled": true, "maxRetries": 3, "baseDelayMs": 2000},
  "compaction": {
    "enabled": true,
    "reserveTokens": 16384,
    "keepRecentTokens": 20000
  }
}
```

Demonstrate faux retry wiring (JSON lines include ``auto_retry_*``):

```bash
./pipy-test.sh --mode json -p "hi" \
  --provider faux --model faux/retry-test
```

Plan: [`docs/superpowers/plans/2026-05-24-pipy-p3a.md`](docs/superpowers/plans/2026-05-24-pipy-p3a.md).

## Roadmap

## Programmatic usage (P2)

### SDK

```python
from pi_coding_agent import CreateAgentSessionOptions, create_agent_session

result = await create_agent_session(
    CreateAgentSessionOptions(model="anthropic/claude-sonnet-4-5", tools=["read", "bash"])
)
await result.session.prompt("Summarize this repo")
```

See [docs/sdk.md](docs/sdk.md) and [examples/sdk/minimal.py](examples/sdk/minimal.py).

### RPC mode

```bash
pipy --mode rpc --no-session
# JSONL commands on stdin, events + responses on stdout
```

See [docs/rpc.md](docs/rpc.md). Python helper: `pi_coding_agent.rpc_client.RpcClient`.

Further work: extensions, fuller RPC parity — see pi docs.

## P3b resources (in progress)

Skills, prompt templates, and Python extensions now load with pi-style locations
and can be enabled/disabled via CLI flags.

| Resource | Default locations |
|----------|-------------------|
| Skills | `~/.pi/agent/skills`, `~/.agents/skills`, `.pi/skills`, ancestor `.agents/skills` |
| Prompts | `~/.pi/agent/prompts`, `.pi/prompts` |
| Extensions | `~/.pi/agent/extensions`, `.pi/extensions` |

Key flags:

```bash
./pipy-test.sh --no-skills --no-prompt-templates --no-extensions
./pipy-test.sh --skill ./skills --prompt-template ./prompts --extension ./ext.py
```

Supported command expansion:
- Prompt templates: `/template-name ...`
- Skills: `/skill:skill-name ...` (controlled by `enableSkillCommands`)
- Extensions: custom slash commands registered by Python extension modules

## Interactive mode

无参数启动 REPL（无 TUI，对标 pi「Start here」最小交互）：

```bash
./pipy-test.sh
```

| 命令 | 说明 |
|------|------|
| `/help` | 帮助 |
| `/exit` | 退出 |
| `/model [pattern]` | 查看或切换模型（支持 `provider/model:high`） |
| `/tools` | 当前工具列表 |
| `/session` | 会话文件路径 |

单行 prompt 也可直接运行（等同 `-p`）：

```bash
./pipy-test.sh "hello"
```

## Settings (`settings.json`)

与 pi 相同路径：全局 `~/.pi/agent/settings.json`，项目 `.pi/settings.json`（后者覆盖前者）。

```json
{
  "defaultProvider": "anthropic",
  "defaultModel": "claude-sonnet-4-5",
  "defaultThinkingLevel": "medium"
}
```

CLI：`--model`、`--thinking` 优先于 settings；模型 pattern 支持 `anthropic/claude-sonnet-4-5:high`。

## Tools

默认：`read,bash`。全部内置：`read`, `edit`, `write`, `grep`, `find`, `ls`, `bash`。

```bash
./pipy-test.sh --tools read,find,ls -p "list python files"
```

## OpenAI `compat`（models.json）

对 `openai-completions` 网关可设置：

```json
"compat": {
  "supportsDeveloperRole": false,
  "supportsReasoningEffort": false,
  "thinkingFormat": "qwen"
}
```

`supportsDeveloperRole: false` 时 system prompt 使用 `system` 角色而非 `developer`。

## Limits

- 交互为终端 REPL，无 pi TUI / 主题 / 快捷键
- OAuth `/login` 未实现（用 `auth.json` 或环境变量）
- API：`openai-completions`、`anthropic-messages`

## Environment

| Provider | Env var(s) |
|----------|------------|
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_OAUTH_TOKEN` |
| OpenAI | `OPENAI_API_KEY` |
| Custom (e.g. DashScope) | Set in models.json `apiKey` (e.g. `DASHSCOPE_API_KEY`) |

### Anta 企业 Anthropic 网关（`claude-sonnet-4-6`）

与 curl 等价：`POST …/private/llm/v1/messages`，`Authorization: Bearer <token>`。

1. 复制示例配置（**勿把 token 提交进 git**）：

```bash
cp docs/models.json.example ~/.pi/agent/models.json
```

2. 设置 token（任选其一）：

```bash
export ANTA_AI_TOKEN='你的 Bearer token'
```

或写入 `~/.pi/agent/auth.json`（与 pi 相同格式）：

```json
{
  "anthropic": {
    "type": "api_key",
    "key": "你的 Bearer token"
  }
}
```

3. 运行：

```bash
./pipy-test.sh --model anthropic/claude-sonnet-4-6 -p "你是什么模型？"
```

`baseUrl` 在示例里为 `https://ai.anta.com/aimodels-server/private/llm`（piPy 会请求 `{baseUrl}/v1/messages`）。`authHeader: true` 表示使用 Bearer，而不是官方 `x-api-key`。
