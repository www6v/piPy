# RPC Mode

Headless JSONL protocol on stdin/stdout (pi: [`docs/rpc.md`](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/docs/rpc.md) subset).

## Start

```bash
pipy --mode rpc --no-session --provider faux --model faux/test
```

For real models, omit `--provider faux` and configure `~/.pi/agent/models.json` + auth.

## Framing

- One JSON object per line, delimiter **LF only** (`\n`)
- Strip optional trailing `\r` from `\r\n`
- Do not use Unicode line separators inside payloads

## Commands (implemented)

| Command | Description |
|---------|-------------|
| `prompt` | `{"type":"prompt","message":"..."}` |
| `abort` | Stop current run |
| `get_state` | Model, thinking, streaming, session paths |
| `get_messages` | Full message list |
| `get_available_models` | Registry models |
| `get_commands` | Extension/prompt/skill slash commands currently available (`sourceInfo` included) |
| `get_resource_diagnostics` | Resource load/collision diagnostics for skills/prompts/extensions |
| `reload` | Reload extensions/skills/prompts and return updated commands/diagnostics |
| `set_model` | `{"type":"set_model","provider":"...","modelId":"..."}` |
| `set_thinking_level` | `{"type":"set_thinking_level","level":"high"}` |
| `new_session` | Fresh session file |
| `compact` | `{"type":"compact"}` or with `customInstructions`; requires a persisted `--session` (not `--no-session`) |
| `set_auto_compaction` | `{"type":"set_auto_compaction","enabled":true}` |
| `set_auto_retry` | `{"type":"set_auto_retry","enabled":true}` toggles bounded auto-retries |
| `abort_retry` | `{"type":"abort_retry"}` cancels an in-flight retry backoff wait |
| `bash` | `{"type":"bash","command":"ls -la"}` executes shell command and stores output as user context |
| `get_session_stats` | Token/message/cost/session metrics for current transcript |
| `export_html` | `{"type":"export_html","outputPath":"/tmp/session.html"}` exports transcript |
| `steer` | `{"type":"steer","message":"..."}` (while streaming use `prompt` + `streamingBehavior` instead) |
| `follow_up` | `{"type":"follow_up","message":"..."}` |
| `set_steering_mode` | `"mode"` is `all` or `one-at-a-time` |
| `set_follow_up_mode` | Same `mode` values as steering |

Successful `compact` responses include `data.summary`, `data.firstKeptEntryId`, and `data.tokensBefore`.

Optional `id` on any command; matching `response` includes the same `id`.

### Response shape

```json
{"id":"1","type":"response","command":"prompt","success":true}
```

```json
{"id":"2","type":"response","command":"get_state","success":true,"data":{"model":{...},"thinkingLevel":"medium","isStreaming":false}}
```

### Events

Agent events are streamed as JSON lines (same shape as `--mode json`), e.g. `message_update`, `message_end`, `agent_end`. Session dict lines include `queue_update`, `compaction_*`, and `auto_retry_start` / `auto_retry_end` when retries run.

## Python client

```python
from pi_coding_agent.rpc_client import RpcClient

client = RpcClient(extra_args=["--provider", "faux", "--model", "faux/test"])
client.start()
client.prompt("List files", request_id="1")
response, events = client.request({"id": "1", "type": "prompt", "message": "hi"})
client.close()
```

Prefer the **SDK** (`create_agent_session`) when both ends are Python.

## Not yet implemented

Extension UI — see pi `rpc.md` for the full protocol ahead of piPy.
