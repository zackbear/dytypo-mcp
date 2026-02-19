# Agent Configuration Guide

## How Agent Registration Works

DyTopo needs to know about your agents/tools/skills to route tasks. There are 3 ways to register them:

### 1. Auto-load from agents.yaml (Recommended)

Edit `agents.yaml` and restart the server. Agents load automatically.

```yaml
agents:
  - id: web_search
    description: "Searches current web content and news"
    metadata:
      category: research
```

**When to use**: Production setup, pre-defined agent sets

---

### 2. Register via MCP Tool Calls

Use the `register_agent` tool:

```python
register_agent("my_agent", "Description of what it does")
```

**When to use**: Dynamic agent registration, testing, one-off tasks

---

### 3. Hybrid (Both)

Pre-load common agents in `agents.yaml`, add specific ones via tool calls.

**When to use**: Mix of stable + dynamic agents

---

## Configuring agents.yaml

The file has 3 sections:

### 1. Agent ID

Unique identifier:
```yaml
- id: web_search  # Use this in routing plans
```

### 2. Description (MOST IMPORTANT)

This is what the embedding model uses for semantic matching. **Be specific**:

**Bad**:
```yaml
description: "Searches stuff"
```

**Good**:
```yaml
description: "Searches current web content, news articles, and online information. Best for recent events, current prices, stock data, weather, breaking news."
```

**Tips**:
- Include what it does
- Mention specific use cases
- Add relevant keywords
- List technologies/domains

### 3. Metadata (Optional)

Arbitrary key-value data:
```yaml
metadata:
  category: research
  cost: low
  language: python
  version: "1.0"
```

Used for filtering, logging, or custom logic.

---

## For Claude Code Users

### Option A: Map Claude Code Tools to Agents

List Claude Code's actual tools in `agents.yaml`:

```yaml
agents:
  # Real Claude Code tools
  - id: web_search
    description: "Searches the web for current information"
    
  - id: web_fetch
    description: "Fetches full webpage content from URLs"
    
  - id: bash_tool
    description: "Executes bash commands in Linux container"
    
  - id: str_replace
    description: "Edits files by replacing unique strings"
    
  - id: view
    description: "Views file contents, images, directory listings"
    
  - id: create_file
    description: "Creates new files with specified content"
```

Now when you get a routing plan, it returns actual Claude Code tool names:

```python
plan = get_routing_plan("Download a webpage and save to file", k=3)
# Returns: ["web_fetch", "create_file"]
# These match Claude Code tool names exactly
```

### Option B: Abstract Skills (Not Direct Tools)

Define higher-level skills that might use multiple tools:

```yaml
agents:
  - id: data_researcher
    description: "Researches data from web sources, processes and analyzes it"
    # Might use: web_search, web_fetch, bash_tool
    
  - id: code_generator
    description: "Generates clean, typed, documented code with tests"
    # Might use: create_file, str_replace
    
  - id: file_manager
    description: "Organizes, reads, and modifies files"
    # Might use: view, str_replace, create_file, bash_tool
```

Use this when you want semantic task routing to skill categories.

---

## Pre-configured Examples

### Example 1: Web Scraping Workflow

```yaml
agents:
  - id: url_finder
    description: "Searches Google/Bing for URLs matching specific criteria"
    
  - id: html_fetcher
    description: "Downloads HTML content from websites"
    
  - id: data_extractor
    description: "Parses HTML and extracts structured data using CSS selectors"
    
  - id: data_validator
    description: "Validates and cleans extracted data"
    
  - id: storage_writer
    description: "Writes data to JSON, CSV, or database"
```

### Example 2: Code Development Workflow

```yaml
agents:
  - id: requirements_analyzer
    description: "Analyzes requirements and creates technical specifications"
    
  - id: python_coder
    description: "Writes Python code with type hints, async patterns, FastAPI"
    
  - id: react_coder
    description: "Writes React components with TypeScript and Tailwind CSS"
    
  - id: test_writer
    description: "Creates pytest unit tests and integration tests"
    
  - id: code_reviewer
    description: "Reviews code for bugs, performance, style, security"
```

### Example 3: Research Workflow

```yaml
agents:
  - id: quick_search
    description: "Fast web search for simple factual questions"
    
  - id: deep_research
    description: "Comprehensive research across multiple sources with citations"
    
  - id: academic_search
    description: "Searches academic papers on ArXiv, PubMed, Google Scholar"
    
  - id: data_analyst
    description: "Processes datasets and performs statistical analysis"
    
  - id: synthesizer
    description: "Combines sources and creates coherent narratives"
```

---

## Customization Tips

### 1. Start with Your Use Cases

What tasks do you actually do?
- Code generation?
- Research?
- Data processing?
- File management?

Define agents for those.

### 2. Match Your Tool Ecosystem

If you use Claude Code: Match tool names
If you use LangChain: Match chain names
If you use Autogen: Match agent names

### 3. Iterate Based on Routing

Run routing plans and check similarity scores:

```python
plan = get_routing_plan("Your task", k=5)

# Check scores
for agent in plan['selected_agents']:
    print(f"{agent['id']}: {agent['relevance_score']}")
```

If scores are low (<0.6), improve descriptions.

### 4. Test Semantic Matching

```python
# Should route to web_search
test1 = get_routing_plan("What's the weather in Tokyo?")

# Should route to code_executor  
test2 = get_routing_plan("Calculate 2^64")

# Should route to file operations
test3 = get_routing_plan("Read config.json and update the API key")
```

Verify it picks the right agents.

---

## Dynamic vs Static Registration

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| agents.yaml | Persistent, version controlled | Must restart server | Production |
| Tool calls | Flexible, runtime changes | Lost on restart | Testing, dynamic |
| Hybrid | Best of both | More complex | Real workflows |

---

## Advanced: Auto-Discovery (Future)

You could build auto-discovery for Claude Code:

```python
# Hypothetical - would need Claude Code integration
from claude_code import list_available_tools

tools = list_available_tools()

for tool in tools:
    register_agent(
        tool.name,
        tool.description,
        metadata={"source": "claude_code"}
    )
```

For now, manually list them in `agents.yaml`.

---

## FAQ

**Q: Do I need to register ALL tools?**

No. Only register tools you want DyTopo to route between. If you have 50 tools but only use 10 for semantic routing, register those 10.

**Q: Can I have multiple agents.yaml files?**

Not currently. But you can organize with comments:

```yaml
agents:
  # === Core Tools ===
  - id: web_search
    # ...
  
  # === Specialized Skills ===
  - id: python_expert
    # ...
  
  # === Project-Specific ===
  - id: custom_agent
    # ...
```

**Q: What if agent descriptions overlap?**

That's fine. DyTopo will select the most relevant. For example:

```yaml
- id: general_coder
  description: "Writes code in any language"
  
- id: python_specialist
  description: "Expert Python developer with FastAPI, async, type hints"
```

Task: "Build FastAPI endpoint" → Selects python_specialist (higher score)
Task: "Write a bash script" → Selects general_coder

**Q: Can I reload agents.yaml without restarting?**

Not currently. Restart the MCP server to reload config.

---

## Getting Started

1. Copy the example agents.yaml
2. Customize descriptions for your use cases
3. Test routing with sample tasks
4. Iterate based on similarity scores
5. Add more agents as needed

The quality of your agent descriptions determines routing quality. Invest time in making them specific and detailed.