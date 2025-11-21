"""\
Tests for special cache implementations: NoCache and CallbackCache.

These caches are not meant to be used as traditional KV stores but as
memoization decorators with special behaviors:
- NoCache: Returns function as-is (always recomputes)
- CallbackCache: Integrates with 3rd-party services via callbacks and feeds
"""

__all__ = [
    "TestNoCache",
    "TestCallbackCache",
]

import pytest
import sys
from pathlib import Path

# Add tests directory to Python path for imports
TESTS_DIR = Path(__file__).resolve().parents[1]
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from ahvn.cache import NoCache, CallbackCache


class TestNoCache:
    """Test NoCache implementation - a no-op cache that always recomputes."""

    def test_nocache_basic_operations(self):
        """Test that NoCache never stores anything."""
        cache = NoCache()

        # Set operations should work but not store anything
        cache.set("test_func", output="test_value", param="hello")

        # Get operations should always return Ellipsis
        result = cache.get("test_func", param="hello")
        assert result is ...

        # Exists should always return False
        assert not cache.exists("test_func", param="hello")

        # Length should always be 0
        assert len(cache) == 0

        # Clear should be a no-op
        cache.clear()  # Should not raise

    def test_nocache_with_default_values(self):
        """Test NoCache get operations with default values."""
        cache = NoCache()

        # Get should always return Ellipsis (no default parameter support)
        result = cache.get("missing_func", param="test")
        assert result is ...

        # The BaseCache.get() method doesn't have a default parameter
        # It always returns Ellipsis for cache misses

    def test_nocache_memoize_always_recomputes(self):
        """Test that NoCache memoize decorator always recomputes functions."""
        cache = NoCache()
        call_count = 0

        @cache.memoize
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x * y + call_count

        # First call
        result1 = expensive_function(2, 3)
        assert result1 == 7  # 2*3 + 1
        assert call_count == 1

        # Second call with same args - should recompute
        result2 = expensive_function(2, 3)
        assert result2 == 8  # 2*3 + 2
        assert call_count == 2

        # Third call with different args - should also recompute
        result3 = expensive_function(3, 4)
        assert result3 == 15  # 3*4 + 3
        assert call_count == 3

    def test_nocache_memoize_with_exception(self):
        """Test NoCache memoize with functions that raise exceptions."""
        cache = NoCache()
        call_count = 0

        @cache.memoize
        def failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Test exception #{call_count}")

        # First call should raise exception
        with pytest.raises(ValueError, match="Test exception #1"):
            failing_function()
        assert call_count == 1

        # Second call should raise different exception (NoCache always recomputes)
        with pytest.raises(ValueError, match="Test exception #2"):
            failing_function()
        assert call_count == 2  # NoCache always recomputes

    def test_nocache_exclude_parameter(self):
        """Test NoCache with exclude parameter."""
        cache = NoCache(exclude=["session_id"])

        @cache.memoize
        def func_with_session(data, session_id):
            return f"data:{data},session:{session_id}"

        # Different session_id should still cause recomputation (since it's excluded from cache key)
        result1 = func_with_session("test", session_id="abc123")
        result2 = func_with_session("test", session_id="def456")

        # Both should have been computed separately
        assert result1 == "data:test,session:abc123"
        assert result2 == "data:test,session:def456"


