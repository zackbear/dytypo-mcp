# Quick Start Guide

Get DyTopo running in 5 minutes.

## 1. Install

```bash
cd dytopo-mcp
pip install -r requirements.txt
```

## 2. Setup API Key

Pick one:

**Option A**: Environment variable
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Option B**: .env file
```bash
cp .env.example .env
# Edit .env with your key
```

## 3. Configure Agents

The `agents.yaml` file comes pre-configured with common tools.

**For Claude Code users**: The defaults match Claude Code tool names. Keep as-is.

**For custom workflows**: Edit descriptions to match your use case:

```yaml
agents:
  - id: your_tool_name
    description: "Detailed description of what it does"
    metadata:
      category: your_category
```

See `AGENT_CONFIG.md` for examples.

## 4. Test It

```bash
python example_usage.py
```

You should see:
```
✓ Loaded 10 agents from agents.yaml

Selected agents:
  • web_search (relevance: 0.89)
  • file_writer (relevance: 0.82)
```

## 5. Use with Claude

Add to Claude Desktop config:

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

## 6. Try It in Chat

```
Get a routing plan for "Download the latest Bitcoin price and save to JSON"
```

Claude will use the `get_routing_plan` tool and show you which agents were selected.

## What's Next?

### Customize Agent Descriptions

Edit `agents.yaml` to better match your tasks:

```yaml
- id: web_search
  description: "Searches Google for cryptocurrency prices, news, and market data"
  # More specific = better routing
```

### Test Different Tasks

```python
# Research task
plan1 = get_routing_plan("Research recent AI papers on arXiv")

# Coding task  
plan2 = get_routing_plan("Write a FastAPI endpoint with authentication")

# Data task
plan3 = get_routing_plan("Process CSV file and calculate statistics")
```

Each task should route to different agents.

### Check Similarity Scores

```python
compute_agent_similarity(
    task_text="Build a React component",
    agent_id_1="react_expert"
)
# Should be > 0.8 for good matches
```

If scores are low, improve agent descriptions.

### Use the Topology

```python
plan = get_routing_plan("Your task", k=4)

# Execute in order
for round in plan["execution_order"]:
    for agent_id in round:
        neighbors = plan["topology"][agent_id]
        # Only pass context from neighbors
```

See `WORKFLOW_EXAMPLES.md` for complete integration patterns.

## Common Issues

### "No agents registered"

The `agents.yaml` file might be missing or has errors.

Check the server output:
```
✓ Loaded N agents from agents.yaml
```

If you don't see this, check:
1. `agents.yaml` exists in the same directory as `server.py`
2. YAML syntax is valid
3. File has `agents:` section

### Low similarity scores

Agent descriptions are too generic.

**Fix**: Add more detail:
```yaml
# Bad
description: "Does coding stuff"

# Good  
description: "Writes Python backend code using FastAPI, SQLAlchemy, async patterns, type hints, and pytest for testing"
```

### Wrong agents selected

Task phrasing might be ambiguous.

**Fix**: Be more specific:
```
# Vague
"Help me with my website"

# Specific
"Debug why my React component won't re-render when props change"
```

## Next Steps

1. ✅ Install and test
2. ✅ Customize agents.yaml
3. ✅ Integrate with your workflow
4. Read `SKILL.md` for implementation patterns
5. Read `WORKFLOW_EXAMPLES.md` for real examples
6. Check `AGENT_CONFIG.md` for advanced config

You're ready to build semantic routing into your agentic workflows.