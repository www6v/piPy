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

**SDK-first**: one `create_agent_session` run drives the workflow. The driver
loads skills into the session (`skill_paths`); the agent invokes
`/skill:baoyu-slide-deck` and, for `--full`, `/skill:baoyu-image-gen` — not
separate outer scripts or direct provider HTTP calls from the example code.

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
uv run python templates/my-app/example/baoyu-slide-deck.py

uv run python templates/my-app/example/baoyu-slide-deck.py --content ./my-article.md --workspace /tmp/slide-run
uv run python templates/my-app/example/baoyu-slide-deck.py --full --slides 3   # also loads baoyu-image-gen
uv run python templates/my-app/example/baoyu-slide-deck.py --force-analysis

PIPY_MODEL=anthropic/claude-sonnet-4-5 uv run python templates/my-app/example/baoyu-slide-deck.py
```

**Full pipeline output** (under workspace, topic slug may differ from bootstrap):

```
slide-deck/{slug}/outline.md
slide-deck/{slug}/prompts/*.md
slide-deck/{slug}/01-slide-cover.png …
slide-deck/{slug}/{slug}.pptx
```

Post-run: exits non-zero if `analysis.md` is missing; outline-only without
`outline.md`; or `--full` without `prompts/` and `NN-slide-*.png` files.

```bash
pytest templates/my-app/example/tests -q
```

## find-skills.py

Search the open agent skills ecosystem using the `find-skills` skill:

```bash
python templates/my-app/example/find-skills.py
python templates/my-app/example/find-skills.py "react performance"
```

Install the skill if missing:

```bash
npx skills add vercel-labs/agent-skills@find-skills -g -y
```
