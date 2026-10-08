import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import embedders


class Dummy(embedders.BaseEmbedder):
    name = "dummy"
    def embed(self, text): return [1.0]


def test_get_embedder_keeps_stdout_clean(monkeypatch, capsys, tmp_path):
    # stdout carries the hook's JSON and the MCP server's protocol stream
    monkeypatch.setattr(embedders, "LocalEmbedder", Dummy)
    monkeypatch.chdir(tmp_path)
    embedders.get_embedder("local")
    out = capsys.readouterr()
    assert out.out == "" and "local" in out.err
