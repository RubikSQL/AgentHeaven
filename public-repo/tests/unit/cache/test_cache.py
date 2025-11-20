"""
Comprehensive cache tests using JSON-based fixtures.

This module tests cache functionality across all backends defined in tests.json.
Focus on public API and BaseUKF round-trip compatibility, no trivial or
backend-specific implementation tests.
"""

import pytest
from ahvn.ukf.templates.basic import KnowledgeUKFT, ExperienceUKFT


class TestCachePublicAPI:
    """Test cache public API across all backends."""

    def test_cache_set_get_roundtrip(self, minimal_cache):
        """Test basic set/get round-trip with various data types."""
        # String value
        minimal_cache.set("func1", output="string_value", arg="test")
        assert minimal_cache.get("func1", arg="test") == "string_value"

        # Dictionary value
        minimal_cache.set("func2", output={"key": "value", "num": 42}, arg="dict")
        result = minimal_cache.get("func2", arg="dict")
        assert result == {"key": "value", "num": 42}

        # List value
        minimal_cache.set("func3", output=[1, 2, 3, "four"], arg="list")
        assert minimal_cache.get("func3", arg="list") == [1, 2, 3, "four"]

        # None value
        minimal_cache.set("func4", output=None, arg="none")
        assert minimal_cache.get("func4", arg="none") is None

    def test_cache_exists_functionality(self, minimal_cache):
        """Test cache existence checking."""
        # Non-existent entry
        assert minimal_cache.exists("nonexistent", arg="test") is False

        # After setting
        minimal_cache.set("test_func", output="value", arg="input")
        assert minimal_cache.exists("test_func", arg="input") is True

        # Different args = different entry
        assert minimal_cache.exists("test_func", arg="other") is False

    def test_cache_clear_functionality(self, minimal_cache):
        """Test cache clearing."""
        # Populate cache
        for i in range(5):
            minimal_cache.set(f"func_{i}", output=f"value_{i}", index=i)

        # Verify populated
        assert minimal_cache.exists("func_0", index=0)
        assert minimal_cache.exists("func_4", index=4)

        # Clear
        minimal_cache.clear()

        # Verify cleared
        assert not minimal_cache.exists("func_0", index=0)
        assert not minimal_cache.exists("func_4", index=4)
        assert len(minimal_cache) == 0

    def test_cache_length_tracking(self, minimal_cache):
        """Test cache length/size tracking."""
        initial_len = len(minimal_cache)

        # Add entries
        minimal_cache.set("func1", output="val1", id=1)
        minimal_cache.set("func2", output="val2", id=2)
        minimal_cache.set("func3", output="val3", id=3)

        # Length should increase
        assert len(minimal_cache) >= initial_len + 3


class TestCacheUKFRoundtrip:
    """Test cache with BaseUKF round-trip scenarios using InMemCache only."""

    def test_cache_knowledge_roundtrip(self, minimal_cache):
        """Test caching Knowledge UKF objects."""
        # Create Knowledge instances
        k1 = KnowledgeUKFT(
            name="Python Basics",
            content="Python is a high-level programming language",
            tags={"[topic:programming]", "[lang:python]"},
        )

        k2 = KnowledgeUKFT(
            name="Testing Best Practices",
            content="Write comprehensive but non-trivial tests",
            tags={"[topic:testing]", "[scope:engineering]"},
        )

        # Cache them using memoize pattern
        minimal_cache.set("get_knowledge", output=k1.to_dict(), topic="python")
        minimal_cache.set("get_knowledge", output=k2.to_dict(), topic="testing")

        # Retrieve and verify
        retrieved_k1 = KnowledgeUKFT.from_dict(minimal_cache.get("get_knowledge", topic="python"))
        assert isinstance(retrieved_k1, KnowledgeUKFT)
        assert retrieved_k1.name == "Python Basics"
        assert "[topic:programming]" in retrieved_k1.tags

        retrieved_k2 = KnowledgeUKFT.from_dict(minimal_cache.get("get_knowledge", topic="testing"))
        assert isinstance(retrieved_k2, KnowledgeUKFT)
        assert retrieved_k2.name == "Testing Best Practices"

    def test_cache_ukf_data_roundtrip(self, minimal_cache):
        """Test caching UKF data (model_dump) across all cache types."""
        # This tests that all caches can handle UKF data dictionaries
        knowledge = KnowledgeUKFT(name="K1", content="Knowledge content", tags={"[test:true]"})
        experience = ExperienceUKFT(name="E1", content="Experience content", priority=10)

        # Use model_dump for universal compatibility
        k_data = knowledge.model_dump()
        e_data = experience.model_dump()

        # Cache the data dictionaries
        minimal_cache.set("get_ukf_data", output=k_data, ukf_type="knowledge", id=1)
        minimal_cache.set("get_ukf_data", output=e_data, ukf_type="experience", id=1)

        # Retrieve and verify
        k_retrieved_data = minimal_cache.get("get_ukf_data", ukf_type="knowledge", id=1)
        e_retrieved_data = minimal_cache.get("get_ukf_data", ukf_type="experience", id=1)

        assert isinstance(k_retrieved_data, dict)
        assert isinstance(e_retrieved_data, dict)
        assert k_retrieved_data["name"] == "K1"
        assert e_retrieved_data["name"] == "E1"
        assert e_retrieved_data["priority"] == 10

        # Can reconstruct objects from data
        k_reconstructed = KnowledgeUKFT(**k_retrieved_data)
        e_reconstructed = ExperienceUKFT(**e_retrieved_data)

        assert k_reconstructed.name == "K1"
        assert e_reconstructed.name == "E1"


