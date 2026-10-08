#!/usr/bin/env python3
"""
DyTopo Bootstrap — Build agents.yaml from your real Claude Code environment.

Scans three sources:
  1. ~/.claude/skills/   — all installed SKILL.md files
  2. Built-in Claude Code tools (Bash, Read, Write, Edit, Glob, Grep, etc.)
  3. MCP server configs  (claude_desktop_config.json / .claude.json)
     and connected claude.ai connectors (`claude mcp list`)

Then optionally PRUNES the resulting registry:
  --prune     Remove duplicate/redundant skills by semantic similarity
  --threshold Cosine-similarity cut-off for "duplicate" (default 0.92)

Usage:
  python bootstrap_agents.py                  # run once, write agents.yaml
  python bootstrap_agents.py --prune          # run + prune duplicates
  python bootstrap_agents.py --prune --dry-run  # show what would be pruned

Scheduled / on-demand:
  --schedule EXPR   e.g. "weekly" | "daily" | "08:30" | "mon@09:00"
                    Requires 'schedule' package: pip install schedule
                    (NOT standard cron syntax — see --help for supported formats)
  Calling bootstrap_agents.py from a terminal (no --schedule) is on-demand.

Environment variables:
  DYTOPO_EMBEDDER      openai | anthropic | local  (auto-detected)
  OPENAI_API_KEY       needed if DYTOPO_EMBEDDER=openai
  ANTHROPIC_API_KEY    needed if DYTOPO_EMBEDDER=anthropic
  DYTOPO_AGENTS_YAML   output path (default: agents.yaml next to this script)
  DYTOPO_SKILLS_DIR    override ~/.claude/skills scan root
  DYTOPO_MCP_CONFIG    override MCP config file path
  DYTOPO_PRUNE_THRESHOLD  override --threshold default (0.92)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# ── Locate repo / load .env ───────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_DIR / ".env")
except ImportError:
    pass

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_AGENTS_YAML = Path(os.getenv("DYTOPO_AGENTS_YAML", REPO_DIR / "agents.yaml"))
DEFAULT_SKILLS_DIR = Path(os.getenv("DYTOPO_SKILLS_DIR", Path.home() / ".claude" / "skills"))
def _default_mcp_configs() -> list[Path]:
    """Return platform-appropriate Claude Desktop config paths."""
    home = Path.home()
    candidates: list[Path] = [home / ".claude.json"]  # cross-platform fallback

    _os = platform.system()
    if _os == "Windows":
        candidates.insert(0, home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json")
    elif _os == "Darwin":
        candidates.insert(0, home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    # Linux: Claude desktop not officially available; .claude.json is enough

    return candidates


DEFAULT_MCP_CONFIGS = _default_mcp_configs()
DEFAULT_PRUNE_THRESHOLD = float(os.getenv("DYTOPO_PRUNE_THRESHOLD", "0.92"))
DEFAULT_OVERRIDES = Path(os.getenv("DYTOPO_DESCRIPTION_OVERRIDES", REPO_DIR / "description_overrides.yaml"))


# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN CLAUDE CODE TOOLS
# Rich descriptions so they score well in semantic search.
# ─────────────────────────────────────────────────────────────────────────────

BUILTIN_TOOLS: list[dict] = [
    {
        "id": "bash",
        "description": (
            "Executes bash/shell commands, scripts, and system operations. "
            "Run CLI tools, install packages, manage processes, git operations, "
            "compile code, run tests, execute any terminal command."
        ),
        "metadata": {"category": "system", "source": "builtin", "cost": "low"},
    },
    {
        "id": "read",
        "description": (
            "Reads file contents from disk. Supports text files, source code, "
            "JSON, YAML, CSV, Markdown, configuration files, and any text-based format."
        ),
        "metadata": {"category": "files", "source": "builtin", "cost": "low"},
    },
    {
        "id": "write",
        "description": (
            "Creates and saves new files to disk. Writes text, JSON, YAML, CSV, "
            "source code, scripts, configurations, documentation, and any text content."
        ),
        "metadata": {"category": "files", "source": "builtin", "cost": "low"},
    },
    {
        "id": "edit",
        "description": (
            "Edits existing files by replacing specific text strings. "
            "Precise code modifications, config updates, refactoring, "
            "find-and-replace across a file."
        ),
        "metadata": {"category": "files", "source": "builtin", "cost": "low"},
    },
    {
        "id": "glob",
        "description": (
            "Finds files matching glob patterns like **/*.py or src/**/*.ts. "
            "File discovery, project structure exploration, listing files by extension."
        ),
        "metadata": {"category": "files", "source": "builtin", "cost": "low"},
    },
    {
        "id": "grep",
        "description": (
            "Searches file contents with regex patterns. Find function definitions, "
            "class names, imports, string literals, error messages anywhere in the codebase."
        ),
        "metadata": {"category": "files", "source": "builtin", "cost": "low"},
    },
    {
        "id": "web_search",
        "description": (
            "Searches the web for current information. News, documentation, prices, "
            "APIs, tutorials, recent events, package versions, and any live online content."
        ),
        "metadata": {"category": "research", "source": "builtin", "cost": "low"},
    },
    {
        "id": "web_fetch",
        "description": (
            "Fetches and reads full webpage content from a URL. "
            "Scrape articles, API docs, GitHub pages, download text content from the internet."
        ),
        "metadata": {"category": "research", "source": "builtin", "cost": "low"},
    },
    {
        "id": "task",
        "description": (
            "Spawns a specialized subagent to handle complex, multi-step tasks autonomously. "
            "Use for parallel workstreams, delegating research, code generation, "
            "exploration, or any subtask that benefits from an independent agent."
        ),
        "metadata": {"category": "orchestration", "source": "builtin", "cost": "medium"},
    },
    {
        "id": "todo_write",
        "description": (
            "Creates and manages a structured task list to track progress. "
            "Plan multi-step workflows, break down complex tasks, monitor completion status."
        ),
        "metadata": {"category": "planning", "source": "builtin", "cost": "low"},
    },
    {
        "id": "notebook_edit",
        "description": (
            "Edits Jupyter notebooks (.ipynb). Modify code cells, markdown cells, "
            "add or delete cells, update data science and ML notebooks."
        ),
        "metadata": {"category": "coding", "source": "builtin", "cost": "low"},
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# SKILL.md PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _extract_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter between --- delimiters."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def _extract_description(path: Path) -> str:
    """
    Pull the best description from a SKILL.md:
      1. frontmatter `description` field (preferred — most skills have this)
      2. First non-empty paragraph after the frontmatter
      3. Fallback: skill folder name
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = _extract_frontmatter(text)

    if fm.get("description"):
        desc = str(fm["description"]).strip()
        # Truncate very long frontmatter descriptions at a sentence boundary
        if len(desc) > 300:
            truncated = desc[:300]
            last_period = truncated.rfind(".")
            desc = (truncated[: last_period + 1] if last_period > 100 else truncated).strip()
        return desc

    # Strip frontmatter block
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL).strip()
    # Skip headings, grab first real paragraph
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("**") and len(line) > 20:
            return line[:280]

    return path.parent.name.replace("-", " ").title()


