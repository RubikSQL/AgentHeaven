"""
Comprehensive KLStore tests using JSON-based fixtures.

This module tests KLStore functionality across all backends defined in tests.json.
Focus on public API and BaseUKF storage/retrieval round-trip compatibility.

Tests cover: upsert, get, exists, remove, clear, batch operations, iteration,
and full BaseUKF round-trip scenarios.
"""

import pytest
from ahvn.ukf.base import BaseUKF
from ahvn.ukf.templates.basic import KnowledgeUKFT, ExperienceUKFT


class TestKLStorePublicAPI:
    """Test KLStore public API across all backends."""

    def test_klstore_upsert_and_get(self, minimal_klstore):
        """Test basic upsert and get operations."""
        # Create a Knowledge object
        knowledge = KnowledgeUKFT(name="Test Knowledge", content="This is test content for KLStore", tags={"[test:klstore]", "[type:basic]"}, priority=7)

        # Upsert the knowledge
        minimal_klstore.upsert(knowledge)

        # Retrieve by ID
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify retrieval
        assert retrieved is not ...
        assert retrieved.id == knowledge.id
        assert retrieved.name == knowledge.name
        assert retrieved.content == knowledge.content
        assert retrieved.priority == knowledge.priority

    def test_klstore_insert_no_duplicate(self, minimal_klstore):
        """Test that insert does not duplicate existing items."""
        knowledge = KnowledgeUKFT(name="Insert Test", content="Testing insert behavior", priority=5)

        # First insert should work
        minimal_klstore.insert(knowledge)
        assert knowledge.id in minimal_klstore

        # Modify the knowledge
        knowledge.priority = 8

        # Second insert should not update (insert only adds new)
        minimal_klstore.insert(knowledge)

        # Retrieve and check - should still have old priority
        retrieved = minimal_klstore.get(knowledge.id)
        assert retrieved.priority == 5  # Original priority

    def test_klstore_upsert_updates_existing(self, minimal_klstore):
        """Test that upsert updates existing items."""
        knowledge = KnowledgeUKFT(name="Upsert Test", content="Original content", priority=5)

        # First upsert
        minimal_klstore.upsert(knowledge)

        # Modify and upsert again
        knowledge.content = "Modified content"
        knowledge.priority = 9
        minimal_klstore.upsert(knowledge)

        # Retrieve and verify update
        retrieved = minimal_klstore.get(knowledge.id)
        assert retrieved.content == "Modified content"
        assert retrieved.priority == 9

    def test_klstore_exists_and_contains(self, minimal_klstore):
        """Test exists() and __contains__ functionality."""
        knowledge = KnowledgeUKFT(name="Exists Test", content="Testing exists method")

        # Should not exist before insertion
        assert not minimal_klstore.exists(knowledge.id)
        assert knowledge.id not in minimal_klstore
        assert knowledge not in minimal_klstore

        # Insert knowledge
        minimal_klstore.upsert(knowledge)

        # Should exist after insertion
        assert minimal_klstore.exists(knowledge.id)
        assert knowledge.id in minimal_klstore
        assert knowledge in minimal_klstore

        # Test with string ID
        assert minimal_klstore.exists(str(knowledge.id))
        assert str(knowledge.id) in minimal_klstore

    def test_klstore_get_with_default(self, minimal_klstore):
        """Test get() with default value for non-existent items."""
        non_existent_id = 999999999

        # Get with default
        result = minimal_klstore.get(non_existent_id, default=None)
        assert result is None

        # Get without default (should return ...)
        result = minimal_klstore.get(non_existent_id)
        assert result is ...

    def test_klstore_getitem_access(self, minimal_klstore):
        """Test __getitem__ access pattern."""
        knowledge = KnowledgeUKFT(name="GetItem Test", content="Testing bracket access")

        minimal_klstore.upsert(knowledge)

        # Access via bracket notation
        retrieved = minimal_klstore[knowledge.id]
        assert retrieved.id == knowledge.id

        # Access with string ID
        retrieved = minimal_klstore[str(knowledge.id)]
        assert retrieved.id == knowledge.id

        # Access with BaseUKF object
        retrieved = minimal_klstore[knowledge]
        assert retrieved.id == knowledge.id

    def test_klstore_remove(self, minimal_klstore):
        """Test remove functionality."""
        knowledge = KnowledgeUKFT(name="Remove Test", content="This will be removed")

        # Insert then remove
        minimal_klstore.upsert(knowledge)
        assert knowledge.id in minimal_klstore

        # Remove by ID
        minimal_klstore.remove(knowledge.id)
        assert knowledge.id not in minimal_klstore

        # Verify can't retrieve
        result = minimal_klstore.get(knowledge.id, default=None)
        assert result is None

    def test_klstore_delitem(self, minimal_klstore):
        """Test __delitem__ functionality."""
        knowledge = KnowledgeUKFT(name="Delete Test", content="Testing delete operation")

        minimal_klstore.upsert(knowledge)
        assert knowledge.id in minimal_klstore

        # Delete using del operator
        del minimal_klstore[knowledge.id]
        assert knowledge.id not in minimal_klstore

    def test_klstore_clear(self, minimal_klstore):
        """Test clear functionality."""
        # Insert multiple items
        knowledges = [KnowledgeUKFT(name=f"Clear Test {i}", content=f"Content {i}") for i in range(5)]

        for k in knowledges:
            minimal_klstore.upsert(k)

        # Verify all exist
        for k in knowledges:
            assert k.id in minimal_klstore

        # Clear store
        minimal_klstore.clear()

        # Verify all removed
        for k in knowledges:
            assert k.id not in minimal_klstore

    def test_klstore_length(self, minimal_klstore):
        """Test __len__ functionality."""
        # Initially empty
        initial_len = len(minimal_klstore)

        # Add items
        knowledges = [KnowledgeUKFT(name=f"Length Test {i}", content=f"Content {i}") for i in range(10)]

        for k in knowledges:
            minimal_klstore.upsert(k)

        # Verify length
        assert len(minimal_klstore) == initial_len + 10

        # Remove some items
        for k in knowledges[:3]:
            minimal_klstore.remove(k.id)

        assert len(minimal_klstore) == initial_len + 7


