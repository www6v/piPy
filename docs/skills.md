# Skills

Skills are markdown capability packs exposed as `/skill:<name>`.

## Quick start

```bash
mkdir -p .pi/skills/demo-skill
cat > .pi/skills/demo-skill/SKILL.md <<'EOF'
---
name: demo-skill
description: Demo skill that requests concise output.
---
Always answer in 3 bullets max.
EOF
./pipy-test.sh --provider faux --model faux/test "/skill:demo-skill summarize repo"
```

## Locations

- `~/.pi/agent/skills/`
- `~/.agents/skills/`
- `.pi/skills/`
- ancestor `.agents/skills/` directories
- CLI: `--skill <path>` (repeatable)
- Settings: `skills` array
- Extensions via `resources_discover.skillPaths`

Disable default discovery:

- `--no-skills`

## Skill Structure

Recommended directory layout:

```text
my-skill/
  SKILL.md
```

`SKILL.md` (or direct `.md` in some roots) should include frontmatter:

```markdown
---
name: my-skill
description: What this skill does and when to use it.
disable-model-invocation: false
---
```

## Runtime Behavior

- Visible skills are injected into system prompt as `<available_skills>...`
- `/skill:name args...` expands to full skill markdown + `User: args`
- `disable-model-invocation: true` hides skill from prompt injection but keeps
  explicit `/skill:name` behavior

## Collision Rule

If multiple skills share the same `name`, first one wins and a collision
diagnostic is emitted (see RPC `get_resource_diagnostics`).
