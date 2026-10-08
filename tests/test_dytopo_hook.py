import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dytopo_hook as h


def scored(*pairs):
    return [{"id": i, "description": i, "relevance_score": s, "metadata": {}} for i, s in pairs]


SCORES = scored(("python-testing-patterns", 0.50), ("uv-package-manager", 0.36),
                ("temporal-python-testing", 0.44), ("mcp_muninn", 0.15),
                ("mcp_mcp_docker", 0.31), ("mcp_public_browser", 0.23))


def ids(sel):
    return [a["id"] for a in sel]


def test_no_rule_match_is_pure_similarity_order():
    assert ids(h.select_agents(SCORES, "write tests for the parser", 3)) == [
        "python-testing-patterns", "temporal-python-testing", "uv-package-manager"]


def test_remember_pins_muninn_first_and_keeps_k():
    sel = h.select_agents(SCORES, "Remember that I prefer pytest over unittest", 3)
    assert ids(sel) == ["mcp_muninn", "python-testing-patterns", "temporal-python-testing"]
    assert sel[0]["matched_rule"]


def test_open_pr_pins_docker():
    assert ids(h.select_agents(SCORES, "open a PR on my repo with these changes", 3))[0] == "mcp_mcp_docker"


def test_form_fill_pins_browser():
    assert ids(h.select_agents(SCORES, "fill out the signup form on example.com", 3))[0] == "mcp_public_browser"


def test_rule_for_unregistered_agent_is_ignored():
    only_skills = [a for a in SCORES if not a["id"].startswith("mcp_")]
    assert ids(h.select_agents(only_skills, "remember this", 2)) == [
        "python-testing-patterns", "temporal-python-testing"]


def test_word_boundaries_avoid_false_positives():
    # "approximate" contains "pr", "remembering" is fine to match, "prefix" must not hit PR rule
    assert "mcp_mcp_docker" not in ids(h.select_agents(SCORES, "approximate the prefix sums", 1))


def run_main(monkeypatch, capsys, payload):
    import io, json
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    return capsys.readouterr().out


def test_non_agent_tool_emits_nothing(monkeypatch, capsys):
    assert run_main(monkeypatch, capsys, {"tool_name": "Read", "tool_input": {"x": 1}}) == ""


def test_agent_call_emits_updated_input(monkeypatch, capsys):
    import json
    monkeypatch.setattr(h, "build_routing_plan", lambda p: {
        "task": p, "top_agent": "mcp_muninn",
        "selected_agents": [{"id": "mcp_muninn", "description": "d", "relevance_score": 0.2}]})
    out = json.loads(run_main(monkeypatch, capsys, {"tool_name": "Agent", "tool_input": {"description": "d", "prompt": "remember x"}}))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse" and "permissionDecision" not in hso
    assert hso["updatedInput"]["description"] == "d"
    assert hso["updatedInput"]["prompt"].startswith("remember x") and "mcp_muninn" in hso["updatedInput"]["prompt"]


def test_build_routing_plan_reads_utf8_registry(tmp_path, monkeypatch):
    p = tmp_path / "agents.yaml"
    # ō = C5 8D in UTF-8; 0x8D is undefined in cp1252 (Windows' default)
    p.write_text("agents:\n- id: a\n  description: Tōkyō café\n", encoding="utf-8")
    monkeypatch.setenv("DYTOPO_AGENTS_YAML", str(p))
    import jev_router
    monkeypatch.setattr(jev_router, "resolve_endpoint", lambda get: ("u", "m", "k"))
    monkeypatch.setattr(jev_router, "route", lambda task, agents, ep, timeout: [("a", 0.9)])
    assert h.build_routing_plan("anything")["top_agent"] == "a"


def write_registry(tmp_path, monkeypatch):
    p = tmp_path / "agents.yaml"
    p.write_text("agents:\n- id: a\n  description: A\n- id: b\n  description: B\n", encoding="utf-8")
    monkeypatch.setenv("DYTOPO_AGENTS_YAML", str(p))


