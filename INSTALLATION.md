# DyTopo Installation & Setup Guide

> **Requirements**: Python 3.10+, OpenAI API key (for embeddings)

## Quick Start (5 minutes)

### 1. Install Dependencies

```bash
cd /path/to/dytopo-mcp
pip install -r requirements.txt
```

### 2. Set OpenAI API Key

**Option A: Environment Variable** (Recommended)
```bash
# Add to ~/.zshrc or ~/.bashrc
export OPENAI_API_KEY="sk-your-key-here"
source ~/.zshrc
```

**Option B: .env File**
```bash
cp .env.example .env
# Edit .env and add your key
```

See `API_KEY_SETUP.md` for more options (keychain, config file, etc.)

### 3. Test the Server

```bash
python example_usage.py
```

You should see:
```
=== DyTopo Example ===

1. Registering agents...
  ✓ web_search
  ✓ code_executor
  ✓ file_reader
  ✓ database_query
  ✓ api_caller

2. Getting routing plan...

Task: Find the current price of Bitcoin and save it to a JSON file

Selected agents:
  • web_search (relevance: 0.89)
  • api_caller (relevance: 0.82)
  • file_reader (relevance: 0.71)

Topology:
  web_search → ['api_caller', 'file_reader']
  api_caller → ['web_search']
  file_reader → ['web_search']
```

If this works, you're ready to go.

---

## Integration Options

### Option 1: Claude Desktop

1. Find your config file:
   - **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add DyTopo server:

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

The server will use your environment variable or .env file. No secrets in the config.

3. Restart Claude Desktop

4. Test in chat:
```
Register an agent called "web_search" with description "Searches web for current info"
```

You should see the tool execute successfully.

---

### Option 2: Claude Code

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "dytopo": {
      "command": "python",
      "args": ["/Users/yourname/dytopo-mcp/server.py"]
    }
  }
}
```

Uses your environment variable or .env file automatically.

---

### Option 3: Direct Python Usage

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def use_dytopo():
    server_params = StdioServerParameters(
        command="python",
        args=["path/to/server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Register agents
            await session.call_tool("register_agent", {
                "agent_id": "test_agent",
                "description": "Test description"
            })
            
            # Get routing plan
            result = await session.call_tool("get_routing_plan", {
                "task": "Your task here",
                "k": 4
            })
            
            print(result)

asyncio.run(use_dytopo())
```

---

## Embedding Cost Estimation

DyTopo uses OpenAI embeddings (text-embedding-3-small).

**Cost**: ~$0.00002 per agent registration

Example costs:
- 10 agents: $0.0002
- 100 agents: $0.002
- 1000 routing requests: $0.02

Embeddings are cached in memory, so you only pay once per agent.

**Monthly estimate** for typical usage:
- 50 agents registered: $0.001
- 1000 routing requests/month: $0.02
- **Total: ~$0.02/month**

---

## Alternative: Use Local Embeddings

If you don't want OpenAI costs:

1. Install sentence-transformers:
```bash
pip install sentence-transformers
```

2. Modify `server.py`:

```python
# Replace this:
def embed_text(self, text: str) -> np.ndarray:
    response = self.openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(response.data[0].embedding)

# With this:
from sentence_transformers import SentenceTransformer

class DyTopoRouter:
    def __init__(self):
        self.agents = {}
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode(text)
```

**Tradeoff**: Faster, free, but slightly lower quality embeddings.

---

## Performance Optimization

### 1. Batch Agent Registration

```python
# Instead of registering one at a time
for agent in agents:
    register_agent(agent.id, agent.description)

# Register in batches (future feature)
batch_register_agents([
    {"id": "agent1", "description": "..."},
    {"id": "agent2", "description": "..."}
])
```

### 2. Precompute Agent Similarity Matrix

```python
# If you have fixed agent set, precompute similarities
def precompute_similarities(agent_ids):
    matrix = {}
    for i, agent_id in enumerate(agent_ids):
        for j, other_id in enumerate(agent_ids[i+1:]):
            score = compute_agent_similarity(agent_id, other_id)
            matrix[(agent_id, other_id)] = score
    return matrix
```