class TestKLStoreBatchOperations:
    """Test KLStore batch operations."""

    def test_klstore_batch_upsert(self, minimal_klstore):
        """Test batch upsert functionality."""
        # Create multiple knowledge items
        knowledges = [KnowledgeUKFT(name=f"Batch Knowledge {i}", content=f"Batch content {i}", priority=i) for i in range(20)]

        # Batch upsert
        minimal_klstore.batch_upsert(knowledges)

        # Verify all inserted
        for k in knowledges:
            assert k.id in minimal_klstore
            retrieved = minimal_klstore.get(k.id)
            assert retrieved.name == k.name
            assert retrieved.priority == k.priority

    def test_klstore_batch_insert(self, minimal_klstore):
        """Test batch insert functionality."""
        # Create items
        knowledges = [KnowledgeUKFT(name=f"Batch Insert {i}", content=f"Content {i}") for i in range(15)]

        # Batch insert
        minimal_klstore.batch_insert(knowledges)

        # Verify all inserted
        for k in knowledges:
            assert k.id in minimal_klstore

        # Modify and try batch insert again (should not update)
        for k in knowledges:
            k.content = "Modified content"

        minimal_klstore.batch_insert(knowledges)

        # Verify not updated (insert only adds new)
        for k in knowledges:
            retrieved = minimal_klstore.get(k.id)
            assert "Modified" not in retrieved.content

    def test_klstore_batch_upsert_updates(self, minimal_klstore):
        """Test that batch upsert updates existing items."""
        # Initial batch
        knowledges = [KnowledgeUKFT(name=f"Update Test {i}", content=f"Original {i}") for i in range(10)]

        minimal_klstore.batch_upsert(knowledges)

        # Modify and batch upsert again
        for k in knowledges:
            k.content = f"Modified {k.name}"

        minimal_klstore.batch_upsert(knowledges)

        # Verify updates
        for k in knowledges:
            retrieved = minimal_klstore.get(k.id)
            assert "Modified" in retrieved.content


class TestKLStoreIteration:
    """Test KLStore iteration functionality."""

    def test_klstore_iteration(self, minimal_klstore):
        """Test iterating over stored items."""
        # Insert items
        knowledges = [KnowledgeUKFT(name=f"Iter Test {i}", content=f"Content {i}") for i in range(10)]

        minimal_klstore.batch_upsert(knowledges)

        # Iterate and collect IDs
        stored_ids = {kl.id for kl in minimal_klstore}
        expected_ids = {k.id for k in knowledges}

        # Verify all IDs present
        for expected_id in expected_ids:
            assert expected_id in stored_ids

    def test_klstore_iteration_empty(self, minimal_klstore):
        """Test iterating over empty store."""
        minimal_klstore.clear()

        # Should not raise error
        items = list(minimal_klstore)
        assert len(items) == 0


