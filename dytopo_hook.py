#!/usr/bin/env python3
"""
DyTopo PreToolUse Hook for Claude Code

Intercepts every Agent (formerly Task) tool dispatch and injects a DyTopo routing plan
into the tool input so Claude spawns the right agents in the right order.

Claude Code hook protocol:
  - Input  : JSON from stdin  { "tool_name": "Task", "tool_input": { "prompt": "..." } }
  - Output : JSON to stdout   { "hookSpecificOutput": { "hookEventName": "PreToolUse",
                                "updatedInput": { ...full tool input... } } }
              OR nothing (exit 0) to leave the call unchanged

Routing plan is appended to the Task prompt so the spawned subagent
receives explicit guidance on which agent type to use and why.

Setup (in .claude/settings.json):
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Agent|Task",
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

Routing: Jev (TypeSafe System One, see jev_router.py) ranks the whole registry
in one ~0.3s call when a key is set. No key or any Jev failure -> the Agent call
passes through unchanged (embedding fallback dropped: sentence-transformers takes
~20s to import per hook process, OpenAI needs a paid key).

Environment variables (same as server.py):
  TYPESAFE_API_KEY  = Jev direct (preferred)   | AI_GATEWAY_API_KEY = Jev via Vercel
                      (env, else Windows Credential Manager: python secret_store.py set NAME)
  DYTOPO_JEV_TIMEOUT = 5  (seconds before giving up and passing the call through)
  DYTOPO_HOOK_K     = 3   (number of agents to select, default 3)
  DYTOPO_HOOK_GRAPH = knn | star | threshold   (default knn)
  DYTOPO_AGENTS_YAML = /path/to/agents.yaml   (default: same dir as this script)
"""

from __future__ import annotations

import json
import os
import re
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


# ── Intent rules ──────────────────────────────────────────────────────────────
# Rankers match a task's *topic* ("pytest") better than its *intent* ("remember").
# A matching rule pins its agent to the top of the selection; Jev's ranking fills the rest.
# ponytail: hand-kept regexes; move to a YAML file if the list grows past a handful.
INTENT_RULES: dict[str, re.Pattern] = {
    "mcp_muninn": re.compile(
        r"\b(remember|memori[sz]e|recall|don'?t forget|note that|"
        r"what did (we|i) (decide|agree|say)|my preference)\b", re.I),
    "mcp_mcp_docker": re.compile(
        r"\b(pull request|PR|open an? PR|merge the PR|github (issue|repo))\b", re.I),
    "superpowers:brainstorming": re.compile(
        r"\b(brainstorm\w*|ideas? (for|on|about)|come up with ideas|"
        r"design an? (new )?feature)\b", re.I),
    "mcp_public_browser": re.compile(
        r"\b(fill (out|in)|sign[- ]?up form|log ?in to|in the browser|web ?page|"
        r"navigate to|screenshot of)\b|https?://", re.I),
}


def select_agents(agent_scores: list[dict], task_prompt: str, k: int) -> list[dict]:
    """Pin rule-matched agents first (by score), then fill to k by similarity."""
    ranked = sorted(agent_scores, key=lambda a: a["relevance_score"], reverse=True)
    pinned = [dict(a, matched_rule=True) for a in ranked
              if a["id"] in INTENT_RULES and INTENT_RULES[a["id"]].search(task_prompt)]
    pinned_ids = {a["id"] for a in pinned}
    rest = [a for a in ranked if a["id"] not in pinned_ids]
    return (pinned + rest)[:max(k, len(pinned))]


# ── Build routing plan ────────────────────────────────────────────────────────
JEV_TIMEOUT_S = float(os.getenv("DYTOPO_JEV_TIMEOUT", "5"))


def load_agents() -> list[dict] | None:
    import yaml
    agents_path = Path(os.getenv("DYTOPO_AGENTS_YAML", REPO_DIR / "agents.yaml"))
    if not agents_path.exists():
        return None
    # libyaml's C loader parses the ~180KB registry ~10x faster (80ms vs 800ms),
    # which matters because the hook runs once per subagent dispatch.
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    with open(agents_path, encoding="utf-8") as f:
        config = yaml.load(f, Loader=loader)
    return config.get("agents") if config else None


