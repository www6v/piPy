# my-app — pi-coding-agent SDK template

Minimal standalone app that depends on **pi-coding-agent** from the piPy
monorepo. Use it as a starting point for your own product or automation.

## Layout

```
my-app/
├── pyproject.toml      # depends on pi-coding-agent (path → monorepo)
├── src/my_app/
│   └── main.py         # create_agent_session + one prompt
├── example/            # runnable SDK examples (slide deck, find-skills)
└── workspace/          # agent cwd (AGENTS.md, future .pi/*)
```

## Quick start (inside piPy repo)

From this directory:

```bash
uv sync
uv run my-app
uv run my-app "List three bullet ideas for a landing page."
```

Default model is **faux/demo** (no API key). For a real provider:

```bash
export PIPY_MODEL=anthropic/claude-sonnet-4-5
# ensure ~/.pi/agent/auth.json or env API keys — see piPy docs/providers.md
uv run my-app "Summarize AGENTS.md in one sentence."
```

Or:

```bash
uv run my-app --model openai/gpt-4o "Hello"
```

## Copy outside the monorepo

1. Copy `templates/my-app/` to your own git repo.
2. Replace `[tool.uv.sources]` in `pyproject.toml` with one of:

**PyPI (after piPy packages are published):**

```toml
dependencies = ["pi-coding-agent>=0.1.0"]
# remove [tool.uv.sources] pi-* path entries
```

**Git:**

```toml
[tool.uv.sources]
pi-coding-agent = {
    git = "https://github.com/YOUR_ORG/piPy.git",
    subdirectory = "packages/pi_coding_agent",
}
```

3. Run `uv sync` in the new project.
4. Extend `src/my_app/main.py` — add `skill_paths`, `extension_paths`, session
   files, or a web/RPC layer. See [docs/sdk.md](../../docs/sdk.md) and
   [example/](example/).

## Related docs

- [SDK guide](../../docs/sdk.md)
- [Providers & auth](../../docs/providers.md)
- [Runnable examples](example/README.md)
