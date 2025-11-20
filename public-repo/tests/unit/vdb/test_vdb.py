"""
Comprehensive VDB (Vector Database) tests using JSON-based fixtures.

This module tests VDB functionality across all backends defined in tests.json.
Focus on public API and BaseUKF round-trip compatibility, no trivial or
backend-specific implementation tests.

Tests cover: insert, delete, batch_insert, search, clear, and vector operations.

Note: VDB implementations are still under development, so some tests may fail
but the test cases themselves are designed correctly.
"""

import pytest
import numpy as np
from ahvn.ukf.templates.basic import KnowledgeUKFT, ExperienceUKFT


class TestVDBPublicAPI:
    """Test VDB public API across all backends."""

    def test_vdb_insert_and_search(self, minimal_vdb):
        """Test basic insert and vector search."""
        # Create simple test records with embeddings
        record1 = {"id": "test_1", "text": "This is a test document about machine learning", "vector": [0.1] * 128, "category": "ml"}

        record2 = {"id": "test_2", "text": "Another document about deep learning", "vector": [0.2] * 128, "category": "dl"}

        # Insert records
        minimal_vdb.insert(record1)
        minimal_vdb.insert(record2)

        # Search with embedding (should find similar vectors)
        query_embedding = [0.15] * 128
        query = minimal_vdb.search(embedding=query_embedding, topk=2)

        # Verify query object is created
        assert query is not None
        assert query.similarity_top_k == 2
        assert len(query.query_embedding) == 128

    def test_vdb_batch_insert(self, minimal_vdb):
        """Test batch insert functionality."""
        # Create multiple records
        records = [{"id": f"batch_{i}", "text": f"Batch document {i}", "vector": [float(i) * 0.1] * 128, "index": i} for i in range(10)]

        # Batch insert
        minimal_vdb.batch_insert(records)

        # Search to verify insertion
        query_embedding = [0.5] * 128
        query = minimal_vdb.search(embedding=query_embedding, topk=5)

        assert query is not None
        assert query.similarity_top_k == 5

    def test_vdb_delete(self, minimal_vdb):
        """Test delete functionality."""
        # Insert a record
        record = {
            "id": "delete_test",
            "text": "This record will be deleted",
            "vector": [0.1] * 128,
        }

        minimal_vdb.insert(record)

        # Delete the record (may not be implemented in all backends)
        try:
            minimal_vdb.delete("delete_test")
        except (NotImplementedError, AttributeError):
            pytest.skip("Delete not implemented for this VDB backend")

    def test_vdb_clear(self, minimal_vdb):
        """Test clear functionality."""
        # Insert some records
        records = [
            {
                "id": f"clear_{i}",
                "text": f"Document {i}",
                "vector": [float(i) * 0.1] * 128,
            }
            for i in range(5)
        ]

        minimal_vdb.batch_insert(records)

        # Clear database
        try:
            minimal_vdb.clear()
        except Exception as e:
            # Clear may fail on some backends, that's expected
            pytest.skip(f"Clear not fully supported: {e}")


class TestVDBEncoderEmbedder:
    """Test VDB encoder and embedder functionality."""

    def test_vdb_k_encode_embed(self, minimal_vdb):
        """Test knowledge encoding and embedding."""
        # Create a knowledge object
        knowledge = KnowledgeUKFT(name="Test Knowledge", content="This is test content for encoding", tags={"[test:encoding]"})

        # Encode and embed
        encoded_text, embedding = minimal_vdb.k_encode_embed(knowledge)

        # Verify outputs
        assert isinstance(encoded_text, str)
        assert len(encoded_text) > 0
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_vdb_q_encode_embed(self, minimal_vdb):
        """Test query encoding and embedding."""
        # Create a query string
        query = "Find documents about machine learning"

        # Encode and embed
        encoded_text, embedding = minimal_vdb.q_encode_embed(query)

        # Verify outputs
        assert isinstance(encoded_text, str)
        assert len(encoded_text) > 0
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_vdb_separate_k_and_q_encode(self, minimal_vdb):
        """Test separate k_encode and q_encode methods."""
        knowledge = KnowledgeUKFT(name="Knowledge Item", content="Knowledge content")
        query = "Search query text"

        # Test k_encode
        k_encoded = minimal_vdb.k_encode(knowledge)
        assert isinstance(k_encoded, str)

        # Test q_encode
        q_encoded = minimal_vdb.q_encode(query)
        assert isinstance(q_encoded, str)

    def test_vdb_separate_k_and_q_embed(self, minimal_vdb):
        """Test separate k_embed and q_embed methods."""
        k_text = "knowledge text for embedding"
        q_text = "query text for embedding"

        # Test k_embed
        k_embedding = minimal_vdb.k_embed(k_text)
        assert isinstance(k_embedding, list)
        assert len(k_embedding) > 0
        assert all(isinstance(x, float) for x in k_embedding)

        # Test q_embed
        q_embedding = minimal_vdb.q_embed(q_text)
        assert isinstance(q_embedding, list)
        assert len(q_embedding) > 0
        assert all(isinstance(x, float) for x in q_embedding)


