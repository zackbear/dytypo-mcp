import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jev_router as j


def agents(n):
    return [{"id": f"a{i}", "description": f"desc {i} " + "x" * 300} for i in range(n)]


def test_questions_stay_under_choice_limit_and_cover_every_agent():
    qs = j.build_questions(agents(368))
    assert len(qs) == 2
    seen = []
    for q in qs.values():
        assert q["type"] == "choice"
        assert len(q["criteria"]) <= j.MAX_CHOICE_OPTIONS
        assert j.NONE_FIT in q["criteria"]
        seen += [k for k in q["criteria"] if k != j.NONE_FIT]
    assert sorted(seen) == sorted(a["id"] for a in agents(368))


def test_descriptions_are_truncated():
    q = j.build_questions(agents(3))["route_0"]
    assert all(len(d) <= j.DESCRIPTION_CHARS for d in q["criteria"].values())


def test_small_registry_is_one_question():
    assert list(j.build_questions(agents(10))) == ["route_0"]


def test_rank_merges_questions_and_drops_none_fit():
    answers = {
        "route_0": {"probabilities": {"a": 0.6, "b": 0.1, j.NONE_FIT: 0.3}},
        "route_1": {"probabilities": {"c": 0.05, j.NONE_FIT: 0.95}},
    }
    assert j.rank_answers(answers) == [("a", 0.6), ("b", 0.1), ("c", 0.05)]


def test_rank_rejects_malformed_answers():
    with pytest.raises(j.JevError):
        j.rank_answers({"route_0": {"choice": "a"}})


def env_only(env):
    return lambda name: env.get(name)


def test_endpoint_prefers_direct_key():
    url, model, key = j.resolve_endpoint(env_only({"TYPESAFE_API_KEY": "t", "AI_GATEWAY_API_KEY": "g"}))
    assert (url, model, key) == (j.TYPESAFE_DIRECT_URL, "jev-latest", "t")


def test_endpoint_falls_back_to_gateway_then_none():
    assert j.resolve_endpoint(env_only({"AI_GATEWAY_API_KEY": "g"})) == (j.GATEWAY_URL, "typesafe-ai/jev", "g")
    assert j.resolve_endpoint(env_only({})) is None


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def test_route_posts_and_ranks(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout):
        sent["auth"] = req.get_header("Authorization")
        sent["body"] = json.loads(req.data)
        return FakeResp(json.dumps({"answers": {"route_0": {
            "probabilities": {"a0": 0.2, "a1": 0.7, j.NONE_FIT: 0.1}}}}).encode())

    monkeypatch.setattr(j, "_open", fake_urlopen)
    ranked = j.route("fix my hook", agents(2), ("https://x.test", "jev-latest", "k"), timeout=1)
    assert ranked == [("a1", 0.7), ("a0", 0.2)]
    assert sent["auth"] == "Bearer k"
    assert sent["body"]["state"] == {"task": "fix my hook"} and sent["body"]["model"] == "jev-latest"


def test_route_wraps_http_errors_without_leaking_key(monkeypatch):
    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr(j, "_open", boom)
    with pytest.raises(j.JevError) as e:
        j.route("t", agents(1), ("https://x.test", "m", "secret-key"), timeout=1)
    assert "401" in str(e.value) and "secret-key" not in str(e.value)


def test_redirects_are_not_followed():
    assert j._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.test") is None
