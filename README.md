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
- **Automatic subagent guidance** via the Claude Code PreToolUse hook

---

## Installation

```bash
cd dytopo-mcp
pip install -r requirements.txt
```

---

## Embedding Providers

DyTopo supports three embedding backends. Set `DYTOPO_EMBEDDER` or let it auto-detect:

| Provider | Key Required | Package | Notes |
|---|---|---|---|
| `openai` | `OPENAI_API_KEY` | `openai` | Default if key present. `text-embedding-3-small`. |
| `anthropic` | `VOYAGE_API_KEY` (or `ANTHROPIC_API_KEY`) | `voyageai` | Voyage AI `voyage-3-lite`. |
| `local` | None | `sentence-transformers` | Free, ~80 MB model download on first use. |

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

Out of the box, `agents.yaml` has ~12 generic agents. `bootstrap_agents.py` replaces it with your **actual installed skills** (300+), built-in Claude Code tools, and MCP servers — automatically.

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
|---|---|
| Built-in Claude Code tools | hardcoded (Bash, Read, Write, Edit, Glob, Grep, WebSearch, …) |
| Installed skills | `~/.claude/skills/` — reads each `SKILL.md` |
| MCP servers | `claude_desktop_config.json` / `.claude.json` |

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

### Semantic Pruner

With 300+ skills, many are semantically redundant. `--prune` computes pairwise cosine similarity and removes near-duplicates, keeping the richer (longer) description.

```
Before:  398 agents
After:   ~260 agents  (varies by threshold, default 0.92)
```

---

## Claude Code PreToolUse Hook

The hook automatically intercepts every Task tool dispatch and injects a DyTopo routing plan into the prompt, guiding Claude to pick the right `subagent_type`.

### Setup

Add to `.claude/settings.json` (global) or `.claude/settings.local.json` (project):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/dytopo-mcp/dytopo_hook.py"
          }
        ]
      }
    ]
  }
}
```

### Hook Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DYTOPO_HOOK_K` | `3` | Agents selected per Task dispatch |
| `DYTOPO_HOOK_GRAPH` | `knn` | Graph topology type |
| `DYTOPO_AGENTS_YAML` | `./agents.yaml` | Path to agent registry |
| `DYTOPO_EMBEDDER` | auto | Embedding provider |

### How It Works

```
Claude dispatches Task tool
        ↓
dytopo_hook.py scores all agents in agents.yaml against the prompt
        ↓
Appends ranking: top-k agents, scores, recommended subagent_type
        ↓
Claude uses the annotation to pick the semantically correct subagent
```

The hook **never blocks** — if it errors, the Task proceeds unmodified.

---

## Agent Configuration

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

Requires `agent_discovery.py` and `OPENAI_API_KEY`. See `LLM_DISCOVERY.md` for the full guide.

---

## Graph Types

| Type | Best For |
|---|---|
| `knn` | Collaborative refinement — agents cross-pollinate context |
| `threshold` | High-precision filtering — only strong matches communicate |
| `star` | Central coordinator — all agents report to the top-ranked one |

---

## Token Efficiency

Example: 10 agents, 3 rounds of communication

| Topology | Connections | Messages | Tokens (est.) |
|---|---|---|---|
| Fully connected | 90 | 270 | ~135,000 |
| DyTopo k=4, graph_k=2 | 8 | 24 | ~12,000 |

**91% token reduction.**

---

## Changelog

### v0.2.0

- **Pluggable embedding providers**: OpenAI (`text-embedding-3-small`), Voyage AI (`voyage-3-lite`), or local (`sentence-transformers`)
- **Atomic persistent cache**: `.dytopo_cache.json` — embed once, reuse forever; temp-file + rename for integrity
- **Batch embed API**: `embed(..., _save=False)` + `flush()` for O(1) disk writes during bulk operations
- **PreToolUse hook**: `dytopo_hook.py` — automatic routing on every Task dispatch
- **Bootstrap script**: `bootstrap_agents.py` — populate `agents.yaml` from 300+ installed skills, built-in tools, and MCP servers; includes semantic pruner and scheduler
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
- Semantic pruner is O(N²) — with thousands of agents, use a higher threshold or skip `--prune`

---

## Next Steps

- `QUICKSTART.md` — 5-minute setup
- `SKILL.md` — implementation patterns, pitfalls, bootstrap guide
- `LLM_DISCOVERY.md` — auto-generate agent definitions with LLM
