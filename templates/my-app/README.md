# my-app — pi-coding-agent SDK template

Minimal standalone app that depends on **pi-coding-agent** from the
[piPy](https://gitee.com/www6v6v/piPy) Git repository. Copy this folder to
your own repo or use it as-is; no monorepo path required.

## Layout

```
my-app/
├── pyproject.toml      # pi-coding-agent via Git subdirectory
├── src/my_app/
│   └── main.py         # create_agent_session + one prompt
├── example/            # runnable SDK examples (slide deck, find-skills)
└── workspace/          # agent cwd (AGENTS.md, future .pi/*)
```

## Quick start

From this directory:

```bash
uv sync
uv run my-app
uv run my-app "List three bullet ideas for a landing page."
```

Default model is **faux/demo** (no API key). For a real provider:

```bash
export PIPY_MODEL=anthropic/claude-sonnet-4-5
# ensure ~/.pi/agent/auth.json or env API keys
uv run my-app "Summarize AGENTS.md in one sentence."
```

Or:

```bash
uv run my-app --model openai/gpt-4o "Hello"
```

## SDK source (Git)

`pyproject.toml` pulls three workspace packages from one repo:

| Package | Subdirectory |
|---------|----------------|
| `pi-coding-agent` | `packages/pi_coding_agent` |
| `pi-agent` | `packages/pi_agent` |
| `pi-ai` | `packages/pi_ai` |

Pin a release by setting `rev` on each `[tool.uv.sources]` entry, e.g.
`rev = "v0.1.0"` or a commit SHA. After changing `rev` or `git` url, run
`uv lock` then `uv sync`.

**PyPI (when published):** remove the `[tool.uv.sources]` block and use
`dependencies = ["pi-coding-agent>=0.1.0"]` only.

**Develop against a local piPy clone:** temporarily replace Git entries with
path + editable, or use `uv pip install -e /path/to/piPy/packages/pi_coding_agent`.

## Extend

- Edit `src/my_app/main.py` — `skill_paths`, `extension_paths`, sessions, etc.
- Examples: [example/](example/)
- Upstream SDK docs: piPy `docs/sdk.md` and `docs/providers.md` in the piPy repo.
