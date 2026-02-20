# DyTopo Quick Start

Get DyTopo running in 5 minutes.

---

## 1. Install

```bash
cd dytopo-mcp
pip install -r requirements.txt
```

---

## 2. Choose an Embedding Provider

Pick one — or use local mode (no API key needed):

**Option A — Local (free, no key)**

```bash
export DYTOPO_EMBEDDER=local
# Downloads ~80 MB model on first use
```

**Option B — OpenAI**

```bash
export OPENAI_API_KEY="sk-..."
# Auto-detected; no need to set DYTOPO_EMBEDDER
```

**Option C — Voyage AI (Anthropic partner)**

```bash
pip install voyageai
export VOYAGE_API_KEY="pa-..."       # or ANTHROPIC_API_KEY as alias
export DYTOPO_EMBEDDER=anthropic
```

Or use a `.env` file:

```bash
cp .env.example.txt .env
# Edit .env with your preferred provider
```

---

## 3. Populate agents.yaml from Your Installed Skills

Instead of editing the 12-agent default, generate a registry from your real environment:

```bash
python bootstrap_agents.py
```

This scans:
- **~/.claude/skills/** — all your installed `SKILL.md` files
- **Built-in Claude Code tools** — Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, Task, etc.
- **MCP servers** — from `claude_desktop_config.json`

Result: `agents.yaml` populated with real agents from your environment, ready for semantic routing.

**Optional: prune duplicate skills**

```bash
python bootstrap_agents.py --prune          # remove near-duplicates (similarity ≥ 0.92)
python bootstrap_agents.py --prune --dry-run  # preview first
```

**Optional: re-run on a schedule**

```bash
python bootstrap_agents.py --schedule weekly   # every Monday 9 AM
python bootstrap_agents.py --schedule 08:30    # daily at 8:30 AM
```

---

## 4. Configure the Claude Code Hook (Recommended)

The hook automatically injects a routing plan into every Task tool dispatch — no manual invocation needed.

Add to `~/.claude/settings.json` (global) or `.claude/settings.local.json` (project-local):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "python /absolute/path/to/dytopo-mcp/dytopo_hook.py"
          }
        ]
      }
    ]
  }
}
```

Now every time Claude spawns a subagent via the Task tool, DyTopo silently annotates the prompt with the top-k semantically matched agents.

---

## 5. Add DyTopo as an MCP Server

**Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop.

---

## 6. Try It

In Claude chat:

```
Get a routing plan for "Download the latest Bitcoin price and save to JSON"
```

Claude will call `get_routing_plan` and show you which agents were selected and why.

---

## Common Issues

### "No agents registered"

`agents.yaml` is missing or has a syntax error. Run:

```bash
python bootstrap_agents.py
```

### Low similarity scores

Agent descriptions are too generic. Run bootstrap with pruning to consolidate, or manually refine descriptions in `agents.yaml`. See **Pitfall 2** in `SKILL.md`.

### Hook not firing

Check the path in `settings.json` is absolute. Test manually:

```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"build a login form"}}' | python dytopo_hook.py
```

You should see a JSON response with the prompt annotated.

### Voyage AI / anthropic provider fails

Make sure you have the right package:

```bash
pip install voyageai
```

And the right key: `VOYAGE_API_KEY` (or `ANTHROPIC_API_KEY` as alias). The `anthropic` Python package is **not** used for embeddings.

---

## Next Steps

1. `README.md` — full feature reference and changelog
2. `SKILL.md` — implementation patterns, bootstrap guide, pitfalls
3. `LLM_DISCOVERY.md` — auto-generate agent definitions with an LLM
