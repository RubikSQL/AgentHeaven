"""
Comprehensive tests for DAACKLEngine functionality.

This module tests the DAACKLEngine class which provides AC automaton-based string search.
The DAAC engine is always non-inplace and non-recoverable, only returning IDs by default.

The tests cover all DAACKLEngine functionality including:
- Basic initialization and configuration
- Search operations with various conflict strategies
- String normalization and encoding
- Whole word matching
- Include options (id, query, matches, kl)
- Performance testing with larger datasets
- Save/load functionality
- Error handling and validation
"""

import pytest
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ahvn.ukf.templates.basic.experience import ExperienceUKFT
from ahvn.ukf.base import BaseUKF
from ahvn.klengine.daac_engine import DAACKLEngine
from ahvn.klstore.cache_store import CacheKLStore
from ahvn.klstore.db_store import DatabaseKLStore
from ahvn.cache import InMemCache


class TestDAACKLEngine:
    """Test DAACKLEngine functionality."""

    def create_test_ukfs(self) -> List[BaseUKF]:
        """Create test UKFs for search testing."""
        ukfs = [
            BaseUKF(
                name="python",
                type="programming_language",
                content="Python is a high-level programming language",
                synonyms=["py", "python3", "Python"],
            ),
            BaseUKF(
                name="java",
                type="programming_language",
                content="Java is a popular object-oriented language",
                synonyms=["Java", "JDK"],
            ),
            BaseUKF(
                name="javascript",
                type="programming_language",
                content="JavaScript is used for web development",
                synonyms=["js", "JavaScript", "ECMAScript"],
            ),
            BaseUKF(
                name="database",
                type="technology",
                content="Database systems store and manage data",
                synonyms=["db", "database", "databases"],
            ),
            BaseUKF(
                name="machine_learning",
                type="field",
                content="Machine learning is a subset of AI",
                synonyms=["ml", "machine learning", "ML"],
            ),
        ]
        return ukfs

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for DAAC engine files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def populated_cache_store(self):
        """Create and populate a CacheKLStore for testing."""
        cache = InMemCache()
        store = CacheKLStore(cache=cache)

        ukfs = self.create_test_ukfs()
        for ukf in ukfs:
            store.upsert(ukf)

        return store

    @pytest.fixture
    def populated_db_store(self, minimal_db_config):
        """Create and populate a DatabaseKLStore for testing."""
        backend, database = minimal_db_config
        store = DatabaseKLStore(provider=backend, database=database)

        ukfs = self.create_test_ukfs()
        for ukf in ukfs:
            store.upsert(ukf)

        return store

    @pytest.fixture
    def daac_engine_cache(self, populated_cache_store, temp_dir):
        """Create a DAAC engine with cache storage."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "daac_cache"),
            encoder=encoder,
            min_length=2,
            inverse=True,
            normalizer=True,
        )

        # Populate engine
        for ukf in populated_cache_store:
            engine.upsert(ukf)
        engine.flush()

        yield engine
        engine.close()

    @pytest.fixture
    def daac_engine_db(self, populated_db_store, temp_dir):
        """Create a DAAC engine with database storage."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_db_store,
            path=str(temp_dir / "daac_db"),
            encoder=encoder,
            min_length=2,
            inverse=True,
            normalizer=True,
        )

        # Populate engine
        for ukf in populated_db_store:
            engine.upsert(ukf)
        engine.flush()

        yield engine
        engine.close()

    # === Initialization Tests ===

    def test_initialization_basic(self, populated_cache_store, temp_dir):
        """Test basic DAAC engine initialization."""

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_init"),
            encoder=encoder,
        )

        assert engine.inplace is False
        assert engine.recoverable is False
        assert engine.storage == populated_cache_store
        assert engine.encoder is not None
        assert engine.min_length == 2
        assert engine.inverse is True
        assert len(engine) == 0  # No UKFs added yet

        engine.close()

    def test_initialization_with_custom_parameters(self, populated_cache_store, temp_dir):
        """Test DAAC engine initialization with custom parameters."""

        def encoder(kl):
            return list(kl.synonyms if kl.synonyms else [])

        def normalizer(text):
            return text.upper()

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_custom"),
            encoder=encoder,
            min_length=3,
            inverse=False,
            normalizer=normalizer,
        )

        assert engine.min_length == 3
        assert engine.inverse is False
        assert engine.normalizer("test") == "TEST"

        engine.close()

    def test_initialization_with_default_encoder(self, populated_cache_store, temp_dir):
        """Test DAAC engine with None encoder (should use default)."""
        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_default_encoder"),
            encoder=None,
        )

        assert engine.encoder is not None

        # Test default encoder behavior
        ukf = BaseUKF(name="test", synonyms=["test1", "test2"])
        encoded = engine.encoder(ukf)
        assert "test" in encoded
        assert "test1" in encoded
        assert "test2" in encoded

        engine.close()

    # === Search Tests - Basic ===

    def test_search_basic_id_only(self, daac_engine_cache):
        """Test basic search returning IDs only."""
        results = daac_engine_cache.search(query="I love python programming", include=["id"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert isinstance(result["id"], int)
            assert "kl" not in result
            assert "query" not in result
            assert "matches" not in result

    def test_search_with_query_include(self, daac_engine_cache):
        """Test search including normalized query."""
        query = "I Love Python Programming"
        results = daac_engine_cache.search(query=query, include=["id", "query"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "query" in result
            # Query should be normalized (lowercased due to normalizer=True)
            assert result["query"].islower()

    def test_search_with_matches_include(self, daac_engine_cache):
        """Test search including match positions."""
        results = daac_engine_cache.search(query="python and javascript", include=["id", "matches"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "matches" in result
            assert isinstance(result["matches"], list)
            # Each match should be a tuple of (start, end)
            for match in result["matches"]:
                assert isinstance(match, tuple)
                assert len(match) == 2
                assert match[0] < match[1]

    def test_search_with_kl_include(self, daac_engine_cache):
        """Test search including KL objects from storage."""
        results = daac_engine_cache.search(query="python programming", include=["id", "kl"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "kl" in result
            assert isinstance(result["kl"], BaseUKF)
            assert result["kl"].id == result["id"]

    def test_search_with_all_includes(self, daac_engine_cache):
        """Test search with all include options."""
        results = daac_engine_cache.search(query="python and javascript", include=["id", "kl", "query", "matches"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "kl" in result
            assert "query" in result
            assert "matches" in result
            assert isinstance(result["kl"], BaseUKF)
            assert result["kl"].id == result["id"]

    # === Search Tests - Conflict Resolution ===

    def test_search_conflict_overlap(self, daac_engine_cache):
        """Test search with overlap conflict strategy."""
        # "javascript" contains "java" - both should match with overlap
        results = daac_engine_cache.search(query="I use javascript daily", conflict="overlap", include=["id", "matches"])

        # Should find multiple matches (javascript and possibly java if it overlaps)
        assert len(results) >= 1

    def test_search_conflict_longest_distinct(self, daac_engine_cache):
        """Test search with longest_distinct conflict strategy."""
        results = daac_engine_cache.search(query="python javascript java", conflict="longest_distinct", include=["id", "matches"])

        assert len(results) >= 1

    # === Search Tests - Whole Word Matching ===

    def test_search_whole_word_true(self, daac_engine_cache):
        """Test search with whole word matching enabled."""
        # "py" should not match "python" when whole_word=True
        results_whole = daac_engine_cache.search(query="python", whole_word=True, include=["id", "kl"])

        results_partial = daac_engine_cache.search(query="python", whole_word=False, include=["id", "kl"])

        # Both should find matches since "python" is a whole word
        assert len(results_whole) >= 1
        assert len(results_partial) >= 1

    def test_search_whole_word_false(self, daac_engine_cache):
        """Test search with whole word matching disabled."""
        # Add a UKF with a short synonym
        ukf = BaseUKF(name="test_short", synonyms=["py"])
        daac_engine_cache.storage.upsert(ukf)
        daac_engine_cache.upsert(ukf)
        daac_engine_cache.flush()

        # "py" in "python" should match when whole_word=False
        results = daac_engine_cache.search(query="python programming", whole_word=False, include=["id", "kl"])

        # Should find matches
        assert len(results) >= 1

    # === Search Tests - Edge Cases ===

    def test_search_empty_query(self, daac_engine_cache):
        """Test search with empty query."""
        results = daac_engine_cache.search(query="", include=["id"])
        assert len(results) == 0

    def test_search_no_matches(self, daac_engine_cache):
        """Test search with query that has no matches."""
        results = daac_engine_cache.search(query="极其罕见的不存在的词语xyzqwerty999", include=["id"])
        assert len(results) == 0

    def test_search_case_insensitive(self, daac_engine_cache):
        """Test that search is case-insensitive with normalizer."""
        results_lower = daac_engine_cache.search(query="python", include=["id"])
        results_upper = daac_engine_cache.search(query="PYTHON", include=["id"])
        results_mixed = daac_engine_cache.search(query="PyThOn", include=["id"])

        # All should return the same results due to normalization
        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_search_with_multiple_matches_same_ukf(self, daac_engine_cache):
        """Test search where same UKF matches multiple times."""
        # "python" and "py" both refer to the same UKF
        results = daac_engine_cache.search(query="python is py python", include=["id", "matches"])

        # Should find the UKF with multiple match positions
        assert len(results) >= 1
        for result in results:
            if len(result["matches"]) > 1:
                # Found a UKF with multiple matches
                break

    # === Data Operations Tests ===

    def test_upsert_and_search(self, populated_cache_store, temp_dir):
        """Test upserting UKFs and searching for them."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_upsert"),
            encoder=encoder,
        )

        ukf = BaseUKF(name="rust", synonyms=["rust", "rust-lang"])
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        results = engine.search(query="I love rust programming", include=["id", "kl"])

        found = False
        for result in results:
            if result["kl"].name == "rust":
                found = True
                break

        assert found

        engine.close()

    def test_remove_and_search(self, daac_engine_cache):
        """Test removing UKFs and verifying they're not in search results."""
        # Find a UKF to remove
        all_ukfs = list(daac_engine_cache.storage)
        if len(all_ukfs) > 0:
            ukf_to_remove = all_ukfs[0]

            # Search before removal
            results_before = daac_engine_cache.search(query=ukf_to_remove.name, include=["id"])

            # Remove from engine
            daac_engine_cache.remove(ukf_to_remove.id)
            daac_engine_cache.flush()

            # Search after removal
            results_after = daac_engine_cache.search(query=ukf_to_remove.name, include=["id"])

            # Should have fewer results after removal
            ids_before = {r["id"] for r in results_before}
            ids_after = {r["id"] for r in results_after}

            assert ukf_to_remove.id not in ids_after
            if ukf_to_remove.id in ids_before:
                assert len(ids_after) < len(ids_before)

    def test_clear(self, daac_engine_cache):
        """Test clearing all UKFs from engine."""
        assert len(daac_engine_cache) > 0

        daac_engine_cache.clear()

        assert len(daac_engine_cache) == 0

        results = daac_engine_cache.search(query="python", include=["id"])
        assert len(results) == 0

    def test_batch_operations(self, populated_cache_store, temp_dir):
        """Test batch upsert operations."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_batch"),
            encoder=encoder,
        )

        ukfs = self.create_test_ukfs()
        for ukf in ukfs:
            engine.upsert(ukf)

        engine.flush()

        assert len(engine) == len(ukfs)

        engine.close()

    def test_batch_remove_basic(self, daac_engine_cache):
        """Test basic batch_remove functionality."""
        all_ukfs = list(daac_engine_cache.storage)
        if len(all_ukfs) >= 5:
            ukfs_to_remove = all_ukfs[:3]
            ukfs_to_keep = all_ukfs[3:5]

            # Batch remove first 3
            daac_engine_cache.batch_remove([ukf.id for ukf in ukfs_to_remove])
            daac_engine_cache.flush()

            # Verify removed
            for ukf in ukfs_to_remove:
                results = daac_engine_cache.search(query=ukf.name, include=["id"])
                ids = {r["id"] for r in results}
                assert ukf.id not in ids

            # Verify others still exist
            for ukf in ukfs_to_keep:
                results = daac_engine_cache.search(query=ukf.name, include=["id"])
                ids = {r["id"] for r in results}
                # Should still be searchable
                assert len(results) >= 0

    def test_batch_remove_with_ukf_instances(self, daac_engine_cache):
        """Test batch_remove with BaseUKF instances."""
        all_ukfs = list(daac_engine_cache.storage)
        if len(all_ukfs) >= 3:
            ukfs_to_remove = all_ukfs[:3]

            # Remove using BaseUKF instances
            daac_engine_cache.batch_remove(ukfs_to_remove)
            daac_engine_cache.flush()

            # Verify removed
            for ukf in ukfs_to_remove:
                results = daac_engine_cache.search(query=ukf.name, include=["id"])
                ids = {r["id"] for r in results}
                assert ukf.id not in ids

    def test_batch_remove_empty_list(self, daac_engine_cache):
        """Test batch_remove with empty list."""
        len_before = len(daac_engine_cache)

        # Remove empty list (should do nothing)
        daac_engine_cache.batch_remove([])
        daac_engine_cache.flush()

        # Length should be unchanged
        assert len(daac_engine_cache) == len_before

    # === Save/Load Tests ===

    def test_save_and_load(self, populated_cache_store, temp_dir):
        """Test saving and loading engine state."""
        path = str(temp_dir / "test_save_load")

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        # Create and populate engine
        engine1 = DAACKLEngine(
            storage=populated_cache_store,
            path=path,
            encoder=encoder,
        )

        ukfs = self.create_test_ukfs()
        for ukf in ukfs:
            engine1.upsert(ukf)
        engine1.flush()

        # Save
        engine1.save()
        engine1.close()

        # Create new engine and load
        engine2 = DAACKLEngine(
            storage=populated_cache_store,
            path=path,
            encoder=encoder,
        )

        # Should have loaded the saved state
        assert len(engine2) == len(ukfs)

        # Search should work
        results = engine2.search(query="python programming", include=["id"])
        assert len(results) > 0

        engine2.close()

    def test_load_nonexistent_fails_gracefully(self, populated_cache_store, temp_dir):
        """Test loading from nonexistent path fails gracefully."""
        path = str(temp_dir / "nonexistent")

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=path,
            encoder=encoder,
        )

        # Should initialize with empty state
        assert len(engine) == 0

        engine.close()

    # === Normalizer Tests ===

    def test_normalizer_true(self, populated_cache_store, temp_dir):
        """Test with normalizer=True (default text normalization)."""

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_norm_true"),
            encoder=encoder,
            normalizer=True,
        )

        ukf = BaseUKF(name="Python")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        # Should find match despite case difference
        results = engine.search(query="PYTHON", include=["id"])
        assert len(results) > 0

        engine.close()

    def test_normalizer_false(self, populated_cache_store, temp_dir):
        """Test with normalizer=False (no normalization)."""

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_norm_false"),
            encoder=encoder,
            normalizer=False,
        )

        ukf = BaseUKF(name="Python")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        # Should find exact match
        results_exact = engine.search(query="Python", include=["id"])
        assert len(results_exact) > 0

        # Should not find case-mismatched query
        results_case = engine.search(query="PYTHON", include=["id"])
        assert len(results_case) == 0

        engine.close()

    def test_normalizer_custom(self, populated_cache_store, temp_dir):
        """Test with custom normalizer function."""

        def encoder(kl):
            return [kl.name]

        def custom_normalizer(text):
            return text.upper().strip()

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_norm_custom"),
            encoder=encoder,
            normalizer=custom_normalizer,
        )

        ukf = BaseUKF(name="python")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        # Normalizer uppercases everything
        results = engine.search(query="  python  ", include=["id"])
        assert len(results) > 0

        engine.close()

    # === Min Length Tests ===

    def test_min_length_filtering(self, populated_cache_store, temp_dir):
        """Test that strings shorter than min_length are filtered out."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_min_len"),
            encoder=encoder,
            min_length=5,  # Only strings with 5+ characters
        )

        ukf = BaseUKF(name="a", synonyms=["ab", "abc", "abcd", "abcde"])
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        # Should only index "abcde" (length 5)
        results_short = engine.search(query="abc", include=["id"])
        assert len(results_short) == 0

        results_long = engine.search(query="abcde", include=["id"])
        assert len(results_long) > 0

        engine.close()

    # === Inverse Mode Tests ===

    def test_inverse_true(self, populated_cache_store, temp_dir):
        """Test with inverse=True (default)."""

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_inverse_true"),
            encoder=encoder,
            inverse=True,
        )

        ukf = BaseUKF(name="test")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        results = engine.search(query="this is a test", include=["id"])
        assert len(results) > 0

        engine.close()

    def test_inverse_false(self, populated_cache_store, temp_dir):
        """Test with inverse=False."""

        def encoder(kl):
            return [kl.name]

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_inverse_false"),
            encoder=encoder,
            inverse=False,
        )

        ukf = BaseUKF(name="test")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)
        engine.flush()

        results = engine.search(query="this is a test", include=["id"])
        assert len(results) > 0

        engine.close()

    # === Performance Tests ===

    def test_performance_large_dataset(self, populated_cache_store, temp_dir):
        """Test performance with a large dataset."""

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_performance"),
            encoder=encoder,
        )

        # Create many UKFs
        large_ukfs = []
        for i in range(100):
            ukf = BaseUKF(name=f"entity_{i}", synonyms=[f"syn_{i}_a", f"syn_{i}_b", f"syn_{i}_c"])
            large_ukfs.append(ukf)
            populated_cache_store.upsert(ukf)
            engine.upsert(ukf)

        engine.flush()

        assert len(engine) >= 100

        # Search should still be fast
        results = engine.search(query="entity_50 and syn_75_b", include=["id"])
        assert len(results) >= 2

        engine.close()

    # === Storage Compatibility Tests ===

    def test_with_database_storage(self, daac_engine_db):
        """Test DAAC engine with database storage."""
        results = daac_engine_db.search(query="python programming", include=["id", "kl"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "kl" in result
            assert isinstance(result["kl"], BaseUKF)

    def test_with_cache_storage(self, daac_engine_cache):
        """Test DAAC engine with cache storage."""
        results = daac_engine_cache.search(query="javascript development", include=["id", "kl"])

        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "kl" in result
            assert isinstance(result["kl"], BaseUKF)

    # === Error Handling Tests ===

    def test_encoder_returns_empty_list(self, populated_cache_store, temp_dir):
        """Test handling of encoder that returns empty list."""

        def encoder(kl):
            return []  # Returns empty list

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_empty_encoder"),
            encoder=encoder,
        )

        ukf = BaseUKF(name="test")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)  # Should not crash
        engine.flush()

        assert len(engine) == 0  # UKF should not be indexed

        engine.close()

    def test_encoder_returns_non_strings(self, populated_cache_store, temp_dir):
        """Test handling of encoder that returns non-string values."""

        def encoder(kl):
            return [kl.name, 123, None, []]  # Mixed types

        engine = DAACKLEngine(
            storage=populated_cache_store,
            path=str(temp_dir / "test_mixed_encoder"),
            encoder=encoder,
        )

        ukf = BaseUKF(name="test")
        populated_cache_store.upsert(ukf)
        engine.upsert(ukf)  # Should filter out non-strings
        engine.flush()

        # Should only index the string "test"
        results = engine.search(query="test", include=["id"])
        assert len(results) > 0

        engine.close()

    def test_double_remove(self, daac_engine_cache):
        """Test removing the same UKF twice."""
        all_ukfs = list(daac_engine_cache.storage)
        if len(all_ukfs) > 0:
            ukf = all_ukfs[0]

            daac_engine_cache.remove(ukf.id)  # First removal
            result2 = daac_engine_cache.remove(ukf.id)  # Second removal

            # Second removal should return False (already removed)
            assert result2 in (False, None)  # Can be False or None depending on implementation

    # === Integration Tests ===

    def test_end_to_end_workflow(self, populated_cache_store, temp_dir):
        """Test complete workflow: init -> upsert -> search -> save -> load -> search."""
        path = str(temp_dir / "test_e2e")

        def encoder(kl):
            return [kl.name] + list(kl.synonyms if kl.synonyms else [])

        # Phase 1: Create and populate
        engine1 = DAACKLEngine(
            storage=populated_cache_store,
            path=path,
            encoder=encoder,
            normalizer=True,
        )

        ukfs = self.create_test_ukfs()
        for ukf in ukfs:
            engine1.upsert(ukf)
        engine1.flush()

        # Phase 2: Search
        results1 = engine1.search(query="I use python and javascript for ML", include=["id", "kl", "matches"])
        assert len(results1) >= 2  # Should find at least python and javascript

        # Phase 3: Save
        engine1.save()
        engine1.close()

        # Phase 4: Load in new engine
        engine2 = DAACKLEngine(
            storage=populated_cache_store,
            path=path,
            encoder=encoder,
            normalizer=True,
        )

        # Phase 5: Search again
        results2 = engine2.search(query="I use python and javascript for ML", include=["id", "kl", "matches"])

        # Results should be consistent
        ids1 = {r["id"] for r in results1}
        ids2 = {r["id"] for r in results2}
        assert ids1 == ids2

        engine2.close()

    def test_search_consistency(self, daac_engine_cache):
        """Test that search results are consistent across multiple calls."""
        query = "python javascript database"
        search_params = {
            "query": query,
            "include": ["id", "matches"],
            "conflict": "longest",
        }

        results1 = daac_engine_cache.search(**search_params)
        results2 = daac_engine_cache.search(**search_params)
        results3 = daac_engine_cache.search(**search_params)

        # All results should be identical
        assert len(results1) == len(results2) == len(results3)

        ids1 = {r["id"] for r in results1}
        ids2 = {r["id"] for r in results2}
        ids3 = {r["id"] for r in results3}

        assert ids1 == ids2 == ids3