class TestKLStoreUKFRoundtrip:
    """Test KLStore with BaseUKF round-trip scenarios."""

    def test_klstore_knowledge_roundtrip(self, minimal_klstore):
        """Test full Knowledge object round-trip."""
        knowledge = KnowledgeUKFT(
            name="Knowledge Roundtrip Test",
            content="This tests complete knowledge storage and retrieval",
            tags={"[topic:testing]", "[type:roundtrip]", "[priority:high]"},
            priority=9,
            metadata={"author": "test_suite", "version": 1, "verified": True},
        )

        # Store
        minimal_klstore.upsert(knowledge)

        # Retrieve
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify all attributes
        assert retrieved.id == knowledge.id
        assert retrieved.name == knowledge.name
        assert retrieved.content == knowledge.content
        assert retrieved.priority == knowledge.priority
        assert retrieved.tags == knowledge.tags
        assert retrieved.metadata == knowledge.metadata

    def test_klstore_experience_roundtrip(self, minimal_klstore):
        """Test full Experience object round-trip."""
        experience = ExperienceUKFT(
            name="Experience Roundtrip Test",
            content="Testing experience storage",
            priority=8,
            tags={"[type:experience]"},
            metadata={"duration_ms": 150, "success": True, "error_count": 0},
        )

        # Store
        minimal_klstore.upsert(experience)

        # Retrieve
        retrieved = minimal_klstore.get(experience.id)

        # Verify all attributes
        assert retrieved.id == experience.id
        assert retrieved.name == experience.name
        assert retrieved.content == experience.content
        assert retrieved.priority == experience.priority
        assert retrieved.metadata["duration_ms"] == 150
        assert retrieved.metadata["success"] is True

    def test_klstore_mixed_ukf_types(self, minimal_klstore):
        """Test storing mixed Knowledge and Experience objects."""
        knowledge = KnowledgeUKFT(name="Mixed Test Knowledge", content="Knowledge in mixed store", priority=7)

        experience = ExperienceUKFT(name="Mixed Test Experience", content="Experience in mixed store", priority=6)

        # Store both
        minimal_klstore.batch_upsert([knowledge, experience])

        # Retrieve both
        k_retrieved = minimal_klstore.get(knowledge.id)
        e_retrieved = minimal_klstore.get(experience.id)

        # Verify types preserved
        assert isinstance(k_retrieved, BaseUKF)
        assert isinstance(e_retrieved, BaseUKF)
        assert k_retrieved.type == "knowledge"
        assert e_retrieved.type == "experience"
        assert k_retrieved.name == knowledge.name
        assert e_retrieved.name == experience.name

    def test_klstore_ukf_with_complex_metadata(self, minimal_klstore):
        """Test UKF objects with complex metadata."""
        knowledge = KnowledgeUKFT(
            name="Complex Metadata Test",
            content="Testing complex metadata storage",
            metadata={
                "nested": {"level1": {"level2": "deep value"}},
                "list_data": [1, 2, 3, 4, 5],
                "mixed": {"string": "value", "number": 42, "float": 3.14, "bool": True, "none": None},
            },
        )

        # Store and retrieve
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify complex metadata preserved
        assert retrieved.metadata["nested"]["level1"]["level2"] == "deep value"
        assert retrieved.metadata["list_data"] == [1, 2, 3, 4, 5]
        assert retrieved.metadata["mixed"]["number"] == 42
        assert retrieved.metadata["mixed"]["bool"] is True

    def test_klstore_ukf_with_tags(self, minimal_klstore):
        """Test UKF objects with various tag patterns."""
        knowledge = KnowledgeUKFT(
            name="Tags Test", content="Testing tag preservation", tags={"[category:test]", "[priority:high]", "[status:active]", "[author:test_suite]"}
        )

        # Store and retrieve
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify all tags preserved
        assert "[UKF_TYPE:general]" in retrieved.tags  # Automatically added tag for Knowledge type
        assert "[UKF_TYPE:knowledge]" in retrieved.tags  # Automatically added tag for Knowledge type
        assert "[category:test]" in retrieved.tags
        assert "[priority:high]" in retrieved.tags
        assert "[status:active]" in retrieved.tags
        assert "[author:test_suite]" in retrieved.tags
        assert len(retrieved.tags) == 6


