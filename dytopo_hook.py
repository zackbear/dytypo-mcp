#!/usr/bin/env python3
"""
DyTopo PreToolUse Hook for Claude Code

Intercepts every Task tool dispatch and injects a DyTopo routing plan
into the tool input so Claude spawns the right agents in the right order.

Claude Code hook protocol:
  - Input  : JSON from stdin  { "tool_name": "Task", "tool_input": { "prompt": "..." } }
  - Output : JSON to stdout   { "tool_input": { ... } }   <- modified input (continue)
              OR exit code 2  to block the tool call entirely

Routing plan is appended to the Task prompt so the spawned subagent
receives explicit guidance on which agent type to use and why.

Setup (in .claude/settings.json):
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

Environment variables (same as server.py):
  DYTOPO_EMBEDDER   = openai | anthropic | local   (auto-detected if unset)
  OPENAI_API_KEY    = sk-...
  ANTHROPIC_API_KEY = sk-ant-...
  DYTOPO_HOOK_K     = 3   (number of agents to select, default 3)
  DYTOPO_HOOK_GRAPH = knn | star | threshold   (default knn)
  DYTOPO_AGENTS_YAML = /path/to/agents.yaml   (default: same dir as this script)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Locate the repo and load .env ────────────────────────────────────────────
REPO_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_DIR / ".env")
except ImportError:
    pass

# ── Read hook input from stdin ────────────────────────────────────────────────
def read_input() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


# ── Build routing plan ────────────────────────────────────────────────────────
def build_routing_plan(task_prompt: str) -> dict | None:
    """
    Import the DyTopo router inline (avoids needing the MCP server running).
    Returns the routing plan dict, or None if routing fails.
    """
    try:
        sys.path.insert(0, str(REPO_DIR))
        from embedders import get_embedder
        import yaml
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        # Load agents
        agents_path = Path(os.getenv("DYTOPO_AGENTS_YAML", REPO_DIR / "agents.yaml"))
        if not agents_path.exists():
            return None

        with open(agents_path) as f:
            config = yaml.safe_load(f)

        if not config or "agents" not in config:
            return None

        embedder = get_embedder()

        # Embed task
        task_emb = embedder.embed(task_prompt)

        # Embed all agents (cached after first run)
        agent_scores = []
        for agent_cfg in config["agents"]:
            desc_emb = embedder.embed(agent_cfg["description"])
            score = float(
                cosine_similarity([task_emb], [desc_emb])[0][0]
            )
            agent_scores.append({
                "id": agent_cfg["id"],
                "description": agent_cfg["description"],
                "relevance_score": round(score, 4),
                "metadata": agent_cfg.get("metadata", {}),
            })

        k = int(os.getenv("DYTOPO_HOOK_K", "3"))
        agent_scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        selected = agent_scores[:k]

        return {
            "task": task_prompt[:120] + ("..." if len(task_prompt) > 120 else ""),
            "selected_agents": selected,
            "top_agent": selected[0]["id"] if selected else None,
        }

    except Exception as e:
        # Never crash Claude Code — silently degrade
        sys.stderr.write(f"[DyTopo hook] Error: {e}\n")
        return None


# ── Format plan as a prompt annotation ───────────────────────────────────────
def format_annotation(plan: dict) -> str:
    lines = [
        "\n\n---",
        "## DyTopo Routing Plan",
        f"Task: {plan['task']}",
        "",
        "Semantically selected agents (ranked by relevance):",
    ]
    for i, agent in enumerate(plan["selected_agents"], 1):
        lines.append(
            f"  {i}. {agent['id']} (score: {agent['relevance_score']}) "
            f"— {agent['description']}"
        )
    lines += [
        "",
        f"Recommended subagent_type: **{plan['top_agent']}**",
        "Use the execution order above to wire agent context passing.",
        "---",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    hook_data = read_input()

    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {})

    # Only act on Task tool calls
    if tool_name != "Task":
        # Pass through unchanged
        print(json.dumps({"tool_input": tool_input}))
        return

    prompt: str = tool_input.get("prompt", "")
    if not prompt:
        print(json.dumps({"tool_input": tool_input}))
        return

    plan = build_routing_plan(prompt)

    if plan:
        annotation = format_annotation(plan)
        tool_input = dict(tool_input)
        tool_input["prompt"] = prompt + annotation
        sys.stderr.write(
            f"[DyTopo hook] Routed to: {plan['top_agent']} "
            f"(score: {plan['selected_agents'][0]['relevance_score']})\n"
        )

    print(json.dumps({"tool_input": tool_input}))


if __name__ == "__main__":
    main()
