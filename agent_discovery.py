"""
LLM-Powered Agent Discovery and Description Generation

Uses Claude/GPT to:
1. Suggest agents for task domains
2. Generate optimal descriptions
3. Improve existing descriptions
4. Analyze coverage gaps
"""

import openai
import os
from typing import List, Dict, Optional
import json

class AgentDiscovery:
    """Uses LLM to discover and define agents."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def suggest_agents_for_domain(self, domain: str, num_agents: int = 5) -> List[Dict]:
        """
        Suggest agents for a given task domain.
        
        Args:
            domain: Description of the task domain (e.g., "web scraping", "code review")
            num_agents: Number of agents to suggest
        
        Returns:
            List of agent configs with id, description, metadata
        """
        prompt = f"""You are an expert in multi-agent system design. Suggest {num_agents} specialized agents for the following task domain:

Domain: {domain}

For each agent, provide:
1. A unique ID (lowercase with underscores)
2. A detailed description (2-3 sentences) that clearly defines:
   - What the agent does
   - Its specific expertise
   - When to use it
   - Key technologies/methods it uses
3. Metadata (category, keywords)

Follow these rules for descriptions:
- Be VERY specific (include technologies, methods, use cases)
- Use concrete examples
- Mention what makes this agent unique
- 50-150 words per description
- Focus on semantic differentiation from other agents

Return ONLY a JSON array, no other text:
[
  {{
    "id": "agent_id",
    "description": "Detailed description here...",
    "metadata": {{"category": "...", "keywords": ["...", "..."]}}
  }}
]"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        agents = json.loads(content)
        return agents
    
    def improve_description(self, current_description: str, agent_id: str, 
                          context: Optional[str] = None) -> str:
        """
        Improve an existing agent description for better semantic matching.
        
        Args:
            current_description: Current agent description
            agent_id: Agent identifier
            context: Optional context about the agent's role
        
        Returns:
            Improved description
        """
        prompt = f"""Improve this agent description for better semantic matching in a multi-agent routing system.

Agent ID: {agent_id}
Current Description: {current_description}
{f"Context: {context}" if context else ""}

Requirements:
1. Keep it concise but specific (50-150 words)
2. Include concrete technologies/methods
3. Add relevant use cases
4. Differentiate from similar agents
5. Use keywords that would match relevant tasks

Return ONLY the improved description, no explanation."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    def analyze_coverage(self, existing_agents: List[Dict], task_domain: str) -> Dict:
        """
        Analyze if existing agents cover a task domain well.
        
        Args:
            existing_agents: List of current agents with descriptions
            task_domain: Domain to analyze coverage for
        
        Returns:
            Analysis with gaps and suggestions
        """
        agents_summary = "\n".join([
            f"- {a['id']}: {a['description'][:100]}..."
            for a in existing_agents
        ])
        
        prompt = f"""Analyze whether these agents provide good coverage for the following task domain.

Task Domain: {task_domain}

Existing Agents:
{agents_summary}

Provide:
1. Coverage assessment (0-100%)
2. Coverage gaps (what's missing)
3. Suggested new agents to fill gaps
4. Agents that might be redundant

Return as JSON:
{{
  "coverage_score": 75,
  "gaps": ["gap1", "gap2"],
  "suggested_agents": [
    {{"id": "new_agent", "reason": "why needed"}}
  ],
  "redundant": ["agent_id"],
  "recommendations": ["recommendation1", "recommendation2"]
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    
    def generate_from_code(self, code_sample: str, language: str = "python") -> Dict:
        """
        Generate agent definition from code sample.
        
        Args:
            code_sample: Sample code showing what the agent does
            language: Programming language
        
        Returns:
            Agent config with id, description, metadata
        """
        prompt = f"""Analyze this {language} code and generate an agent definition.

Code:
```{language}
{code_sample}
```

Create an agent definition that describes what this code does. Include:
1. A unique ID based on the functionality
2. Detailed description (what it does, when to use it, technologies)
3. Relevant metadata

Return as JSON:
{{
  "id": "agent_id",
  "description": "Detailed description...",
  "metadata": {{"language": "{language}", "category": "..."}}
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    
    def discover_from_tools_list(self, tools: List[str]) -> List[Dict]:
        """
        Generate agent definitions from a list of tool names.
        
        Args:
            tools: List of tool names (e.g., ["web_search", "file_reader"])
        
        Returns:
            List of agent configs
        """
        tools_str = "\n".join([f"- {tool}" for tool in tools])
        
        prompt = f"""Generate agent definitions for these tools:

{tools_str}

For each tool, create a detailed description that:
1. Explains what it does
2. When to use it
3. What makes it unique
4. Key capabilities

Return as JSON array:
[
  {{
    "id": "tool_name",
    "description": "Detailed description...",
    "metadata": {{"category": "..."}}
  }}
]"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    
    def suggest_missing_agents(self, tasks: List[str], existing_agents: List[Dict]) -> List[Dict]:
        """
        Suggest agents needed to handle a list of tasks that existing agents can't.
        
        Args:
            tasks: List of task descriptions
            existing_agents: Current agent definitions
        
        Returns:
            Suggested new agents
        """
        tasks_str = "\n".join([f"- {task}" for task in tasks])
        agents_str = "\n".join([
            f"- {a['id']}: {a.get('description', 'No description')[:80]}..."
            for a in existing_agents
        ])
        
        prompt = f"""Given these tasks and existing agents, suggest new agents needed.

Tasks:
{tasks_str}

Existing Agents:
{agents_str}

For each task that existing agents can't handle well, suggest a new specialized agent.

Return as JSON:
[
  {{
    "id": "new_agent_id",
    "description": "What it does...",
    "fills_gap_for": ["task1", "task2"],
    "metadata": {{"category": "..."}}
  }}
]

If existing agents cover all tasks well, return empty array []."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)