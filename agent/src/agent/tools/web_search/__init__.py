"""
Web Search Module

Provides LangChain tools for searching package information, breaking changes,
deprecations, and API updates using Brave Search API.

This enables the LLM to have up-to-date information about packages being
reviewed, preventing outdated suggestions based on stale training data.

Supported ecosystems:
- npm (JavaScript/TypeScript)
- pip/pypi (Python)
"""

from typing import Any, Dict, List

from .config import (
    SearchConfig,
    SearchError,
    PackageEcosystem,
    get_config,
    is_search_enabled,
)
from .brave_client import (
    brave_search_async,
    brave_search_sync,
    format_search_results,
)
from .tools import (
    get_all_search_tools,
    search_package_breaking_changes,
    search_package_deprecations,
    search_new_package_apis,
    search_package_security,
    search_code_best_practices,
    search_python_package_changes,
    search_general_web,
)
from ...services.cache import get_search_cache


def get_search_cache_stats() -> Dict[str, Any]:
    """Get statistics from the search cache."""
    cache = get_search_cache()
    return cache.stats.to_dict()


__all__ = [
    # Config
    "SearchConfig",
    "SearchError",
    "PackageEcosystem",
    "get_config",
    "is_search_enabled",
    # Client
    "brave_search_async",
    "brave_search_sync",
    "format_search_results",
    # Tools
    "get_all_search_tools",
    "search_package_breaking_changes",
    "search_package_deprecations",
    "search_new_package_apis",
    "search_package_security",
    "search_code_best_practices",
    "search_python_package_changes",
    "search_general_web",
    # Utilities
    "get_search_cache_stats",
]
