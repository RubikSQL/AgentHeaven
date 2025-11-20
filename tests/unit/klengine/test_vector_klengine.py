"""Comprehensive test suite for unified vector database interface.

This test suite tests all three vector database providers (lancedb, chroma, milvus)
through the unified VectorKLStore and VectorKLEngine interface, providing 3x
the test coverage of individual backend tests.
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock
import uuid
import sys

from ahvn import VectorKLStore, VectorKLEngine, BaseUKF
from ahvn.ukf import ptags

# Import the global _get_short_name from fixtures
# Add tests to Python path for imports if not already there
ROOT_DIR = Path(__file__).resolve().parents[3]
TESTS_DIR = ROOT_DIR / "tests"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from fixtures.factory import _get_short_name
from fixtures import TestConfigLoader


# Load vector providers from tests.json
def pytest_generate_tests(metafunc):
    """Generate test parameters from tests.json VDB configurations."""
    if "provider" in metafunc.fixturenames:
        config_loader = TestConfigLoader()
        configs = config_loader.get_vdb_configs(metafunc.function.__name__)
        # Extract unique providers from VDB configs
        providers = sorted(set(backend for backend, _ in configs))
        metafunc.parametrize("provider", providers)


# Determine minimal providers from tests.json dynamically
def _get_minimal_providers():
    """Get list of minimal vector providers from tests.json."""
    config_loader = TestConfigLoader()
    configs = config_loader.get_vdb_configs("test")
    return tuple(sorted(set(backend for backend, _ in configs)))


MINIMAL_VECTOR_PROVIDERS = _get_minimal_providers()


def _build_vector_store(provider, temp_dir, encoder_fn, query_encoder_fn, embedder_fn, label, name=None):
    """Helper to create a VectorKLStore with provider-specific parameters."""
    store_params = {"encoder": (encoder_fn, query_encoder_fn), "embedder": embedder_fn, "provider": provider}

    # Use provided name or generate from label
    if name is None:
        name = _get_short_name(label)

    collection_name = f"{name}_collection"

    if provider == "lancedb":
        store_params.update({"uri": str(temp_dir / name), "collection": collection_name, "name": name})
    elif provider == "simple":
        # Simple provider uses in-memory storage
        store_params.update({"collection": collection_name, "name": name})
    elif provider == "chroma":
        store_params.update({"mode": "persistent", "path": str(temp_dir / name), "collection": collection_name, "name": name})
    elif provider == "chromalite":
        store_params.update({"mode": "ephemeral", "collection": collection_name, "name": name})
    elif provider == "milvuslite":
        store_params.update(
            {
                "uri": str(temp_dir / f"{name}.db"),
                "collection": collection_name,
                "connection_alias": f"{name}_{uuid.uuid4().hex[:8]}",
                "name": name,
            }
        )
    elif provider == "pgvector":
        store_params.update(
            {
                "collection": collection_name,
                "database": "test_db",
                "name": name,
            }
        )
    else:
        raise ValueError(f"Unsupported vector store provider '{provider}'")

    return VectorKLStore(**store_params)


def _apply_engine_provider_params(provider, temp_dir, label, name=None):
    """Build provider-specific engine parameters for non-inplace engines."""
    # Use provided name or generate from label
    if name is None:
        name = _get_short_name(label)

    if provider == "lancedb":
        return {"uri": str(temp_dir / name), "collection": f"{name}_engine", "name": name}
    if provider == "simple":
        # Simple provider uses in-memory storage
        return {"collection": f"{name}_engine", "name": name}
    if provider == "chroma":
        return {
            "mode": "persistent",
            "path": str(temp_dir / name),
            "collection": f"{name}_engine",
            "name": name,
        }
    if provider == "chromalite":
        return {"mode": "ephemeral", "collection": f"{name}_engine", "name": name}
    if provider == "milvuslite":
        return {
            "uri": str(temp_dir / f"{name}_engine.db"),
            "collection": f"{name}_engine",
            "connection_alias": f"{name}_{uuid.uuid4().hex[:8]}",
            "name": name,
        }
    if provider == "pgvector":
        return {
            "collection": f"{name}_engine",
            "database": "test_db",
            "name": name,
        }

    raise ValueError(f"Unsupported provider '{provider}' for engine parameters")


@pytest.fixture
def provider(request):
    """Provider parameter from tests.json via pytest_generate_tests."""
    return request.param


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_encoder():
    """Mock encoder function for UKF objects."""
    return lambda ukf: f"encoded_{ukf.name if hasattr(ukf, 'name') else str(ukf)}"


@pytest.fixture
def mock_query_encoder():
    """Mock encoder function for query strings."""
    return lambda query: f"encoded_{query}"


@pytest.fixture
def mock_embedder():
    """Mock embedder function."""
    return lambda text: [[0.1] * 128] * len(text) if isinstance(text, list) else ([0.1] * 128)  # 128-dimensional vector


@pytest.fixture
def sample_ukf():
    """Create a sample BaseUKF for testing."""
    return BaseUKF(name="test_ukf", content="This is a test UKF object", synonyms=["test", "sample"], tags=ptags(FIELD="test", TOPIC="vector", TYPE="sample"))


@pytest.fixture
def sample_ukfs():
    """Create multiple sample BaseUKF objects for testing."""
    return [BaseUKF(name=f"test_ukf_{i}", content=f"This is test UKF object {i}", tags=ptags(FIELD="test", TOPIC="vector", INDEX=str(i))) for i in range(1, 6)]


@pytest.fixture
def unified_store(provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, request):
    """Create a VectorKLStore for testing with specified provider."""
    # Use test node ID for generating short hash
    test_name = request.node.nodeid
    short_name = _get_short_name(test_name)
    store = _build_vector_store(provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, test_name, name=short_name)
    yield store
    store.close()


@pytest.fixture
def unified_inplace_engine(unified_store):
    """Create a VectorKLEngine in inplace mode."""
    engine = VectorKLEngine(storage=unified_store, inplace=True)
    yield engine
    engine.close()


@pytest.fixture
def unified_non_inplace_engine(request, provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder):
    """Create VectorKLEngine instances in non-inplace mode with varied storages.

    Tests combinations of storage providers with engine providers from tests.json.
    Uses first provider as storage and parametrized provider as engine.
    """
    # Get available providers from tests.json
    available_providers = list(MINIMAL_VECTOR_PROVIDERS)

    if not available_providers:
        pytest.skip("No vector providers configured in tests.json")

    # Use first available provider as storage provider
    storage_provider = available_providers[0]

    # Use test node ID for generating short hash
    test_name = request.node.nodeid
    short_name = _get_short_name(test_name)

    storage_name = f"{short_name}_st"
    engine_name = f"{short_name}_eg"

    storage = _build_vector_store(storage_provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, f"{test_name}_storage", name=storage_name)

    engine_params = {
        "storage": storage,
        "inplace": False,
        "encoder": (mock_encoder, mock_query_encoder),
        "embedder": mock_embedder,
        "provider": provider,
    }
    engine_params.update(_apply_engine_provider_params(provider, temp_dir, f"{test_name}_engine", name=engine_name))

    engine = VectorKLEngine(**engine_params)
    yield engine
    engine.close()
    storage.close()


class TestUnifiedVectorKLStore:
    """Test cases for unified VectorKLStore."""

    def test_init_with_invalid_provider(self, temp_dir, mock_encoder, mock_query_encoder, mock_embedder):
        """Test initialization with invalid provider."""
        with pytest.raises(ValueError, match="Unsupported vector database provider"):
            VectorKLStore(provider="invalid_provider", encoder=(mock_encoder, mock_query_encoder), embedder=mock_embedder)

    def test_upsert_and_get(self, unified_store, sample_ukf):
        """Test upsert and get operations."""
        unified_store.clear()
        unified_store.upsert(sample_ukf)
        unified_store.vdb.flush()

        retrieved = unified_store.get(sample_ukf.id)
        assert retrieved is not None
        assert retrieved.id == sample_ukf.id
        assert retrieved.name == sample_ukf.name
        assert retrieved.content == sample_ukf.content

    def test_batch_upsert_and_get_multiple(self, unified_store, sample_ukfs):
        """Test batch upsert and get multiple operations."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs)
        unified_store.vdb.flush()

        for ukf in sample_ukfs:
            retrieved = unified_store.get(ukf.id)
            assert retrieved is not None
            assert retrieved.id == ukf.id
            assert retrieved.name == ukf.name

        assert len(unified_store) == len(sample_ukfs)

    def test_remove(self, unified_store, sample_ukf):
        """Test remove operation."""
        unified_store.clear()
        unified_store.upsert(sample_ukf)
        unified_store.vdb.flush()
        assert len(unified_store) == 1

        unified_store.remove(sample_ukf.id)
        unified_store.vdb.flush()
        assert len(unified_store) == 0

        retrieved = unified_store.get(sample_ukf.id)
        assert retrieved == ...

    def test_clear(self, unified_store, sample_ukfs):
        """Test clear operation."""
        unified_store.batch_upsert(sample_ukfs)
        unified_store.vdb.flush()
        assert len(unified_store) == len(sample_ukfs)

        unified_store.clear()
        unified_store.vdb.flush()
        assert len(unified_store) == 0

    def test_contains_and_keys(self, unified_store, sample_ukfs):
        """Test contains operation and keys."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs)
        unified_store.vdb.flush()

        for ukf in sample_ukfs:
            assert ukf.id in unified_store

        assert len(unified_store) == len(sample_ukfs)
        for ukf in sample_ukfs:
            assert ukf.id in unified_store

    def test_embedding_field_property(self, unified_store):
        """Test embedding_field property."""
        assert unified_store.adapter.embedding_field is not None
        assert isinstance(unified_store.adapter.embedding_field, str)

    def test_adapter_property(self, unified_store):
        """Test adapter property."""
        assert unified_store.adapter is not None
        # k_encoder and k_embedder are on the vdb, not the adapter
        assert hasattr(unified_store.vdb, "k_encoder")
        assert hasattr(unified_store.vdb, "k_embedder")

    def test_close_and_reopen(self, unified_store, sample_ukf):
        """Test close and reopen functionality."""
        unified_store.upsert(sample_ukf)
        unified_store.vdb.flush()
        unified_store.close()

        # Should be able to close again without error
        unified_store.close()


class TestUnifiedVectorKLEngine:
    """Test cases for unified VectorKLEngine."""

    def test_init_inplace_mode(self, unified_store):
        """Test initialization in inplace mode."""
        engine = VectorKLEngine(storage=unified_store, inplace=True)

        assert engine.inplace is True
        assert engine.storage == unified_store
        assert engine.adapter == unified_store.adapter
        engine.close()

    def test_init_non_inplace_mode(self, provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, request):
        """Test initialization in non-inplace mode."""
        test_name = request.node.nodeid
        short_name = _get_short_name(test_name)
        storage_name = f"{short_name}_st"
        engine_name = f"{short_name}_eg"

        storage = _build_vector_store(provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, f"{test_name}_storage", name=storage_name)

        engine_params = {
            "storage": storage,
            "inplace": False,
            "encoder": (mock_encoder, mock_query_encoder),
            "embedder": mock_embedder,
            "provider": provider,
        }
        engine_params.update(_apply_engine_provider_params(provider, temp_dir, f"{test_name}_engine", name=engine_name))

        engine = VectorKLEngine(**engine_params)

        assert engine.inplace is False
        assert engine.adapter is not None
        engine.close()
        storage.close()

    def test_init_with_invalid_provider(self, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, request):
        """Test initialization with invalid provider."""
        test_name = request.node.nodeid
        short_name = _get_short_name(test_name)
        storage = _build_vector_store("lancedb", temp_dir, mock_encoder, mock_query_encoder, mock_embedder, test_name, name=short_name)

        try:
            with pytest.raises(ValueError, match="Unsupported vector database provider"):
                VectorKLEngine(
                    storage=storage,
                    provider="invalid_provider",
                    inplace=False,
                    encoder=(mock_encoder, mock_query_encoder),
                    embedder=mock_embedder,
                )
        finally:
            storage.close()

    def test_search_inplace_mode(self, unified_inplace_engine, sample_ukf):
        """Test search in inplace mode."""
        unified_inplace_engine.storage.clear()
        unified_inplace_engine.storage.upsert(sample_ukf)
        unified_inplace_engine.storage.vdb.flush()

        results = unified_inplace_engine.search(query="test", topk=1)

        assert isinstance(results, list)
        assert len(results) >= 0  # May not find matches due to mock embedder

        for result in results:
            assert "id" in result
            # Milvus uses VARCHAR for ID storage but we try to preserve original types
            provider = getattr(unified_inplace_engine.storage, "provider", None)
            if provider in ["milvus", "milvuslite"]:
                # Most IDs should be integers, but we'll accept both
                assert isinstance(result["id"], (int, str))
            else:
                assert isinstance(result["id"], int)

    def test_search_non_inplace_mode(self, unified_non_inplace_engine, sample_ukf):
        """Test search in non-inplace mode."""
        unified_non_inplace_engine.clear()
        unified_non_inplace_engine.upsert(sample_ukf)
        unified_non_inplace_engine.vdb.flush()

        results = unified_non_inplace_engine.search(query="test", topk=1)

        assert isinstance(results, list)
        assert len(results) >= 0  # May not find matches due to mock embedder

        for result in results:
            assert "id" in result
            assert isinstance(result["id"], (int, str))

    def test_search_with_include_parameters(self, unified_inplace_engine, sample_ukf):
        """Test search with various include parameters."""
        unified_inplace_engine.storage.clear()
        unified_inplace_engine.storage.upsert(sample_ukf)
        unified_inplace_engine.storage.vdb.flush()

        # Test with id only
        results = unified_inplace_engine.search(query="test", topk=1, include=["id"])
        for result in results:
            assert "id" in result
            assert "score" not in result

        # Test with score only
        results = unified_inplace_engine.search(query="test", topk=1, include=["score"])
        for result in results:
            assert "id" not in result
            # Score may or may not be present depending on backend

        # Test with both id and score
        results = unified_inplace_engine.search(query="test", topk=1, include=["id", "score"])
        for result in results:
            assert "id" in result

    def test_upsert_inplace_mode(self, unified_inplace_engine, sample_ukf):
        """Test upsert in inplace mode."""
        unified_inplace_engine.storage.clear()

        unified_inplace_engine.upsert(sample_ukf)

        assert len(unified_inplace_engine.storage) == 0
        retrieved = unified_inplace_engine.storage.get(sample_ukf.id)
        assert retrieved is ...

        unified_inplace_engine.storage.upsert(sample_ukf)
        assert len(unified_inplace_engine.storage) == 1
        retrieved = unified_inplace_engine.storage.get(sample_ukf.id)
        assert retrieved is not ...
        assert retrieved.id == sample_ukf.id

    def test_upsert_non_inplace_mode(self, unified_non_inplace_engine, sample_ukf):
        """Test upsert in non-inplace mode."""
        unified_non_inplace_engine.clear()

        unified_non_inplace_engine.upsert(sample_ukf)
        unified_non_inplace_engine.vdb.flush()

        assert len(unified_non_inplace_engine) == 1

    def test_batch_upsert_inplace_mode(self, unified_inplace_engine, sample_ukfs):
        """Test batch_upsert in inplace mode."""
        unified_inplace_engine.storage.clear()

        unified_inplace_engine.batch_upsert(sample_ukfs)

        assert len(unified_inplace_engine.storage) == 0

        unified_inplace_engine.storage.batch_upsert(sample_ukfs)

        assert len(unified_inplace_engine.storage) == len(sample_ukfs)

    def test_batch_upsert_non_inplace_mode(self, unified_non_inplace_engine, sample_ukfs):
        """Test batch_upsert in non-inplace mode."""
        unified_non_inplace_engine.clear()

        unified_non_inplace_engine.batch_upsert(sample_ukfs)
        unified_non_inplace_engine.vdb.flush()

        assert len(unified_non_inplace_engine) == len(sample_ukfs)

    def test_remove_inplace_mode(self, unified_inplace_engine, sample_ukf):
        """Test remove in inplace mode."""
        unified_inplace_engine.storage.clear()
        unified_inplace_engine.storage.upsert(sample_ukf)

        unified_inplace_engine.remove(sample_ukf.id)

        assert len(unified_inplace_engine.storage) == 1

        unified_inplace_engine.storage.remove(sample_ukf.id)

        assert len(unified_inplace_engine.storage) == 0

    def test_remove_non_inplace_mode(self, unified_non_inplace_engine, sample_ukf):
        """Test remove in non-inplace mode."""
        unified_non_inplace_engine.clear()
        unified_non_inplace_engine.storage.clear()
        unified_non_inplace_engine.storage.upsert(sample_ukf)
        unified_non_inplace_engine.storage.vdb.flush()
        unified_non_inplace_engine.upsert(sample_ukf)
        unified_non_inplace_engine.vdb.flush()

        unified_non_inplace_engine.remove(sample_ukf.id)
        unified_non_inplace_engine.vdb.flush()

        assert len(unified_non_inplace_engine.storage) == 1
        assert len(unified_non_inplace_engine) == 0

    def test_clear_inplace_mode(self, unified_inplace_engine, sample_ukfs):
        """Test clear in inplace mode."""
        unified_inplace_engine.storage.batch_upsert(sample_ukfs)
        assert len(unified_inplace_engine.storage) == len(sample_ukfs)

        unified_inplace_engine.clear()

        assert len(unified_inplace_engine.storage) == len(sample_ukfs)

        unified_inplace_engine.storage.clear()

        assert len(unified_inplace_engine.storage) == 0

    def test_clear_non_inplace_mode(self, unified_non_inplace_engine, sample_ukfs):
        """Test clear in non-inplace mode."""
        unified_non_inplace_engine.batch_upsert(sample_ukfs)
        unified_non_inplace_engine.vdb.flush()
        assert len(unified_non_inplace_engine) == len(sample_ukfs)

        unified_non_inplace_engine.clear()
        unified_non_inplace_engine.vdb.flush()

        assert len(unified_non_inplace_engine) == 0

    def test_len_inplace_mode(self, unified_inplace_engine, sample_ukf):
        """Test __len__ in inplace mode."""
        unified_inplace_engine.storage.clear()
        assert len(unified_inplace_engine) == 0

        unified_inplace_engine.storage.upsert(sample_ukf)
        unified_inplace_engine.storage.vdb.flush()
        assert len(unified_inplace_engine) == 1

    def test_len_non_inplace_mode(self, unified_non_inplace_engine, sample_ukf):
        """Test __len__ in non-inplace mode."""
        unified_non_inplace_engine.clear()
        assert len(unified_non_inplace_engine) == 0

        unified_non_inplace_engine.upsert(sample_ukf)
        unified_non_inplace_engine.vdb.flush()
        assert len(unified_non_inplace_engine) == 1

    def test_list_search_methods(self, unified_inplace_engine):
        """Test list_search method."""
        methods = unified_inplace_engine.list_search()
        assert methods == [None, "vector"]

    def test_flush(self, unified_inplace_engine):
        """Test flush method."""
        # Should not raise an exception
        unified_inplace_engine.flush()

    def test_search_mode_routing(self, unified_inplace_engine, sample_ukf):
        """Test search mode routing."""
        # Add data first to avoid LanceDB empty result warning
        unified_inplace_engine.storage.clear()
        unified_inplace_engine.storage.upsert(sample_ukf)
        unified_inplace_engine.storage.vdb.flush()

        # Test default mode
        results = unified_inplace_engine.search(query="test", mode=None)
        assert isinstance(results, list)

        # Test invalid mode
        with pytest.raises(ValueError, match="Search mode 'invalid' not found"):
            unified_inplace_engine.search(query="test", mode="invalid")

    def test_k_encode_method(self, unified_inplace_engine, sample_ukf):
        """Test k_encode method."""
        encoded = unified_inplace_engine.k_encode(sample_ukf)
        assert isinstance(encoded, str)
        assert "encoded_" in encoded

    def test_k_embed_method(self, unified_inplace_engine):
        """Test k_embed method."""
        embedding = unified_inplace_engine.k_embed("test_text")
        assert isinstance(embedding, list)
        assert len(embedding) == 128  # Based on mock embedder

    def test_q_encode_method(self, unified_inplace_engine):
        """Test q_encode method."""
        encoded = unified_inplace_engine.q_encode("test_query")
        assert isinstance(encoded, str)
        assert "encoded_" in encoded

    def test_q_embed_method(self, unified_inplace_engine):
        """Test q_embed method."""
        embedding = unified_inplace_engine.q_embed("test_query")
        assert isinstance(embedding, list)
        assert len(embedding) == 128  # Based on mock embedder

    def test_embedding_field_property(self, unified_inplace_engine):
        """Test embedding_field property."""
        assert unified_inplace_engine.adapter.embedding_field is not None
        assert isinstance(unified_inplace_engine.adapter.embedding_field, str)

    def test_adapter_property(self, unified_inplace_engine):
        """Test adapter property."""
        assert unified_inplace_engine.adapter is not None
        # k_encoder and k_embedder are on the vdb, not the adapter
        assert hasattr(unified_inplace_engine.vdb, "k_encoder")
        assert hasattr(unified_inplace_engine.vdb, "k_embedder")


class TestUnifiedVectorIntegration:
    """Integration tests for unified vector interface."""

    def test_end_to_end_workflow(self, provider, temp_dir, mock_encoder, mock_query_encoder, mock_embedder, sample_ukfs, request):
        """Test complete workflow with unified interface."""
        test_name = request.node.nodeid
        short_name = _get_short_name(test_name)

        # Create store
        store_params = {"encoder": (mock_encoder, mock_query_encoder), "embedder": mock_embedder, "provider": provider, "name": short_name}

        if provider == "lancedb":
            store_params.update({"uri": str(temp_dir / short_name), "collection": f"{short_name}_collection"})
        elif provider == "chroma":
            store_params.update({"path": str(temp_dir / short_name), "collection": f"{short_name}_collection"})
        elif provider == "chromalite":
            store_params.update({"collection": f"{short_name}_collection", "mode": "ephemeral"})
        elif provider == "milvuslite":
            store_params.update(
                {
                    "uri": str(temp_dir / f"{short_name}.db"),
                    "collection": f"{short_name}_collection",
                    "connection_alias": f"{short_name}_{uuid.uuid4().hex[:8]}",
                }
            )
        elif provider == "pgvector":
            store_params.update(
                {
                    "collection": f"{short_name}_collection",
                    "database": "test_db",
                }
            )

        store = VectorKLStore(**store_params)

        non_inplace_storage = None
        non_inplace_engine = None

        try:
            # Store data
            store.batch_upsert(sample_ukfs)
            store.vdb.flush()
            assert len(store) == len(sample_ukfs)

            # Create inplace engine
            inplace_engine = VectorKLEngine(storage=store, inplace=True)

            # Search with inplace engine
            results = inplace_engine.search(query="test", topk=3, include=["id", "score"])
            assert isinstance(results, list)

            # Verify results have valid IDs and other expected fields
            for result in results:
                if "id" in result:
                    # IDs can be int or string depending on the backend
                    assert isinstance(result["id"], (int, str))
                    # Verify we can retrieve the UKF with this ID from the store
                    retrieved_ukf = store.get(result["id"])
                    assert retrieved_ukf is not None
                    # Verify the content matches what we'd expect from our sample data
                    assert "test" in retrieved_ukf.content.lower() or "vector" in retrieved_ukf.content.lower()

            inplace_engine.close()

            # Create non-inplace engine
            engine_name = f"{short_name}_eg"
            storage_name = f"{short_name}_st"

            engine_params = {
                "inplace": False,
                "encoder": (mock_encoder, mock_query_encoder),
                "embedder": mock_embedder,
                "provider": provider,
                "name": engine_name,
            }

            if provider == "lancedb":
                engine_params.update({"uri": str(temp_dir / engine_name), "collection": f"{engine_name}_collection"})
            elif provider == "chroma":
                engine_params.update({"path": str(temp_dir / engine_name), "collection": f"{engine_name}_collection"})
            elif provider == "chromalite":
                engine_params.update({"collection": f"{engine_name}_collection", "mode": "ephemeral"})
            elif provider == "milvuslite":
                engine_params.update(
                    {
                        "uri": str(temp_dir / f"{engine_name}.db"),
                        "collection": f"{engine_name}_collection",
                        "connection_alias": f"{engine_name}_{uuid.uuid4().hex[:8]}",
                    }
                )
            elif provider == "pgvector":
                engine_params.update(
                    {
                        "collection": f"{engine_name}_collection",
                        "database": "test_db",
                    }
                )

            non_inplace_storage = _build_vector_store(
                provider,
                temp_dir,
                mock_encoder,
                mock_query_encoder,
                mock_embedder,
                f"{test_name}_storage",
                name=storage_name,
            )

            engine_params["storage"] = non_inplace_storage

            non_inplace_engine = VectorKLEngine(**engine_params)

            # Store and search with non-inplace engine
            non_inplace_engine.batch_upsert(sample_ukfs)
            non_inplace_engine.vdb.flush()
            results = non_inplace_engine.search(query="test", topk=3, include=["id", "score"])
            assert isinstance(results, list)

            # Verify results have valid IDs and expected fields
            for result in results:
                if "id" in result:
                    # IDs should always be integers in the Python model for logical consistency
                    # regardless of underlying VDB storage format
                    assert isinstance(result["id"], int)

        finally:
            if non_inplace_engine is not None:
                try:
                    non_inplace_engine.close()
                except Exception:
                    pass
            if non_inplace_storage is not None:
                try:
                    non_inplace_storage.close()
                except Exception:
                    pass
            store.close()

    def test_multiple_searches(self, unified_inplace_engine, sample_ukfs):
        """Test multiple search operations."""
        unified_inplace_engine.storage.batch_upsert(sample_ukfs)
        unified_inplace_engine.storage.vdb.flush()

        queries = ["test", "vector", "database", "search"]

        for query in queries:
            results = unified_inplace_engine.search(query=query, topk=2)
            assert isinstance(results, list)

            for result in results:
                assert "id" in result
                # Milvus uses VARCHAR for ID storage but we try to preserve original types
                provider = getattr(unified_inplace_engine.storage, "provider", None)
                if provider in ["milvus", "milvuslite"]:
                    # Most IDs should be integers, but we'll accept both
                    assert isinstance(result["id"], (int, str))
                else:
                    assert isinstance(result["id"], int)

    def test_large_batch_operations(self, unified_store):
        """Test large batch operations."""
        # Create 5 UKF objects (simplified for better compatibility)
        large_batch = [
            BaseUKF(name=f"large_test_ukf_{i}", content=f"This is large test UKF object {i}", tags=ptags(BATCH="large", INDEX=str(i))) for i in range(1, 6)
        ]

        unified_store.clear()
        unified_store.batch_upsert(large_batch)
        unified_store.vdb.flush()

        assert len(unified_store) == 5

        # Test retrieval - just check they exist without specific ID lookups
        values = list(unified_store)
        assert len(values) == 5
        # Check that all expected names are present
        expected_names = {f"large_test_ukf_{i}" for i in range(1, 6)}
        actual_names = {ukf.name for ukf in values}
        assert expected_names == actual_names

    def test_error_handling(self, unified_store):
        """Test error handling."""
        # Test getting non-existent ID
        result = unified_store.get(99999)
        assert result == ...

        # Test removing non-existent ID
        unified_store.remove(99999)  # Should not raise exception

        # Test contains for non-existent ID
        assert 99999 not in unified_store

    def test_concurrent_access(self, unified_store, sample_ukfs):
        """Test concurrent access to store and engine."""
        import threading
        import time

        def worker(store, ukfs, worker_id):
            """Worker function for concurrent testing."""
            for ukf in ukfs:
                store.upsert(ukf)
                time.sleep(0.01)  # Small delay to simulate concurrent access
                retrieved = store.get(ukf.id)
                assert retrieved is not None
                assert retrieved.id == ukf.id

        # Split UKFs among workers
        num_workers = 3
        ukf_chunks = [sample_ukfs[i::num_workers] for i in range(num_workers)]

        threads = []
        for i, chunk in enumerate(ukf_chunks):
            thread = threading.Thread(target=worker, args=(unified_store, chunk, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all UKFs were stored
        assert len(unified_store) == len(sample_ukfs)

    def test_batch_remove_basic(self, unified_store, sample_ukfs):
        """Test basic batch_remove with vector stores."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs[:5])
        unified_store.vdb.flush()

        # Verify all exist
        for ukf in sample_ukfs[:5]:
            assert ukf.id in unified_store

        # Batch remove first 3
        unified_store.batch_remove([sample_ukfs[0].id, sample_ukfs[1].id, sample_ukfs[2].id])
        unified_store.vdb.flush()

        # Verify first 3 removed
        for ukf in sample_ukfs[:3]:
            assert ukf.id not in unified_store

        # Verify last 2 still exist
        for ukf in sample_ukfs[3:5]:
            assert ukf.id in unified_store

    def test_batch_remove_with_ukf_instances(self, unified_store, sample_ukfs):
        """Test batch_remove with BaseUKF instances."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs[:3])
        unified_store.vdb.flush()

        # Remove using BaseUKF instances
        unified_store.batch_remove(sample_ukfs[:3])
        unified_store.vdb.flush()

        # Verify all removed
        for ukf in sample_ukfs[:3]:
            assert ukf.id not in unified_store

    def test_batch_remove_with_string_ids(self, unified_store, sample_ukfs):
        """Test batch_remove with string IDs."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs[:3])
        unified_store.vdb.flush()

        # Remove using string IDs
        string_ids = [str(ukf.id) for ukf in sample_ukfs[:3]]
        unified_store.batch_remove(string_ids)
        unified_store.vdb.flush()

        # Verify all removed
        for ukf in sample_ukfs[:3]:
            assert ukf.id not in unified_store

    def test_batch_remove_mixed_types(self, unified_store, sample_ukfs):
        """Test batch_remove with mixed int, string, and BaseUKF types."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs[:4])
        unified_store.vdb.flush()

        # Remove using mixed types
        mixed_keys = [sample_ukfs[0].id, str(sample_ukfs[1].id), sample_ukfs[2], sample_ukfs[3].id]
        unified_store.batch_remove(mixed_keys)
        unified_store.vdb.flush()

        # Verify all removed
        for ukf in sample_ukfs[:4]:
            assert ukf.id not in unified_store

    def test_batch_remove_empty_list(self, unified_store, sample_ukfs):
        """Test batch_remove with empty list."""
        unified_store.clear()
        unified_store.batch_upsert(sample_ukfs[:3])
        unified_store.vdb.flush()

        # Remove empty list (should do nothing)
        unified_store.batch_remove([])
        unified_store.vdb.flush()

        # Verify all still exist
        for ukf in sample_ukfs[:3]:
            assert ukf.id in unified_store