def scan_skills(skills_dir: Path) -> list[dict]:
    """Scan ~/.claude/skills/ and return agent dicts for each SKILL.md found."""
    if not skills_dir.exists():
        print(f"[bootstrap] Skills dir not found: {skills_dir}", file=sys.stderr)
        return []

    agents: list[dict] = []
    skill_mds = sorted(skills_dir.rglob("SKILL.md"))

    for skill_md in skill_mds:
        folder = skill_md.parent
        # Use folder name as ID; strip plugin namespace prefixes (e.g. compound-engineering/)
        raw_name = folder.name
        agent_id = re.sub(r"[^\w-]", "_", raw_name.lower())

        try:
            description = _extract_description(skill_md)
        except Exception as e:
            print(f"[bootstrap] Warning: could not parse {skill_md}: {e}", file=sys.stderr)
            description = raw_name.replace("-", " ").title()

        # Read frontmatter for source/category hints
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            fm = _extract_frontmatter(text)
            source = str(fm.get("source", "skill")).split()[0]
        except Exception:
            source = "skill"

        agents.append({
            "id": agent_id,
            "description": description,
            "metadata": {
                "category": "skill",
                "source": source,
                "skill_path": str(skill_md),
            },
        })

    print(f"[bootstrap] Skills scanned: {len(agents)}", file=sys.stderr)
    return agents


