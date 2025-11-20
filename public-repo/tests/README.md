# AgentHeaven Test Suite - Contributor Guide

Welcome! This guide will help you quickly add new test cases to the AgentHeaven test suite.

## Quick Start: Adding a New Test

### Step 1: Choose the Right Test File

Find the appropriate test file for your component:

```
tests/unit/
├── cache/test_cache.py         # Cache functionality tests
├── db/test_db.py   # Database functionality tests
├── vdb/test_vdb.py              # Vector database tests
├── klstore/test_klstore.py     # KnowledgeUKFT store tests
├── klengine/                    # KnowledgeUKFT engine tests
└── utils/                       # Utility function tests
```

### Step 2: Add Your Test Method

```python
class TestCachePublicAPI:
    def test_your_new_feature(self, minimal_cache):
        """Test description - what you're validating."""
        # Arrange: Set up test data
        minimal_cache.set("key", output="value", param="test")
        
        # Act: Execute the functionality
        result = minimal_cache.get("key", param="test")
        
        # Assert: Verify the result
        assert result == "value"
```

### Step 3: Choose Test Coverage Level

Pick the right fixture based on how thorough you want the test:

| Fixture | Backends Tested | Use Case |
|---------|-----------------|----------|
| `minimal_cache` | 1 backend (fastest) | Quick smoke tests, debugging |
| `representative_cache` | ~6 backends | Balanced coverage |
| `cache` | All 9 backends | Exhaustive CI/CD testing |

Same pattern applies for `database`, `vdb`, `klstore`, `klengine`.

### Step 4: Run Your Test

```bash
# Run just your new test
pytest tests/unit/cache/test_cache.py::TestCachePublicAPI::test_your_new_feature -v

# Run all tests in the class
pytest tests/unit/cache/test_cache.py::TestCachePublicAPI -v

# Run all cache tests
pytest tests/unit/cache/test_cache.py -v
```

That's it! Your test will automatically run across all configured backends.

---

## Test Guidelines

### ✅ DO: Write Good Tests

**1. Test Public API Only**
```python
# ✅ GOOD: Test public methods
def test_cache_set_and_get(self, minimal_cache):
    minimal_cache.set("key", output="value")
    assert minimal_cache.get("key") == "value"

# ❌ BAD: Test internal implementation
def test_cache_internal_hash(self, minimal_cache):
    assert minimal_cache._internal_hash("key") == 12345
```

**2. Test Real Functionality, Not Trivia**
```python
# ✅ GOOD: Test meaningful behavior
def test_cache_overwrites_existing_key(self, minimal_cache):
    minimal_cache.set("key", output="old")
    minimal_cache.set("key", output="new")
    assert minimal_cache.get("key") == "new"

# ❌ BAD: Test trivial behavior
def test_cache_exists(self, minimal_cache):
    assert minimal_cache is not None
```

**3. Include BaseUKF Round-Trips**
```python
# ✅ GOOD: Test with actual UKF objects (critical for data integrity)
def test_cache_knowledge_storage(self, minimal_cache):
    from ahvn.ukf.templates.basic import KnowledgeUKFT
    
    k = KnowledgeUKFT(name="Test", content="Data")
    minimal_cache.set("knowledge", output=k)
    result = minimal_cache.get("knowledge")
    
    assert result.name == "Test"
    assert result.content == "Data"
```

**4. Skip Incompatible Scenarios**
```python
def test_cache_complex_objects(self, minimal_cache):
    # Some backends can't serialize complex objects
    cache_class = minimal_cache.__class__.__name__
    if cache_class in ["JsonCache", "DatabaseCache"]:
        pytest.skip(f"{cache_class} requires explicit serialization")
    
    # Test logic for compatible backends...
```

### ❌ DON'T: Common Mistakes

**1. Don't Test Backend-Specific Implementation**
```python
# ❌ BAD: Testing SQLite-specific behavior
def test_sqlite_pragma(self, minimal_database):
    if minimal_database.dialect != "sqlite":
        pytest.skip("SQLite only")
    minimal_database.execute("PRAGMA table_info(test)")
    # This is testing SQLite, not our Database abstraction!
```

