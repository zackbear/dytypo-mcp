# DyTopo Skill - Dynamic Topology Routing for Agentic Workflows

**Purpose**: Implement semantic-based agent routing to improve efficiency, reduce token waste, and enable task-conditioned agent selection.

**Based on**: DyTopo: Dynamic Topology Routing for Multi-Agent Reasoning via Semantic Matching (arXiv:2602.06039)

**When to use this skill**: Any multi-agent workflow, tool selection, skill routing, or task decomposition scenario where you want semantic matching instead of fixed topologies. Also activates automatically via the PreToolUse hook whenever the Task tool is dispatched.

---

## Core Concept

Traditional approach:
```
Task → Broadcast to ALL agents → Collect responses → Filter
```

DyTopo approach:
```
Task → Embed task → Select relevant agents → Build semantic graph → Route efficiently
```

Key difference: **Topology adapts to task semantics**

---

## PreToolUse Hook (Automatic Routing)

DyTopo installs a Claude Code hook that fires **before every Task tool call**.
The hook appends a routing plan to the Task prompt, guiding subagent selection.

### How It Works

```
Claude dispatches Task tool
        ↓
dytopo_hook.py reads prompt from stdin
        ↓
Embeds prompt → scores all agents in agents.yaml
        ↓
Appends routing plan to prompt (top-k agents, scores, recommended subagent_type)
        ↓
Claude sees the annotation and uses it to pick the right subagent_type
```

### Hook Configuration

In `.claude/settings.json` (or `settings.local.json`):

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
| `DYTOPO_HOOK_K` | `3` | Number of agents to select |
| `DYTOPO_HOOK_GRAPH` | `knn` | Graph type (knn, star, threshold) |
| `DYTOPO_AGENTS_YAML` | `./agents.yaml` | Path to agent registry |
| `DYTOPO_EMBEDDER` | auto | Embedding provider |

---

## Embedding Providers

DyTopo supports three embedding backends. Set via `DYTOPO_EMBEDDER` env var or auto-detected.

### Auto-Detection Order

```
OPENAI_API_KEY set?    → openai
ANTHROPIC_API_KEY set? → anthropic
Otherwise              → local (sentence-transformers, no key needed)
```

### Provider Comparison

| Provider | Key Required | Quality | Cost | Latency |
|---|---|---|---|---|
| `openai` | Yes (OPENAI_API_KEY) | High | ~$0.00002/1K tokens | Low |
| `anthropic` | Yes (ANTHROPIC_API_KEY) | High | Per Voyage pricing | Low |
| `local` | None | Good | Free | First load only |

### Setting the Provider

```bash
# Option A: env var
export DYTOPO_EMBEDDER=local

# Option B: .env file
DYTOPO_EMBEDDER=local
DYTOPO_LOCAL_MODEL=all-MiniLM-L6-v2   # optional override
```

### Embedding Cache

All providers are wrapped by `CachedEmbedder` which persists embeddings to
`.dytopo_cache.json`. Each unique text is embedded **once** — subsequent calls
use the cached vector instantly, regardless of provider.

Cache is keyed by `provider_name:sha256(text)[:16]`, so switching providers
does not pollute existing cache entries.

---

## Implementation Patterns

### Pattern 1: Tool Selection via Semantic Routing

**Problem**: Claude Code has 50+ tools. Broadcasting context to all tools wastes tokens.

**Solution**: Register tools as agents, route based on task semantics.

```python
# Setup (once)
from dytopo import register_agent, get_routing_plan

# Register tools with capability descriptions
register_agent(
    "web_search",
    "Searches current web content, news, and online information. Best for recent events, current prices, live data."
)

register_agent(
    "file_writer",
    "Saves, exports, and outputs data to files. Writes and creates text, JSON, CSV, code, and configuration files on disk."
)

register_agent(
    "code_executor",
    "Executes Python code and returns output. Useful for calculations, data processing, testing."
)

# Route task to relevant tools
task = "What's the current price of Bitcoin and save it to prices.json"

plan = get_routing_plan(task, k=3)

# Result:
# Selected: web_search (0.91), file_writer (0.84), code_executor (0.72)
# Topology: web_search → file_writer → code_executor
```

**Execution**:
```python
# Execute in topology order
for round in plan["execution_order"]:
    for agent_id in round:
        # Get context from neighbors
        neighbor_ids = plan["topology"][agent_id]
        neighbor_outputs = [outputs[n] for n in neighbor_ids if n in outputs]

        # Execute with neighbor context
        result = execute_tool(agent_id, task, neighbor_outputs)
        outputs[agent_id] = result
```

