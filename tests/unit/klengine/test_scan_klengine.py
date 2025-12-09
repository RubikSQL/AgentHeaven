"""
Tests for ScanKLEngine with brute-force scan functionality.

This module tests the ScanKLEngine class which performs search by scanning
through the entire attached KLStore and using `eval_filter` on each KL.

The tests cover:
- Basic initialization and configuration
- Search operations with various operators (AND, OR, NOT, LIKE, BETWEEN, etc.)
- Global facets and filtering
- Topk and offset support
- Compatibility with different KLStore types
"""

import pytest
from typing import List

from ahvn.ukf.templates.basic.experience import ExperienceUKFT
from ahvn.klengine.scan_engine import ScanKLEngine
from ahvn.utils.klop import KLOp
from ahvn.cache import InMemCache


class TestScanKLEngine:
    """Test ScanKLEngine functionality."""

    def create_test_experiences(self) -> List[ExperienceUKFT]:
        """Create test experiences for search testing."""
        experiences = []

        # Create fibonacci cache experiences
        cache = InMemCache()

        @cache.memoize()
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        # Generate experiences for n=0 to 5
        for i in range(6):
            fibonacci(i)

        # Convert cache entries to experiences
        exps = [ExperienceUKFT.from_cache_entry(entry) for entry in cache]

        # Enhance experiences with metadata and tags
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
                priority=i * 10,
            )
            experiences.append(exp)

        return experiences

    @pytest.fixture
    def populated_klstore(self, minimal_klstore_config):
        """Create a KLStore with test experiences."""
        from fixtures import UniversalFactory, cleanup_instance

        store_type, backend_args = minimal_klstore_config
        klstore = UniversalFactory.create_klstore(store_type, backend_args, label="scan_test")
        klstore.clear()

        # Create and populate with test experiences
        experiences = self.create_test_experiences()
        klstore.batch_upsert(experiences)
        klstore.flush()

        yield klstore
        cleanup_instance(klstore, "klstore")

    @pytest.fixture
    def scan_engine(self, populated_klstore):
        """Create ScanKLEngine attached to populated KLStore."""
        return ScanKLEngine(storage=populated_klstore)

    # === Initialization Tests ===

    def test_initialization(self, populated_klstore):
        """Test ScanKLEngine initialization."""
        engine = ScanKLEngine(storage=populated_klstore)

        assert engine.inplace is True
        assert engine.storage == populated_klstore
        assert engine.exprs is None

    def test_initialization_with_name(self, populated_klstore):
        """Test ScanKLEngine initialization with custom name."""
        engine = ScanKLEngine(storage=populated_klstore, name="custom_scan")

        assert engine.name == "custom_scan"

    def test_initialization_with_facets(self, populated_klstore):
        """Test ScanKLEngine with global facets."""
        global_facets = {"type": "experience"}
        engine = ScanKLEngine(storage=populated_klstore, facets=global_facets)

        assert engine.exprs is not None

    # === Basic Search Tests ===

    def test_search_all(self, scan_engine):
        """Test searching for all items."""
        results = scan_engine.search(include=["id", "kl"])

        assert len(results) == 6
        for result in results:
            assert "id" in result
            assert "kl" in result

    def test_search_with_topk(self, scan_engine):
        """Test search with topk limit."""
        results = scan_engine.search(topk=3, include=["id", "kl"])

        assert len(results) == 3

    def test_search_with_offset(self, scan_engine):
        """Test search with offset."""
        all_results = scan_engine.search(include=["id"])
        offset_results = scan_engine.search(offset=2, include=["id"])

        assert len(offset_results) == len(all_results) - 2

    def test_search_with_topk_and_offset(self, scan_engine):
        """Test search with both topk and offset."""
        results = scan_engine.search(topk=2, offset=1, include=["id"])

        assert len(results) == 2

    # === Filter Tests ===

    def test_search_with_equality_filter(self, scan_engine):
        """Test search with equality filter."""
        results = scan_engine.search(type="experience", include=["id", "kl"])

        assert len(results) == 6
        for result in results:
            assert result["kl"].type == "experience"

    def test_search_with_priority_filter(self, scan_engine):
        """Test search with priority filter using comparison."""
        results = scan_engine.search(priority=KLOp.GTE(30), include=["id", "kl"])

        # Should match priorities 30, 40, 50 (indices 3, 4, 5)
        assert len(results) == 3
        for result in results:
            assert result["kl"].priority >= 30

    def test_search_with_between_filter(self, scan_engine):
        """Test search with BETWEEN filter."""
        results = scan_engine.search(priority=KLOp.BETWEEN(10, 40), include=["id", "kl"])

        # Should match priorities 10, 20, 30, 40 (indices 1, 2, 3, 4)
        assert len(results) == 4
        for result in results:
            assert 10 <= result["kl"].priority <= 40

    def test_search_with_like_filter(self, scan_engine):
        """Test search with LIKE filter on tags."""
        results = scan_engine.search(tags=KLOp.LIKE("%odd%"), include=["id", "kl"])

        # Should match odd indices: 1, 3, 5
        assert len(results) == 3
        for result in results:
            assert any("odd" in tag for tag in result["kl"].tags)

    def test_search_with_in_filter(self, scan_engine):
        """Test search with IN filter."""
        results = scan_engine.search(priority=KLOp.IN([0, 20, 50]), include=["id", "kl"])

        # Should match priorities 0, 20, 50 (indices 0, 2, 5)
        assert len(results) == 3
        for result in results:
            assert result["kl"].priority in [0, 20, 50]

    # === Global Facets Tests ===

    def test_search_with_global_facets(self, populated_klstore):
        """Test ScanKLEngine with global facets."""
        engine = ScanKLEngine(
            storage=populated_klstore,
            facets={"priority": KLOp.GTE(20)},
        )

        results = engine.search(include=["id", "kl"])

        # Should only match priorities >= 20 (indices 2, 3, 4, 5)
        assert len(results) == 4
        for result in results:
            assert result["kl"].priority >= 20

    def test_search_with_global_facets_and_additional_filter(self, populated_klstore):
        """Test ScanKLEngine with global facets plus additional filter."""
        engine = ScanKLEngine(
            storage=populated_klstore,
            facets={"type": "experience"},
        )

        results = engine.search(priority=KLOp.LTE(30), include=["id", "kl"])

        # Should match type=experience AND priority <= 30 (indices 0, 1, 2, 3)
        assert len(results) == 4
        for result in results:
            assert result["kl"].type == "experience"
            assert result["kl"].priority <= 30

    # === No-op Method Tests ===

    def test_upsert_is_noop(self, scan_engine, populated_klstore):
        """Test that upsert is a no-op for ScanKLEngine."""
        initial_count = len(populated_klstore)

        exp = ExperienceUKFT(name="test_new_experience", priority=999)
        scan_engine.upsert(exp)

        # Storage count should remain the same (upsert is no-op)
        assert len(populated_klstore) == initial_count

    def test_remove_is_noop(self, scan_engine, populated_klstore):
        """Test that remove is a no-op for ScanKLEngine."""
        initial_count = len(populated_klstore)
        first_result = scan_engine.search(topk=1, include=["id"])[0]

        scan_engine.remove(first_result["id"])

        # Storage count should remain the same (remove is no-op)
        assert len(populated_klstore) == initial_count

    def test_clear_is_noop(self, scan_engine, populated_klstore):
        """Test that clear is a no-op for ScanKLEngine."""
        initial_count = len(populated_klstore)

        scan_engine.clear()

        # Storage count should remain the same (clear is no-op)
        assert len(populated_klstore) == initial_count

    # === Utility Method Tests ===

    def test_has(self, scan_engine):
        """Test _has method delegates to storage."""
        first_result = scan_engine.search(topk=1, include=["id"])[0]
        assert first_result["id"] in scan_engine

    def test_len(self, scan_engine, populated_klstore):
        """Test __len__ delegates to storage."""
        assert len(scan_engine) == len(populated_klstore)

    def test_iter(self, scan_engine, populated_klstore):
        """Test __iter__ delegates to storage."""
        engine_items = list(scan_engine)
        storage_items = list(populated_klstore)
        assert len(engine_items) == len(storage_items)

    def test_get(self, scan_engine):
        """Test _get method delegates to storage."""
        first_result = scan_engine.search(topk=1, include=["id", "kl"])[0]
        kl = scan_engine.get(first_result["id"])
        assert kl is not None
        assert kl.id == first_result["id"]
