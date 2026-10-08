"""
Scan claude.ai connectors (Vercel, Supabase, Context7, ...) into DyTopo agent dicts.

Connectors live in your claude.ai account, not in any local MCP config file, so
the config scanner never sees them. `claude mcp list` does, one per line:

    claude.ai Vercel: https://mcp.vercel.com - ✔ Connected

Only connected ones are registered: a connector that needs authentication has
no usable tools. Claude Code names their tools mcp__claude_ai_<Name>__*, with
non-word characters in <Name> replaced by "_".

Connector configs carry no description; add one per id to
description_overrides.yaml (bootstrap warns about any that lack one).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

CONNECTOR_LINE = re.compile(r"^claude\.ai (?P<name>.+?): (?P<url>\S+) - (?P<status>.+)$")
CONNECTED = "Connected"
LIST_TIMEOUT_S = 180  # `claude mcp list` health-checks every server


def _connector_agent(name: str, url: str) -> dict:
    slug = re.sub(r"\W", "_", name)
    return {
        "id": "mcp_claude_ai_" + slug.lower(),
        "description": f"claude.ai connector: {name} ({url}).",
        "metadata": {"category": "mcp", "source": "claude.ai",
                     "server_name": "claude_ai_" + slug, "url": url},
    }


def parse_connectors(output: str) -> list[dict]:
    agents = []
    for line in output.splitlines():
        m = CONNECTOR_LINE.match(line.strip())
        if m and m["status"].strip().endswith(CONNECTED) and "✘" not in m["status"]:
            agents.append(_connector_agent(m["name"].strip(), m["url"]))
    return agents


def scan_claude_ai_connectors() -> list[dict]:
    """Connected claude.ai connectors, or [] (with the reason on stderr)."""
    claude = shutil.which("claude") or "claude"  # resolves claude.cmd on Windows
    try:
        out = subprocess.run([claude, "mcp", "list"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=LIST_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[bootstrap] Skipping claude.ai connectors: `claude mcp list` failed: {e}", file=sys.stderr)
        return []
    agents = parse_connectors(out.stdout)
    print(f"[bootstrap] claude.ai connectors (connected): {len(agents)}", file=sys.stderr)
    return agents
