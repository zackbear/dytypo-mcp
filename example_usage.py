#!/usr/bin/env python3
"""
Example usage of DyTopo MCP Server
Run with: python example_usage.py
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    """Demonstrate DyTopo routing."""
    
    # Start MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("=== DyTopo Example ===\n")
            
            # Register agents
            print("1. Registering agents...")
            
            agents = [
                ("web_search", "Searches current web content and news articles"),
                ("code_executor", "Executes Python code and returns output"),
                ("file_reader", "Reads and analyzes file contents"),
                ("database_query", "Queries SQL databases for data retrieval"),
                ("api_caller", "Makes HTTP requests to REST APIs"),
            ]
            
            for agent_id, description in agents:
                result = await session.call_tool(
                    "register_agent",
                    arguments={
                        "agent_id": agent_id,
                        "description": description
                    }
                )
                print(f"  ✓ {agent_id}")
            
            # Get routing plan
            print("\n2. Getting routing plan...")
            
            task = "Find the current price of Bitcoin and save it to a JSON file"
            
            result = await session.call_tool(
                "get_routing_plan",
                arguments={
                    "task": task,
                    "k": 3,
                    "graph_k": 2,
                    "graph_type": "knn"
                }
            )
            
            plan = json.loads(result.content[0].text)
            
            print(f"\nTask: {task}")
            print(f"\nSelected agents:")
            for agent in plan["selected_agents"]:
                print(f"  • {agent['id']} (relevance: {agent['relevance_score']:.2f})")
            
            print(f"\nTopology:")
            for agent_id, neighbors in plan["topology"].items():
                print(f"  {agent_id} → {neighbors}")
            
            print(f"\nExecution order:")
            for i, round_agents in enumerate(plan["execution_order"], 1):
                print(f"  Round {i}: {round_agents}")
            
            # Check similarity
            print("\n3. Checking agent similarities...")
            
            result = await session.call_tool(
                "compute_agent_similarity",
                arguments={
                    "agent_id_1": "web_search",
                    "agent_id_2": "api_caller"
                }
            )
            
            similarity = json.loads(result.content[0].text)
            print(f"  web_search ↔ api_caller: {similarity['similarity']:.2f}")
            
            # Task-agent similarity
            result = await session.call_tool(
                "compute_agent_similarity",
                arguments={
                    "task_text": "Search for recent news articles",
                    "agent_id_1": "web_search"
                }
            )
            
            similarity = json.loads(result.content[0].text)
            print(f"  'Search for news' → web_search: {similarity['similarity']:.2f}")
            
            print("\n=== Done ===")

if __name__ == "__main__":
    asyncio.run(main())
