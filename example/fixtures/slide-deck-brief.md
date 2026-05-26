# Building Reliable AI Agents

## Why agents fail in production

Most demos work once; production needs retries, clear tool boundaries, and
observable runs. Without those, small environment gaps become full stops.

## Three design pillars

1. **Deterministic setup** — workspace dirs, config files, and credentials
   exist before the agent starts.
2. **Scoped tools** — read, write, and bash only where needed; no surprise
   side effects.
3. **Checkpointed artifacts** — outlines, prompts, and outputs on disk so
   runs can resume.

## SDK takeaway

Programmatic sessions should bootstrap the filesystem the skill expects,
then invoke `/skill:baoyu-slide-deck` with flags that match the run mode
(for example `--outline-only` for a fast, non-interactive pass).
