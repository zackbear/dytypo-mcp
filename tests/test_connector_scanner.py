import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import connector_scanner as c

SAMPLE = """Checking MCP server health...

github: https://api.githubcopilot.com/mcp/ (HTTP) - ✔ Connected
claude.ai Vercel: https://mcp.vercel.com - ✔ Connected
claude.ai Trading View MCP: https://mcp.tradingview.com/mcp - ✔ Connected
claude.ai Stripe: https://mcp.stripe.com - ! Needs authentication
claude.ai Broken: https://x.test - ✘ Failed to connect
"""


def test_parses_only_connected_claude_ai_connectors():
    agents = c.parse_connectors(SAMPLE)
    assert [a["id"] for a in agents] == ["mcp_claude_ai_vercel", "mcp_claude_ai_trading_view_mcp"]


def test_server_name_matches_claude_code_tool_prefix():
    vercel, tv = c.parse_connectors(SAMPLE)
    # Tools are named mcp__claude_ai_Vercel__*, mcp__claude_ai_Trading_View_MCP__*
    assert vercel["metadata"]["server_name"] == "claude_ai_Vercel"
    assert tv["metadata"]["server_name"] == "claude_ai_Trading_View_MCP"
    assert vercel["metadata"]["category"] == "mcp" and vercel["metadata"]["source"] == "claude.ai"
    assert vercel["metadata"]["url"] == "https://mcp.vercel.com"


def test_placeholder_description_names_the_connector():
    assert "Vercel" in c.parse_connectors(SAMPLE)[0]["description"]


def test_scan_returns_empty_when_cli_missing(monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError("claude")
    monkeypatch.setattr(c.subprocess, "run", boom)
    assert c.scan_claude_ai_connectors() == []
    assert "claude mcp list" in capsys.readouterr().err


def test_scan_returns_empty_on_timeout(monkeypatch, capsys):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    monkeypatch.setattr(c.subprocess, "run", slow)
    assert c.scan_claude_ai_connectors() == []


def test_scan_parses_cli_output(monkeypatch):
    monkeypatch.setattr(c.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=SAMPLE, stderr=""))
    assert len(c.scan_claude_ai_connectors()) == 2