---

### Pattern 2: Skill-Based Code Generation

**Problem**: Different coding tasks need different expertise. Routing all tasks through generic code generation is inefficient.

**Solution**: Register specialized coding skills.

```python
# Register coding skills
register_agent(
    "react_specialist",
    "React components, hooks, state management, TypeScript, Tailwind CSS, responsive design"
)

register_agent(
    "api_specialist",
    "REST APIs, FastAPI, Express, request validation, error handling, authentication"
)

register_agent(
    "database_specialist",
    "SQL queries, schema design, migrations, indexing, query optimization, ORM usage"
)

register_agent(
    "testing_specialist",
    "Unit tests, integration tests, mocking, pytest, jest, test coverage"
)

# Route task
task = "Build a login endpoint with JWT tokens and rate limiting"

plan = get_routing_plan(task, k=3, graph_type="knn")

# Selected: api_specialist (0.95), database_specialist (0.78), testing_specialist (0.71)
# Graph: api_specialist ↔ database_specialist ↔ testing_specialist
```

**Multi-round refinement**:
```python
# Round 1: API specialist designs endpoint
api_output = generate_code("api_specialist", task)

# Round 2: Database specialist adds user model
db_output = generate_code(
    "database_specialist",
    task,
    context=[api_output]  # Only from graph neighbors
)

# Round 3: Testing specialist adds tests
test_output = generate_code(
    "testing_specialist",
    task,
    context=[api_output, db_output]
)
```

---

### Pattern 3: Research Task Decomposition

**Problem**: Complex research tasks benefit from specialized agents but determining which agents to use is manual.

**Solution**: Semantic task decomposition with dynamic routing.

```python
# Register research agents
register_agent(
    "web_researcher",
    "Searches web for current information, analyzes sources, fact-checks claims"
)

register_agent(
    "data_analyst",
    "Processes datasets, performs statistical analysis, identifies trends"
)

register_agent(
    "academic_researcher",
    "Searches academic papers, summarizes research, cites sources properly"
)

register_agent(
    "synthesis_expert",
    "Combines multiple sources, creates coherent narratives, resolves contradictions"
)

# Task
task = "Research the impact of remote work on productivity with academic backing and current statistics"

plan = get_routing_plan(task, k=4, graph_k=2)

# Topology might be:
# academic_researcher → synthesis_expert
# web_researcher → synthesis_expert
# data_analyst → synthesis_expert
# (Star pattern with synthesis_expert as hub)
```

**Why this works**: The semantic matching identifies that you need academic sources, current data, and synthesis - without manually specifying the workflow.

---

### Pattern 4: Code Review Routing

**Problem**: Different code needs different review expertise.

**Solution**: Route to specialized reviewers based on code characteristics.

```python
# Register reviewers
register_agent(
    "security_reviewer",
    "Identifies SQL injection, XSS, authentication flaws, data exposure, OWASP vulnerabilities"
)

register_agent(
    "performance_reviewer",
    "Analyzes algorithmic complexity, database query optimization, memory usage, caching"
)

register_agent(
    "style_reviewer",
    "Checks code formatting, naming conventions, documentation, best practices"
)

register_agent(
    "logic_reviewer",
    "Finds edge cases, logic errors, race conditions, error handling gaps"
)

# Route based on code context
task = "Review this authentication middleware for production deployment"

plan = get_routing_plan(task, k=3)

# Selected: security_reviewer (0.94), logic_reviewer (0.82), performance_reviewer (0.76)
# Automatically prioritizes security without manual specification
```

---

### Pattern 5: Multi-Agent Dialogue with Sparse Communication

**Problem**: In collaborative problem-solving, not all agents need to talk to all other agents.

**Solution**: Build semantic communication graph.

```python
# Register dialogue agents
register_agent(
    "product_manager",
    "Defines requirements, prioritizes features, considers user needs and business goals"
)

register_agent(
    "architect",
    "Designs system architecture, selects technologies, defines interfaces and patterns"
)

register_agent(
    "frontend_dev",
    "Implements UI components, handles user interactions, manages client state"
)

register_agent(
    "backend_dev",
    "Builds APIs, manages data persistence, handles business logic and validation"
)

task = "Design a real-time chat feature for the mobile app"

plan = get_routing_plan(task, k=4, graph_type="knn", graph_k=2)

# Topology example:
# product_manager ↔ architect
# architect ↔ frontend_dev, backend_dev
# frontend_dev ↔ backend_dev
```

