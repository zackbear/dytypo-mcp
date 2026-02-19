# LLM-Powered Agent Discovery Guide

Use Claude/GPT to automatically discover, create, and improve agent definitions.

## Why Use LLM Discovery?

Writing good agent descriptions is hard:
- Need to be specific enough for semantic matching
- Should include relevant keywords
- Must differentiate from similar agents
- Requires domain knowledge

Let the LLM do it for you.

---

## 1. Suggest Agents for a Domain

**Use case**: You're starting a new project and need agents for a specific domain.

```python
# Ask LLM to suggest agents
suggest_agents_for_domain(
    domain="web scraping and data extraction",
    num_agents=5
)
```

**Returns**:
```json
{
  "suggested_agents": [
    {
      "id": "url_discoverer",
      "description": "Searches and identifies target URLs using search engines (Google, Bing), site maps, and link crawling. Specializes in finding pages matching specific criteria like domain, content type, or URL patterns. Uses BeautifulSoup and Scrapy for discovery.",
      "metadata": {"category": "discovery", "keywords": ["search", "crawling", "urls"]}
    },
    {
      "id": "html_parser",
      "description": "Extracts structured data from HTML using CSS selectors, XPath, and DOM parsing. Handles dynamic content loaded via JavaScript. Works with BeautifulSoup, lxml, and Selenium for comprehensive parsing.",
      "metadata": {"category": "extraction", "keywords": ["parsing", "html", "dom"]}
    },
    // ... more agents
  ]
}
```

**Then**: Review and register the ones you want:
```python
register_agent("html_parser", "Extracts structured data from HTML...")
```

---

## 2. Improve Existing Descriptions

**Use case**: Your agent descriptions are too vague and routing quality is low.

```python
# Current description
current = "Searches the web"

# Improve it
improve_agent_description(
    agent_id="web_search",
    current_description=current,
    context="Used for finding current information, news, and data"
)
```

**Returns**:
```json
{
  "original_description": "Searches the web",
  "improved_description": "Performs real-time web searches using Google and Bing APIs to find current information, breaking news, recent events, stock prices, weather data, and trending topics. Excels at queries requiring up-to-date information rather than historical knowledge. Returns ranked results with snippets and URLs."
}
```

Much better for semantic matching!

---

## 3. Analyze Coverage Gaps

**Use case**: Check if your current agents cover a new domain well.

```python
analyze_agent_coverage(
    task_domain="building a REST API with authentication",
    existing_agent_ids=["python_expert", "database_expert", "frontend_dev"]
)
```

**Returns**:
```json
{
  "coverage_score": 65,
  "gaps": [
    "Authentication and JWT token handling",
    "API security (rate limiting, CORS, input validation)",
    "API documentation and testing"
  ],
  "suggested_agents": [
    {
      "id": "auth_specialist",
      "reason": "None of the existing agents specifically handle authentication, JWT, OAuth, or session management"
    },
    {
      "id": "api_security_expert",
      "reason": "Missing specialized knowledge in API security best practices"
    }
  ],
  "redundant": [],
  "recommendations": [
    "Add auth_specialist for authentication flows",
    "Enhance python_expert description to include FastAPI/Flask specifics"
  ]
}
```

Now you know exactly what's missing.

---

## 4. Discover from Tool Names

**Use case**: You have a list of tool names but no descriptions.

```python
discover_agents_from_tools(
    tools=["web_search", "web_fetch", "bash_tool", "str_replace", "view"]
)
```

**Returns**:
```json
{
  "discovered_agents": [
    {
      "id": "web_search",
      "description": "Performs web searches using search engines to find relevant URLs, content, and information. Best for discovering online resources, recent news, current events, and fact-checking. Returns URLs and snippets for further processing.",
      "metadata": {"category": "research"}
    },
    {
      "id": "web_fetch",
      "description": "Downloads complete webpage content from URLs. Retrieves full HTML, text, and embedded resources. Useful for reading articles, documentation, blog posts, and any web-based content after URLs are identified.",
      "metadata": {"category": "research"}
    },
    // ... more
  ]
}
```

Perfect for bootstrapping your agents.yaml from existing tool lists.

---

## 5. Suggest Missing Agents for Tasks