def test_routing_plan_uses_jev_when_key_present(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch)
    import jev_router
    monkeypatch.setattr(jev_router, "resolve_endpoint", lambda env: ("u", "m", "k"))
    monkeypatch.setattr(jev_router, "route", lambda task, agents, ep, timeout: [("b", 0.8), ("a", 0.1)])
    plan = h.build_routing_plan("anything")
    assert plan["router"] == "jev" and plan["top_agent"] == "b"
    assert plan["selected_agents"][0]["relevance_score"] == 0.8


def test_routing_plan_is_skipped_when_jev_fails(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch)
    import jev_router

    def fail(*a, **k):
        raise jev_router.JevError("HTTP 529")

    monkeypatch.setattr(jev_router, "resolve_endpoint", lambda get: ("u", "m", "k"))
    monkeypatch.setattr(jev_router, "route", fail)
    assert h.build_routing_plan("anything") is None


def test_routing_plan_is_skipped_without_a_key(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch)
    import jev_router
    monkeypatch.setattr(jev_router, "resolve_endpoint", lambda get: None)
    assert h.build_routing_plan("anything") is None


def test_annotation_names_the_router():
    plan = {"task": "t", "top_agent": "x", "router": "jev", "selected_agents": [
        {"id": "x", "description": "X.", "relevance_score": 0.8, "metadata": {}}]}
    assert "jev 0.8" in h.format_annotation(plan)


def test_how_to_use_by_kind():
    assert h.how_to_use({"id": "tdd", "metadata": {"category": "skill"}}) == 'Skill tool, skill="tdd"'
    assert h.how_to_use({"id": "mcp_muninn", "metadata": {"category": "mcp", "server_name": "muninn"}}) == "mcp__muninn__* tools"
    assert h.how_to_use({"id": "bash", "metadata": {"source": "builtin"}}) == "Bash tool"
    assert h.how_to_use({"id": "web_search", "metadata": {"source": "builtin"}}) == "WebSearch tool"
    assert h.how_to_use({"id": "task", "metadata": {"source": "builtin"}}) == "Agent tool"
    assert h.how_to_use({"id": "odd", "metadata": {}}) == "odd"


def test_annotation_is_a_tool_hint_not_a_subagent_type():
    plan = {"task": "t", "top_agent": "mcp_muninn", "selected_agents": [
        {"id": "mcp_muninn", "description": "Memory DB.", "relevance_score": 0.14, "matched_rule": True,
         "metadata": {"category": "mcp", "server_name": "muninn"}},
        {"id": "tdd", "description": "Tests.", "relevance_score": 0.5, "metadata": {"category": "skill"}}]}
    text = h.format_annotation(plan)
    assert "subagent_type" not in text and "execution order" not in text
    assert "mcp__muninn__* tools" in text and 'Skill tool, skill="tdd"' in text
    assert "intent match" in text and "0.14" not in text


BRAINSTORM_SCORES = scored(("zapier:zapier-onboard", 0.52), ("productivity:start", 0.42),
                           ("superpowers:brainstorming", 0.34))


def test_brainstorm_intent_pins_brainstorming():
    for prompt in ("brainstorm a new onboarding feature", "Brainstorming session on pricing",
                   "give me ideas for the onboarding flow", "help me design a new feature for exports"):
        assert ids(h.select_agents(BRAINSTORM_SCORES, prompt, 2))[0] == "superpowers:brainstorming", prompt


def test_implementation_task_does_not_pin_brainstorming():
    assert ids(h.select_agents(BRAINSTORM_SCORES, "implement the onboarding feature per the spec", 2))[0] == "zapier:zapier-onboard"


def test_load_agents_uses_libyaml_when_available(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch)
    import yaml
    used = []
    real = yaml.load
    monkeypatch.setattr(yaml, "load", lambda stream, Loader: used.append(Loader) or real(stream, Loader=Loader))
    assert [a["id"] for a in h.load_agents()] == ["a", "b"]
    assert used == [yaml.CSafeLoader]


def test_load_agents_falls_back_without_libyaml(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch)
    import yaml
    monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    assert [a["id"] for a in h.load_agents()] == ["a", "b"]
