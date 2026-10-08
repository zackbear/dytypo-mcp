import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bootstrap_agents as b


def write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "muninn": {"command": "x"},
        "MCP_DOCKER": {"command": "docker", "env": {"SECRET_TOKEN": "hunter2"}},
    }}), encoding="utf-8")
    return cfg


def test_scan_mcp_servers_ids_and_no_secret_values(tmp_path):
    agents = b.scan_mcp_servers([write_config(tmp_path)])
    by_id = {a["id"]: a for a in agents}
    assert set(by_id) == {"mcp_muninn", "mcp_mcp_docker"}
    assert by_id["mcp_mcp_docker"]["description"].startswith("MCP server 'MCP_DOCKER'.")
    assert "hunter2" not in json.dumps(agents)


def test_apply_overrides_replaces_by_id_and_flags_it():
    agents = [{"id": "mcp_muninn", "description": "MCP server 'muninn'.", "metadata": {"category": "mcp"}},
              {"id": "2d-games", "description": "2D game principles.", "metadata": {"category": "skill"}}]
    out = b.apply_description_overrides(agents, {"2d-games": "Build 2D games: sprites, tilemaps."})
    assert out[1]["description"] == "Build 2D games: sprites, tilemaps."
    assert out[1]["metadata"]["description_override"] is True
    assert out[0]["description"] == "MCP server 'muninn'."
    assert agents[1]["description"] == "2D game principles."  # input not mutated


def test_apply_overrides_warns_on_unknown_ids_and_bare_mcp(capsys):
    agents = [{"id": "mcp_muninn", "description": "MCP server 'muninn'.", "metadata": {"category": "mcp"}}]
    b.apply_description_overrides(agents, {"uninstalled-skill": "x"})
    err = capsys.readouterr().err
    assert "uninstalled-skill" in err and "mcp_muninn" in err


def test_load_overrides_missing_file_returns_empty(tmp_path):
    assert b.load_description_overrides(tmp_path / "nope.yaml") == {}


def test_load_overrides_rejects_non_mapping(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("- just a list\n", encoding="utf-8")
    assert b.load_description_overrides(p) == {}


def test_load_overrides_reads_mapping(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("mcp_muninn: Stores memories.\n", encoding="utf-8")
    assert b.load_description_overrides(p) == {"mcp_muninn": "Stores memories."}
