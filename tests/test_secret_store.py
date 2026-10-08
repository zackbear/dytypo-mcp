import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import secret_store as s


class FakeWinError(Exception):
    def __init__(self, winerror):
        self.winerror = winerror


def fake_win32cred(store):
    def cred_read(target, kind):
        if target not in store:
            raise FakeWinError(s.ERROR_NOT_FOUND)
        return {"CredentialBlob": store[target].encode("utf-16-le")}

    def cred_write(cred, flags):
        store[cred["TargetName"]] = cred["CredentialBlob"]

    return types.SimpleNamespace(CredRead=cred_read, CredWrite=cred_write,
                                 CRED_TYPE_GENERIC=1, CRED_PERSIST_LOCAL_MACHINE=2)


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(s, "_backend", lambda: (fake_win32cred(data), FakeWinError))
    return data


def test_round_trip(store):
    s.write_secret("TYPESAFE_API_KEY", "abc")
    assert store == {"dytopo/TYPESAFE_API_KEY": "abc"}
    assert s.read_secret("TYPESAFE_API_KEY") == "abc"


def test_missing_secret_is_none(store):
    assert s.read_secret("NOPE") is None


def test_other_errors_are_logged_not_raised(monkeypatch, capsys):
    def boom(target, kind):
        raise FakeWinError(5)
    win = types.SimpleNamespace(CredRead=boom, CRED_TYPE_GENERIC=1)
    monkeypatch.setattr(s, "_backend", lambda: (win, FakeWinError))
    assert s.read_secret("X") is None
    assert "dytopo/X" in capsys.readouterr().err


def test_no_backend_is_none(monkeypatch):
    monkeypatch.setattr(s, "_backend", lambda: None)
    assert s.read_secret("X") is None


def test_lookup_prefers_env_then_store(store):
    store["dytopo/A"] = "from-store"
    assert s.lookup("A", {"A": "from-env"}) == "from-env"
    assert s.lookup("A", {}) == "from-store"
