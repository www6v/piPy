# Python SDK Examples

Programmatic usage of `pi_coding_agent.create_agent_session()` in Python.

These examples mirror the TypeScript examples in
`harness/pi/packages/coding-agent/examples/sdk` feature-by-feature.

## Examples

- `01-minimal.py`: Simplest usage
- `02-custom-model.py`: Select model and thinking level
- `03-custom-prompt.py`: Replace system prompt
- `04-skills.py`: Discover and scope skills
- `05-tools.py`: Tool allowlists
- `06-extensions.py`: Load Python extensions
- `07-context-files.py`: Context files (AGENTS.md / CLAUDE.md)
- `08-prompt-templates.py`: File-based prompt templates
- `09-api-keys-and-oauth.py`: API key and auth storage flow
- `10-settings.py`: Settings from `.pi/settings.json`
- `11-sessions.py`: In-memory, persistent, continue, open, fork
- `12-full-control.py`: Explicit no-discovery setup
- `13-session-runtime.py`: Replace active session manually

## Running

```bash
cd packages/pi_coding_agent
python examples/sdk/01-minimal.py
```