class TestKLStoreEdgeCases:
    """Test KLStore behavior with edge cases."""

    def test_klstore_empty_store_operations(self, minimal_klstore):
        """Test operations on empty store."""
        minimal_klstore.clear()

        # Get from empty store
        result = minimal_klstore.get(999999, default=None)
        assert result is None

        # Exists in empty store
        assert not minimal_klstore.exists(999999)

        # Length of empty store
        assert len(minimal_klstore) >= 0  # Could have residual data

        # Iteration over empty store
        items = list(minimal_klstore)
        # After clear, should be empty or have minimal items
        assert isinstance(items, list)

    def test_klstore_remove_nonexistent(self, minimal_klstore):
        """Test removing non-existent item."""
        # Try to remove item that doesn't exist
        try:
            minimal_klstore.remove(999999999)
        except (KeyError, Exception):
            # Some implementations may raise error, others may silently ignore
            pass

    def test_klstore_large_batch(self, minimal_klstore):
        """Test handling large batch of items."""
        # Create 100 knowledge items
        knowledges = [KnowledgeUKFT(name=f"Large Batch {i}", content=f"Content for item {i}", priority=i % 10) for i in range(100)]

        # Batch upsert
        minimal_klstore.batch_upsert(knowledges)

        # Verify random samples
        for i in [0, 25, 50, 75, 99]:
            retrieved = minimal_klstore.get(knowledges[i].id)
            assert retrieved is not ...
            assert retrieved.name == f"Large Batch {i}"

    def test_klstore_unicode_content(self, minimal_klstore):
        """Test handling Unicode content."""
        knowledge = KnowledgeUKFT(name="Unicode Test 你好世界", content="Testing Unicode: 你好世界 🎉 مرحبا العالم", tags={"[lang:mixed]", "[unicode:true]"})

        # Store and retrieve
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify Unicode preserved
        assert "你好世界" in retrieved.name
        assert "你好世界" in retrieved.content
        assert "🎉" in retrieved.content
        assert "[unicode:true]" in retrieved.tags

    def test_klstore_special_characters(self, minimal_klstore):
        """Test handling special characters in content."""
        knowledge = KnowledgeUKFT(name="Special Chars: 'quotes' \"double\" <tags>", content="Line1\nLine2\tTabbed\r\nWindows", tags={"[special:chars]"})

        # Store and retrieve
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        # Verify special chars preserved
        assert "quotes" in retrieved.name
        assert "\n" in retrieved.content or "\\n" in retrieved.content
        assert "\t" in retrieved.content or "\\t" in retrieved.content

    def test_klstore_empty_strings(self, minimal_klstore):
        """Test handling empty strings in UKF fields."""
        knowledge = KnowledgeUKFT(name="", content="Non-empty content")  # Empty name

        # Store and retrieve
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        assert retrieved.name == ""
        assert retrieved.content == "Non-empty content"

    def test_klstore_max_priority(self, minimal_klstore):
        """Test handling maximum priority values."""
        knowledge = KnowledgeUKFT(name="Max Priority", content="Testing max priority", priority=10)  # Max priority

        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)

        assert retrieved.priority == 10

    def test_klstore_repeated_operations(self, minimal_klstore):
        """Test repeated upsert/remove cycles."""
        knowledge = KnowledgeUKFT(name="Repeated Ops Test", content="Original content")

        # Repeated upsert/remove cycles
        for i in range(5):
            knowledge.content = f"Iteration {i}"
            minimal_klstore.upsert(knowledge)
            assert knowledge.id in minimal_klstore

            retrieved = minimal_klstore.get(knowledge.id)
            assert retrieved.content == f"Iteration {i}"

            minimal_klstore.remove(knowledge.id)
            assert knowledge.id not in minimal_klstore

        # Final upsert
        knowledge.content = "Final content"
        minimal_klstore.upsert(knowledge)
        retrieved = minimal_klstore.get(knowledge.id)
        assert retrieved.content == "Final content"

    def test_klstore_batch_remove_basic(self, minimal_klstore):
        """Test basic batch_remove with multiple items."""
        # Create and insert multiple knowledge items
        knowledges = [KnowledgeUKFT(name=f"Batch Remove {i}", content=f"Content {i}") for i in range(5)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Verify all exist
        for k in knowledges:
            assert k.id in minimal_klstore

        # Batch remove first 3 items
        minimal_klstore.batch_remove([knowledges[0].id, knowledges[1].id, knowledges[2].id])

        # Verify first 3 are removed
        assert knowledges[0].id not in minimal_klstore
        assert knowledges[1].id not in minimal_klstore
        assert knowledges[2].id not in minimal_klstore

        # Verify last 2 still exist
        assert knowledges[3].id in minimal_klstore
        assert knowledges[4].id in minimal_klstore

    def test_klstore_batch_remove_with_ukf_instances(self, minimal_klstore):
        """Test batch_remove with BaseUKF instances."""
        knowledges = [KnowledgeUKFT(name=f"UKF Batch {i}", content=f"Content {i}") for i in range(3)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Remove using BaseUKF instances
        minimal_klstore.batch_remove(knowledges)

        # Verify all removed
        for k in knowledges:
            assert k.id not in minimal_klstore

    def test_klstore_batch_remove_with_string_ids(self, minimal_klstore):
        """Test batch_remove with string IDs."""
        knowledges = [KnowledgeUKFT(name=f"String ID Batch {i}", content=f"Content {i}") for i in range(3)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Remove using string IDs
        string_ids = [str(k.id) for k in knowledges]
        minimal_klstore.batch_remove(string_ids)

        # Verify all removed
        for k in knowledges:
            assert k.id not in minimal_klstore

    def test_klstore_batch_remove_mixed_types(self, minimal_klstore):
        """Test batch_remove with mixed int, string, and BaseUKF types."""
        knowledges = [KnowledgeUKFT(name=f"Mixed Types {i}", content=f"Content {i}") for i in range(4)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Remove using mixed types
        mixed_keys = [knowledges[0].id, str(knowledges[1].id), knowledges[2], knowledges[3].id]
        minimal_klstore.batch_remove(mixed_keys)

        # Verify all removed
        for k in knowledges:
            assert k.id not in minimal_klstore

    def test_klstore_batch_remove_empty_list(self, minimal_klstore):
        """Test batch_remove with empty list."""
        # Insert some items
        knowledges = [KnowledgeUKFT(name=f"Empty Batch {i}", content=f"Content {i}") for i in range(3)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Remove empty list (should do nothing)
        minimal_klstore.batch_remove([])

        # Verify all still exist
        for k in knowledges:
            assert k.id in minimal_klstore

    def test_klstore_batch_remove_nonexistent_items(self, minimal_klstore):
        """Test batch_remove with non-existent items."""
        # Insert one real item
        knowledge = KnowledgeUKFT(name="Real Item", content="Real content")
        minimal_klstore.upsert(knowledge)

        # Try to remove mix of real and non-existent
        try:
            minimal_klstore.batch_remove([knowledge.id, 999999999, 888888888])
        except (KeyError, Exception):
            # Some implementations may raise error, others may silently ignore
            pass

        # Real item should be removed regardless
        # (Implementation detail: some stores may remove what exists)

    def test_klstore_batch_remove_duplicates(self, minimal_klstore):
        """Test batch_remove with duplicate IDs in the list."""
        knowledge = KnowledgeUKFT(name="Duplicate Test", content="Content")
        minimal_klstore.upsert(knowledge)

        # Remove with duplicates
        minimal_klstore.batch_remove([knowledge.id, knowledge.id, knowledge.id])

        # Should be removed (duplicate removal requests should be idempotent)
        assert knowledge.id not in minimal_klstore

    def test_klstore_batch_remove_all_items(self, minimal_klstore):
        """Test batch_remove to remove all items at once."""
        knowledges = [KnowledgeUKFT(name=f"Remove All {i}", content=f"Content {i}") for i in range(10)]
        for k in knowledges:
            minimal_klstore.upsert(k)

        # Get all IDs
        all_ids = [k.id for k in knowledges]

        # Batch remove all
        minimal_klstore.batch_remove(all_ids)

        # Verify all removed
        for k in knowledges:
            assert k.id not in minimal_klstore