**Execution with message passing**:
```python
messages = {agent_id: task for agent_id in plan["selected_agents"]}

for round_num in range(3):  # 3 rounds of dialogue
    new_messages = {}

    for agent_id in plan["selected_agents"]:
        # Get messages from neighbors only
        neighbor_msgs = [
            messages[n] for n in plan["topology"][agent_id]
        ]

        # Generate response
        prompt = f"""
        Task: {task}

        Messages from collaborators:
        {format_messages(neighbor_msgs)}

        Your response as {agent_id}:
        """

        response = llm(prompt)
        new_messages[agent_id] = response

    messages = new_messages
```

**Token savings**: With 4 agents, fully connected = 12 message passes per round. Sparse graph = 6 message passes. 50% reduction.

---

### Pattern 6: Adaptive Tool Chain Construction

**Problem**: Tool chains are usually hardcoded. Different tasks need different chains.

**Solution**: Use topology as execution plan.

```python
# Register tools
register_agent("google_search", "Searches Google for web content")
register_agent("scrape_webpage", "Extracts content from URLs")
register_agent("analyze_sentiment", "Performs sentiment analysis on text")
register_agent("generate_summary", "Creates concise summaries")
register_agent("save_to_database", "Stores data in PostgreSQL")

# Task 1: Research task
task1 = "Find recent news about AI regulation and summarize sentiment"
plan1 = get_routing_plan(task1, k=4)

# Chain: google_search → scrape_webpage → analyze_sentiment → generate_summary

# Task 2: Different task
task2 = "Archive today's top tech news to database"
plan2 = get_routing_plan(task2, k=3)

# Chain: google_search → scrape_webpage → save_to_database

# Same tools, different chains, zero manual configuration
```

---

### Pattern 7: Confidence-Weighted Routing

**Advanced**: Weight edges by historical accuracy.

```python
# Extend agent metadata with performance tracking
register_agent(
    "agent_1",
    "Description...",
    metadata={"accuracy_history": [0.85, 0.92, 0.88]}
)

# Custom routing with confidence weights
def weighted_routing_plan(task, k=4):
    base_plan = get_routing_plan(task, k)

    # Reweight edges by agent performance
    weighted_topology = {}
    for agent_id, neighbors in base_plan["topology"].items():
        agent_confidence = np.mean(
            get_agent_metadata(agent_id)["accuracy_history"]
        )
        weighted_topology[agent_id] = {
            neighbor: agent_confidence
            for neighbor in neighbors
        }

    return weighted_topology

# Use weights to prioritize high-confidence paths
```

---

### Pattern 8: Human-in-the-Loop Triggers

**Use case**: Invoke human review when agent consensus is low.

```python
# Register agents + human reviewer
register_agent("agent_1", "...")
register_agent("agent_2", "...")
register_agent("human_reviewer", "Human expert for ambiguous cases")

# After agent execution
def check_consensus(outputs):
    scores = [output["confidence"] for output in outputs.values()]
    return np.mean(scores)

consensus = check_consensus(agent_outputs)

if consensus < 0.75:
    # Low consensus - add human to topology
    plan = get_routing_plan(
        task,
        k=3,
        # Force include human_reviewer
    )
    # Human reviews agent outputs before final decision
```

---

## Integration with Claude Code

### Workflow 1: File Operation Routing

```python
# Register file operation agents
register_agent("text_editor", "Edits text files, code files, documentation")
register_agent("json_processor", "Reads and modifies JSON files")
register_agent("csv_handler", "Processes CSV files, data analysis")
register_agent("image_handler", "Resizes, converts, analyzes images")

# Route based on file type
task = "Process all JSON files in /data and extract email addresses"

plan = get_routing_plan(task, k=2)
# Selects: json_processor + text_editor
```

### Workflow 2: Debug Session Routing

```python
# Register debug agents
register_agent("error_analyzer", "Parses stack traces, identifies root causes")
register_agent("code_inspector", "Examines code for bugs and logical errors")
register_agent("dependency_checker", "Validates package versions and compatibility")
register_agent("log_analyzer", "Searches logs for error patterns")

task = "Application crashes on startup with ModuleNotFoundError"

plan = get_routing_plan(task, k=3)
# Likely selects: error_analyzer → dependency_checker → log_analyzer
```

---

## Best Practices

### Agent Description Quality

**Bad**:
```python
register_agent("agent_1", "Does stuff with code")
```