**2. Don't Repeat the Same Test**
```python
# ❌ BAD: Duplicate tests with minor variations
def test_cache_set_string(self, minimal_cache):
    minimal_cache.set("key", output="string")
    
def test_cache_set_integer(self, minimal_cache):
    minimal_cache.set("key", output=42)
    
# ✅ GOOD: One parametrized test
@pytest.mark.parametrize("value", ["string", 42, 3.14, True, None])
def test_cache_set_various_types(self, minimal_cache, value):
    minimal_cache.set("key", output=value)
    assert minimal_cache.get("key") == value
```

**3. Don't Hardcode Backend Names**
```python
# ❌ BAD: Hardcoded backend checks
def test_cache_feature(self, cache):
    if "inmem" in str(type(cache)):
        # InMemCache-specific test
        pass

# ✅ GOOD: Use class name properly
def test_cache_feature(self, cache):
    cache_class = cache.__class__.__name__
    if cache_class == "InMemCache":
        # InMemCache-specific test
        pass
```

---

## Test Organization

### Class Structure

Organize tests into logical classes within each test file:

```python
class TestCachePublicAPI:
    """Test basic cache operations: set, get, exists, clear, length."""
    
    def test_cache_set_get_roundtrip(self, minimal_cache):
        """Test basic set/get functionality."""
        pass
    
    def test_cache_exists_functionality(self, minimal_cache):
        """Test existence checking."""
        pass


class TestCacheUKFRoundtrip:
    """Test cache with BaseUKF objects (KnowledgeUKFT, ExperienceUKFT)."""
    
    def test_cache_knowledge_roundtrip(self, minimal_cache):
        """Test caching KnowledgeUKFT objects."""
        pass


class TestCacheEdgeCases:
    """Test edge cases: empty cache, large datasets, unicode."""
    
    def test_cache_unicode_content(self, minimal_cache):
        """Test cache handles unicode correctly."""
        pass
```

### Naming Conventions

- **Test files**: `test_<component>.py` (e.g., `test_cache.py`)
- **Test classes**: `Test<Component><Aspect>` (e.g., `TestCachePublicAPI`)
- **Test methods**: `test_<component>_<functionality>` (e.g., `test_cache_set_get_roundtrip`)

---

## Adding a New Backend

Want to test against a new backend? Just edit `tests.json`!

### Example: Adding Redis Cache

**Step 1:** Edit `tests/tests.json`
```json
{
    "cache": [
        ["InMemCache", null, null],
        ["JsonCache", null, "./pytest_cache/{name}/jc/"],
        ["RedisCache", null, "localhost:6379"]   ← Add this line
    ]
}
```

**Step 2:** Run tests
```bash
pytest tests/unit/cache/test_cache.py -v
```

That's it! Every test in `test_cache.py` now automatically runs on Redis.

**Result**: 9 test methods × 10 cache backends = **90 tests** (up from 81)

---

## Architecture Overview

### How It Works

```
tests.json                    ← Backend configurations (single source of truth)
     ↓
conftest.py                   ← pytest_generate_tests hook
     ↓
Parametrized fixtures         ← minimal_cache, cache, etc.
     ↓
Test methods                  ← Your tests run on all backends automatically
```

### Directory Structure

```
tests/
├── tests.json                # Backend configurations ← Edit to add backends
├── conftest.py               # Fixture parametrization (don't edit)
├── fixtures/                 # Infrastructure (don't edit)
│   ├── config_loader.py      # Loads tests.json
│   ├── factory.py            # Creates test instances
│   ├── parametrize.py        # Dynamic parametrization
│   ├── cleanup.py            # Test cleanup
│   └── mock_embedder.py      # Mock embeddings for VDB tests
└── unit/                     # Your test files ← Add tests here
    ├── cache/test_cache.py
    ├── db/test_db.py
    ├── vdb/test_vdb.py
    └── klstore/test_klstore.py
```

---

## Common Patterns

### Pattern 1: Testing Different Data Types

