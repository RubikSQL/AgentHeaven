"""
Pytest configuration and shared fixtures for AgentHeaven tests.

This module provides test fixtures using the new JSON-based configuration
system from tests.json, enabling comprehensive and modular testing across
all backend combinations.
"""

import os
import sys
import pytest
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Generator, Any

# Add src and tests to Python path for imports
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
TESTS_DIR = ROOT_DIR / "tests"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from fixtures import (
    ConfigLoader,
    UniversalFactory,
    cleanup_instance,
    minimal_cache_filter,
    minimal_db_filter,
    minimal_vdb_filter,
    minimal_mdb_filter,
    minimal_klstore_filter,
    minimal_klengine_filter,
    representative_cache_filter,
    representative_db_filter,
    representative_vdb_filter,
    representative_mdb_filter,
    representative_klstore_filter,
    representative_klengine_filter,
)


# ============================================================================
# Basic Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return ROOT_DIR


@pytest.fixture(scope="session")
def src_dir() -> Path:
    """Return the source code directory."""
    return SRC_DIR


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_cache_dir() -> Generator[Path, None, None]:
    """Create pytest cache directory for temporary files."""
    cache_path = ROOT_DIR / ".pytest_cache"
    cache_path.mkdir(exist_ok=True)

    # Create unique subdirectory for this test session
    test_path = cache_path / f"test_{uuid.uuid4().hex[:8]}"
    test_path.mkdir(exist_ok=True)

    try:
        yield test_path
    finally:
        shutil.rmtree(test_path, ignore_errors=True)