**Good**:
```python
register_agent(
    "python_linter",
    "Analyzes Python code for PEP 8 violations, unused imports, type hints, complexity metrics. Uses pylint, flake8, mypy."
)
```

**Why**: Embeddings capture semantic detail. Specific descriptions = better routing.

**Tip**: Use keywords that match how tasks are naturally phrased — e.g. "save", "export", "output" for a file writer agent, not just "creates files".

---

### Optimal K Values

- **k=1-2**: Very focused, may miss relevant agents
- **k=3-5**: Sweet spot for most tasks
- **k=6-8**: Broader coverage, higher token cost
- **k>10**: Usually wasteful, defeats sparsity purpose

**Rule**: Start with k=4, adjust based on task complexity. Hook uses k=3 by default.

---

### Graph Type Selection

| Task Type | Graph Type | Reasoning |
|-----------|------------|-----------|
| Independent subtasks | star | Central coordinator |
| Collaborative refinement | knn | Cross-pollination |
| High specialization | threshold | Only strong matches |
| Sequential pipeline | custom | Use execution_order |

---

### Debugging Low-Quality Routes

If routing seems off:

1. Check agent descriptions (are they specific enough?)
2. Compute similarity scores manually
3. Try different graph_k values
4. Consider task phrasing (more detail = better matching)

```python
# Debug similarity
result = compute_agent_similarity(
    task_text=task,
    agent_id_1="suspicious_agent"
)
print(f"Similarity: {result['similarity']}")
# If < 0.6, agent probably shouldn't be selected
```

---

## Token Efficiency Analysis

**Example**: 10 agents, 3 rounds of communication

**Fully connected**:
- Connections: 10 × 9 = 90
- Messages per round: 90
- Total messages: 270
- Avg message length: 500 tokens
- **Total: 135,000 tokens**

**DyTopo (k=4, graph_k=2)**:
- Selected agents: 4
- Connections: 4 × 2 = 8
- Messages per round: 8
- Total messages: 24
- **Total: 12,000 tokens**

**Savings**: 91% token reduction

---

## Advanced: Switching Embedding Providers

```bash
# Switch to local (no API key, free, ~80MB download once)
export DYTOPO_EMBEDDER=local

# Switch to Anthropic/Voyage
export DYTOPO_EMBEDDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Keep OpenAI (original default)
export DYTOPO_EMBEDDER=openai
export OPENAI_API_KEY=sk-...
```

The cache handles provider switching gracefully — each provider has its own
namespace in `.dytopo_cache.json`, so cached vectors are never mixed.

---

## Common Pitfalls

### Pitfall 1: Generic Agent Descriptions

```python
# Bad
register_agent("helper", "Helps with tasks")

# Good
register_agent("sql_optimizer", "Optimizes SQL queries by adding indexes, rewriting joins, using CTEs, analyzing execution plans")
```

### Pitfall 2: Missing Keywords in Descriptions

```python
# Bad — won't surface for "save to JSON" tasks
register_agent("file_writer", "Creates new files with content.")

# Good — "save", "export", "output" all match natural task phrasing
register_agent("file_writer", "Saves, exports, and outputs data to files. Writes and creates text, JSON, CSV, code, and configuration files on disk.")
```

### Pitfall 3: Over-Routing

Don't use DyTopo for every single operation. Use it when:
- You have 5+ potential agents/tools
- Task semantics vary significantly
- Token costs matter
- You need explainable routing

### Pitfall 4: Ignoring Topology

```python
# Bad - getting plan but not using it
plan = get_routing_plan(task, k=5)
# Then broadcasting to all agents anyway

# Good - actually route based on topology
for agent_id in plan["selected_agents"]:
    neighbors = plan["topology"][agent_id]
    # Only pass context from neighbors
```

---

## Testing Your Routing

```python
def test_routing_quality(task, expected_agents):
    plan = get_routing_plan(task, k=len(expected_agents))
    selected = [a["id"] for a in plan["selected_agents"]]

    coverage = len(set(selected) & set(expected_agents))
    precision = coverage / len(selected)
    recall = coverage / len(expected_agents)

    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")

    return precision > 0.8 and recall > 0.8

# Example
test_routing_quality(
    "Debug React component not rendering",
    expected_agents=["frontend_debugger", "react_specialist"]
)
```

---

## Real-World Example: Code Generation Pipeline

Complete implementation:

