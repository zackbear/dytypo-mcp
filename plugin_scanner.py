"""
Scan Claude Code plugin skills into DyTopo agent dicts.

Two sources under ~/.claude/plugins:
  1. installed_plugins.json — marketplace plugins; only those enabled in
     settings.json `enabledPlugins` are loaded by Claude Code, so only those count.
  2. synced/<org_user>/<id>/  — plugins synced from claude.ai (each has a
     sibling <id>.meta.json and a .claude-plugin/plugin.json naming it).

Agent ids are "<plugin>:<skill>" — the exact name the Skill tool accepts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bootstrap_agents import _extract_description, _extract_frontmatter

DEFAULT_PLUGINS_DIR = Path.home() / ".claude" / "plugins"
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"


def _read_json(path: Path) -> dict:
    """Return parsed JSON, or {} (with a logged reason) if missing or invalid."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[bootstrap] Could not read {path}: {e}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _installed_plugin_dirs(plugins_dir: Path, settings_path: Path) -> list[tuple[str, Path]]:
    enabled = _read_json(settings_path).get("enabledPlugins", {})
    installed = _read_json(plugins_dir / "installed_plugins.json").get("plugins", {})
    dirs = []
    for key, records in installed.items():
        if enabled.get(key) is not True or not records:
            continue
        path = Path(records[0].get("installPath", ""))
        if path.is_dir():
            dirs.append((key.split("@")[0], path))
    return dirs


def _synced_plugin_dirs(plugins_dir: Path) -> list[tuple[str, Path]]:
    dirs = []
    for manifest in sorted(plugins_dir.glob("synced/*/*/.claude-plugin/plugin.json")):
        plugin_dir = manifest.parent.parent
        name = _read_json(manifest).get("name")
        if name and (plugin_dir.parent / f"{plugin_dir.name}.meta.json").exists():
            dirs.append((str(name), plugin_dir))
    return dirs


def _skill_agent(plugin: str, skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    skill = str(_extract_frontmatter(text).get("name") or skill_md.parent.name)
    return {
        "id": f"{plugin}:{skill}",
        "description": _extract_description(skill_md),
        "metadata": {"category": "skill", "source": "plugin", "plugin": plugin,
                     "skill_path": str(skill_md)},
    }


def scan_plugin_skills(plugins_dir: Path = DEFAULT_PLUGINS_DIR,
                       settings_path: Path = DEFAULT_SETTINGS) -> list[dict]:
    """Return one agent per skill in every enabled installed or synced plugin."""
    agents: list[dict] = []
    for plugin, plugin_dir in _installed_plugin_dirs(plugins_dir, settings_path) + _synced_plugin_dirs(plugins_dir):
        for skill_md in sorted(plugin_dir.glob("skills/*/SKILL.md")):
            try:
                agents.append(_skill_agent(plugin, skill_md))
            except OSError as e:
                print(f"[bootstrap] Could not read {skill_md}: {e}", file=sys.stderr)
    if agents:
        print(f"[bootstrap] Plugin skills scanned: {len(agents)}", file=sys.stderr)
    return agents
