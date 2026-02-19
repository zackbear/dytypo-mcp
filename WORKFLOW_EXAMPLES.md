# DyTopo Workflow Integration Examples

## Example 1: Claude Code with DyTopo Routing

### Scenario
You're building a web scraper that needs to:
1. Search for target URLs
2. Fetch HTML content
3. Parse specific data
4. Store in database
5. Generate report

### Without DyTopo
```python
# Hardcoded pipeline - always runs all steps
steps = [
    web_search_tool,
    web_fetch_tool, 
    html_parser_tool,
    database_tool,
    report_generator_tool
]

for step in steps:
    result = step(task)  # Each tool sees everything
```

### With DyTopo
```python
# Dynamic routing based on task
from dytopo import get_routing_plan

# Register tools once
tools = {
    "web_search": "Searches Google/Bing for URLs matching query",
    "web_fetch": "Fetches HTML content from URLs",
    "html_parser": "Extracts structured data from HTML using selectors",
    "json_processor": "Transforms and validates JSON data",
    "database_writer": "Writes data to PostgreSQL/MySQL",
    "csv_exporter": "Exports data to CSV files",
    "report_generator": "Creates markdown/HTML reports from data"
}

for tool_id, description in tools.items():
    register_agent(tool_id, description)

# Route different tasks differently
task1 = "Scrape product prices from Amazon and save to PostgreSQL"
plan1 = get_routing_plan(task1, k=4)
# Selects: web_search → web_fetch → html_parser → database_writer

task2 = "Get company info from Crunchbase API and export to CSV"  
plan2 = get_routing_plan(task2, k=3)
# Selects: web_fetch → json_processor → csv_exporter
# (Skips web_search, html_parser, report_generator)

# Execute with only selected tools
def execute_plan(task, plan):
    context = {"task": task}
    
    for round in plan["execution_order"]:
        for tool_id in round:
            # Only get context from topology neighbors
            neighbors = plan["topology"][tool_id]
            neighbor_outputs = {n: context[n] for n in neighbors if n in context}
            
            # Execute tool
            result = tools_executor[tool_id](task, neighbor_outputs)
            context[tool_id] = result
    
    return context
```

**Token savings**: ~60% by skipping irrelevant tools

---

## Example 2: Agentic Code Review System

### Setup
```python
# Register specialized reviewers
reviewers = {
    "security": "Identifies OWASP top 10, injection attacks, auth issues, crypto misuse",
    "performance": "Finds N+1 queries, memory leaks, inefficient algorithms, blocking operations",
    "style": "Checks PEP 8, naming, documentation, code smells, duplicate code",
    "logic": "Detects edge cases, race conditions, error handling, type safety",
    "testing": "Assesses test coverage, mocking correctness, assertion quality",
    "accessibility": "Validates WCAG compliance, ARIA labels, keyboard navigation, screen readers"
}

for reviewer_id, capabilities in reviewers.items():
    register_agent(f"{reviewer_id}_reviewer", capabilities)

# Route based on code context
def review_code(code, context=""):
    task = f"Review this code: {context}\n\n{code[:500]}"
    
    plan = get_routing_plan(task, k=4, graph_k=2)
    
    print(f"Selected reviewers: {[a['id'] for a in plan['selected_agents']]}")
    print(f"Topology: {plan['topology']}")
    
    # Execute reviews in topology order
    reviews = {}
    for round in plan["execution_order"]:
        for reviewer_id in round:
            # Get reviews from connected reviewers
            neighbors = plan["topology"][reviewer_id]
            prior_reviews = [reviews[n] for n in neighbors if n in reviews]
            
            # Run review with context
            review = run_reviewer(reviewer_id, code, prior_reviews)
            reviews[reviewer_id] = review
    
    return aggregate_reviews(reviews)

# Example 1: Authentication code
code1 = """
def login(username, password):
    user = db.query(f"SELECT * FROM users WHERE username='{username}'")
    if user and user.password == password:
        return create_session(user)
"""

review1 = review_code(code1, "login endpoint")
# Selects: security_reviewer (0.96), logic_reviewer (0.81), testing_reviewer (0.73)
# Security finds SQL injection, plain text password comparison
# Logic finds missing null check
# Testing suggests test cases

# Example 2: UI component
code2 = """
function ProductCard({ product }) {
    return <div onClick={handleClick}>
        <img src={product.image} />
        <h3>{product.name}</h3>
    </div>
}
"""

review2 = review_code(code2, "React component")
# Selects: accessibility_reviewer (0.92), style_reviewer (0.85), testing_reviewer (0.71)
# Accessibility finds missing alt text, keyboard access issues
# Style suggests PropTypes
# Testing recommends component tests
```

