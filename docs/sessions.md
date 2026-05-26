# Sessions and Branching

This document reflects the currently supported session features in piPy.

## Interactive commands

Start interactive mode:

```bash
./pipy-test.sh
```

### `/tree` and `/clone`

- `/tree` prints a compact session tree and active leaf
- `/clone [entryId]` forks only the selected branch path into a new session file
- If `entryId` is omitted, `/clone` uses the current active leaf
- Both commands require a persisted session file

### `/new`, `/name`, `/resume`

- `/new` creates a fresh persisted session and switches to it
- `/name <name>` sets the display name in the session header
- `/resume` opens a recent-session picker and switches to the selected session

Related helpers:

- `/session` prints current session file path
- `/export [file]` exports transcript HTML

## Continue/fork/session-path flags

These flags are currently supported by the CLI:

- `-c`, `--continue`  
  Continue the latest session for current working directory
- `--session <path>`  
  Open a specific session file
- `-r`, `--resume`  
  Open a recent-session picker before starting
- `--fork <path_or_id>`  
  Fork a session by path or session id in current cwd

The flags are available across text/print, interactive, and RPC startup paths.

## SDK equivalents

`CreateAgentSessionOptions` supports the same session selectors:

- `continue_session=True`
- `session_path='.../session.jsonl'`
- `fork_session='path-or-id'`

Selection behavior:

1. `session_path` has priority when provided
2. `fork_session` creates a new session from the source session
3. `continue_session` uses latest session for cwd
4. Otherwise a new session file is created

## Notes and limits

- `--no-session` (RPC) creates in-memory sessions; persisted-session commands do not apply there
- Session picker (`/resume` or `--resume`) defaults to latest when input is non-interactive