def score_with_jev(task_prompt: str, agents: list[dict]) -> list[float] | None:
    """Jev probability per agent, or None (no key, or Jev failed -> skip routing)."""
    import jev_router
    import secret_store
    endpoint = jev_router.resolve_endpoint(lambda name: secret_store.lookup(name, os.environ))
    if not endpoint:
        return None
    try:
        probs = dict(jev_router.route(task_prompt, agents, endpoint, JEV_TIMEOUT_S))
    except jev_router.JevError as e:
        sys.stderr.write(f"[DyTopo hook] Jev failed, skipping routing: {e}\n")
        return None
    return [probs.get(a["id"], 0.0) for a in agents]


def build_routing_plan(task_prompt: str) -> dict | None:
    """Routing plan dict, or None if routing fails (never crash Claude Code)."""
    try:
        sys.path.insert(0, str(REPO_DIR))
        agents = load_agents()
        if not agents:
            return None

        scores = score_with_jev(task_prompt, agents)
        if scores is None:
            return None

        agent_scores = [{
            "id": a["id"],
            "description": a["description"],
            "relevance_score": round(float(s), 4),
            "metadata": a.get("metadata", {}),
        } for a, s in zip(agents, scores)]

        k = int(os.getenv("DYTOPO_HOOK_K", "3"))
        selected = select_agents(agent_scores, task_prompt, k)

        return {
            "task": task_prompt[:120] + ("..." if len(task_prompt) > 120 else ""),
            "router": "jev",
            "selected_agents": selected,
            "top_agent": selected[0]["id"] if selected else None,
        }

    except Exception as e:
        sys.stderr.write(f"[DyTopo hook] Error: {e}\n")
        return None


# ── Format plan as a prompt annotation ───────────────────────────────────────
# Registry ids that don't map to a tool name by snake_case -> PascalCase.
BUILTIN_TOOL_NAMES = {"task": "Agent"}


def how_to_use(agent: dict) -> str:
    """Tell the subagent how to invoke this registry entry."""
    meta = agent.get("metadata", {})
    if meta.get("category") == "skill":
        return f'Skill tool, skill="{agent["id"]}"'
    if meta.get("category") == "mcp" and meta.get("server_name"):
        return f"mcp__{meta['server_name']}__* tools"
    if meta.get("source") == "builtin":
        name = BUILTIN_TOOL_NAMES.get(agent["id"]) or "".join(p.title() for p in agent["id"].split("_"))
        return f"{name} tool"
    return agent["id"]


def format_annotation(plan: dict) -> str:
    # Appended to the subagent's prompt after its type is already chosen, so it
    # points at tools/skills to reach for, not at a subagent_type.
    lines = [
        "\n\n---",
        "## DyTopo routing hint",
        "Tools and skills most relevant to this task, best first:",
    ]
    for i, agent in enumerate(plan["selected_agents"], 1):
        why = "intent match" if agent.get("matched_rule") else \
            f"{plan.get('router', 'similarity')} {agent['relevance_score']}"
        lines.append(f"  {i}. {how_to_use(agent)} ({why}) — {agent['description']}")
    lines += [
        "",
        "Use them where they fit; ignore any that don't apply.",
        "---",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    hook_data = read_input()

    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {})

    # Only act on subagent dispatches ("Task" was renamed "Agent").
    # Printing nothing + exit 0 leaves the call untouched.
    prompt: str = tool_input.get("prompt", "")
    if tool_name not in ("Agent", "Task") or not prompt:
        return

    plan = build_routing_plan(prompt)
    if not plan:
        return

    sys.stderr.write(
        f"[DyTopo hook] Routed to: {plan['top_agent']} "
        f"(score: {plan['selected_agents'][0]['relevance_score']})\n"
    )
    # updatedInput replaces the whole input, so carry every field over.
    # No permissionDecision: the normal permission flow still applies.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": dict(tool_input, prompt=prompt + format_annotation(plan)),
    }}))


if __name__ == "__main__":
    main()