**Benefit**: Different code gets different expertise without manual routing rules

---

## Example 3: Multi-Language Code Generation

### Problem
You're building a full-stack app. Frontend in React, backend in Python, infrastructure in Terraform.

### Solution
```python
# Register language-specific agents
agents = {
    "react_expert": "React, JSX, hooks, TypeScript, Tailwind, component patterns",
    "python_expert": "Python, FastAPI, async, type hints, SQLAlchemy, pytest",
    "sql_expert": "PostgreSQL, queries, indexes, migrations, optimization",
    "terraform_expert": "AWS infrastructure, networking, security groups, IAM",
    "docker_expert": "Containerization, multi-stage builds, docker-compose",
    "cicd_expert": "GitHub Actions, testing pipelines, deployment automation"
}

for agent_id, skills in agents.items():
    register_agent(agent_id, skills)

# Route tasks to appropriate experts
tasks = [
    "Build user registration form with validation",
    "Create API endpoint for user registration with email verification", 
    "Design database schema for users and verification tokens",
    "Set up AWS infrastructure for production deployment",
    "Configure CI/CD pipeline for automated testing and deployment"
]

for task in tasks:
    plan = get_routing_plan(task, k=3)
    print(f"\nTask: {task}")
    print(f"Agents: {[a['id'] for a in plan['selected_agents']]}")
    
    # Execute with selected agents
    outputs = execute_agents(task, plan)

# Results:
# Task 1 → react_expert, python_expert
# Task 2 → python_expert, sql_expert
# Task 3 → sql_expert, python_expert  
# Task 4 → terraform_expert, docker_expert
# Task 5 → cicd_expert, docker_expert, terraform_expert
```

**Benefit**: Automatic expert selection per task, no manual orchestration

---

## Example 4: Research Pipeline with Dynamic Depth

### Scenario
User asks research question. Depth of research should adapt to question complexity.

### Implementation
```python
# Register research agents with different specializations
research_agents = {
    "quick_web": "Fast web search for current info, basic facts, simple questions",
    "deep_web": "Comprehensive web research across multiple sources with fact-checking",
    "academic": "Searches academic papers, ArXiv, Google Scholar, PubMed",
    "data_analyst": "Processes datasets, performs statistical analysis",
    "expert_synthesizer": "Combines sources, resolves contradictions, creates narratives"
}

for agent_id, description in research_agents.items():
    register_agent(agent_id, description)

# Different questions get different research depth
questions = [
    "What's the current weather in Tokyo?",
    "Explain the impact of quantum computing on cryptography with academic sources",
    "Compare remote work productivity studies from 2020-2024"
]

for question in questions:
    plan = get_routing_plan(question, k=5)
    
    selected = [a['id'] for a in plan['selected_agents']]
    print(f"\nQ: {question}")
    print(f"Research depth: {len(selected)} agents")
    print(f"Agents: {selected}")

# Results:
# Weather question → quick_web only (1 agent)
# Quantum/crypto → academic, expert_synthesizer, deep_web (3 agents)
# Productivity comparison → deep_web, academic, data_analyst, expert_synthesizer (4 agents)
```

**Benefit**: Research depth adapts automatically to question complexity

---

## Example 5: Agent Zero Integration

### Add DyTopo to Agent Zero's sub-agent system

