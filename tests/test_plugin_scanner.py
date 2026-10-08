import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plugin_scanner as ps


def make_skill(plugin_dir: Path, folder: str, frontmatter: str) -> None:
    d = plugin_dir / "skills" / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nBody.\n", encoding="utf-8")


def make_env(tmp_path: Path) -> tuple[Path, Path]:
    plugins = tmp_path / "plugins"
    on, off = tmp_path / "cache" / "superpowers", tmp_path / "cache" / "dev-browser"
    make_skill(on, "brainstorming", "name: brainstorming\ndescription: Explore intent before building.")
    make_skill(off, "dev-browser", "description: Disabled plugin skill.")
    plugins.mkdir()
    (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
        "superpowers@official": [{"scope": "user", "installPath": str(on)}],
        "dev-browser@market": [{"scope": "user", "installPath": str(off)}],
        "ghost@official": [{"scope": "user", "installPath": str(tmp_path / "missing")}],
    }}), encoding="utf-8")

    synced = plugins / "synced" / "org_user" / "abc123"
    (synced / ".claude-plugin").mkdir(parents=True)
    (synced / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "extract-alpha"}), encoding="utf-8")
    (synced.parent / "abc123.meta.json").write_text("{}", encoding="utf-8")
    make_skill(synced, "extract", "name: extract-alpha\ndescription: Remove image backgrounds.")

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"enabledPlugins": {
        "superpowers@official": True, "dev-browser@market": False, "ghost@official": True}}), encoding="utf-8")
    return plugins, settings


def by_id(agents):
    return {a["id"]: a for a in agents}


def test_scans_enabled_installed_and_synced_plugins(tmp_path):
    agents = by_id(ps.scan_plugin_skills(*make_env(tmp_path)))
    assert set(agents) == {"superpowers:brainstorming", "extract-alpha:extract-alpha"}
    assert agents["superpowers:brainstorming"]["description"] == "Explore intent before building."
    assert agents["superpowers:brainstorming"]["metadata"]["category"] == "skill"
    assert agents["extract-alpha:extract-alpha"]["metadata"]["plugin"] == "extract-alpha"


def test_skill_name_falls_back_to_folder(tmp_path):
    plugins, settings = make_env(tmp_path)
    make_skill(tmp_path / "cache" / "superpowers", "tdd", "description: Tests first.")
    assert "superpowers:tdd" in by_id(ps.scan_plugin_skills(plugins, settings))


def test_missing_files_return_empty(tmp_path):
    assert ps.scan_plugin_skills(tmp_path / "nope", tmp_path / "nope.json") == []


def test_corrupt_installed_json_still_scans_synced(tmp_path):
    plugins, settings = make_env(tmp_path)
    (plugins / "installed_plugins.json").write_text("{not json", encoding="utf-8")
    assert set(by_id(ps.scan_plugin_skills(plugins, settings))) == {"extract-alpha:extract-alpha"}