```python
def test_cache_data_types(self, minimal_cache):
    """Test cache handles various data types."""
    test_cases = {
        "string": "hello",
        "integer": 42,
        "float": 3.14,
        "boolean": True,
        "none": None,
        "list": [1, 2, 3],
        "dict": {"key": "value"}
    }
    
    for key, value in test_cases.items():
        minimal_cache.set(f"test_{key}", output=value)
        result = minimal_cache.get(f"test_{key}")
        assert result == value
```

### Pattern 2: Testing Database Features

```python
def test_db_transaction_commit(self, minimal_database):
    """Test database transaction commit."""
    # Create table
    minimal_database.execute(
        "CREATE TABLE test (id INTEGER, value TEXT)",
        autocommit=True
    )
    
    # Start transaction
    minimal_database.execute(
        "INSERT INTO test (id, value) VALUES (1, 'data')",
        autocommit=False
    )
    
    # Commit
    minimal_database.commit()
    
    # Verify
    result = minimal_database.execute("SELECT value FROM test WHERE id = 1")
    rows = list(result.fetchall())
    assert rows[0]["value"] == "data"
```

### Pattern 3: Testing VDB with Mock Embeddings

```python
def test_vdb_insert_and_search(self, minimal_vdb):
    """Test VDB insert and search."""
    # Insert (mock embedder automatically used)
    minimal_vdb.insert(
        ids=["doc1"],
        texts=["This is a test document"],
        metadatas=[{"source": "test"}]
    )
    
    # Search
    results = minimal_vdb.search(
        query_texts=["test document"],
        topk=1
    )
    
    assert len(results) > 0
    assert results[0]["id"] == "doc1"
```

### Pattern 4: Testing KLStore with UKF

```python
def test_klstore_knowledge_storage(self, minimal_klstore):
    """Test KLStore with KnowledgeUKFT objects."""
    from ahvn.ukf.templates.basic import KnowledgeUKFT
    
    # Create KnowledgeUKFT
    k = KnowledgeUKFT(
        name="Python Basics",
        content="Python is a programming language",
        tags={"[topic:programming]", "[lang:python]"}
    )
    
    # Store
    minimal_klstore.upsert(k)
    
    # Retrieve
    retrieved = minimal_klstore.get(k.id)
    
    # Verify
    assert retrieved.name == "Python Basics"
    assert retrieved.content == "Python is a programming language"
    assert "[topic:programming]" in retrieved.tags
```

---

## Testing Best Practices

### 1. Use Descriptive Test Names

```python
# ✅ GOOD: Clear what's being tested
def test_cache_returns_ellipsis_for_missing_key(self, minimal_cache):
    pass

# ❌ BAD: Unclear intent
def test_cache_get(self, minimal_cache):
    pass
```

### 2. Write Self-Documenting Tests

```python
def test_cache_overwrites_on_duplicate_key(self, minimal_cache):
    """Test that setting a key twice overwrites the first value."""
    # Set initial value
    minimal_cache.set("key", output="first")
    
    # Overwrite with new value
    minimal_cache.set("key", output="second")
    
    # Should get the new value
    assert minimal_cache.get("key") == "second"
```

### 3. Test Edge Cases

```python
def test_cache_empty_string_key(self, minimal_cache):
    """Test cache handles empty string keys."""
    minimal_cache.set("", output="value")
    assert minimal_cache.get("") == "value"

def test_cache_unicode_content(self, minimal_cache):
    """Test cache handles unicode characters."""
    unicode_text = "Hello 世界 🌍"
    minimal_cache.set("key", output=unicode_text)
    assert minimal_cache.get("key") == unicode_text
```

### 4. Clean Up After Tests

```python
def test_cache_with_cleanup(self, minimal_cache):
    """Test with explicit cleanup."""
    # Set up
    minimal_cache.set("key", output="value")
    
    # Test
    assert minimal_cache.exists("key")
    
    # Cleanup (usually automatic via fixtures)
    minimal_cache.clear()
```

---

## Debugging Tests

### Running Specific Tests