```python
# In Agent Zero config
from dytopo import register_agent, get_routing_plan

# Register Agent Zero's tools as agents
def register_agent_zero_tools():
    tools = {
        "code_execution": "Executes Python code in isolated environment",
        "knowledge_search": "Searches knowledge base and documentation",
        "web_search": "Real-time web search for current information",
        "file_operations": "File system operations - read, write, edit",
        "api_calls": "HTTP requests to external APIs",
        "memory_query": "Queries agent's episodic memory",
        "subprocess": "Runs system commands and scripts"
    }
    
    for tool_id, description in tools.items():
        register_agent(f"tool_{tool_id}", description)

# Replace Agent Zero's tool selection with DyTopo routing
class DyTopoToolSelector:
    def select_tools(self, task: str, max_tools: int = 4):
        plan = get_routing_plan(task, k=max_tools)
        
        selected_tools = [
            a['id'].replace('tool_', '')  # Remove prefix
            for a in plan['selected_agents']
        ]
        
        # Return tools in execution order
        return {
            'tools': selected_tools,
            'topology': plan['topology'],
            'execution_order': plan['execution_order']
        }

# Use in Agent Zero
agent = Agent(
    tool_selector=DyTopoToolSelector()
)

response = agent.run("Debug why my React app won't build")
# Automatically routes to: code_execution → file_operations → knowledge_search
```

---

## Example 6: Confidence-Weighted Multi-Round

### Advanced pattern for iterative refinement

```python
# Track agent performance
agent_performance = {
    "agent_1": {"successes": 45, "failures": 5},
    "agent_2": {"successes": 38, "failures": 12},
    "agent_3": {"successes": 50, "failures": 0}
}

def confidence_score(agent_id):
    perf = agent_performance[agent_id]
    return perf["successes"] / (perf["successes"] + perf["failures"])

# Multi-round with confidence weighting
def execute_with_confidence(task, rounds=3):
    plan = get_routing_plan(task, k=5)
    
    outputs = {}
    confidences = {}
    
    for round_num in range(rounds):
        for agent_id in plan['selected_agents']:
            # Get neighbor outputs weighted by confidence
            neighbors = plan['topology'][agent_id]
            weighted_context = []
            
            for neighbor_id in neighbors:
                if neighbor_id in outputs:
                    weight = confidences.get(neighbor_id, 0.5)
                    weighted_context.append({
                        'output': outputs[neighbor_id],
                        'weight': weight
                    })
            
            # Execute agent
            result = execute_agent(agent_id, task, weighted_context)
            
            outputs[agent_id] = result['output']
            confidences[agent_id] = result.get('confidence', confidence_score(agent_id))
        
        # Early stopping if consensus is high
        if all(c > 0.9 for c in confidences.values()):
            break
    
    # Weight final aggregation by confidence
    weighted_outputs = [
        (outputs[aid], confidences[aid]) 
        for aid in outputs
    ]
    
    return aggregate_weighted(weighted_outputs)
```

---

## Example 7: Human-in-Loop Escalation

### Escalate to human when agent consensus is low

```python
# Register agents including human
agents = {
    "auto_agent_1": "Automated task executor",
    "auto_agent_2": "Automated analyzer",
    "auto_agent_3": "Automated validator",
    "human_expert": "Human expert for ambiguous cases"
}

for agent_id, desc in agents.items():
    register_agent(agent_id, desc, metadata={
        "is_human": agent_id == "human_expert"
    })

def execute_with_human_fallback(task):
    # Try automated agents first
    plan = get_routing_plan(task, k=3)
    
    # Exclude human initially
    auto_agents = [a for a in plan['selected_agents'] if not a['id'] == 'human_expert']
    
    # Execute automated agents
    outputs = {}
    for agent in auto_agents:
        outputs[agent['id']] = execute_agent(agent['id'], task)
    
    # Check consensus
    confidences = [o.get('confidence', 0.5) for o in outputs.values()]
    avg_confidence = sum(confidences) / len(confidences)
    
    if avg_confidence < 0.7:
        # Low confidence - escalate to human
        print("🔴 Low confidence detected - escalating to human")
        
        # Add human to topology
        human_plan = get_routing_plan(
            f"{task}\n\nAutomated agents uncertain. Outputs: {outputs}",
            k=1
        )
        
        human_output = request_human_input(task, outputs)
        outputs['human_expert'] = human_output
    
    return aggregate(outputs)
```

---

## Key Takeaways

1. **Register once, route many**: Set up agents once, reuse for all tasks
2. **Topology = execution plan**: Use the graph structure to control flow
3. **Semantic matching beats rules**: Let embeddings find relevant agents
4. **Start simple, add complexity**: Begin with basic routing, add confidence weighting later
5. **Monitor and debug**: Track similarity scores to understand routing decisions

The MCP server handles complexity. You just register agents and execute plans.
