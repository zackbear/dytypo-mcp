#!/usr/bin/env python3
"""
Example: LLM-Powered Agent Discovery

Demonstrates using Claude/GPT to automatically generate agent definitions.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    """Demonstrate LLM-powered agent discovery."""
    
    # Start MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("=== LLM-Powered Agent Discovery Demo ===\n")
            
            # Example 1: Suggest agents for a domain
            print("1. Suggesting agents for 'web scraping' domain...")
            
            result = await session.call_tool(
                "suggest_agents_for_domain",
                arguments={
                    "domain": "web scraping and data extraction",
                    "num_agents": 3
                }
            )
            
            suggestions = json.loads(result.content[0].text)
            print(f"\nSuggested {len(suggestions['suggested_agents'])} agents:")
            
            for agent in suggestions['suggested_agents']:
                print(f"\n  • {agent['id']}")
                print(f"    {agent['description'][:100]}...")
                
                # Register the agent
                await session.call_tool(
                    "register_agent",
                    arguments={
                        "agent_id": agent['id'],
                        "description": agent['description'],
                        "metadata": agent.get('metadata', {})
                    }
                )
            
            print("\n✓ Agents registered\n")
            
            # Example 2: Improve a description
            print("2. Improving an agent description...")
            
            result = await session.call_tool(
                "improve_agent_description",
                arguments={
                    "agent_id": "web_search",
                    "current_description": "Searches the web for stuff",
                    "context": "Used specifically for finding current cryptocurrency prices and news"
                }
            )
            
            improvement = json.loads(result.content[0].text)
            print(f"\nOriginal: {improvement['original_description']}")
            print(f"\nImproved: {improvement['improved_description']}")
            
            # Example 3: Analyze coverage
            print("\n\n3. Analyzing agent coverage...")
            
            result = await session.call_tool(
                "analyze_agent_coverage",
                arguments={
                    "task_domain": "complete web scraping pipeline with data storage"
                }
            )
            
            analysis = json.loads(result.content[0].text)
            print(f"\nCoverage Score: {analysis['coverage_score']}%")
            print(f"\nGaps identified:")
            for gap in analysis.get('gaps', []):
                print(f"  • {gap}")
            
            if analysis.get('suggested_agents'):
                print(f"\nSuggested new agents:")
                for suggestion in analysis['suggested_agents']:
                    print(f"  • {suggestion['id']}: {suggestion['reason']}")
            
            # Example 4: Discover from tool names
            print("\n\n4. Discovering agents from tool names...")
            
            result = await session.call_tool(
                "discover_agents_from_tools",
                arguments={
                    "tools": ["bash_tool", "str_replace", "view", "create_file"]
                }
            )
            
            discovered = json.loads(result.content[0].text)
            print(f"\nDiscovered {len(discovered['discovered_agents'])} agents:")
            for agent in discovered['discovered_agents']:
                print(f"\n  • {agent['id']}")
                print(f"    {agent['description'][:80]}...")
            
            # Example 5: Get routing plan using LLM-generated agents
            print("\n\n5. Testing routing with LLM-generated agents...")
            
            result = await session.call_tool(
                "get_routing_plan",
                arguments={
                    "task": "Scrape product data from e-commerce site and save to database",
                    "k": 3
                }
            )
            
            plan = json.loads(result.content[0].text)
            print(f"\nSelected agents for task:")
            for agent in plan['selected_agents']:
                print(f"  • {agent['id']} (relevance: {agent['relevance_score']:.2f})")
            
            print("\n=== Demo Complete ===")
            print("\nTakeaways:")
            print("• LLM generates detailed, semantically-rich agent descriptions")
            print("• Coverage analysis identifies gaps in your agent set")
            print("• Automatic improvement makes descriptions more specific")
            print("• Discovery works from just tool names")

if __name__ == "__main__":
    asyncio.run(main())