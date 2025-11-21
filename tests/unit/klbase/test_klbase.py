"""
Comprehensive KLBase integration tests.

This module tests KLBase functionality as an integration layer
that combines multiple storages and engines.

Tests cover: batch operations across multiple storages/engines,
including batch_remove functionality.
"""

import pytest
from ahvn.ukf.templates.basic import KnowledgeUKFT, ExperienceUKFT
from ahvn.klbase import KLBase
from ahvn.klstore import CacheKLStore
from ahvn.cache import InMemCache


@pytest.fixture
def simple_klbase():
    """Create a simple KLBase with two cache stores."""
    store1 = CacheKLStore(name="store1", cache=InMemCache())
    store2 = CacheKLStore(name="store2", cache=InMemCache())

    klbase = KLBase(storages=[store1, store2], engines=[], name="test_klbase")

    yield klbase

    # Cleanup
    klbase.clear()


@pytest.fixture
def populated_klbase(simple_klbase):
    """Create a KLBase populated with test data."""
    knowledges = [KnowledgeUKFT(name=f"Knowledge {i}", content=f"Content {i}", priority=i) for i in range(10)]

    # Add to both stores
    for knowledge in knowledges:
        simple_klbase.upsert(knowledge)

    return simple_klbase


class TestKLBaseBatchRemove:
    """Test KLBase batch_remove functionality."""

    def test_batch_remove_basic(self, populated_klbase):
        """Test basic batch_remove across all storages."""
        # Get some knowledge items
        all_knowledges = list(populated_klbase.storages["store1"])
        keys_to_remove = [all_knowledges[i].id for i in range(3)]

        # Batch remove from all storages
        populated_klbase.batch_remove(keys_to_remove)

        # Verify removed from all storages
        for storage_name, storage in populated_klbase.storages.items():
            for key in keys_to_remove:
                assert key not in storage

        # Verify others still exist
        for i in range(3, 10):
            assert all_knowledges[i].id in populated_klbase.storages["store1"]
            assert all_knowledges[i].id in populated_klbase.storages["store2"]

    def test_batch_remove_with_ukf_instances(self, populated_klbase):
        """Test batch_remove with BaseUKF instances."""
        all_knowledges = list(populated_klbase.storages["store1"])
        ukfs_to_remove = all_knowledges[:3]

        # Remove using BaseUKF instances
        populated_klbase.batch_remove(ukfs_to_remove)

        # Verify removed from all storages
        for storage in populated_klbase.storages.values():
            for ukf in ukfs_to_remove:
                assert ukf.id not in storage

    def test_batch_remove_with_string_ids(self, populated_klbase):
        """Test batch_remove with string IDs."""
        all_knowledges = list(populated_klbase.storages["store1"])
        string_ids = [str(all_knowledges[i].id) for i in range(3)]

        # Remove using string IDs
        populated_klbase.batch_remove(string_ids)

        # Verify removed
        for storage in populated_klbase.storages.values():
            for str_id in string_ids:
                assert int(str_id) not in storage

    def test_batch_remove_specific_storages(self, populated_klbase):
        """Test batch_remove from specific storages only."""
        all_knowledges = list(populated_klbase.storages["store1"])
        keys_to_remove = [all_knowledges[i].id for i in range(3)]

        # Remove only from store1
        populated_klbase.batch_remove(keys_to_remove, storages=["store1"])

        # Verify removed from store1
        for key in keys_to_remove:
            assert key not in populated_klbase.storages["store1"]

        # Verify still in store2
        for key in keys_to_remove:
            assert key in populated_klbase.storages["store2"]

    def test_batch_remove_specific_engines(self, simple_klbase):
        """Test batch_remove from specific engines only."""
        # For this test, we'd need engines configured
        # This is a placeholder for when engines are involved
        knowledges = [KnowledgeUKFT(name=f"Engine Test {i}", content=f"Content {i}") for i in range(3)]

        for k in knowledges:
            simple_klbase.upsert(k)

        # When only engines parameter is specified, storages still default to all
        # To remove only from engines, need to explicitly pass storages=[]
        simple_klbase.batch_remove([k.id for k in knowledges], storages=[], engines=[])

        # Items should still be in storages (only engines were targeted)
        for k in knowledges:
            assert k.id in simple_klbase.storages["store1"]

    def test_batch_remove_mixed_types(self, populated_klbase):
        """Test batch_remove with mixed int, string, and BaseUKF types."""
        all_knowledges = list(populated_klbase.storages["store1"])

        # Mix of types
        mixed_keys = [all_knowledges[0].id, str(all_knowledges[1].id), all_knowledges[2], all_knowledges[3].id]

        # Remove
        populated_klbase.batch_remove(mixed_keys)

        # Verify all removed
        for i in range(4):
            for storage in populated_klbase.storages.values():
                assert all_knowledges[i].id not in storage

    def test_batch_remove_empty_list(self, populated_klbase):
        """Test batch_remove with empty list."""
        # Count items before
        count_before = len(populated_klbase.storages["store1"])

        # Remove empty list
        populated_klbase.batch_remove([])

        # Count should be unchanged
        count_after = len(populated_klbase.storages["store1"])
        assert count_before == count_after

    def test_batch_remove_from_empty_storages(self, simple_klbase):
        """Test batch_remove when storages are empty."""
        # Try to remove from empty KLBase
        simple_klbase.batch_remove([999999, 888888, 777777])

        # Should complete without error
        assert len(simple_klbase.storages["store1"]) == 0

    def test_batch_remove_all_storages_all_engines(self, populated_klbase):
        """Test batch_remove with storages=None and engines=None (all)."""
        all_knowledges = list(populated_klbase.storages["store1"])
        keys_to_remove = [all_knowledges[i].id for i in range(5)]

        # Remove from all (None means all)
        populated_klbase.batch_remove(keys_to_remove, storages=None, engines=None)

        # Verify removed from all storages
        for storage in populated_klbase.storages.values():
            for key in keys_to_remove:
                assert key not in storage

    def test_batch_remove_nonexistent_storage_name(self, populated_klbase):
        """Test batch_remove with non-existent storage name."""
        all_knowledges = list(populated_klbase.storages["store1"])
        keys_to_remove = [all_knowledges[0].id]

        # Try to remove from non-existent storage (should be ignored)
        populated_klbase.batch_remove(keys_to_remove, storages=["nonexistent_store"])

        # Items should still exist in actual storages
        assert all_knowledges[0].id in populated_klbase.storages["store1"]

    def test_batch_remove_large_batch(self, simple_klbase):
        """Test batch_remove with large batch of items."""
        # Create many items
        knowledges = [KnowledgeUKFT(name=f"Large Batch {i}", content=f"Content {i}") for i in range(100)]

        for k in knowledges:
            simple_klbase.upsert(k)

        # Remove all at once
        keys = [k.id for k in knowledges]
        simple_klbase.batch_remove(keys)

        # Verify all removed
        for k in knowledges:
            for storage in simple_klbase.storages.values():
                assert k.id not in storage

    def test_batch_remove_duplicate_keys(self, populated_klbase):
        """Test batch_remove with duplicate keys in list."""
        all_knowledges = list(populated_klbase.storages["store1"])
        key_to_remove = all_knowledges[0].id

        # Remove with duplicates
        populated_klbase.batch_remove([key_to_remove, key_to_remove, key_to_remove])

        # Should be removed (idempotent)
        for storage in populated_klbase.storages.values():
            assert key_to_remove not in storage