```python
# 1. Register specialized agents
agents = [
    ("requirements_analyzer", "Analyzes user requirements, creates technical specs, defines acceptance criteria"),
    ("architecture_designer", "Designs system architecture, selects patterns, defines module structure"),
    ("code_generator", "Writes clean, typed, well-documented code following best practices"),
    ("test_writer", "Creates comprehensive unit and integration tests with edge case coverage"),
    ("security_auditor", "Reviews code for vulnerabilities, validates input handling, checks authentication"),
    ("optimizer", "Improves performance, reduces complexity, optimizes algorithms and queries")
]

for agent_id, description in agents:
    register_agent(agent_id, description)

# 2. Get routing plan
task = "Build a user registration API with email verification"

plan = get_routing_plan(task, k=5, graph_type="knn", graph_k=2)

print(f"Selected {len(plan['selected_agents'])} agents")
print(f"Topology: {plan['topology']}")

# 3. Execute multi-round pipeline
context = {"task": task}

for round_idx, agent_round in enumerate(plan["execution_order"]):
    print(f"\n=== Round {round_idx + 1} ===")

    for agent_id in agent_round:
        neighbors = plan["topology"][agent_id]
        neighbor_context = [
            context[n] for n in neighbors
            if n in context and n != "task"
        ]

        prompt = f"""
        Task: {task}

        Previous work from collaborators:
        {json.dumps(neighbor_context, indent=2)}

        As the {agent_id}, provide your contribution:
        """

        output = llm(prompt)
        context[agent_id] = output

        print(f"{agent_id}: {output[:100]}...")

# 4. Final aggregation
all_outputs = [context[a["id"]] for a in plan["selected_agents"]]
final_result = synthesize(all_outputs)
```

---

---

## Bootstrap: Populate agents.yaml from Your Environment

Out of the box, `agents.yaml` contains ~12 generic agents.
`bootstrap_agents.py` replaces it with **your actual installed skills** (300+)
plus built-in tools and MCP servers — automatically.

### Quick Start

```bash
# One-time run (on-demand)
python bootstrap_agents.py

# Run + semantic pruning (removes duplicate/redundant skills)
python bootstrap_agents.py --prune

# Preview what pruning would do without writing
python bootstrap_agents.py --prune --dry-run

# Tighten or loosen the duplicate threshold (default 0.92)
python bootstrap_agents.py --prune --threshold 0.90
```

### Sources Scanned

| Source | Default Location | Env Override |
|---|---|---|
| Built-in Claude Code tools | (hardcoded) | `--no-builtins` |
| Installed skills | `~/.claude/skills/` | `DYTOPO_SKILLS_DIR` |
| MCP servers | `claude_desktop_config.json` | `DYTOPO_MCP_CONFIG` |

### Scheduled Execution

```bash
# Run every Monday at 9 AM (requires: pip install schedule)
python bootstrap_agents.py --schedule weekly

# Daily at a specific time
python bootstrap_agents.py --schedule 08:30

# Every Friday afternoon
python bootstrap_agents.py --schedule fri@17:00
```

Supported schedule expressions:
- `daily`  — every day at 09:00
- `weekly` — every Monday at 09:00
- `HH:MM`  — daily at that time (e.g. `08:30`)
- `DAY@HH:MM` — weekly (e.g. `mon@08:30`, `fri@17:00`)

For system-level scheduling, use `cron` (Linux/macOS) or Task Scheduler (Windows):
```
# crontab: every Monday at 9 AM
0 9 * * 1 python /path/to/dytypo-mcp/bootstrap_agents.py
```

### Semantic Pruner

With 300+ skills, many are semantically redundant. The pruner uses cosine
similarity to cluster descriptions and removes duplicates automatically.

```
Before prune:  398 agents
After prune:   ~260 agents  (varies by threshold)
```

Agents removed are those where similarity ≥ threshold with a richer peer.
The richer description (longer) is always kept.

---

## Summary

DyTopo transforms multi-agent systems from:
- Fixed topologies → Task-conditioned graphs
- Broadcast communication → Semantic routing
- Manual coordination → Automatic selection
- High token cost → Sparse efficiency

The **PreToolUse hook** means this happens automatically on every Task dispatch — no manual invocation needed.

The **pluggable embedder + cache** means you can use OpenAI, Anthropic, or a fully local model, and each agent description is only ever embedded once.

The **bootstrap script** keeps your `agents.yaml` in sync with your real installed skills — run it on-demand or on a schedule whenever you install new skills.

Use it whenever you have multiple agents/tools/skills and want intelligent routing based on task semantics.
