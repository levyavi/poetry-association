import numpy as np


class TestEmbeddingService:
    def test_encode_returns_correct_shape(self, embedding_service):
        vec = embedding_service.encode("Title", "Some poem text")
        assert vec.ndim == 1
        assert vec.shape[0] == embedding_service.dimension

    def test_is_unit_normalized(self, embedding_service):
        vec = embedding_service.encode("Test", "A poem about the sea")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5

    def test_serialization_roundtrip(self, embedding_service):
        vec = embedding_service.encode("Hello", "World of poetry")
        blob = embedding_service.to_bytes(vec)
        restored = embedding_service.from_bytes(blob)
        np.testing.assert_array_almost_equal(vec, restored)

    def test_deterministic(self, embedding_service):
        a = embedding_service.encode("Same", "Same text here")
        b = embedding_service.encode("Same", "Same text here")
        np.testing.assert_array_equal(a, b)

    def test_encode_query_is_normalized(self, embedding_service):
        vec = embedding_service.encode_query("quiet grief")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5

    def test_empty_title_uses_text_only(self, embedding_service):
        vec = embedding_service.encode("", "Just the text")
        assert vec.shape[0] == embedding_service.dimension
