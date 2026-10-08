import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server


def test_server_does_not_import_sklearn():
    # Checks DyTopo's own code: the local embedder (sentence-transformers) pulls
    # sklearn into sys.modules by itself, so sys.modules can't tell us.
    assert "sklearn" not in Path(server.__file__).read_text(encoding="utf-8")


def test_compute_relevance_is_cosine():
    rel = server.DyTopoRouter.compute_relevance
    assert rel(None, np.array([1.0, 0.0]), np.array([2.0, 0.0])) == 1.0
    assert rel(None, np.array([1.0, 0.0]), np.array([0.0, 3.0])) == 0.0
    assert np.isclose(rel(None, np.array([1.0, 0.0]), np.array([1.0, 1.0])), 2 ** -0.5)


def test_compute_relevance_zero_vector_is_zero_not_nan():
    assert server.DyTopoRouter.compute_relevance(None, np.zeros(2), np.array([1.0, 0.0])) == 0.0


def test_server_starts_without_openai_key_and_disables_discovery():
    # Importing server must not require OPENAI_API_KEY; discovery (LLM) is optional.
    import os
    if not os.getenv("OPENAI_API_KEY"):
        assert server.router.discovery is None
