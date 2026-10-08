"""
Jev router: ranks registry entries for a task with one TypeSafe System One call.

The whole registry goes to Jev as `choice` questions (the API caps a choice at
255 options, so a large registry is split across several questions in the same
request; they run in parallel server-side). Each question also offers NONE_FIT,
so a chunk with no good match puts its mass there instead of inflating weak
options, which keeps probabilities comparable across chunks.

Endpoint resolution matches jev-loop: TYPESAFE_API_KEY (direct, fastest), then
AI_GATEWAY_API_KEY (Vercel AI Gateway, one extra hop), else None. Keys come
from the caller's get_secret (the hook uses env, then Credential Manager).
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from typing import Callable

TYPESAFE_DIRECT_URL = "https://api.typesafe.ai/v1/systemone"
GATEWAY_URL = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
DIRECT_MODEL = "jev-latest"
GATEWAY_MODEL = "typesafe-ai/jev"

MAX_CHOICE_OPTIONS = 255
NONE_FIT = "none_fit"
NONE_FIT_DESCRIPTION = "None of the other options fit the task."
DESCRIPTION_CHARS = 150
INSTRUCTIONS = "Which tool or skill is the best fit for the `task`?"
ERROR_BODY_CHARS = 200

Endpoint = tuple[str, str, str]  # (url, model, api_key)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # The Authorization header must never follow a 3xx to another host.
    def redirect_request(self, *args, **kwargs):
        return None


_open = urllib.request.build_opener(_NoRedirect).open


class JevError(Exception):
    """Jev could not produce a ranking (network, HTTP, or malformed response)."""


def resolve_endpoint(get_secret: Callable[[str], str | None]) -> Endpoint | None:
    if key := get_secret("TYPESAFE_API_KEY"):
        return TYPESAFE_DIRECT_URL, DIRECT_MODEL, key
    if key := get_secret("AI_GATEWAY_API_KEY"):
        return GATEWAY_URL, GATEWAY_MODEL, key
    return None


def build_questions(agents: list[dict]) -> dict:
    per_question = MAX_CHOICE_OPTIONS - 1  # leave room for NONE_FIT
    n_questions = max(1, math.ceil(len(agents) / per_question))
    size = math.ceil(len(agents) / n_questions)  # even chunks
    questions = {}
    for i in range(n_questions):
        chunk = agents[i * size:(i + 1) * size]
        criteria = {a["id"]: a["description"][:DESCRIPTION_CHARS] for a in chunk}
        criteria[NONE_FIT] = NONE_FIT_DESCRIPTION
        questions[f"route_{i}"] = {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria}
    return questions


def rank_answers(answers: dict) -> list[tuple[str, float]]:
    merged = {}
    for qid, answer in answers.items():
        probs = answer.get("probabilities") if isinstance(answer, dict) else None
        if not isinstance(probs, dict):
            raise JevError(f"malformed answer for {qid}: no probabilities")
        merged.update({k: float(p) for k, p in probs.items() if k != NONE_FIT})
    return sorted(merged.items(), key=lambda kv: kv[1], reverse=True)


def route(task: str, agents: list[dict], endpoint: Endpoint, timeout: float) -> list[tuple[str, float]]:
    url, model, key = endpoint
    body = {"model": model, "state": {"task": task}, "questions": build_questions(agents)}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with _open(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise JevError(f"HTTP {e.code} from {url}: {e.read()[:ERROR_BODY_CHARS]!r}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise JevError(f"request to {url} failed: {e}") from None
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        raise JevError("malformed response: no 'answers' object")
    return rank_answers(answers)
