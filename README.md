# DyTopo MCP Server

Dynamic Topology Routing for Multi-Agent Systems via Semantic Matching.

Based on: **DyTopo: Dynamic Topology Routing for Multi-Agent Reasoning via Semantic Matching** (arXiv:2602.06039)

> **New to DyTopo?** See `QUICKSTART.md` for 5-minute setup.
> **LLM-Powered Discovery**: See `LLM_DISCOVERY.md` to auto-generate agent definitions.

---

## What It Does

Routes tasks to semantically relevant agents and builds dynamic communication graphs.

Instead of fixed topologies and broadcasting to all agents, you get:

- Task-conditioned agent selection via semantic similarity
- Sparse communication graphs (k-NN, star, or threshold)
- Automatic topology construction — no manual routing logic
- **Automatic subagent guidance** via the Claude Code PreToolUse hook, ranked by TypeSafe's Jev model in ~0.3s

---

## Installation

```bash
cd dytopo-mcp
pip install -r requirements.txt
```

---

## Embedding Providers

The **MCP server** (`server.py`) and the bootstrap pruner use embeddings. The hook does not; it ranks with Jev (see [below](#ranking-with-jev)). Set `DYTOPO_EMBEDDER` or let it auto-detect:

| Provider | Key Required | Package | Notes |
| -------- | ------------ | ------- | ----- |
| `openai` | `OPENAI_API_KEY` | `openai` | Default if key present. `text-embedding-3-small`. |
| `anthropic` | `VOYAGE_API_KEY` (or `ANTHROPIC_API_KEY`) | `voyageai` | Voyage AI `voyage-3-lite`. |
| `local` | None | `sentence-transformers` | Free, ~80 MB model download on first use. The import takes ~20s, which a long-running server pays only once at startup. |

**Auto-detection order**: openai → anthropic (Voyage) → local

```bash
# No API key — fully local
export DYTOPO_EMBEDDER=local

# OpenAI
export OPENAI_API_KEY="sk-..."

# Voyage AI (via anthropic provider name)
export VOYAGE_API_KEY="pa-..."        # or ANTHROPIC_API_KEY as alias
export DYTOPO_EMBEDDER=anthropic
```

Or copy `.env.example.txt` to `.env` and fill in your values.

### Embedding Cache

All providers cache embeddings to `.dytopo_cache.json`. Each text is embedded **once** and reused across restarts. Switching providers is safe — each has its own cache namespace keyed by `provider:sha256(text)`.

---

## Bootstrap: Populate agents.yaml from Your Environment

Out of the box, the server falls back to `agents.example.yaml` (14 generic agents). `bootstrap_agents.py` generates your own `agents.yaml` automatically from your **actual installed skills**, plugin skills, built-in Claude Code tools and MCP servers.

### Quick Start

```bash
# Scan and write agents.yaml
python bootstrap_agents.py

# Scan + remove semantically duplicate skills
python bootstrap_agents.py --prune

# Preview what pruning would remove (no writes)
python bootstrap_agents.py --prune --dry-run --threshold 0.90
```

### Sources

| Source | Default Location |
| ---- | --- |
| Built-in Claude Code tools | hardcoded (Bash, Read, Write, Edit, Glob, Grep, WebSearch, …) |
| Installed skills | `~/.claude/skills/`: reads each `SKILL.md` |
| Plugin skills | `~/.claude/plugins/`: marketplace plugins enabled in `settings.json` (`enabledPlugins`), plus plugins synced from claude.ai. Ids are `plugin:skill`, the name the Skill tool accepts |
| MCP servers | `claude_desktop_config.json` / `.claude.json` |
| claude.ai connectors | `claude mcp list`: connected connectors only (Vercel, Supabase, Context7, …). They are in no local config file. Ids are `mcp_claude_ai_<name>`, and the hint points at `mcp__claude_ai_<Name>__*` tools. Give each one a description in `description_overrides.yaml` |

### Description Overrides

Routing is only as good as the descriptions. MCP configs carry no description at all, and some `SKILL.md` descriptions are too terse to match on. Put hand-written replacements in `description_overrides.yaml` (gitignored; override the path with `DYTOPO_DESCRIPTION_OVERRIDES`), keyed by agent id. Your `SKILL.md` files are never touched:

```yaml
mcp_muninn: >-
  Long-term memory database. Remember, store, recall and link facts,
  preferences and decisions across sessions.
```

Re-run `bootstrap_agents.py` after editing. It warns about MCP servers that still have no description, and about overrides for agents that are no longer installed.

### Scheduled Execution

```bash
# Re-run every Monday at 9 AM (requires: pip install schedule)
python bootstrap_agents.py --schedule weekly

# Daily at a specific time
python bootstrap_agents.py --schedule 08:30

# Every Friday afternoon
python bootstrap_agents.py --schedule fri@17:00
```

Supported schedule expressions: `daily`, `weekly`, `HH:MM`, `DAY@HH:MM`
For system-level scheduling use cron (macOS/Linux) or Task Scheduler (Windows) to call the script directly — no `schedule` package needed.

On Windows, this registers a daily run that opens no console window and logs to `bootstrap.log`. Missed runs (PC off) run at the next chance:

```powershell
$repo = "C:\path	o\dytopo-mcp"
$run  = '-c "import sys,runpy; f=open(''bootstrap.log'',''w'',encoding=''utf-8''); sys.stdout=sys.stderr=f; sys.argv=[''bootstrap_agents.py'']; runpy.run_path(''bootstrap_agents.py'', run_name=''__main__'')"'
Register-ScheduledTask -TaskName dytopo-bootstrap `
  -Action (New-ScheduledTaskAction -Execute "C:\path	o\pythonw.exe" -Argument $run -WorkingDirectory $repo) `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 9:00am) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10))
```

`agents.yaml` is written to a temp file and renamed into place, so the hook never reads a half-written registry during a scheduled run. Check `bootstrap.log` for `No description for …` lines: these are new MCP servers or connectors that need an entry in `description_overrides.yaml`.

### Semantic Pruner

When many skills are installed, they are often semantically redundant. `--prune` computes pairwise cosine similarity and removes near-duplicates, keeping the richer (longer) description.

``` bash
Before:  398 agents
After:   ~260 agents  (varies by threshold, default 0.92)
```

---

## Claude Code PreToolUse Hook

The hook intercepts every subagent dispatch (`Agent`, formerly `Task`) and appends a short "DyTopo routing hint" to the subagent's prompt: the tools and skills from `agents.yaml` that best fit the task.

### Setup

Add to `.claude/settings.json` (global) or `.claude/settings.local.json` (project). Use the full path of the Python that has this repo's dependencies installed:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Agent|Task",
        "hooks": [
          {
            "type": "command",
            "command": "\"/path/to/python\" \"/path/to/dytopo-mcp/dytopo_hook.py\""
          }
        ]
      }
    ]
  }
}
```

### Ranking with Jev

The hook ranks the registry with [TypeSafe](https://docs.typesafe.ai)'s Jev decision model (`jev_router.py`). It makes one System One request, which takes about 0.3s and needs no embeddings. The API allows at most 255 options per `choice` question, so a larger registry is split across several questions in the same request. Each question also gets a `none_fit` option, so probabilities from different questions can be compared. Intent rules (for example "remember…" → MuninnDB) still put their entry first.

The hook needs a key: `TYPESAFE_API_KEY` (direct, preferred) or `AI_GATEWAY_API_KEY` (through Vercel's AI Gateway). It checks the environment first, then **Windows Credential Manager**. On Windows, store keys there rather than in `.env`:

```bash
python secret_store.py set TYPESAFE_API_KEY   # hidden prompt; stored as dytopo/TYPESAFE_API_KEY
```

With no key, or if Jev fails or times out, the hook passes the call through unchanged. There is no embedding fallback: per-call hook processes can't afford sentence-transformers' ~20s import.

### Hook Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `TYPESAFE_API_KEY` / `AI_GATEWAY_API_KEY` | (Credential Manager) | Jev credentials |
| `DYTOPO_JEV_TIMEOUT` | `5` | Seconds before giving up and passing the call through |
| `DYTOPO_HOOK_K` | `3` | Entries suggested per dispatch |
| `DYTOPO_AGENTS_YAML` | `./agents.yaml` | Path to agent registry |

### How It Works

``` bash
Claude dispatches the Agent tool
        ↓
