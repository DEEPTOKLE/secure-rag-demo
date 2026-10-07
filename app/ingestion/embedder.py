"""
Sentence-transformers embedding wrapper (all-MiniLM-L6-v2, 384 dims, local).
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL


class Embedder:
    """Lazy-loading singleton that wraps the local embedding model."""

    _model: SentenceTransformer | None = None

    @classmethod
    def _ensure_model(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model = SentenceTransformer(EMBEDDING_MODEL)
        return cls._model

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._ensure_model()
        return model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
