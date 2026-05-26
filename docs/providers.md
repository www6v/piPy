# Providers and Auth

This document reflects the current implementation in piPy.

## Interactive `/login` and `/logout`

In interactive mode (`./pipy-test.sh`), use:

```bash
/login <provider> <key>
/logout <provider>
```

Examples:

```text
/login openai sk-xxx
/logout openai
```

Behavior:

- `/login` writes `{ "type": "api_key", "key": "<key>" }` for that provider in `auth.json`
- `/logout` removes that provider entry from `auth.json` (no-op if missing)

## RPC login/logout payloads

In RPC mode (`pipy --mode rpc`), send JSON commands:

```json
{"id":"1","type":"login","provider":"openai","key":"sk-xxx"}
{"id":"2","type":"logout","provider":"openai"}
```

Success responses:

```json
{"id":"1","type":"response","command":"login","success":true}
{"id":"2","type":"response","command":"logout","success":true,"data":{"removed":true}}
```

Validation errors return `success: false` with an `error` string.

## `auth.json` path and resolution order

Default path:

- `~/.pi/agent/auth.json`

If `PI_CODING_AGENT_DIR` is set, path becomes:

- `$PI_CODING_AGENT_DIR/auth.json`

Auth resolution order for a model request:

1. CLI or SDK explicit API key override (`--api-key` / `api_key`)
2. `auth.json` provider key (written by `/login`)
3. Provider environment variables (for example `OPENAI_API_KEY`, `ANTHROPIC_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`)
4. `models.json` provider `apiKey` configuration

Note: if a provider is configured with `authHeader: true` in `models.json`, resolved keys are converted to `Authorization: Bearer ...` header.

## Placeholder providers

These providers are currently registered but placeholder-limited:

- `azure-openai-responses`
- `amazon-bedrock`

Current status:

- They appear in model discovery/listing
- Their runtime stream adapters emit explicit "not implemented yet" errors
- For Azure today, use `models.json` mapping to `openai-completions` if you need working runtime requests
