# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.2.x   | ✅ Current |
| 0.1.x   | ❌ No longer maintained |

---

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities privately via GitHub's [Security Advisories](https://github.com/zackbear/dytypo-mcp/security/advisories/new) feature.

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- The version(s) affected
- Any suggested mitigations if you have them

You can expect an acknowledgment within **72 hours** and a status update within **7 days**.

---

## Security Model

DyTopo is a **local routing layer**. It runs on your machine alongside Claude Code and communicates only with:

- The local MCP stdio transport (no network listener)
- Third-party embedding APIs (OpenAI, Voyage AI) — only when those providers are configured

There is no authentication layer, no web server, and no inbound network exposure by design.

---

## API Key Handling

DyTopo reads API keys from environment variables or a local `.env` file. It does not:

- Log or print key values at any verbosity level
- Include key values in MCP tool responses or agent descriptions
- Transmit keys anywhere other than the provider's official API endpoint

**What is sent to embedding APIs**: Only the text of agent descriptions and task prompts — never file contents, shell output, or any other ambient data from your machine.

MCP server descriptions built from your `claude_desktop_config.json` include server names and environment variable *key names* only. Environment variable *values* (including secrets) are explicitly excluded.

### Key Storage

On Windows, prefer **Credential Manager**: `python secret_store.py set NAME` stores the key DPAPI-encrypted under your login as `dytopo/NAME`. The hook checks env vars first, then Credential Manager. It keeps keys out of plaintext files and out of synced or backed-up copies of the repo. It does not protect against code already running as you. Otherwise use `.env` (gitignored by default) or your shell profile. Never commit keys to version control. The `.gitignore` included in this repo excludes `.env` and `.dytopo_cache.json`.

---

## Embedding Cache

Embeddings are cached locally in `.dytopo_cache.json`. This file contains vector representations of your agent descriptions and task prompts — not raw text or API keys.

The cache file is gitignored. Do not commit it. On shared or multi-user machines, restrict read access to this file if your agent descriptions contain sensitive information.

Cache writes are atomic (written to a `.tmp` file then renamed) to prevent corruption on process kill.

---

## agents.yaml

`agents.yaml` is a plain-text registry of agent IDs and descriptions. If you include sensitive information in agent descriptions (e.g., internal system names, hostnames, or credentials), those strings will be:

- Sent to your configured embedding provider
- Stored in `.dytopo_cache.json`
- Potentially visible in MCP tool responses (`list_agents`, `get_routing_plan`)

Keep agent descriptions functional and non-sensitive.

---

## Hook (dytopo_hook.py)

The PreToolUse hook reads the `tool_input.prompt` field from Claude Code's Task dispatch and appends a routing annotation. It:

- Never modifies or suppresses the original task prompt
- Never executes shell commands or spawns subprocesses
- Fails silently — any error leaves the Task prompt unmodified and Claude proceeds normally

The hook runs with the same OS-level permissions as the Claude Code process.

---

## Bootstrap (bootstrap_agents.py)

`bootstrap_agents.py` reads files from your local filesystem:

- `~/.claude/skills/*/SKILL.md` — reads description text only
- `claude_desktop_config.json` / `.claude.json` — reads server names and env key names only; **never reads env values**

It writes only to `agents.yaml` in the project directory (or a path you specify with `--output`). It does not make network requests, run shell commands, or write anywhere else.

---

## Dependency Supply Chain

Core dependencies and their roles:

| Package | Purpose | Network access |
| --- | --- | --- |
| `mcp` | MCP stdio transport | stdio only |
| `numpy` | Vector math | None |
| `pyyaml` | YAML parsing | None |
| `python-dotenv` | `.env` loading | None |
| `openai` | Embeddings (if configured) | `api.openai.com` |
| `voyageai` | Embeddings (if configured) | `api.voyageai.com` |
| `sentence-transformers` | Local embeddings (if configured) | HuggingFace (first download only) |
| `schedule` | Scheduler for bootstrap | None |
| `pywin32` (Windows) | Credential Manager access (`secret_store.py`) | None |
| stdlib `urllib` | Jev routing (`jev_router.py`) | `api.typesafe.ai` or `ai-gateway.vercel.sh`; redirects are refused so the `Authorization` header can't follow a 3xx |

`requirements.txt` pins exact versions for the core and tested packages.

---

## Known Limitations

- **No input sanitization on agent IDs**: Agent IDs from `agents.yaml` are used as dictionary keys and returned in responses. They are not executed or interpolated into shell commands, but avoid using untrusted YAML sources.
- **YAML loading**: `agents.yaml` is loaded with `yaml.safe_load`. Do not replace this with `yaml.load` without an explicit `Loader`.
- **Local model download**: The `local` embedding provider downloads a model from HuggingFace on first use (~80 MB). In air-gapped environments, pre-download the model and set `DYTOPO_LOCAL_MODEL` to a local path.
- **O(N²) pruner**: The semantic pruner in `bootstrap_agents.py` is quadratic. With very large agent registries it is slow but not a security concern — it runs locally with no network exposure.
