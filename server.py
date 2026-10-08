"""
DyTopo MCP Server - Dynamic Topology Routing for Multi-Agent Systems

Provides semantic matching and dynamic graph construction for agent routing.
"""

import sys
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import yaml

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, skip

# Import pluggable embedder
from embedders import get_embedder, CachedEmbedder

# Agent discovery is optional — requires OPENAI_API_KEY and the agent_discovery module.
# If unavailable, discovery MCP tools degrade gracefully with a clear error message.
try:
    from agent_discovery import AgentDiscovery
    _DISCOVERY_AVAILABLE = True
except ImportError:
    _DISCOVERY_AVAILABLE = False
    AgentDiscovery = None  # type: ignore[assignment,misc]

# MCP imports
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

@dataclass
class Agent:
    """Agent with semantic embedding."""
    id: str
    description: str
    embedding: Optional[np.ndarray] = None
    metadata: Optional[Dict] = None

    def to_dict(self):
        data = asdict(self)
        if self.embedding is not None:
            data['embedding'] = self.embedding.tolist()
        return data


class DyTopoRouter:
    """Core semantic routing engine."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.embedder: CachedEmbedder = get_embedder()
        # Discovery is an optional OpenAI-backed feature; without a key, leave it off
        # (the tool handler reports it as unavailable) instead of crashing on import.
        self.discovery = AgentDiscovery() if _DISCOVERY_AVAILABLE and os.getenv("OPENAI_API_KEY") else None

        # Auto-load agents from config file
        self._load_agents_from_config()

    def _load_agents_from_config(self):
        """Load agents from agents.yaml, falling back to agents.example.yaml."""
        repo_dir = Path(__file__).parent
        config_path = repo_dir / 'agents.yaml'
        fallback_path = repo_dir / 'agents.example.yaml'

        if not config_path.exists():
            if fallback_path.exists():
                config_path = fallback_path
                print("[DyTopo] agents.yaml not found — loading agents.example.yaml. "
                      "Run 'python bootstrap_agents.py' to generate your own agents.yaml.", file=sys.stderr)
            else:
                return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not config or 'agents' not in config:
                return

            for agent_config in config['agents']:
                agent_id = agent_config['id']
                description = agent_config['description']
                metadata = agent_config.get('metadata', {})

                self.register_agent(agent_id, description, metadata)

            print(f"[DyTopo] Loaded {len(config['agents'])} agents from {config_path.name}", file=sys.stderr)

        except Exception as e:
            print(f"[DyTopo] Warning: Could not load {config_path.name}: {e}", file=sys.stderr)


    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text (via cached provider)."""
        return self.embedder.embed(text)

    def register_agent(self, agent_id: str, description: str, metadata: Optional[Dict] = None) -> Agent:
        """Register agent with semantic embedding."""
        embedding = self.embed_text(description)
        agent = Agent(
            id=agent_id,
            description=description,
            embedding=embedding,
            metadata=metadata or {}
        )
        self.agents[agent_id] = agent
        return agent

    def compute_relevance(self, task_embedding: np.ndarray, agent_embedding: np.ndarray) -> float:
        """Compute semantic relevance score."""
        a, b = np.asarray(task_embedding, dtype=float), np.asarray(agent_embedding, dtype=float)
        return float(a @ b / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12))

    def select_top_k(self, task_text: str, k: int) -> List[Tuple[str, float]]:
        """Select top-k most relevant agents for task."""
        task_emb = self.embed_text(task_text)

        scores = []
        for agent in self.agents.values():
            score = self.compute_relevance(task_emb, agent.embedding)
            scores.append((agent.id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

    def build_knn_graph(self, selected_agent_ids: List[str], k: int = 2) -> Dict[str, List[str]]:
        """Build k-NN semantic graph between selected agents."""
        graph = {}

        for agent_id in selected_agent_ids:
            agent = self.agents[agent_id]

            similarities = []
            for other_id in selected_agent_ids:
                if other_id == agent_id:
                    continue
                other = self.agents[other_id]
                score = self.compute_relevance(agent.embedding, other.embedding)
                similarities.append((other_id, score))

            similarities.sort(key=lambda x: x[1], reverse=True)
            neighbors = [s[0] for s in similarities[:k]]
            graph[agent_id] = neighbors

        return graph

    def build_threshold_graph(self, selected_agent_ids: List[str], threshold: float = 0.7) -> Dict[str, List[str]]:
        """Build graph connecting agents above similarity threshold."""
        graph = {agent_id: [] for agent_id in selected_agent_ids}

        for i, agent_id in enumerate(selected_agent_ids):
            agent = self.agents[agent_id]

            for other_id in selected_agent_ids[i+1:]:
                other = self.agents[other_id]
                score = self.compute_relevance(agent.embedding, other.embedding)

                if score >= threshold:
                    graph[agent_id].append(other_id)
                    graph[other_id].append(agent_id)

        return graph

    def get_routing_plan(self, task_text: str, k: int = 4, graph_k: int = 2,
                        graph_type: str = "knn") -> Dict:
        """Generate complete routing plan for task."""
        selected = self.select_top_k(task_text, k)
        selected_ids = [s[0] for s in selected]

        if graph_type == "knn":
            graph = self.build_knn_graph(selected_ids, graph_k)
        elif graph_type == "threshold":
            graph = self.build_threshold_graph(selected_ids, 0.7)
        elif graph_type == "star":
            graph = {selected_ids[0]: selected_ids[1:]}
            for agent_id in selected_ids[1:]:
                graph[agent_id] = [selected_ids[0]]
        else:
            raise ValueError(f"Unknown graph type: {graph_type}")

        return {
            "task": task_text,
            "selected_agents": [
                {
                    "id": agent_id,
                    "relevance_score": score,
                    "description": self.agents[agent_id].description
                }
                for agent_id, score in selected
            ],
            "topology": graph,
            "graph_type": graph_type,
            "execution_order": self._compute_execution_order(graph, selected_ids[0])
        }

    def _compute_execution_order(self, graph: Dict[str, List[str]], start_node: str) -> List[List[str]]:
        """Compute BFS execution order for parallel rounds."""
        visited = set()
        rounds = []
        current_round = [start_node]

        while current_round:
            rounds.append(current_round)
            visited.update(current_round)

            next_round = []
            for node in current_round:
                for neighbor in graph.get(node, []):
                    if neighbor not in visited and neighbor not in next_round:
                        next_round.append(neighbor)

            current_round = next_round

        return rounds


# Initialize router
router = DyTopoRouter()

# Create MCP server
server = Server("dytopo-router")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available DyTopo tools."""
    return [
        types.Tool(
            name="register_agent",
            description="Register an agent with semantic embedding. Provide agent_id, description of capabilities, and optional metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "description": {"type": "string"},
                    "metadata": {"type": "object"}
                },
                "required": ["agent_id", "description"]
            }
        ),
        types.Tool(
            name="list_agents",
            description="List all registered agents with their descriptions.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_routing_plan",
            description="Generate dynamic routing plan for a task. Returns selected agents, topology graph, and execution order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "k": {"type": "integer", "default": 4, "description": "Number of agents to select"},
                    "graph_k": {"type": "integer", "default": 2, "description": "Neighbors per agent in graph"},
                    "graph_type": {"type": "string", "enum": ["knn", "threshold", "star"], "default": "knn"}
                },
                "required": ["task"]
            }
        ),
        types.Tool(
            name="compute_agent_similarity",
            description="Compute semantic similarity between two agents or between task and agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id_1": {"type": "string"},
                    "agent_id_2": {"type": "string"},
                    "task_text": {"type": "string"}
                }
            }
        ),
        types.Tool(
            name="clear_agents",
            description="Clear all registered agents.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="clear_embedding_cache",
            description="Clear the persistent embedding cache. Useful after bulk description updates.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_embedder_info",
            description="Return the active embedding provider name and cache stats.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # LLM-Powered Agent Discovery Tools
        types.Tool(
            name="suggest_agents_for_domain",
            description="Use LLM to suggest specialized agents for a task domain. Generates agent IDs, detailed descriptions, and metadata automatically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Task domain (e.g., 'web scraping', 'code review', 'data analysis')"},
                    "num_agents": {"type": "integer", "default": 5, "description": "Number of agents to suggest"}
                },
                "required": ["domain"]
            }
        ),
        types.Tool(
            name="improve_agent_description",
            description="Use LLM to improve an existing agent description for better semantic matching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "current_description": {"type": "string"},
                    "context": {"type": "string", "description": "Optional context about the agent's role"}
                },
                "required": ["agent_id", "current_description"]
            }
        ),
        types.Tool(
            name="analyze_agent_coverage",
            description="Use LLM to analyze if existing agents cover a task domain well. Identifies gaps and suggests improvements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_domain": {"type": "string", "description": "Domain to analyze coverage for"},
                    "existing_agent_ids": {"type": "array", "items": {"type": "string"}, "description": "List of agent IDs to analyze"}
                },
                "required": ["task_domain"]
            }
        ),
        types.Tool(
            name="discover_agents_from_tools",
            description="Generate agent definitions from a list of tool names using LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tools": {"type": "array", "items": {"type": "string"}, "description": "List of tool names"}
                },
                "required": ["tools"]
            }
        ),
        types.Tool(
            name="suggest_missing_agents",
            description="Analyze tasks and suggest new agents needed to handle them that existing agents can't.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks": {"type": "array", "items": {"type": "string"}, "description": "List of task descriptions"},
                    "existing_agent_ids": {"type": "array", "items": {"type": "string"}, "description": "Current agent IDs"}
                },
                "required": ["tasks"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""

    if name == "register_agent":
        agent = router.register_agent(
            agent_id=arguments["agent_id"],
            description=arguments["description"],
            metadata=arguments.get("metadata")
        )
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "status": "registered",
                "agent_id": agent.id,
                "description": agent.description,
                "metadata": agent.metadata,
                "embedder": router.embedder.name
            }, indent=2)
        )]

    elif name == "list_agents":
        agents_list = [
            {
                "id": agent.id,
                "description": agent.description,
                "metadata": agent.metadata
            }
            for agent in router.agents.values()
        ]
        return [types.TextContent(
            type="text",
            text=json.dumps(agents_list, indent=2)
        )]

    elif name == "get_routing_plan":
        plan = router.get_routing_plan(
            task_text=arguments["task"],
            k=arguments.get("k", 4),
            graph_k=arguments.get("graph_k", 2),
            graph_type=arguments.get("graph_type", "knn")
        )
        return [types.TextContent(
            type="text",
            text=json.dumps(plan, indent=2)
        )]

    elif name == "compute_agent_similarity":
        if "task_text" in arguments:
            task_emb = router.embed_text(arguments["task_text"])
            agent = router.agents[arguments["agent_id_1"]]
            score = router.compute_relevance(task_emb, agent.embedding)
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "task": arguments["task_text"],
                    "agent_id": arguments["agent_id_1"],
                    "similarity": score
                }, indent=2)
            )]
        else:
            agent1 = router.agents[arguments["agent_id_1"]]
            agent2 = router.agents[arguments["agent_id_2"]]
            score = router.compute_relevance(agent1.embedding, agent2.embedding)
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "agent_1": arguments["agent_id_1"],
                    "agent_2": arguments["agent_id_2"],
                    "similarity": score
                }, indent=2)
            )]

    elif name == "clear_agents":
        router.agents.clear()
        return [types.TextContent(
            type="text",
            text=json.dumps({"status": "cleared"})
        )]

    elif name == "clear_embedding_cache":
        router.embedder.clear()
        return [types.TextContent(
            type="text",
            text=json.dumps({"status": "cache_cleared", "embedder": router.embedder.name})
        )]

    elif name == "get_embedder_info":
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "embedder": router.embedder.name,
                "cache_entries": router.embedder.cache_size,
                "cache_path": str(router.embedder.cache_path)
            }, indent=2)
        )]

    # LLM-Powered Discovery Tools
    elif name in (
        "suggest_agents_for_domain",
        "improve_agent_description",
        "analyze_agent_coverage",
        "discover_agents_from_tools",
        "suggest_missing_agents",
    ):
        if not _DISCOVERY_AVAILABLE or router.discovery is None:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": (
                        "Agent discovery tools require the 'agent_discovery' module and "
                        "an OPENAI_API_KEY. "
                        "Install dependencies and set the key to enable LLM-powered discovery."
                    )
                }, indent=2)
            )]

    if name == "suggest_agents_for_domain":
        agents = router.discovery.suggest_agents_for_domain(
            domain=arguments["domain"],
            num_agents=arguments.get("num_agents", 5)
        )
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "domain": arguments["domain"],
                "suggested_agents": agents,
                "note": "Review and customize these agents, then register them if appropriate"
            }, indent=2)
        )]

    if name == "improve_agent_description":
        improved = router.discovery.improve_description(
            current_description=arguments["current_description"],
            agent_id=arguments["agent_id"],
            context=arguments.get("context")
        )
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "agent_id": arguments["agent_id"],
                "original_description": arguments["current_description"],
                "improved_description": improved
            }, indent=2)
        )]

    if name == "analyze_agent_coverage":
        agent_ids = arguments.get("existing_agent_ids")
        if agent_ids:
            existing_agents = [
                {"id": aid, "description": router.agents[aid].description}
                for aid in agent_ids if aid in router.agents
            ]
        else:
            existing_agents = [
                {"id": a.id, "description": a.description}
                for a in router.agents.values()
            ]

        analysis = router.discovery.analyze_coverage(
            existing_agents=existing_agents,
            task_domain=arguments["task_domain"]
        )
        return [types.TextContent(
            type="text",
            text=json.dumps(analysis, indent=2)
        )]

    if name == "discover_agents_from_tools":
        agents = router.discovery.discover_from_tools_list(
            tools=arguments["tools"]
        )
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "discovered_agents": agents,
                "note": "Review these agent definitions and register if appropriate"
            }, indent=2)
        )]

    if name == "suggest_missing_agents":
        agent_ids = arguments.get("existing_agent_ids", [])
        existing_agents = [
            {"id": aid, "description": router.agents.get(aid, Agent(aid, "")).description}
            for aid in agent_ids if aid in router.agents
        ]

        suggestions = router.discovery.suggest_missing_agents(
            tasks=arguments["tasks"],
            existing_agents=existing_agents
        )
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "missing_agents": suggestions,
                "note": "These agents would help cover tasks not well handled by existing agents"
            }, indent=2)
        )]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="dytopo-router",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