```bash
# Run one specific test
pytest tests/unit/cache/test_cache.py::TestCachePublicAPI::test_cache_set_get_roundtrip -v

# Run with specific backend
pytest tests/unit/cache/test_cache.py::TestCachePublicAPI::test_cache_set_get_roundtrip[inmemcache] -v

# Run with verbose output and full traceback
pytest tests/unit/cache/test_cache.py -vv --tb=long

# Run with print statements visible
pytest tests/unit/cache/test_cache.py -s

# Stop on first failure
pytest tests/unit/cache/test_cache.py -x
```

### Common Issues

**Issue**: `fixture 'minimal_cache' not found`  
**Fix**: Make sure the fixture name matches exactly (check `conftest.py`)

**Issue**: All tests skipped for a backend  
**Fix**: Check filter functions in `conftest.py` or your skip conditions

**Issue**: Test passes locally but fails in CI  
**Fix**: Try running with `representative_*` or full fixture instead of `minimal_*`

---

## Mock Infrastructure

For VDB and VectorKLStore tests, we use mock embeddings instead of real LLM services.

### How Mock Embeddings Work

```python
# Mock embedder automatically used by minimal_vdb fixture
def mock_embedder(text: str, dim: int = 384) -> List[float]:
    """Generate deterministic embeddings from text."""
    seed = md5hash(text)  # Hash text to integer
    return stable_rnd_vector(seed, dim=dim)  # Generate stable vector
```

**Properties:**
- ✅ Same text → same vector (deterministic)
- ✅ Different texts → different vectors (unique)
- ✅ Realistic distribution (softmax + L2 normalization)
- ✅ Fast (no network calls)

### Using Mock Embeddings

```python
def test_vdb_embedding_consistency(self, minimal_vdb):
    """Test that same text produces consistent embeddings."""
    # Insert same text twice
    minimal_vdb.insert(ids=["1"], texts=["test"])
    minimal_vdb.insert(ids=["2"], texts=["test"])
    
    # Should be identical (mock embedder is deterministic)
    results1 = minimal_vdb.search(query_texts=["test"], topk=2)
    results2 = minimal_vdb.search(query_texts=["test"], topk=2)
    
    assert results1 == results2
```

---

## FAQ

**Q: How do I test only on SQLite?**  
A: Use a specific backend ID in pytest:
```bash
pytest tests/unit/db/test_db.py::test_name[sqlite_memory] -v
```

**Q: How do I add a new component to test?**  
A: 
1. Add configuration to `tests.json`
2. Add factory function in `tests/fixtures/factory.py`
3. Add fixture in `conftest.py`
4. Create `test_<component>.py` in `tests/unit/<component>/`

**Q: Can I run tests in parallel?**  
A: Yes! Install `pytest-xdist` and run:
```bash
pytest tests/unit/ -n auto
```

**Q: How do I see which backends are configured?**  
A: Check `tests/tests.json` - it's the single source of truth

**Q: Why are some tests skipped?**  
A: Tests skip when backend doesn't support the feature (e.g., native enums in SQLite)

---

## Quick Reference

### Fixture Cheat Sheet

```python
minimal_cache          # 1 cache backend
representative_cache   # ~6 cache backends  
cache                  # All 9 cache backends

minimal_database       # 1 database backend
representative_database # ~4 database backends
database               # All 6 database backends

minimal_vdb            # 1 VDB backend
representative_vdb     # ~2 VDB backends
vdb                    # All 4 VDB backends

minimal_klstore        # ~3 KLStore configs
representative_klstore # ~7 KLStore configs
klstore                # All 19 KLStore configs
```

### Test Template

```python
class TestYourComponent:
    """Test your component functionality."""
    
    def test_your_feature(self, minimal_component):
        """Test description."""
        # Arrange
        # ... setup test data
        
        # Act
        # ... execute functionality
        
        # Assert
        # ... verify results
```

---

## Need Help?

- **Check existing tests** - `tests/unit/cache/test_cache.py` has many examples
- **Read conftest.py** - See how fixtures are defined
- **Check tests.json** - See all configured backends
- **Run with -v** - See which backends are being tested

Happy testing! 🎉
