"""
Dependency management utilities for AgentHeaven.

This module provides a clean, industrial-standard dependency management system.
"""

__all__ = [
    "DependencyManager",
    "DependencyError",
    "OptionalDependencyError",
    "deps",
]

from typing import Dict, List, Optional, Any
from enum import Enum
import importlib

try:
    from .default_deps import DependencyInfo, get_default_dependencies
except ImportError:
    # Fallback for direct imports
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    deps_path = os.path.join(current_dir, "deps_definitions.py")
    spec = importlib.util.spec_from_file_location("deps_definitions", deps_path)
    deps_defs_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deps_defs_module)
    DependencyInfo = deps_defs_module.DependencyInfo
    get_default_dependencies = deps_defs_module.get_default_dependencies


class DependencyError(Exception):
    """Dependency-related error."""

    pass


class OptionalDependencyError(DependencyError, ImportError):
    """Optional dependency not available."""

    pass


class DependencyStatus(Enum):
    """Dependency status."""

    AVAILABLE = "available"
    MISSING = "missing"


class DependencyManager:
    """Clean dependency management system."""

    _instance: Optional["DependencyManager"] = None

    def __new__(cls) -> "DependencyManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager."""
        if hasattr(self, "_initialized"):
            return

        self._deps: Dict[str, DependencyInfo] = {}
        self._cache: Dict[str, bool] = {}

        self._load_defaults()
        self._initialized = True

    def _load_defaults(self):
        """Load default dependencies."""
        for dep_info in get_default_dependencies().values():
            self.add(dep_info)

    def add(self, dep_info: DependencyInfo) -> None:
        """Add a dependency."""
        if not dep_info.name:
            raise ValueError("Dependency name cannot be empty")

        if dep_info.name in self._deps:
            raise ValueError(f"Dependency '{dep_info.name}' already exists")

        self._deps[dep_info.name] = dep_info
        self._cache.pop(dep_info.name, None)

    def remove(self, name: str) -> None:
        """Remove a dependency."""
        if name not in self._deps:
            raise KeyError(f"Dependency '{name}' not found")

        del self._deps[name]
        self._cache.pop(name, None)

    def check(self, name: str) -> bool:
        """Check if dependency is available."""
        if name not in self._deps:
            raise KeyError(f"Dependency '{name}' not found")

        if name in self._cache:
            return self._cache[name]

        dep_info = self._deps[name]

        try:
            for package in dep_info.packages:
                importlib.import_module(package)

            self._cache[name] = True
            return True

        except ImportError:
            self._cache[name] = False
            return False

    def require(self, name: str, feature: Optional[str] = None) -> None:
        """Require a dependency to be available."""
        if name not in self._deps:
            available = ", ".join(self._deps.keys())
            raise KeyError(f"Unknown dependency: {name}. Available: {available}")

        if not self.check(name):
            dep_info = self._deps[name]
            feature_msg = f" for {feature}" if feature else ""
            raise OptionalDependencyError(f"{dep_info.description} is required{feature_msg}.\n" f"Install with: {dep_info.install}")

    def list(self, filter_optional: Optional[bool] = None) -> List[str]:
        """List all dependencies."""
        deps = list(self._deps.keys())

        if filter_optional is not None:
            deps = [name for name in deps if self._deps[name].optional == filter_optional]

        return deps

    def missing(self) -> List[str]:
        """Get list of missing dependencies."""
        return [name for name in self._deps if not self.check(name)]

    def info(self, name: str) -> Dict[str, Any]:
        """Get dependency information."""
        if name not in self._deps:
            raise KeyError(f"Dependency '{name}' not found")

        dep_info = self._deps[name]
        return {
            "name": name,
            "description": dep_info.description,
            "packages": dep_info.packages,
            "install": dep_info.install,
            "optional": dep_info.optional,
            "available": self.check(name),
            "required_for": dep_info.required_for,
        }

    def clear_cache(self) -> None:
        """Clear dependency cache."""
        self._cache.clear()


# Global instance
deps = DependencyManager()
