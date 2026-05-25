# Extensions (Python)

`piPy` supports Python-based extensions that mirror the core lifecycle style of
`pi` extensions.

## Quick start

```bash
mkdir -p .pi/extensions
cp examples/extensions/demo_extension.py .pi/extensions/demo_extension.py
./pipy-test.sh --provider faux --model faux/test
# In REPL: /reload
```

## Locations

Auto-discovery paths:

- `~/.pi/agent/extensions`
- `.pi/extensions` (project local)

Extra paths:

- CLI: `--extension /path/to/ext.py` (repeatable)
- Settings: `extensions` array in `settings.json`

Disable discovery:

- `--no-extensions`

## Extension Module Shape

An extension module exports `register(pi)` (or `setup(pi)`).

```python
def register(pi):
    def on_start(event, ctx):
        # event["reason"]: startup | reload
        pass

    pi.on("session_start", on_start)
```

## Supported API (current)

- `pi.register_command(name, description=..., handler=...)`
- `pi.register_tool(tool_object)`
- `pi.on(event, handler)` for:
  - `session_start`
  - `resources_discover`
  - `input`
  - `before_agent_start`
  - `context`
  - `tool_call`
  - `tool_result`

Command handlers receive `(args, ctx)` where `ctx.session` is the active
`AgentSession`.

## Events

### `resources_discover`

Return extra resource paths at startup/reload:

```python
def on_discover(event, ctx):
    return {
        "skillPaths": ["/opt/skills"],
        "promptPaths": ["/opt/prompts"],
        "themePaths": [],
    }
```

`event["reason"]` is `startup` or `reload`.

### `context`

Can rewrite message context before each LLM call:

```python
def on_context(event, ctx):
    messages = event["messages"]
    return {"messages": messages}
```

### `tool_call`

Can block or rewrite tool args:

```python
def on_tool_call(event, ctx):
    if event["toolName"] == "bash":
        cmd = event["input"].get("command", "")
        if "rm -rf" in cmd:
            return {"block": True, "reason": "blocked by extension"}
```

### `tool_result`

Can patch result content/details/error flags:

```python
def on_tool_result(event, ctx):
    if event["toolName"] == "bash":
        content = event.get("content", [])
        return {"content": content, "isError": event.get("isError", False)}
```

## Reload

- Interactive: `/reload`
- RPC: `{"type":"reload"}`

Reload updates:

- extension commands/tools/hooks
- skill/prompt inventories
- system prompt (including context/skills sections)

See example: `examples/extensions/demo_extension.py`
