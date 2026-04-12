from __future__ import annotations

import struct

import numpy as np


class EmbeddingService:
    """Owns the loaded sentence-transformers model and exposes encoding
    and serialization for poem embeddings."""

    def __init__(self, model_name_or_path: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name_or_path, local_files_only=True)
        self._dim: int = self._model.get_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dim

    def encode(self, title: str, text: str) -> np.ndarray:
        """Encode a poem (title + body) into a unit-normalized float32 vector.

        Embedding input format per design doc §8.3:
        ``Title. Full poem text`` — or just the text if title is empty.
        """
        if title:
            combined = f"{title}. {text}"
        else:
            combined = text

        vector = self._model.encode(combined, normalize_embeddings=True)
        return np.asarray(vector, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a cleaned query string into a unit-normalized vector."""
        vector = self._model.encode(query, normalize_embeddings=True)
        return np.asarray(vector, dtype=np.float32)

    def to_bytes(self, vector: np.ndarray) -> bytes:
        """Serialize a vector to bytes: uint32 dimension + float32 data."""
        vec = np.asarray(vector, dtype=np.float32)
        return struct.pack("<I", len(vec)) + vec.tobytes()

    def from_bytes(self, blob: bytes) -> np.ndarray:
        """Deserialize bytes back to a float32 numpy array."""
        (dim,) = struct.unpack("<I", blob[:4])
        if dim != self._dim:
            raise ValueError(
                f"Embedding dimension mismatch: blob has {dim}, "
                f"model expects {self._dim}"
            )
        return np.frombuffer(blob[4:], dtype=np.float32).copy()
