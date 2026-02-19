# DyTopo MCP Server

Dynamic Topology Routing for Multi-Agent Systems via Semantic Matching.

Based on the paper: **DyTopo: Dynamic Topology Routing for Multi-Agent Reasoning via Semantic Matching** (arXiv:2602.06039)

> **🚀 New user?** See `QUICKSTART.md` for 5-minute setup  
> **🤖 LLM-Powered Discovery**: See `LLM_DISCOVERY.md` to auto-generate agent definitions

## What It Does

Routes tasks to semantically relevant agents and builds dynamic communication graphs.

Instead of:
- Fixed agent topologies
- Broadcasting to all agents
- Manual routing logic

You get:
- Task-conditioned agent selection
- Sparse semantic graphs
- Automatic topology construction

> **📖 Documentation**: See `API_KEY_SETUP.md` for secure API key management options  
> **🤖 Agent Setup**: See `AGENT_CONFIG.md` for configuring agents/tools/skills

## Installation

```bash
cd dytopo-mcp
pip install -r requirements.txt
```

**Set API key** (choose one):

Option A - Environment variable:
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Option B - .env file:
```bash
cp .env.example .env
# Edit .env with your key
```

See `API_KEY_SETUP.md` for more options.

## Agent Configuration

Agents auto-load from `agents.yaml` on server start.

Edit `agents.yaml` to define your agents:
```yaml
agents:
  - id: web_search
    description: "Searches current web content, news, and online information"
    metadata:
      category: research

  - id: python_expert
    description: "Expert in Python, FastAPI, async, type hints, pytest"
    metadata:
      language: python
```

Or register dynamically via tool calls:
```python
register_agent("my_agent", "What this agent does")
```

See `AGENT_CONFIG.md` for detailed configuration guide.

## Configuration

Add to your MCP settings file (claude_desktop_config.json):

```json
{
  "mcpServers": {
    "dytopo": {
      "command": "python",
      "args": ["/path/to/dytopo-mcp/server.py"]
    }
  }
}
```

Server automatically uses your environment variable or .env file. No secrets in config files.

## Tools

### register_agent
Register an agent with semantic embedding.

```python
{
  "agent_id": "code_reviewer",
  "description": "Reviews Python code for bugs, performance issues, and style violations",
  "metadata": {"language": "python", "version": "3.11"}
}
```

### get_routing_plan
Generate routing plan for a task.

```python
{
  "task": "Review this FastAPI endpoint for security vulnerabilities",
  "k": 4,              # Select top 4 agents
  "graph_k": 2,        # Each agent connects to 2 neighbors
  "graph_type": "knn"  # or "threshold" or "star"
}
```

Returns:
```json
{
  "selected_agents": [
    {"id": "security_auditor", "relevance_score": 0.92},
    {"id": "code_reviewer", "relevance_score": 0.87}
  ],
  "topology": {
    "security_auditor": ["code_reviewer"],
    "code_reviewer": ["security_auditor"]
  },
  "execution_order": [
    ["security_auditor"],
    ["code_reviewer"]
  ]
}
```

### LLM-Powered Discovery Tools

**New**: Use Claude/GPT to automatically generate and improve agent definitions.

#### suggest_agents_for_domain
```python
{
  "domain": "web scraping and data extraction",
  "num_agents": 5
}
# Returns: LLM-generated agent definitions with detailed descriptions
```

#### improve_agent_description
```python
{
  "agent_id": "web_search",
  "current_description": "Searches the web",
  "context": "Used for finding current cryptocurrency prices"
}
# Returns: Improved description optimized for semantic matching
```

#### analyze_agent_coverage
```python
{
  "task_domain": "building REST APIs",
  "existing_agent_ids": ["python_expert", "database_expert"]
}
# Returns: Coverage score, gaps, and suggestions for missing agents
```

See `LLM_DISCOVERY.md` for complete guide.

### compute_agent_similarity
Check semantic alignment between agents or task-agent fit.

```python
# Task-agent similarity
{
  "task_text": "Debug memory leak in React app",
  "agent_id_1": "frontend_debugger"
}

# Agent-agent similarity
{
  "agent_id_1": "python_expert",
  "agent_id_2": "django_specialist"
}
```

## Usage Patterns

### Pattern 1: Task Routing
```python
# 1. Register your agents once
register_agent("security_expert", "Identifies security vulnerabilities in web apps")
register_agent("performance_expert", "Optimizes database queries and API response times")
register_agent("ux_expert", "Improves user interface and interaction design")

# 2. Get routing plan for each task
plan = get_routing_plan("Optimize checkout flow for mobile users", k=3)

# 3. Execute using the topology
for round in plan["execution_order"]:
    for agent_id in round:
        # Send messages only to graph neighbors
        neighbors = plan["topology"][agent_id]
        # ... execute agent with neighbor context
```

### Pattern 2: Tool Selection
```python
# Register tools as agents
register_agent("web_search", "Searches current web content and news")
register_agent("code_executor", "Runs Python code and returns results")
register_agent("file_reader", "Reads and analyzes file contents")

# Route task to relevant tools
plan = get_routing_plan("Find latest npm package version and check if it's compatible")
# Automatically selects: web_search -> file_reader
```

### Pattern 3: Skill Routing
```python
# Register skills
register_agent("frontend_skill", "React, TypeScript, Tailwind CSS, responsive design")
register_agent("backend_skill", "FastAPI, PostgreSQL, Redis, async Python")
register_agent("devops_skill", "Docker, Kubernetes, CI/CD, monitoring")

# Route development tasks
plan = get_routing_plan("Build user authentication with email verification")
# Selects: backend_skill -> devops_skill (for deployment)
```

## Graph Types

**knn**: Each agent connects to k most similar agents
- Best for: Collaborative refinement
- Use when: Agents should cross-pollinate ideas

**threshold**: Connect agents above similarity threshold (0.7)
- Best for: Filtering out unrelated agents
- Use when: You want sparse, high-confidence connections

**star**: All agents connect to highest-relevance agent
- Best for: Central coordinator pattern
- Use when: One agent orchestrates others

## Token Efficiency

Example with 10 agents:
- Fully connected: 45 connections
- DyTopo (k=4, graph_k=2): 8 connections

83% reduction in communication overhead.

## Integration Examples

### With LangGraph
```python
# Build StateGraph from DyTopo topology
plan = get_routing_plan(task, k=5)

for agent_id in plan["selected_agents"]:
    graph.add_node(agent_id, agent_function)

for agent_id, neighbors in plan["topology"].items():
    for neighbor in neighbors:
        graph.add_edge(agent_id, neighbor)
```

### With Claude Code
See skill document for full patterns.

### With Autogen
```python
# Replace GroupChat with DyTopo topology
plan = get_routing_plan(task, k=4)
allowed_transitions = plan["topology"]

groupchat = GroupChat(
    agents=selected_agents,
    allowed_or_disallowed_speaker_transitions=allowed_transitions
)
```

## Performance Tips

1. Cache agent embeddings (they're stored in memory)
2. Keep k small (3-6) for cost control
3. Recompute graph per task (it's fast)
4. Use threshold graph for very sparse routing
5. Log similarity scores for debugging

## Limitations

- Requires OpenAI API key for embeddings
- Embeddings cost ~$0.0001 per agent registration
- Quality depends on agent description clarity
- No built-in agent execution (routing only)

## Next Steps

See SKILL.md for implementation patterns and workflow integration.