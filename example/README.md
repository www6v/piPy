# Runnable SDK Examples

Real examples that call live models and tools (no faux/mock providers).

## Prerequisites

- API key in `~/.pi/agent/auth.json` or provider env vars
- `find-skills` installed at `~/.agents/skills/find-skills`
- Node.js / `npx` for the Skills CLI (`npx skills find`)

## find-skills.py

Search the open agent skills ecosystem using the `find-skills` skill:

```bash
# from repo root
python example/find-skills.py

# custom query
python example/find-skills.py "react performance"

# explicit model
PIPY_MODEL=anthropic/claude-sonnet-4-5 python example/find-skills.py
```

Install the skill if missing:

```bash
npx skills add vercel-labs/agent-skills@find-skills -g -y
```