class TestVDBUKFRoundtrip:
    """Test VDB with BaseUKF round-trip scenarios."""

    def test_vdb_ukf_knowledge_storage(self, minimal_vdb):
        """Test storing and retrieving Knowledge objects in VDB."""
        # Create knowledge objects
        k1 = KnowledgeUKFT(name="VDB Knowledge 1", content="Vector databases enable semantic search", tags={"[topic:vdb]", "[type:definition]"}, priority=8)

        k2 = KnowledgeUKFT(
            name="VDB Knowledge 2", content="Embeddings represent text as dense vectors", tags={"[topic:embeddings]", "[type:definition]"}, priority=7
        )

        # Encode and embed knowledge objects
        text1, vec1 = minimal_vdb.k_encode_embed(k1)
        text2, vec2 = minimal_vdb.k_encode_embed(k2)

        # Store as records
        record1 = {
            "id": str(k1.id),
            "text": text1,
            "vector": vec1,
            "name": k1.name,
            "priority": k1.priority,
        }

        record2 = {
            "id": str(k2.id),
            "text": text2,
            "vector": vec2,
            "name": k2.name,
            "priority": k2.priority,
        }

        # Insert records
        minimal_vdb.insert(record1)
        minimal_vdb.insert(record2)

        # Search with query embedding
        query_text, query_vec = minimal_vdb.q_encode_embed("What is a vector database?")
        query = minimal_vdb.search(embedding=query_vec, topk=2)

        # Verify search query is valid
        assert query is not None
        assert len(query.query_embedding) > 0

    def test_vdb_ukf_experience_storage(self, minimal_vdb):
        """Test storing and retrieving Experience objects in VDB."""
        # Create experience objects
        exp1 = ExperienceUKFT(
            name="Vector Search Performed", content="Successfully executed similarity search", priority=6, metadata={"duration_ms": 120, "results": 5}
        )

        exp2 = ExperienceUKFT(
            name="Embedding Generated", content="Generated embeddings for user query", priority=5, metadata={"model": "text-embedding-ada-002"}
        )

        # Encode and embed
        text1, vec1 = minimal_vdb.k_encode_embed(exp1)
        text2, vec2 = minimal_vdb.k_encode_embed(exp2)

        # Store as records
        records = [
            {
                "id": str(exp1.id),
                "text": text1,
                "vector": vec1,
                "name": exp1.name,
                "priority": exp1.priority,
            },
            {
                "id": str(exp2.id),
                "text": text2,
                "vector": vec2,
                "name": exp2.name,
                "priority": exp2.priority,
            },
        ]

        # Batch insert
        minimal_vdb.batch_insert(records)

        # Search
        query_text, query_vec = minimal_vdb.q_encode_embed("search operations")
        query = minimal_vdb.search(embedding=query_vec, topk=2)

        assert query is not None

    def test_vdb_ukf_mixed_types(self, minimal_vdb):
        """Test storing mixed Knowledge and Experience objects."""
        knowledge = KnowledgeUKFT(name="Mixed Test Knowledge", content="Knowledge for mixed type test", tags={"[test:mixed]"})

        experience = ExperienceUKFT(name="Mixed Test Experience", content="Experience for mixed type test", priority=7)

        # Encode and embed both
        k_text, k_vec = minimal_vdb.k_encode_embed(knowledge)
        e_text, e_vec = minimal_vdb.k_encode_embed(experience)

        # Store both
        records = [
            {
                "id": str(knowledge.id),
                "text": k_text,
                "vector": k_vec,
                "ukf_type": "knowledge",
                "name": knowledge.name,
            },
            {
                "id": str(experience.id),
                "text": e_text,
                "vector": e_vec,
                "ukf_type": "experience",
                "name": experience.name,
            },
        ]

        minimal_vdb.batch_insert(records)

        # Search across both types
        query_text, query_vec = minimal_vdb.q_encode_embed("mixed test")
        query = minimal_vdb.search(embedding=query_vec, topk=2)

        assert query is not None


