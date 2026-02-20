"""
DyTopo Embedding Providers

Pluggable embedding backends. Controlled via DYTOPO_EMBEDDER env var:
  - "openai"     (default if OPENAI_API_KEY set)
  - "anthropic"  (requires ANTHROPIC_API_KEY)
  - "local"      (sentence-transformers, no API key needed)

All providers are wrapped by CachedEmbedder which persists embeddings to
.dytopo_cache.json so each unique text is only embedded once.
"""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

CACHE_PATH = Path(__file__).parent / ".dytopo_cache.json"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseEmbedder(ABC):
    """All embedders return a 1-D numpy array."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIEmbedder(BaseEmbedder):
    MODEL = "text-embedding-3-small"

    def __init__(self) -> None:
        import openai  # lazy import
        self._client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    @property
    def name(self) -> str:
        return "openai"

    def embed(self, text: str) -> np.ndarray:
        response = self._client.embeddings.create(model=self.MODEL, input=text)
        return np.array(response.data[0].embedding)


# ---------------------------------------------------------------------------
# Voyage AI (Anthropic-recommended embedding provider, separate package)
# ---------------------------------------------------------------------------

class AnthropicEmbedder(BaseEmbedder):
    """
    Uses Voyage AI embeddings (voyage-3-lite model).

    Voyage AI is Anthropic's recommended embedding partner.
    Requires the `voyageai` package and a VOYAGE_API_KEY or ANTHROPIC_API_KEY.

    Install: pip install voyageai
    Key:     export VOYAGE_API_KEY=...
             (ANTHROPIC_API_KEY is accepted as a fallback alias)
    """
    MODEL = "voyage-3-lite"

    def __init__(self) -> None:
        try:
            import voyageai  # lazy import
        except ImportError:
            raise ImportError(
                "voyageai package required for the 'anthropic' embedder. "
                "Install with: pip install voyageai\n"
                "Get an API key at: https://www.voyageai.com/"
            )
        # Accept VOYAGE_API_KEY or fall back to ANTHROPIC_API_KEY as alias
        api_key = os.environ.get("VOYAGE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "VOYAGE_API_KEY (or ANTHROPIC_API_KEY) must be set for the 'anthropic' embedder."
            )
        self._client = voyageai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    def embed(self, text: str) -> np.ndarray:
        result = self._client.embed([text], model=self.MODEL)
        return np.array(result.embeddings[0])


# ---------------------------------------------------------------------------
# Local (sentence-transformers)
# ---------------------------------------------------------------------------

class LocalEmbedder(BaseEmbedder):
    MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # lazy import
        except ImportError:
            raise ImportError(
                "sentence-transformers package required for LocalEmbedder. "
                "Install with: pip install sentence-transformers"
            )
        model = model_name or os.getenv("DYTOPO_LOCAL_MODEL", self.MODEL)
        self._model = SentenceTransformer(model)

    @property
    def name(self) -> str:
        return "local"

    def embed(self, text: str) -> np.ndarray:
        return self._model.encode(text, convert_to_numpy=True)


# ---------------------------------------------------------------------------
# Cache wrapper
# ---------------------------------------------------------------------------

class CachedEmbedder(BaseEmbedder):
    """
    Wraps any BaseEmbedder with a persistent JSON cache keyed by
    (provider_name, sha256(text)). Embeddings are computed once and
    reused across server restarts.
    """

    def __init__(self, inner: BaseEmbedder, cache_path: Path = CACHE_PATH) -> None:
        self._inner = inner
        self._cache_path = cache_path
        self._cache: dict[str, list[float]] = self._load()

    def _load(self) -> dict[str, list[float]]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        """Atomically write cache to disk via a temp file + rename."""
        tmp = self._cache_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
            tmp.replace(self._cache_path)  # atomic on POSIX; best-effort on Windows
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self._inner.name}:{digest}"

    @property
    def name(self) -> str:
        return f"cached({self._inner.name})"

    def embed(self, text: str, _save: bool = True) -> np.ndarray:
        """
        Embed `text` and return a 1-D numpy array.

        When embedding many texts in a tight loop, pass `_save=False` and call
        `flush()` once at the end to reduce disk I/O from O(N) writes to O(1).
        """
        key = self._key(text)
        if key in self._cache:
            return np.array(self._cache[key])
        vec = self._inner.embed(text)
        self._cache[key] = vec.tolist()
        if _save:
            self._save()
        return vec

    def flush(self) -> None:
        """Persist any in-memory cache entries that have not yet been written."""
        self._save()

    def invalidate(self, text: str) -> None:
        """Remove a single entry from cache (e.g. after description update)."""
        key = self._key(text)
        if key in self._cache:
            del self._cache[key]
            self._save()

    def clear(self) -> None:
        """Wipe entire cache."""
        self._cache = {}
        if self._cache_path.exists():
            self._cache_path.unlink()

    # ── Public introspection ──────────────────────────────────────────────────

    @property
    def cache_size(self) -> int:
        """Number of cached embeddings."""
        return len(self._cache)

    @property
    def cache_path(self) -> Path:
        """Path to the persistent cache file."""
        return self._cache_path


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_embedder(provider: str | None = None) -> CachedEmbedder:
    """
    Return a CachedEmbedder wrapping the requested provider.

    Priority:
      1. Explicit `provider` argument
      2. DYTOPO_EMBEDDER env var
      3. Auto-detect: openai if OPENAI_API_KEY set,
                      anthropic if ANTHROPIC_API_KEY set,
                      otherwise local
    """
    provider = (
        provider
        or os.getenv("DYTOPO_EMBEDDER")
        or _auto_detect()
    )

    if provider == "openai":
        inner: BaseEmbedder = OpenAIEmbedder()
    elif provider == "anthropic":
        inner = AnthropicEmbedder()
    elif provider == "local":
        inner = LocalEmbedder()
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            "Choose from: openai, anthropic, local"
        )

    print(f"[DyTopo] Embedding provider: {provider}")
    return CachedEmbedder(inner)


def _auto_detect() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("VOYAGE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "local"
