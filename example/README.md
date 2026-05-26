# Runnable SDK Examples

Real examples that call live models and tools (no faux/mock providers).

## Prerequisites

- API key in `~/.pi/agent/auth.json` or provider env vars
- Skills installed under `~/.agents/skills/` (see each script)
- Node.js / `npx` when a skill runs merge scripts (`baoyu-slide-deck` PPTX/PDF)

## baoyu-slide-deck.py

Generate a slide deck with the **baoyu-slide-deck** skill. Missing
`analysis.md` before Step 3 is handled by the **`slide_deck_guard` extension**
(not by the main script writing analysis directly).

| Component | Role |
|-----------|------|
| `baoyu-slide-deck.py` | Thin driver: workspace prep, session, prompt, verify |
| `slide_deck_bootstrap.py` | Shared logic: slug, `analysis.md` template, `ensure_analysis_md()` |
| `extensions/slide_deck_guard.py` | SDK hooks: `before_agent_start` + `write` guard |

### Lifecycle

1. Script writes `EXTEND.md`, `content.md`, and creates `slide-deck/`.
2. On `/skill:baoyu-slide-deck ...`, extension **`before_agent_start`** calls
   `ensure_analysis_md()` and appends runbook to the system prompt.
3. If the agent `write`s `outline.md` / `prompts/*` without `analysis.md`, the
   **`tool_call`** hook bootstraps first, then allows the write.

| Path | Purpose |
|------|---------|
| `.baoyu-skills/baoyu-slide-deck/EXTEND.md` | defaults, `review: false` |
| `content.md` | source for `/skill:... content.md` |
| `slide-deck/{slug}/analysis.md` | created by extension before Step 3 |
| `slide-deck/{slug}/source.md` | copy of source in topic dir |

```bash
# from repo root — outline only (default)
python example/baoyu-slide-deck.py

python example/baoyu-slide-deck.py --content ./my-article.md --workspace /tmp/slide-run
python example/baoyu-slide-deck.py --full
python example/baoyu-slide-deck.py --force-analysis

PIPY_MODEL=anthropic/claude-sonnet-4-5 python example/baoyu-slide-deck.py
```

Post-run: exits non-zero if `analysis.md` is missing, or outline-only without
`outline.md`.

```bash
pytest example/tests -q
```

## find-skills.py

Search the open agent skills ecosystem using the `find-skills` skill:

```bash
python example/find-skills.py
python example/find-skills.py "react performance"
```

Install the skill if missing:

```bash
npx skills add vercel-labs/agent-skills@find-skills -g -y
```