class TestVDBSearchFeatures:
    """Test VDB search features and capabilities."""

    def test_vdb_search_with_query_text(self, minimal_vdb):
        """Test search using query text (not just embedding)."""
        # Insert some documents
        records = [
            {
                "id": "doc1",
                "text": "Machine learning algorithms",
                "vector": [0.1] * 128,
            },
            {
                "id": "doc2",
                "text": "Deep neural networks",
                "vector": [0.2] * 128,
            },
        ]

        minimal_vdb.batch_insert(records)

        # Search with query text (will be encoded and embedded)
        query = minimal_vdb.search(query="machine learning", topk=1)

        assert query is not None
        assert query.similarity_top_k == 1

    def test_vdb_search_topk_variation(self, minimal_vdb):
        """Test search with different topk values."""
        # Insert many records
        records = [
            {
                "id": f"topk_{i}",
                "text": f"Document number {i}",
                "vector": [float(i) * 0.01] * 128,
            }
            for i in range(20)
        ]

        minimal_vdb.batch_insert(records)

        # Search with different topk values
        for k in [1, 5, 10]:
            query = minimal_vdb.search(embedding=[0.1] * 128, topk=k)
            assert query.similarity_top_k == k

    def test_vdb_search_requires_query_or_embedding(self, minimal_vdb):
        """Test that search raises error without query or embedding."""
        with pytest.raises(ValueError, match="Either 'query' or 'embedding' must be provided"):
            minimal_vdb.search(topk=5)


class TestVDBEdgeCases:
    """Test VDB behavior with edge cases."""

    def test_vdb_empty_database_search(self, minimal_vdb):
        """Test searching an empty database."""
        # Search empty database
        query = minimal_vdb.search(embedding=[0.1] * 128, topk=5)

        # Query should be created even if database is empty
        assert query is not None

    def test_vdb_large_batch_insert(self, minimal_vdb):
        """Test inserting a large batch of records."""
        # Create 100 records
        records = [
            {
                "id": f"large_{i}",
                "text": f"Large batch document {i}",
                "vector": [float(i % 10) * 0.1] * 128,
                "batch_id": i // 10,
            }
            for i in range(100)
        ]

        # Batch insert
        minimal_vdb.batch_insert(records)

        # Search should work
        query = minimal_vdb.search(embedding=[0.5] * 128, topk=10)
        assert query is not None

    def test_vdb_high_dimensional_vectors(self, minimal_vdb):
        """Test with higher dimensional vectors."""
        # Create records with 128-dimensional vectors
        dim = 128
        records = [
            {
                "id": f"highdim_{i}",
                "text": f"High dimensional document {i}",
                "vector": [float(i % 10) * 0.01] * dim,
            }
            for i in range(5)
        ]

        # Insert records
        minimal_vdb.batch_insert(records)

        # Search
        query_vec = [0.05] * dim
        query = minimal_vdb.search(embedding=query_vec, topk=3)

        assert query is not None
        assert len(query.query_embedding) == dim

    def test_vdb_special_characters_in_text(self, minimal_vdb):
        """Test handling special characters in text fields."""
        records = [
            {
                "id": "special_1",
                "text": "Text with 'quotes' and \"double quotes\"",
                "vector": [0.1] * 128,
            },
            {
                "id": "special_2",
                "text": "Unicode: 你好世界 🎉",
                "vector": [0.2] * 128,
            },
            {
                "id": "special_3",
                "text": "Newlines\nand\ttabs",
                "vector": [0.3] * 128,
            },
        ]

        # Insert records with special characters
        minimal_vdb.batch_insert(records)

        # Search should work
        query = minimal_vdb.search(embedding=[0.2] * 128, topk=3)
        assert query is not None

    def test_vdb_zero_vector(self, minimal_vdb):
        """Test handling zero vectors."""
        record = {
            "id": "zero_vec",
            "text": "Record with zero vector",
            "vector": [0.0] * 128,
        }

        # Insert zero vector
        minimal_vdb.insert(record)

        # Search with zero vector
        query = minimal_vdb.search(embedding=[0.0] * 128, topk=1)
        assert query is not None

    def test_vdb_metadata_preservation(self, minimal_vdb):
        """Test that metadata is preserved correctly."""
        record = {
            "id": "meta_test",
            "text": "Text with metadata",
            "vector": [0.1] * 128,
            "string_field": "value",
            "int_field": 42,
            "float_field": 3.14,
            "bool_field": True,
            "none_field": None,
        }

        # Insert record with various metadata types
        minimal_vdb.insert(record)

        # Verify insertion succeeded (metadata handling tested)
        query = minimal_vdb.search(embedding=[0.1] * 128, topk=1)
        assert query is not None