class TestCacheMemoization:
    """Test cache memoization patterns."""

    def test_memoize_decorator_pattern(self, minimal_cache):
        """Test using cache with memoize decorator pattern."""
        call_count = {"value": 0}

        @minimal_cache.memoize()
        def expensive_computation(n):
            call_count["value"] += 1
            return n * n

        # First calls - should execute
        result1 = expensive_computation(5)
        assert result1 == 25
        assert call_count["value"] == 1

        result2 = expensive_computation(10)
        assert result2 == 100
        assert call_count["value"] == 2

        # Repeated calls - should use cache
        result3 = expensive_computation(5)
        assert result3 == 25
        assert call_count["value"] == 2  # No new computation

        result4 = expensive_computation(10)
        assert result4 == 100
        assert call_count["value"] == 2  # No new computation

    def test_memoize_with_complex_args(self, minimal_cache):
        """Test memoization with complex argument types."""

        @minimal_cache.memoize()
        def process_data(data: dict, options: list):
            return {
                "processed": True,
                "data_keys": list(data.keys()),
                "options_count": len(options),
            }

        # Call with complex args
        result = process_data({"a": 1, "b": 2}, ["opt1", "opt2"])
        assert result["processed"] is True
        assert result["data_keys"] == ["a", "b"]
        assert result["options_count"] == 2

        # Should retrieve from cache
        cached_result = process_data({"a": 1, "b": 2}, ["opt1", "opt2"])
        assert cached_result == result


class TestCacheEdgeCases:
    """Test cache behavior with edge cases."""

    def test_cache_empty_values(self, minimal_cache):
        """Test caching empty but valid values."""
        # Empty string
        minimal_cache.set("func", output="", key="empty_str")
        assert minimal_cache.get("func", key="empty_str") == ""

        # Empty dict
        minimal_cache.set("func", output={}, key="empty_dict")
        assert minimal_cache.get("func", key="empty_dict") == {}

        # Empty list
        minimal_cache.set("func", output=[], key="empty_list")
        assert minimal_cache.get("func", key="empty_list") == []

        # Zero
        minimal_cache.set("func", output=0, key="zero")
        assert minimal_cache.get("func", key="zero") == 0

        # False
        minimal_cache.set("func", output=False, key="false")
        assert minimal_cache.get("func", key="false") is False

    def test_cache_overwrite_behavior(self, minimal_cache):
        """Test cache behavior when overwriting values."""
        # Set initial value
        minimal_cache.set("func", output="original", key="test")
        assert minimal_cache.get("func", key="test") == "original"

        # Overwrite
        minimal_cache.set("func", output="updated", key="test")
        assert minimal_cache.get("func", key="test") == "updated"

    def test_cache_large_values(self, minimal_cache):
        """Test caching large values."""
        # Large list
        large_list = list(range(1000))
        minimal_cache.set("func", output=large_list, size="large")
        retrieved = minimal_cache.get("func", size="large")
        assert len(retrieved) == 1000
        assert retrieved[0] == 0
        assert retrieved[999] == 999

        # Large dict
        large_dict = {f"key_{i}": f"value_{i}" for i in range(500)}
        minimal_cache.set("func", output=large_dict, type="dict")
        retrieved_dict = minimal_cache.get("func", type="dict")
        assert len(retrieved_dict) == 500
        assert retrieved_dict["key_0"] == "value_0"
        assert retrieved_dict["key_499"] == "value_499"