@pytest.fixture(scope="session")
def config_loader() -> ConfigLoader:
    """Return shared ConfigLoader instance."""
    return ConfigLoader()


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Provide a mock configuration for testing."""
    return {
        "core": {
            "encrypt_keys": ["api_key", "token"],
            "debug": True,
        },
        "llm": {
            "handle_model_mismatch": "ignore",
            "default_preset": "sys",
            "default_model": "test-model",
            "default_provider": "test-provider",
            "default_args": {"seed": 42, "timeout": 120, "max_tokens": 2048, "repetition_penalty": 1.0},
        },
    }


@pytest.fixture
def mock_cache_data() -> dict[str, Any]:
    """Provide mock data for cache testing."""
    return {
        "simple_data": {"key": "value", "number": 42},
        "complex_data": {
            "nested": {"data": {"structure": [1, 2, 3]}},
            "list": ["a", "b", "c"],
            "boolean": True,
        },
    }


# ============================================================================
# JSON-Based Parametrized Fixtures via pytest_generate_tests
# ============================================================================


def pytest_generate_tests(metafunc):
    """
    Dynamically generate test parameters from tests.json.

    This function is called by pytest for each test function, allowing us to
    parametrize tests based on the JSON configuration.
    """
    config_loader = ConfigLoader()
    test_name = f"test_{uuid.uuid4().hex[:8]}"

    # Cache fixtures
    if "cache_config" in metafunc.fixturenames:
        configs = config_loader.get_cache_configs(test_name)
        ids = [config_loader.get_config_id("cache", c) for c in configs]
        metafunc.parametrize("cache_config", configs, ids=ids)

    if "minimal_cache_config" in metafunc.fixturenames:
        configs = config_loader.get_cache_configs(test_name)
        configs = [c for c in configs if minimal_cache_filter(c)]
        ids = [config_loader.get_config_id("cache", c) for c in configs]
        metafunc.parametrize("minimal_cache_config", configs, ids=ids)

    if "representative_cache_config" in metafunc.fixturenames:
        configs = config_loader.get_cache_configs(test_name)
        configs = [c for c in configs if representative_cache_filter(c)]
        ids = [config_loader.get_config_id("cache", c) for c in configs]
        metafunc.parametrize("representative_cache_config", configs, ids=ids)

    # Database fixtures
    if "db_config" in metafunc.fixturenames:
        configs = config_loader.get_db_configs(test_name)
        ids = [config_loader.get_config_id("db", c) for c in configs]
        metafunc.parametrize("db_config", configs, ids=ids)

    if "minimal_db_config" in metafunc.fixturenames:
        configs = config_loader.get_db_configs(test_name)
        configs = [c for c in configs if minimal_db_filter(c)]
        ids = [config_loader.get_config_id("db", c) for c in configs]
        metafunc.parametrize("minimal_db_config", configs, ids=ids)

    if "representative_db_config" in metafunc.fixturenames:
        configs = config_loader.get_db_configs(test_name)
        configs = [c for c in configs if representative_db_filter(c)]
        ids = [config_loader.get_config_id("db", c) for c in configs]
        metafunc.parametrize("representative_db_config", configs, ids=ids)

    if "minimal_mdb_config" in metafunc.fixturenames:
        configs = config_loader.get_mdb_configs(test_name)
        configs = [c for c in configs if minimal_mdb_filter(c)]
        ids = [config_loader.get_config_id("mdb", c) for c in configs]
        metafunc.parametrize("minimal_mdb_config", configs, ids=ids)

    if "representative_mdb_config" in metafunc.fixturenames:
        configs = config_loader.get_mdb_configs(test_name)
        configs = [c for c in configs if representative_mdb_filter(c)]
        ids = [config_loader.get_config_id("mdb", c) for c in configs]
        metafunc.parametrize("representative_mdb_config", configs, ids=ids)

    # VDB fixtures
    if "vdb_config" in metafunc.fixturenames:
        configs = config_loader.get_vdb_configs(test_name)
        ids = [config_loader.get_config_id("vdb", c) for c in configs]
        metafunc.parametrize("vdb_config", configs, ids=ids)

    if "minimal_vdb_config" in metafunc.fixturenames:
        configs = config_loader.get_vdb_configs(test_name)
        configs = [c for c in configs if minimal_vdb_filter(c)]
        ids = [config_loader.get_config_id("vdb", c) for c in configs]
        metafunc.parametrize("minimal_vdb_config", configs, ids=ids)

    if "representative_vdb_config" in metafunc.fixturenames:
        configs = config_loader.get_vdb_configs(test_name)
        configs = [c for c in configs if representative_vdb_filter(c)]
        ids = [config_loader.get_config_id("vdb", c) for c in configs]
        metafunc.parametrize("representative_vdb_config", configs, ids=ids)

    # KLStore fixtures
    if "klstore_config" in metafunc.fixturenames:
        configs = config_loader.get_klstore_configs(test_name)
        ids = [config_loader.get_config_id("klstore", c) for c in configs]
        metafunc.parametrize("klstore_config", configs, ids=ids)

    if "minimal_klstore_config" in metafunc.fixturenames:
        configs = config_loader.get_klstore_configs(test_name)
        configs = [c for c in configs if minimal_klstore_filter(c)]
        ids = [config_loader.get_config_id("klstore", c) for c in configs]
        metafunc.parametrize("minimal_klstore_config", configs, ids=ids)

    if "representative_klstore_config" in metafunc.fixturenames:
        configs = config_loader.get_klstore_configs(test_name)
        configs = [c for c in configs if representative_klstore_filter(c)]
        ids = [config_loader.get_config_id("klstore", c) for c in configs]
        metafunc.parametrize("representative_klstore_config", configs, ids=ids)

    # KLEngine fixtures
    if "klengine_config" in metafunc.fixturenames:
        configs = config_loader.get_klengine_configs(test_name)
        ids = [config_loader.get_config_id("klengine", c) for c in configs]
        metafunc.parametrize("klengine_config", configs, ids=ids)

    if "minimal_klengine_config" in metafunc.fixturenames:
        configs = config_loader.get_klengine_configs(test_name)
        configs = [c for c in configs if minimal_klengine_filter(c)]
        ids = [config_loader.get_config_id("klengine", c) for c in configs]
        metafunc.parametrize("minimal_klengine_config", configs, ids=ids)

    if "representative_klengine_config" in metafunc.fixturenames:
        configs = config_loader.get_klengine_configs(test_name)
        configs = [c for c in configs if representative_klengine_filter(c)]
        ids = [config_loader.get_config_id("klengine", c) for c in configs]
        metafunc.parametrize("representative_klengine_config", configs, ids=ids)


# ============================================================================
# Cache Fixtures
# ============================================================================


@pytest.fixture
def cache(cache_config, request):
    """Create cache instance from JSON configuration."""
    cache_type, backend, path = cache_config

    # Skip external services if not available
    if backend in ["postgresql", "mysql"]:
        if not UniversalFactory.check_service_available(backend):
            pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_cache(cache_type, backend, path, label=label)
    yield instance
    cleanup_instance(instance, "cache")


@pytest.fixture
def minimal_cache(minimal_cache_config, request):
    """Create minimal cache instance from JSON configuration."""
    cache_type, backend, path = minimal_cache_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_cache(cache_type, backend, path, label=label)
    yield instance
    cleanup_instance(instance, "cache")


@pytest.fixture
def representative_cache(representative_cache_config, request):
    """Create representative cache instance from JSON configuration."""
    cache_type, backend, path = representative_cache_config

    # Skip external services if not available
    if backend in ["postgresql", "mysql"]:
        if not UniversalFactory.check_service_available(backend):
            pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_cache(cache_type, backend, path, label=label)
    yield instance
    cleanup_instance(instance, "cache")


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture
def database(db_config, request):
    """Create database instance from JSON configuration."""
    backend, path = db_config

    # Skip external services if not available
    if backend in ["postgresql", "mysql"]:
        if not UniversalFactory.check_service_available(backend):
            pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_database(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "database")


@pytest.fixture
def minimal_database(minimal_db_config, request):
    """Create minimal database instance from JSON configuration."""
    backend, path = minimal_db_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_database(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "database")


@pytest.fixture
def representative_database(representative_db_config, request):
    """Create representative database instance from JSON configuration."""
    backend, path = representative_db_config

    # Skip external services if not available
    if backend in ["postgresql", "mysql"]:
        if not UniversalFactory.check_service_available(backend):
            pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_database(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "database")


# ============================================================================
# VDB Fixtures
# ============================================================================


@pytest.fixture
def vdb(vdb_config, request):
    """Create vector database instance from JSON configuration."""
    backend, path = vdb_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_vdb(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "vdb")


@pytest.fixture
def minimal_vdb(minimal_vdb_config, request):
    """Create minimal VDB instance from JSON configuration."""
    backend, path = minimal_vdb_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_vdb(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "vdb")


@pytest.fixture
def representative_vdb(representative_vdb_config, request):
    """Create representative VDB instance from JSON configuration."""
    backend, path = representative_vdb_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_vdb(backend, path, label=label)
    yield instance
    cleanup_instance(instance, "vdb")


# ============================================================================
# KLStore Fixtures
# ============================================================================


@pytest.fixture
def klstore(klstore_config, request):
    """Create KLStore instance from JSON configuration."""
    store_type, backend_args = klstore_config

    # Check if backend requires external service
    if len(backend_args) >= 2:
        backend = backend_args[0] if isinstance(backend_args[0], str) else backend_args[1]
        if backend in ["postgresql", "mysql"]:
            if not UniversalFactory.check_service_available(backend):
                pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klstore(store_type, backend_args, label=label)
    yield instance
    cleanup_instance(instance, "klstore")


@pytest.fixture
def minimal_klstore(minimal_klstore_config, request):
    """Create minimal KLStore instance from JSON configuration."""
    store_type, backend_args = minimal_klstore_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klstore(store_type, backend_args, label=label)
    yield instance
    cleanup_instance(instance, "klstore")


@pytest.fixture
def representative_klstore(representative_klstore_config, request):
    """Create representative KLStore instance from JSON configuration."""
    store_type, backend_args = representative_klstore_config

    # Check if backend requires external service
    if len(backend_args) >= 2:
        backend = backend_args[0] if isinstance(backend_args[0], str) else backend_args[1]
        if backend in ["postgresql", "mysql"]:
            if not UniversalFactory.check_service_available(backend):
                pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klstore(store_type, backend_args, label=label)
    yield instance
    cleanup_instance(instance, "klstore")


# ============================================================================
# KLEngine Fixtures
# ============================================================================


@pytest.fixture
def klengine(klengine_config, request):
    """Create KLEngine instance from JSON configuration."""
    engine_type, store_args, engine_backend_args, inplace = klengine_config

    # Check if backend requires external service
    store_type, backend_args = store_args
    if len(backend_args) >= 2:
        backend = backend_args[0] if isinstance(backend_args[0], str) else backend_args[1]
        if backend in ["postgresql", "mysql"]:
            if not UniversalFactory.check_service_available(backend):
                pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klengine(engine_type, store_args, engine_backend_args, inplace, label=label)
    yield instance
    cleanup_instance(instance, "klengine")


@pytest.fixture
def minimal_klengine(minimal_klengine_config, request):
    """Create minimal KLEngine instance from JSON configuration."""
    engine_type, store_args, engine_backend_args, inplace = minimal_klengine_config
    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klengine(engine_type, store_args, engine_backend_args, inplace, label=label)
    yield instance
    cleanup_instance(instance, "klengine")


@pytest.fixture
def representative_klengine(representative_klengine_config, request):
    """Create representative KLEngine instance from JSON configuration."""
    engine_type, store_args, engine_backend_args, inplace = representative_klengine_config

    # Check if backend requires external service
    store_type, backend_args = store_args
    if len(backend_args) >= 2:
        backend = backend_args[0] if isinstance(backend_args[0], str) else backend_args[1]
        if backend in ["postgresql", "mysql"]:
            if not UniversalFactory.check_service_available(backend):
                pytest.skip(f"{backend.upper()} service not available")

    # Use test node ID as label for generating short names
    label = request.node.nodeid
    instance = UniversalFactory.create_klengine(engine_type, store_args, engine_backend_args, inplace, label=label)
    yield instance
    cleanup_instance(instance, "klengine")


# ============================================================================
# Special Fixtures
# ============================================================================


@pytest.fixture
def no_cache():
    """Create NoCache instance for testing."""
    from ahvn.cache import NoCache

    return NoCache()


@pytest.fixture
def callback_cache():
    """Create CallbackCache instance for testing."""
    from ahvn.cache import CallbackCache

    return CallbackCache()


# ============================================================================
# Config Reset Fixture
# ============================================================================


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset ConfigManager cache before each test."""
    try:
        from ahvn.utils.basic.config_utils import ConfigManager

        # Reset the config cache
        if hasattr(ConfigManager, "_instance"):
            ConfigManager._instance = None
    except Exception:
        pass

    yield