**Use case**: You have specific tasks and want to know if you need new agents.

```python
suggest_missing_agents(
    tasks=[
        "Review Python code for security vulnerabilities",
        "Optimize SQL queries for better performance",
        "Generate API documentation from code",
        "Set up CI/CD pipeline with GitHub Actions"
    ],
    existing_agent_ids=["python_expert", "database_expert"]
)
```

**Returns**:
```json
{
  "missing_agents": [
    {
      "id": "security_auditor",
      "description": "Specialized in identifying security vulnerabilities in Python code. Detects SQL injection, XSS, CSRF, insecure dependencies, crypto misuse, and OWASP top 10 issues. Uses tools like Bandit and Safety.",
      "fills_gap_for": [
        "Review Python code for security vulnerabilities"
      ],
      "metadata": {"category": "security"}
    },
    {
      "id": "api_doc_generator",
      "description": "Automatically generates API documentation from code and docstrings. Creates OpenAPI/Swagger specs, README files, and interactive docs. Works with FastAPI, Flask, Django REST Framework.",
      "fills_gap_for": [
        "Generate API documentation from code"
      ],
      "metadata": {"category": "documentation"}
    },
    {
      "id": "cicd_engineer",
      "description": "Sets up and configures CI/CD pipelines using GitHub Actions, GitLab CI, and Jenkins. Handles testing automation, deployment workflows, environment management, and release strategies.",
      "fills_gap_for": [
        "Set up CI/CD pipeline with GitHub Actions"
      ],
      "metadata": {"category": "devops"}
    }
  ]
}
```

SQL optimization is covered by `database_expert`, so only new agents for gaps are suggested.

---

## Workflows

### Workflow 1: Bootstrap New Project

```python
# 1. Get suggestions for your domain
agents = suggest_agents_for_domain("e-commerce backend development", num_agents=6)

# 2. Review and register the good ones
for agent in agents['suggested_agents']:
    register_agent(agent['id'], agent['description'], agent['metadata'])

# 3. Test routing
plan = get_routing_plan("Build user authentication with JWT", k=4)

# 4. Check coverage
analysis = analyze_agent_coverage("e-commerce backend development")

# 5. Add missing agents if coverage is low
if analysis['coverage_score'] < 80:
    for suggestion in analysis['suggested_agents']:
        # Register suggested agents
        pass
```

### Workflow 2: Improve Existing Setup

```python
# 1. List current agents
agents = list_agents()

# 2. Improve each description
for agent in agents:
    improved = improve_agent_description(
        agent_id=agent['id'],
        current_description=agent['description']
    )
    
    # Review the improvement
    print(f"Original: {agent['description']}")
    print(f"Improved: {improved['improved_description']}")
    
    # Update if better (manual review)
    if user_approves:
        # Re-register with new description
        register_agent(agent['id'], improved['improved_description'])
```

### Workflow 3: Task-Driven Agent Discovery

```python
# 1. List all tasks you need to handle
tasks = [
    "Scrape product prices from competitor websites",
    "Store data in PostgreSQL with proper indexing",
    "Send price alerts via email when thresholds are met",
    "Generate daily reports with visualizations"
]

# 2. Get current agents
current_agents = ["web_scraper", "database_writer"]

# 3. Find what's missing
missing = suggest_missing_agents(
    tasks=tasks,
    existing_agent_ids=current_agents
)

# 4. Register missing agents
for agent in missing['missing_agents']:
    register_agent(agent['id'], agent['description'])

# 5. Test that all tasks can be routed
for task in tasks:
    plan = get_routing_plan(task, k=3)
    print(f"Task: {task}")
    print(f"Selected: {[a['id'] for a in plan['selected_agents']]}")
```

---

## Best Practices

### 1. Always Review LLM Suggestions

LLM-generated descriptions are good starting points but may need tweaking:

```python
# Get suggestion
agents = suggest_agents_for_domain("data science workflows")

# Review and customize
for agent in agents['suggested_agents']:
    # Check if description matches your actual use case
    # Adjust terminology to match your stack
    # Add specific libraries/tools you use
    
    customized_description = agent['description'] + " Uses pandas, scikit-learn, and Jupyter notebooks."
    register_agent(agent['id'], customized_description)
```