dytopo_hook.py asks Jev to rank every agents.yaml entry for the prompt
        ↓
Appends the top-k tools/skills (and how to invoke each) to the subagent's prompt
        ↓
The subagent reaches for those where they fit
```

The hook **never blocks**: if anything fails, the call proceeds unmodified.

---

## Agent Configuration

`agents.yaml` is gitignored — it's your personal registry, generated from your environment. The repo ships with `agents.example.yaml` as a starting point. The server falls back to the example file automatically if `agents.yaml` is not present.

**To get started:**

```bash
# Option A: generate from your installed skills (recommended)
python bootstrap_agents.py

# Option B: start from the example and edit manually
cp agents.example.yaml agents.yaml
```

Agents auto-load from `agents.yaml` on server start. Edit manually or generate with `bootstrap_agents.py`:

```yaml
agents:
  - id: web_search
    description: "Searches current web content, news, and online information. Best for recent events, current prices, live data."
    metadata:
      category: research

  - id: file_writer
    description: "Saves, exports, and outputs data to files. Writes and creates text, JSON, CSV, code, and configuration files on disk."
    metadata:
      category: files
```

**Description quality matters.** Use keywords that match how tasks are naturally phrased. See `SKILL.md` — "Pitfall 2: Missing Keywords."

---

## MCP Server Configuration

Add to your MCP settings (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dytopo": {
      "command": "python",
      "args": ["/absolute/path/to/dytopo-mcp/server.py"]
    }
  }
}
```

---

## Tools

### Core Routing

**`get_routing_plan`** — Generate routing plan for a task.

