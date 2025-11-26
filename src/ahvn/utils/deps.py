"""
Dependency management utilities for AgentHeaven.

This module is deprecated. Please use `ahvn.utils.basic.deps_utils` instead.
"""

from .basic.deps_utils import (
    DependencyManager,
    DependencyError,
    OptionalDependencyError,
    deps,
    DependencyInfo,
    get_default_dependencies,
)

__all__ = [
    "DependencyManager",
    "DependencyError",
    "OptionalDependencyError",
    "deps",
    "DependencyInfo",
    "get_default_dependencies",
]