# ─────────────────────────────────────────────────────────────────────────────
# MCP CONFIG SCANNER
# ─────────────────────────────────────────────────────────────────────────────

def load_description_overrides(path: Path) -> dict[str, str]:
    """Load hand-written {agent_id: description} overrides; {} if absent or invalid."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[bootstrap] Could not read {path}: {e}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"[bootstrap] {path} must be a mapping of agent id -> description; ignoring.", file=sys.stderr)
        return {}
    return {str(k): str(v).strip() for k, v in data.items() if v}


def apply_description_overrides(agents: list[dict], overrides: dict[str, str]) -> list[dict]:
    """Swap in hand-written descriptions by agent id (without editing SKILL.md files).

    MCP configs carry no semantic info, so an MCP server without an override is
    registered as a placeholder that routing can only match by name — warn about it.
    """
    ids = {a["id"] for a in agents}
    for stale in sorted(set(overrides) - ids):
        print(f"[bootstrap] Override for unknown agent '{stale}' (uninstalled?) — ignoring.", file=sys.stderr)
    out = []
    for a in agents:
        if a["id"] in overrides:
            a = dict(a, description=overrides[a["id"]],
                     metadata=dict(a.get("metadata") or {}, description_override=True))
        elif (a.get("metadata") or {}).get("category") == "mcp":
            print(f"[bootstrap] No description for '{a['id']}' — add one to {DEFAULT_OVERRIDES.name}", file=sys.stderr)
        out.append(a)
    return out


def scan_mcp_servers(config_paths: list[Path]) -> list[dict]:
    """Parse MCP config files and return one agent per registered server."""
    agents: list[dict] = []
    seen: set[str] = set()

    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[bootstrap] Could not read {config_path}: {e}", file=sys.stderr)
            continue

        servers: dict = data.get("mcpServers", {})
        for name, cfg in servers.items():
            agent_id = "mcp_" + re.sub(r"\W", "_", name.lower())
            if agent_id in seen:
                continue
            seen.add(agent_id)

            # Build a safe description — only include the server name and env key
            # names (not values). Exclude args because they may contain file paths
            # or inline credentials.
            env_keys = list(cfg.get("env", {}).keys())
            desc_parts = [f"MCP server '{name}'."]
            if env_keys:
                # Key names only — never values
                desc_parts.append(f"Config: {', '.join(env_keys[:6])}.")

            agents.append({
                "id": agent_id,
                "description": " ".join(desc_parts),
                "metadata": {
                    "category": "mcp",
                    "source": str(config_path.name),
                    "server_name": name,
                },
            })

    if agents:
        print(f"[bootstrap] MCP servers found: {len(agents)}", file=sys.stderr)
    return agents


# ─────────────────────────────────────────────────────────────────────────────
# DEDUPLICATION — resolve same skill installed multiple times
# (same folder name at different paths → keep first, drop rest)
# ─────────────────────────────────────────────────────────────────────────────

def dedup_by_id(agents: list[dict]) -> list[dict]:
    """Keep the first occurrence of each agent ID."""
    seen: set[str] = set()
    out: list[dict] = []
    for a in agents:
        if a["id"] not in seen:
            seen.add(a["id"])
            out.append(a)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# SEMANTIC PRUNER
# ─────────────────────────────────────────────────────────────────────────────

def prune_by_similarity(
    agents: list[dict],
    threshold: float = DEFAULT_PRUNE_THRESHOLD,
    dry_run: bool = False,
) -> list[dict]:
    """
    Cluster agents by cosine similarity of their descriptions.
    When two agents exceed `threshold`, keep the one with the longer/richer
    description and flag the other as redundant.

    Returns the pruned list. Prints a report of what was removed.
    """
    try:
        import numpy as np
    except ImportError:
        print("[bootstrap] numpy not installed — skipping semantic prune.", file=sys.stderr)
        return agents

    sys.path.insert(0, str(REPO_DIR))
    from embedders import get_embedder

    print(f"\n[bootstrap] Computing embeddings for {len(agents)} agents…", file=sys.stderr)
    embedder = get_embedder()

    descs = [a["description"] for a in agents]
    vecs: list[Any] = []
    for i, d in enumerate(descs):
        vecs.append(embedder.embed(d, _save=False))  # batch; flush once at end
        if (i + 1) % 50 == 0:
            print(f"[bootstrap]   embedded {i + 1}/{len(descs)}", file=sys.stderr)
    embedder.flush()  # single atomic write instead of N writes

    matrix = np.vstack(vecs)  # shape (N, dim)
    unit = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12, None)
    sim_matrix = unit @ unit.T  # (N, N) cosine similarity

    removed: set[int] = set()
    clusters: list[tuple[int, int, float]] = []  # (keeper_idx, removed_idx, score)

    n = len(agents)
    for i in range(n):
        if i in removed:
            continue
        for j in range(i + 1, n):
            if j in removed:
                continue
            score = float(sim_matrix[i, j])
            if score >= threshold:
                # Keep the one with the longer description (richer)
                len_i = len(agents[i]["description"])
                len_j = len(agents[j]["description"])
                keeper, loser = (i, j) if len_i >= len_j else (j, i)
                removed.add(loser)
                clusters.append((keeper, loser, score))

    # Report
    print(f"\n[bootstrap] Pruning report (threshold={threshold}):", file=sys.stderr)
    if not clusters:
        print("  No duplicates found.", file=sys.stderr)
    else:
        for keeper_idx, loser_idx, score in sorted(clusters, key=lambda x: -x[2]):
            action = "would remove" if dry_run else "removing"
            print(
                f"  {action}: '{agents[loser_idx]['id']}' "
                f"(sim={score:.3f} with '{agents[keeper_idx]['id']}')",
                file=sys.stderr,
            )

    print(
        f"\n[bootstrap] {len(removed)} agents {'would be' if dry_run else ''} pruned "
        f"({n - len(removed)} remain).",
        file=sys.stderr,
    )

    if dry_run:
        return agents  # no changes

    return [a for i, a in enumerate(agents) if i not in removed]


# ─────────────────────────────────────────────────────────────────────────────
# YAML WRITER
# ─────────────────────────────────────────────────────────────────────────────

def write_agents_yaml(agents: list[dict], output_path: Path) -> None:
    """Write a clean agents.yaml file."""
    import datetime

    # Use a local Dumper subclass so we don't mutate the global yaml.Dumper state.
    class _Dumper(yaml.Dumper):
        pass

    def _str_presenter(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
        if "\n" in data or len(data) > 80:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    _Dumper.add_representer(str, _str_presenter)

    doc = {
        "agents": [
            {k: v for k, v in agent.items() if k != "metadata" or v}
            for agent in agents
        ]
    }

    header = (
        "# DyTopo Agent Registry — auto-generated by bootstrap_agents.py\n"
        f"# Generated: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
        f"# Total agents: {len(agents)}\n"
        "#\n"
        "# Sources:\n"
        "#   - Built-in Claude Code tools\n"
        "#   - ~/.claude/skills/  (SKILL.md files)\n"
        "#   - MCP server configs and claude.ai connectors\n"
        "#\n"
        "# Re-run:  python bootstrap_agents.py\n"
        "# Prune:   python bootstrap_agents.py --prune\n\n"
    )

    yaml_body = yaml.dump(doc, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=120)
    output_path.write_text(header + yaml_body, encoding="utf-8")
    print(f"\n[bootstrap] Written: {output_path}  ({len(agents)} agents)", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# CORE RUN FUNCTION — callable programmatically or on schedule
# ─────────────────────────────────────────────────────────────────────────────

def run(
    output_path: Path = DEFAULT_AGENTS_YAML,
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    mcp_config_paths: list[Path] | None = None,
    prune: bool = False,
    prune_threshold: float = DEFAULT_PRUNE_THRESHOLD,
    dry_run: bool = False,
    include_builtins: bool = True,
    include_skills: bool = True,
    include_mcp: bool = True,
) -> list[dict]:
    """
    Bootstrap agents.yaml from all real Claude Code sources.

    Returns the final list of agents (for programmatic use).
    """
    if mcp_config_paths is None:
        mcp_config_paths = DEFAULT_MCP_CONFIGS

    print("\n[bootstrap] Starting DyTopo agent bootstrap…", file=sys.stderr)

    all_agents: list[dict] = []

    # 1. Built-in tools (always first so they get priority in dedup)
    if include_builtins:
        all_agents.extend(BUILTIN_TOOLS)
        print(f"[bootstrap] Built-in tools loaded: {len(BUILTIN_TOOLS)}", file=sys.stderr)

    # 2. Installed skills, then plugin skills (ids are "plugin:skill", so no clashes)
    if include_skills:
        from plugin_scanner import scan_plugin_skills  # local: plugin_scanner imports this module
        all_agents.extend(scan_skills(skills_dir))
        all_agents.extend(scan_plugin_skills())

    # 3. MCP servers: local configs, then claude.ai connectors (not in any local config)
    if include_mcp:
        from connector_scanner import scan_claude_ai_connectors
        all_agents.extend(scan_mcp_servers(mcp_config_paths))
        all_agents.extend(scan_claude_ai_connectors())

    # Deduplicate by ID (same skill installed in multiple locations)
    before_dedup = len(all_agents)
    all_agents = dedup_by_id(all_agents)
    if before_dedup != len(all_agents):
        print(
            f"[bootstrap] Deduped by ID: {before_dedup} -> {len(all_agents)}",
            file=sys.stderr,
        )
    all_agents = apply_description_overrides(all_agents, load_description_overrides(DEFAULT_OVERRIDES))

    # Semantic prune
    if prune:
        all_agents = prune_by_similarity(all_agents, prune_threshold, dry_run)

    # Write output (unless dry-run AND prune: still write if not pruning)
    if not (dry_run and prune):
        write_agents_yaml(all_agents, output_path)
    else:
        print(
            "[bootstrap] Dry run — agents.yaml NOT written.",
            file=sys.stderr,
        )

    return all_agents


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

def run_on_schedule(cron_expr: str, run_kwargs: dict) -> None:
    """
    Run bootstrap on a cron-like schedule using the `schedule` library.
    Supports common patterns: "daily", "weekly", or "HH:MM" (daily at time).
    For full cron support install `cronsim` or use a system cron instead.
    """
    try:
        import schedule
    except ImportError:
        print(
            "[bootstrap] ERROR: 'schedule' package not installed.\n"
            "  Install with: pip install schedule\n"
            "  Or use a system cron job to call:  python bootstrap_agents.py",
            file=sys.stderr,
        )
        sys.exit(1)

    def _job() -> None:
        print(f"\n[bootstrap] Scheduled run triggered at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        run(**run_kwargs)

    # Parse simple schedule expressions
    expr = cron_expr.strip().lower()
    if expr == "daily":
        schedule.every().day.at("09:00").do(_job)
        print("[bootstrap] Scheduled: daily at 09:00", file=sys.stderr)
    elif expr == "weekly":
        schedule.every().monday.at("09:00").do(_job)
        print("[bootstrap] Scheduled: every Monday at 09:00", file=sys.stderr)
    elif re.match(r"^\d{1,2}:\d{2}$", expr):
        schedule.every().day.at(expr).do(_job)
        print(f"[bootstrap] Scheduled: daily at {expr}", file=sys.stderr)
    elif re.match(r"^(mon|tue|wed|thu|fri|sat|sun)@\d{1,2}:\d{2}$", expr):
        day, t = expr.split("@")
        day_map = {
            "mon": schedule.every().monday,
            "tue": schedule.every().tuesday,
            "wed": schedule.every().wednesday,
            "thu": schedule.every().thursday,
            "fri": schedule.every().friday,
            "sat": schedule.every().saturday,
            "sun": schedule.every().sunday,
        }
        day_map[day].at(t).do(_job)
        print(f"[bootstrap] Scheduled: every {day} at {t}", file=sys.stderr)
    else:
        print(
            f"[bootstrap] ERROR: Unrecognised schedule '{cron_expr}'.\n"
            "  Supported formats:\n"
            "    daily         — every day at 09:00\n"
            "    weekly        — every Monday at 09:00\n"
            "    HH:MM         — daily at specific time (e.g. 08:30)\n"
            "    DAY@HH:MM     — weekly (e.g. mon@08:30, fri@17:00)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Run once immediately on startup, then loop
    _job()
    print("[bootstrap] Scheduler running. Ctrl-C to stop.", file=sys.stderr)
    while True:
        schedule.run_pending()
        time.sleep(30)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build agents.yaml from your real Claude Code environment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bootstrap_agents.py
  python bootstrap_agents.py --prune
  python bootstrap_agents.py --prune --threshold 0.90 --dry-run
  python bootstrap_agents.py --schedule daily
  python bootstrap_agents.py --schedule mon@08:30
  python bootstrap_agents.py --no-skills --no-mcp   # built-ins only
""",
    )
    p.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_AGENTS_YAML,
        metavar="PATH",
        help=f"Output agents.yaml path (default: {DEFAULT_AGENTS_YAML})",
    )
    p.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        metavar="DIR",
        help=f"Root of skills directory (default: {DEFAULT_SKILLS_DIR})",
    )
    p.add_argument(
        "--prune",
        action="store_true",
        help="Remove semantically duplicate/redundant skills",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_PRUNE_THRESHOLD,
        metavar="FLOAT",
        help=f"Cosine similarity threshold for pruning (default: {DEFAULT_PRUNE_THRESHOLD})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pruned without writing output",
    )
    p.add_argument(
        "--schedule",
        metavar="EXPR",
        help="Run on a schedule: daily | weekly | HH:MM | DAY@HH:MM",
    )
    p.add_argument("--no-builtins", action="store_true", help="Skip built-in Claude Code tools")
    p.add_argument("--no-skills", action="store_true", help="Skip ~/.claude/skills/ scan")
    p.add_argument("--no-mcp", action="store_true", help="Skip MCP server config scan")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    run_kwargs: dict = {
        "output_path": args.output,
        "skills_dir": args.skills_dir,
        "prune": args.prune,
        "prune_threshold": args.threshold,
        "dry_run": args.dry_run,
        "include_builtins": not args.no_builtins,
        "include_skills": not args.no_skills,
        "include_mcp": not args.no_mcp,
    }

    if args.schedule:
        run_on_schedule(args.schedule, run_kwargs)
    else:
        run(**run_kwargs)


if __name__ == "__main__":
    main()