### 2. Use Context Parameter

Provide context for better improvements:

```python
improve_agent_description(
    agent_id="code_reviewer",
    current_description="Reviews code",
    context="This agent specifically reviews Python FastAPI code for a microservices architecture. Focuses on async patterns, type hints, and API design."
)
```

### 3. Iterate on Coverage

Coverage analysis helps you iteratively improve:

```python
iteration = 1
while True:
    analysis = analyze_agent_coverage("your domain")
    
    print(f"Iteration {iteration}: Coverage {analysis['coverage_score']}%")
    
    if analysis['coverage_score'] >= 85:
        break
    
    # Add suggested agents
    for suggestion in analysis['suggested_agents'][:2]:  # Add top 2
        # Implement agent
        pass
    
    iteration += 1
```

### 4. Domain-Specific Vocabulary

LLM suggestions are generic. Add your specific vocabulary:

```python
# Generic suggestion
generic = "Handles database operations with PostgreSQL"

# Your improvement
specific = "Handles database operations using PostgreSQL 15 with TimescaleDB extension for time-series data. Specializes in hypertable optimization and continuous aggregates for our IoT sensor data pipeline."
```

---

## Advanced: Batch Processing

Process multiple domains at once:

```python
domains = [
    "frontend development",
    "backend APIs",
    "database management",
    "DevOps automation"
]

all_agents = []
for domain in domains:
    agents = suggest_agents_for_domain(domain, num_agents=3)
    all_agents.extend(agents['suggested_agents'])

# Remove duplicates, review, and register
unique_agents = deduplicate_by_similarity(all_agents)
for agent in unique_agents:
    register_agent(agent['id'], agent['description'])
```

---

## Example: Complete Setup from Scratch

```python
# Starting a new web scraping project

# 1. Generate initial agents
agents = suggest_agents_for_domain("web scraping and data processing", num_agents=8)

# 2. Register them
for agent in agents['suggested_agents']:
    register_agent(agent['id'], agent['description'])

# 3. Test with real tasks
test_tasks = [
    "Find all product URLs on Amazon for 'wireless headphones'",
    "Extract price, rating, and reviews from product pages",
    "Store data in PostgreSQL with deduplication",
    "Generate price trend charts"
]

# 4. Check coverage
analysis = analyze_agent_coverage(
    task_domain="complete web scraping pipeline",
    existing_agent_ids=[a['id'] for a in agents['suggested_agents']]
)

print(f"Coverage: {analysis['coverage_score']}%")

# 5. Fill gaps if needed
if analysis['coverage_score'] < 80:
    missing = suggest_missing_agents(
        tasks=test_tasks,
        existing_agent_ids=[a['id'] for a in agents['suggested_agents']]
    )
    
    for agent in missing['missing_agents']:
        register_agent(agent['id'], agent['description'])

# 6. Improve descriptions based on actual use
for task in test_tasks:
    plan = get_routing_plan(task, k=4)
    
    # If routing seems off, improve descriptions
    for agent in plan['selected_agents']:
        if agent['relevance_score'] < 0.7:
            improved = improve_agent_description(
                agent_id=agent['id'],
                current_description=agent['description'],
                context=f"Should be highly relevant for: {task}"
            )
            # Update if better
```

---

## Cost Considerations

LLM discovery uses GPT-4 API calls:

**Approximate costs**:
- `suggest_agents_for_domain`: ~$0.02 per call
- `improve_agent_description`: ~$0.01 per call
- `analyze_agent_coverage`: ~$0.02 per call
- `discover_agents_from_tools`: ~$0.015 per call
- `suggest_missing_agents`: ~$0.02 per call

**Budget**: $0.50 can generate ~25 agent definitions and improvements.

Bootstrap once, then manually maintain.

---

## Tips

1. **Start broad, refine narrow**: Get suggestions for broad domains, then improve specific agents

2. **Compare before/after**: Always compare LLM suggestions with your current setup

3. **Domain vocabulary matters**: LLM doesn't know your specific tools/libraries - add them

4. **Test routing**: After generating agents, test routing on real tasks to validate

5. **Iterate**: Use coverage analysis → add agents → retest → repeat

The LLM handles the hard part (semantic richness). You handle the domain specifics.