```json
{
  "task": "Review this FastAPI endpoint for security vulnerabilities",
  "k": 4,
  "graph_k": 2,
  "graph_type": "knn"
}
```

Returns selected agents, topology graph, and BFS execution order.

**`register_agent`** — Register an agent with semantic embedding.

**`list_agents`** — List all registered agents with scores.

**`compute_agent_similarity`** — Score one agent against a task string.

### Cache / Embedder

**`get_embedder_info`** — Returns active provider name, cache entry count, and cache path.

**`clear_embedding_cache`** — Wipes the embedding cache. Useful after bulk description updates.

### LLM-Powered Discovery

**`suggest_agents_for_domain`**, **`improve_agent_description`**, **`analyze_agent_coverage`**, **`discover_agents_from_tools`**, **`suggest_missing_agents`**

Requires `agent_discovery.py` and `OPENAI_API_KEY`. Without them the server still starts, and these tools report that discovery is unavailable. See `LLM_DISCOVERY.md` for the full guide.

---

## Graph Types

Topology types from the DyTopo paper (Chen et al., arXiv:2602.06039):

| Type | When to Use | Behavior |
| --- | --- | --- |
| `knn` | Multi-step tasks needing collaboration | Each agent connects to its k nearest neighbors — agents cross-pollinate context across rounds |
| `threshold` | High-precision or domain-specific tasks | Only agents above a similarity threshold communicate — strong matches only, no noise |
| `star` | Tasks with a clear orchestrator | All agents report to the top-ranked agent — hub-and-spoke, good for synthesis or review tasks |

---

## Token Efficiency

Example: 10 agents, 3 rounds of communication

| Topology | Connections | Messages | Tokens (est.) |
| --- | --- | --- | --- |
| Fully connected | 90 | 270 | ~135,000 |
| DyTopo k=4, graph_k=2 | 8 | 24 | ~12,000 |

**91% token reduction.**

---

## Changelog

### Unreleased

- **Jev routing in the hook** (`jev_router.py`): ranks the whole registry in one TypeSafe System One request (~0.3s, vs ~5s for embeddings plus cache load). The registry is split into choice questions of at most 255 options, each with a `none_fit` option. Uses `TYPESAFE_API_KEY` first, then `AI_GATEWAY_API_KEY`; redirects are refused
- **Hook passes calls through** when there is no Jev key or Jev fails; the embedding fallback is removed
- **Hook hint names tools and skills**, with how to invoke each, instead of a `subagent_type`. The matcher is now `Agent|Task`
- **Windows Credential Manager for API keys** (`secret_store.py`): env vars first, then `dytopo/NAME`
- **Plugin skill scanning** (`plugin_scanner.py`) and **description overrides** in bootstrap
- **claude.ai connector scanning** (`connector_scanner.py`): connected connectors from `claude mcp list` join the registry
- The PR/GitHub intent rule now points to the official GitHub MCP server (`mcp_github`)
- **scikit-learn removed**: cosine similarity is computed with numpy
- **Fix**: the server no longer crashes on startup without `OPENAI_API_KEY`
- Logging goes to stderr (stdout is the hook's JSON channel and the MCP protocol stream). Core requirements are pinned

### v0.2.0

- **Pluggable embedding providers**: OpenAI (`text-embedding-3-small`), Voyage AI (`voyage-3-lite`), or local (`sentence-transformers`)
- **Atomic persistent cache**: `.dytopo_cache.json` — embed once, reuse forever; temp-file + rename for integrity
- **Batch embed API**: `embed(..., _save=False)` + `flush()` for O(1) disk writes during bulk operations
- **PreToolUse hook**: `dytopo_hook.py` — automatic routing on every Task dispatch
- **Bootstrap script**: `bootstrap_agents.py` — populate `agents.yaml` from installed skills, built-in tools, and MCP servers; includes semantic pruner and scheduler
- **Two new MCP tools**: `get_embedder_info`, `clear_embedding_cache`
- **`agent_discovery` optional**: server starts cleanly without it; discovery tools return a clear error instead of crashing
- **Public cache API**: `CachedEmbedder.cache_size`, `CachedEmbedder.cache_path` (no more private `_cache` access)
- **Cross-platform MCP config detection**: Windows, macOS, Linux paths all handled in bootstrap

### v0.1.0

- Initial release: DyTopo semantic routing via OpenAI embeddings, `agents.yaml` config, MCP server, LLM discovery tools

---

## Limitations

- Routing quality depends on agent description clarity — generic descriptions produce poor matches
- No built-in agent execution — DyTopo is a routing layer only
- Local embedder slightly lower quality than API-based providers
- The hook's routing needs network access and a TypeSafe key; without them, calls go through without a hint
- Credential Manager storage is Windows-only; other platforms use env vars or `.env`
- Semantic pruner is O(N²) — with thousands of agents, use a higher threshold or skip `--prune`

---

## Next Steps

- `QUICKSTART.md` — 5-minute setup
- `SKILL.md` — implementation patterns, pitfalls, bootstrap guide
- `LLM_DISCOVERY.md` — auto-generate agent definitions with LLM
