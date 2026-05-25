# Prompt Templates

Prompt templates are markdown snippets expanded from `/name ...`.

## Quick start

```bash
mkdir -p .pi/prompts
cat > .pi/prompts/review.md <<'EOF'
---
description: Quick review template
argument-hint: "<path>"
---
Review $1 for bugs and missing tests.
EOF
./pipy-test.sh --provider faux --model faux/test "/review README.md"
```

## Locations

- `~/.pi/agent/prompts/*.md`
- `.pi/prompts/*.md`
- CLI: `--prompt-template <path>` (repeatable)
- Settings: `prompts` array
- Extensions via `resources_discover.promptPaths`

Disable default discovery:

- `--no-prompt-templates`

## File Format

```markdown
---
description: Review a file quickly
argument-hint: "<path> [focus]"
---
Review $1 with focus: ${@:2}
```

- filename `review.md` -> command `/review`
- `description` optional (fallback: first non-empty body line)
- `argument-hint` optional (autocomplete hint)

## Arguments

- `$1`, `$2`, ... positional
- `$@` and `$ARGUMENTS` all args joined
- `${@:N}` slice from N (1-indexed)
- `${@:N:L}` length-limited slice

## Collision Rule

If multiple templates share the same name, first one wins and a collision
diagnostic is emitted (see RPC `get_resource_diagnostics`).