### 3. Cache Routing Plans

```python
# For repeated tasks, cache the routing plan
routing_cache = {}

def get_cached_plan(task, k=4):
    cache_key = f"{task}:{k}"
    if cache_key not in routing_cache:
        routing_cache[cache_key] = get_routing_plan(task, k)
    return routing_cache[cache_key]
```

---

## Troubleshooting

### Error: "OpenAI API key not found"

**Solution 1**: Set environment variable:
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Solution 2**: Use .env file:
```bash
cp .env.example .env
# Edit .env with your key
```

**Solution 3**: See `API_KEY_SETUP.md` for keychain and config file options.

**Verify it works**:
```bash
python -c "import os; print('✓ Key found' if os.getenv('OPENAI_API_KEY') else '✗ Key not found')"
```

---

### Error: "Module 'mcp' not found"

**Solution**: Install MCP:
```bash
pip install mcp
```

---

### Low similarity scores for obvious matches

**Problem**: Agent descriptions too vague.

**Solution**: Add more specific details:

```python
# Bad
register_agent("coder", "Writes code")

# Good
register_agent("python_backend", "Writes Python backend code using FastAPI, SQLAlchemy, async patterns, type hints, and pytest for testing")
```

---

### Routing plan seems wrong

**Debug**: Check similarity scores manually:

```python
result = compute_agent_similarity(
    task_text="Your task",
    agent_id_1="suspected_wrong_agent"
)

print(f"Similarity: {result['similarity']}")

# If < 0.6, agent shouldn't be selected
# If > 0.8, agent should definitely be selected
```

---

### Want different embedding model

**Options**:
1. OpenAI text-embedding-3-large (higher quality, 2x cost)
2. Cohere embeddings
3. Local: sentence-transformers/all-MiniLM-L6-v2
4. Local: sentence-transformers/all-mpnet-base-v2 (better quality)

Modify `embed_text()` function in server.py.

---

## Advanced Configuration

### Custom Graph Construction

Modify `build_knn_graph()` in server.py:

```python
def build_custom_graph(self, selected_agent_ids, params):
    """Your custom graph logic"""
    graph = {}
    
    # Example: Connect agents with > 0.8 similarity
    for agent_id in selected_agent_ids:
        neighbors = [
            other_id for other_id in selected_agent_ids
            if self.compute_relevance(
                self.agents[agent_id].embedding,
                self.agents[other_id].embedding
            ) > 0.8
        ]
        graph[agent_id] = neighbors
    
    return graph
```

### Add Metadata Filtering

```python
def select_with_constraints(self, task, k, constraints):
    """Select agents matching metadata constraints"""
    task_emb = self.embed_text(task)
    
    # Filter by metadata first
    candidates = [
        agent for agent in self.agents.values()
        if all(agent.metadata.get(k) == v for k, v in constraints.items())
    ]
    
    # Then rank by similarity
    scores = [
        (agent.id, self.compute_relevance(task_emb, agent.embedding))
        for agent in candidates
    ]
    
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:k]
```

---

## Monitoring & Logging

Add logging to track routing decisions:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dytopo")

def get_routing_plan(self, task, k=4):
    logger.info(f"Routing task: {task[:100]}")
    
    plan = # ... generate plan
    
    logger.info(f"Selected {len(plan['selected_agents'])} agents")
    for agent in plan['selected_agents']:
        logger.info(f"  {agent['id']}: {agent['relevance_score']:.2f}")
    
    return plan
```

---

## Next Steps

1. ✅ Install and test
2. ✅ Integrate with your agentic system
3. ✅ Register your actual agents/tools/skills
4. ✅ Run routing experiments
5. ✅ Monitor similarity scores
6. ✅ Optimize agent descriptions
7. ✅ Add confidence weighting (optional)
8. ✅ Implement caching (optional)

See SKILL.md and WORKFLOW_EXAMPLES.md for usage patterns.