class TestKLBaseIntegration:
    """Test KLBase integration with batch operations."""

    def test_batch_upsert_then_batch_remove(self, simple_klbase):
        """Test full cycle of batch_upsert followed by batch_remove."""
        knowledges = [KnowledgeUKFT(name=f"Cycle Test {i}", content=f"Content {i}") for i in range(10)]

        # Batch upsert
        simple_klbase.batch_upsert(knowledges)

        # Verify all exist
        for k in knowledges:
            for storage in simple_klbase.storages.values():
                assert k.id in storage

        # Batch remove half
        keys_to_remove = [knowledges[i].id for i in range(5)]
        simple_klbase.batch_remove(keys_to_remove)

        # Verify removed
        for i in range(5):
            for storage in simple_klbase.storages.values():
                assert knowledges[i].id not in storage

        # Verify others remain
        for i in range(5, 10):
            for storage in simple_klbase.storages.values():
                assert knowledges[i].id in storage

    def test_multiple_batch_remove_operations(self, populated_klbase):
        """Test multiple consecutive batch_remove operations."""
        all_knowledges = list(populated_klbase.storages["store1"])

        # Remove in batches
        populated_klbase.batch_remove([all_knowledges[0].id, all_knowledges[1].id])
        populated_klbase.batch_remove([all_knowledges[2].id, all_knowledges[3].id])
        populated_klbase.batch_remove([all_knowledges[4].id])

        # Verify first 5 removed
        for i in range(5):
            for storage in populated_klbase.storages.values():
                assert all_knowledges[i].id not in storage

        # Verify rest remain
        for i in range(5, 10):
            for storage in populated_klbase.storages.values():
                assert all_knowledges[i].id in storage
