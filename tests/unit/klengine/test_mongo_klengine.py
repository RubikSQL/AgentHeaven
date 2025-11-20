"""
Comprehensive tests for MongoKLEngine.

This module tests the MongoKLEngine class, which operates inplace on a MongoKLStore.

The tests cover all MongoKLEngine functionality including:
- Basic initialization and configuration
- MQL search operations with various filter operators
- Global filters and dynamic filtering
- Pagination (topk, offset)
- Error handling and validation
"""

import pytest
from typing import List

from ahvn.ukf.templates.basic.experience import ExperienceUKFT
from ahvn.klengine.mongo_engine import MongoKLEngine
from ahvn.klstore.mdb_store import MongoKLStore
from ahvn.utils.klop import KLOp
from ahvn.cache import InMemCache


class TestMongoKLEngine:
    """Test MongoKLEngine functionality."""

    def create_test_experiences(self) -> List[ExperienceUKFT]:
        """Create test experiences for search testing."""
        experiences = []
        cache = InMemCache()

        @cache.memoize()
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        for i in range(6):
            fibonacci(i)

        exps = [ExperienceUKFT.from_cache_entry(entry) for entry in cache]

        for i, exp in enumerate(exps):
            exp = exp.clone(
                tags=exp.tags.union(
                    {
                        f"[index:{i}]",
                        "[dataset:TEST_DATA]",
                        f"[fibonacci:{fibonacci(i)}]",
                        f"[parity:{'odd' if i % 2 == 1 else 'even'}]",
                        f"[prime:{'prime' if i in {2, 3, 5} else 'composite'}]" if i > 1 else "[prime:neither]",
                    }
                ),
                metadata={"index": i, "fibonacci_value": fibonacci(i), "is_prime": i in {2, 3, 5} if i > 1 else False, "is_odd": i % 2 == 1},
                priority=i,
            )
            experiences.append(exp)

        return experiences

    @pytest.fixture(scope="function")
    def populated_mongo_klstore(self, minimal_mdb_config, request):
        """Create a MongoKLStore with test experiences."""
        db_name, collection_name = minimal_mdb_config
        # Use test node ID as name for generating unique collection names
        name = request.node.nodeid
        klstore = MongoKLStore(database=db_name, collection=collection_name, name=name)
        klstore.clear()

        experiences = self.create_test_experiences()
        klstore.batch_upsert(experiences)

        yield klstore

        klstore.clear()
        klstore.close()

    @pytest.fixture
    def mongo_engine(self, populated_mongo_klstore):
        """Create MongoKLEngine with inplace=True."""
        return MongoKLEngine(storage=populated_mongo_klstore, sync=True)

    @pytest.fixture
    def mongo_engine_with_filters(self, populated_mongo_klstore):
        """Create MongoKLEngine with global filters."""
        global_filters = {"type": "experience"}
        return MongoKLEngine(storage=populated_mongo_klstore, filters=global_filters, sync=True)

    # === Initialization Tests ===

    def test_initialization(self, populated_mongo_klstore):
        """Test MongoKLEngine initialization."""
        engine = MongoKLEngine(storage=populated_mongo_klstore, sync=True)
        assert engine.inplace is True
        assert engine.storage == populated_mongo_klstore
        assert engine.mdb == populated_mongo_klstore.mdb
        assert engine.adapter == populated_mongo_klstore.adapter
        assert engine.exprs is None

    def test_initialization_with_filters(self, populated_mongo_klstore):
        """Test MongoKLEngine with global filters."""
        global_filters = {"type": "experience", "metadata.is_odd": True}
        engine = MongoKLEngine(storage=populated_mongo_klstore, filters=global_filters, sync=True)
        assert engine.inplace is True
        assert engine.exprs is not None
        # Test that the global filter is applied
        results = engine.search(include=["id"])
        assert len(results) == 3  # 1, 3, 5 are odd

    def test_initialization_fails_without_mongo_store(self):
        """Test that initialization fails if storage is not MongoKLStore in inplace mode."""
        with pytest.raises(ValueError, match="When inplace=True, storage must be a MongoKLStore instance"):
            MongoKLEngine(storage=None, sync=True)

    # === Basic Functionality Tests ===

    def test_len(self, mongo_engine, populated_mongo_klstore):
        """Test that __len__ returns the correct count."""
        mongo_engine.sync()
        assert len(mongo_engine) == len(populated_mongo_klstore)
        assert len(mongo_engine) == 6

    def test_has(self, mongo_engine):
        """Test that _has correctly checks for existence."""
        # ID of the first experience should exist
        mongo_engine.sync()
        first_id = self.create_test_experiences()[0].id
        assert mongo_engine._has(first_id) is True
        # A non-existent ID
        assert mongo_engine._has(99999) is False

    def test_get(self, mongo_engine):
        """Test that _get retrieves the correct item."""
        mongo_engine.sync()
        experiences = self.create_test_experiences()
        first_exp = experiences[0]
        retrieved_exp = mongo_engine._get(first_exp.id, None)
        assert retrieved_exp is not None
        assert retrieved_exp.id == first_exp.id
        assert retrieved_exp.name == first_exp.name

    # === MQL Search Tests (_search_mql) ===

    def test_search_mql_no_filters(self, mongo_engine):
        """Test _search_mql with no filters, should return all items."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Pass empty MQL dict to get all results
        results = mongo_engine.search(mode="mql", mql={}, include=["id"])
        assert len(results) == 6

    def test_search_mql_operator_filter(self, mongo_engine):
        """Test _search_mql with a KLOp operator."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Search for experiences with priority >= 4
        mql = MongoCompiler.compile(expr=KLOp.expr(priority=KLOp.GTE(4)))
        results = mongo_engine.search(mode="mql", mql=mql, include=["id"])
        assert len(results) == 2  # priorities 4, 5

    def test_search_mql_json_filter(self, mongo_engine):
        """Test _search_mql with a JSON (nested field) filter."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Search for experiences where metadata.fibonacci_value is 5
        mql = MongoCompiler.compile(expr=KLOp.expr(metadata=KLOp.JSON(fibonacci_value=5)))
        results = mongo_engine.search(mode="mql", mql=mql, include=["kl"])
        assert len(results) == 1
        assert results[0]["kl"].metadata["fibonacci_value"] == 5

    def test_search_mql_multiple_filters(self, mongo_engine):
        """Test _search_mql with multiple filter conditions."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Search for experiences where priority >= 2 and is_odd is True
        mql = MongoCompiler.compile(expr=KLOp.expr(priority=KLOp.GTE(2), metadata=KLOp.JSON(is_odd=True)))
        results = mongo_engine.search(mode="mql", mql=mql, include=["id"])
        assert len(results) == 2  # indices 3, 5

    def test_search_mql_nf_filter(self, mongo_engine):
        """Test _search_mql with an NF filter on tags."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Search for experiences with a 'prime' tag using normalized form
        # Tags are in format "[key:value]", so we search for slot="prime", value="prime"
        mql = MongoCompiler.compile(expr=KLOp.expr(tags=KLOp.NF(slot="prime", value="prime")))
        results = mongo_engine.search(mode="mql", mql=mql, include=["id"])
        assert len(results) == 3  # indices 2, 3, 5

    def test_search_mql_with_global_filters(self, mongo_engine_with_filters):
        """Test that global filters are applied correctly."""
        from ahvn.utils.mdb.compiler import MongoCompiler

        # Engine is configured to only find 'experience' type
        # This search should find nothing (type=other contradicts global filter)
        mql = MongoCompiler.compile(expr=KLOp.expr(type="other"))
        results = mongo_engine_with_filters.search(mode="mql", mql=mql, include=["id"])
        assert len(results) == 0
        # This search with empty MQL should find all 6 (global filter applied)
        results = mongo_engine_with_filters.search(mode="mql", mql={}, include=["id"])
        assert len(results) == 6

    # === Inplace Operation Tests ===

    def test_inplace_methods_are_no_op(self, mongo_engine):
        """Test that modification methods are no-ops for an inplace engine."""
        initial_count = len(mongo_engine)
        exp = self.create_test_experiences()[0].clone(id=999)

        # These should do nothing
        mongo_engine._upsert(exp)
        mongo_engine._insert(exp)
        mongo_engine._batch_upsert([exp])
        mongo_engine._batch_insert([exp])

        # Count should be unchanged
        assert len(mongo_engine) == initial_count
        assert not mongo_engine._has(999)

        # Removal should also do nothing
        mongo_engine._remove(exp.id)
        mongo_engine._batch_remove([exp.id])
        assert not mongo_engine._has(999)

        # Clear should do nothing
        mongo_engine._clear()
        assert len(mongo_engine) == initial_count