class TestCallbackCache:
    """Test CallbackCache implementation - integrates with 3rd-party services."""

    def test_callbackcache_basic_operations(self):
        """Test CallbackCache basic operations without custom callbacks/feeds."""
        cache = CallbackCache()

        # Set should work but not store locally
        cache.set("test_func", output="test_value", param="hello")

        # Get should return Ellipsis when no feeds provide value
        result = cache.get("test_func", param="hello")
        assert result is ...

        # Length should always be 0
        assert len(cache) == 0

        # Should raise NotImplementedError for unsupported operations
        with pytest.raises(NotImplementedError):
            cache.exists("test_func", param="hello")

        with pytest.raises(NotImplementedError):
            cache._has(123)

        with pytest.raises(NotImplementedError):
            cache._get(123)

        with pytest.raises(NotImplementedError):
            cache._remove(123)

        with pytest.raises(NotImplementedError):
            cache._clear()

    def test_callbackcache_with_custom_callbacks(self):
        """Test CallbackCache with custom callbacks."""
        callback_results = []

        def test_callback(key, value):
            callback_results.append((key, value))

        cache = CallbackCache(callbacks=[test_callback])

        # Set should trigger the callback
        cache.set("test_func", output="cached_value", param="test")

        assert len(callback_results) == 1
        key, value = callback_results[0]
        assert value["output"] == "cached_value"
        assert value["inputs"]["param"] == "test"

    def test_callbackcache_with_custom_feeds(self):
        """Test CallbackCache with custom feeds."""
        feed_data = {}

        def test_feed(func, **kwargs):
            # Simple key generation for testing
            key = f"{func}_{sorted(kwargs.items())}"
            return feed_data.get(key, ...)

        cache = CallbackCache(feeds=[test_feed])

        # Set up feed data
        feed_data["test_func_[('param', 'test')]"] = "fed_value"

        # Get should use the feed
        result = cache.get("test_func", param="test")
        assert result == "fed_value"

        # Get with missing data should return Ellipsis
        result = cache.get("missing_func", param="test")
        assert result is ...

    def test_callbackcache_with_callable_function(self):
        """Test CallbackCache get with callable function."""
        cache = CallbackCache()

        def test_function(x, y):
            return x + y

        # When feeds return Ellipsis, should NOT execute the function (behavior changed)
        result = cache.get(test_function, x=5, y=10)
        assert result == ...

    def test_callbackcache_memoization_with_feeds(self):
        """Test CallbackCache memoize decorator with feeds."""
        call_count = 0

        def test_feed(func, **kwargs):
            # For memoized functions, func is the actual function object
            # Return Ellipsis to let the function execute normally
            return ...

        cache = CallbackCache(feeds=[test_feed])

        @cache.memoize
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x * y

        # First call - feed returns ..., should compute
        result1 = expensive_function(2, 3)
        assert result1 == 6
        assert call_count == 1

        # Second call - feed still returns ..., should compute again (no caching)
        result2 = expensive_function(2, 3)
        assert result2 == 6  # Recomputed
        assert call_count == 2  # CallbackCache doesn't store, so always recomputes

    def test_callbackcache_integration_with_callbacks(self):
        """Test CallbackCache direct integration with callbacks."""
        callback_results = []

        def test_callback(key, value):
            callback_results.append((key, value))

        cache = CallbackCache(callbacks=[test_callback])

        # Test direct set operation - should trigger callback
        cache.set("test_func", output="cached_value", param="test")

        assert len(callback_results) == 1
        key, value = callback_results[0]
        assert value["output"] == "cached_value"
        assert value["inputs"]["param"] == "test"

        # Test direct add operation - should also trigger callback
        from src.ahvn.cache.base import CacheEntry

        entry = CacheEntry.from_args(func="add_test", output="add_value", x=1, y=2)
        cache.add(entry)

        assert len(callback_results) == 2
        key, value = callback_results[1]
        assert value["output"] == "add_value"
        assert value["inputs"]["x"] == 1

    def test_callbackcache_error_handling(self):
        """Test CallbackCache error handling in callbacks and feeds."""

        def failing_callback(key, value):
            raise ValueError("Callback failed")

        def failing_feed(func, **kwargs):
            raise RuntimeError("Feed failed")

        cache = CallbackCache(callbacks=[failing_callback], feeds=[failing_feed])

        # Set should not raise despite callback failure
        cache.set("test_func", output="test_value")  # Should not raise

        # Get should not raise despite feed failure, should return Ellipsis
        result = cache.get("test_func")
        assert result is ...

    def test_callbackcache_multiple_callbacks_and_feeds(self):
        """Test CallbackCache with multiple callbacks and feeds."""
        callback1_results = []
        callback2_results = []

        def callback1(key, value):
            callback1_results.append((key, value))

        def callback2(key, value):
            callback2_results.append((key, value))

        def feed1(func, **kwargs):
            return ...  # No value

        def feed2(func, **kwargs):
            return "from_feed2"

        cache = CallbackCache(callbacks=[callback1, callback2], feeds=[feed1, feed2])

        # Set should trigger all callbacks
        cache.set("test_func", output="test_value")
        assert len(callback1_results) == 1
        assert len(callback2_results) == 1

        # Get should try feeds in order and use first non-Ellipsis result
        result = cache.get("test_func")
        assert result == "from_feed2"  # From feed2, since feed1 returned ...

    def test_callbackcache_exclude_parameter(self):
        """Test CallbackCache with exclude parameter."""
        callback_results = []

        def test_callback(key, value):
            callback_results.append((key, value))

        cache = CallbackCache(callbacks=[test_callback], exclude=["session_id"])

        # Test direct set operation with exclude parameter
        cache.set("func_with_session", output="test_result", data="test", session_id="abc123")

        # Verify callback was called
        assert len(callback_results) == 1
        # The inputs should not contain session_id (it should be excluded)
        assert "session_id" not in callback_results[0][1]["inputs"]
        assert callback_results[0][1]["inputs"]["data"] == "test"
