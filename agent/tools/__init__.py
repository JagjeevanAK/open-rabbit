"""
Agent Tools Module

LangChain tools for web search and package intelligence.

Note: Utility functions have been moved to agent.utils module.
"""

from .web_search import (
    search_package_breaking_changes,
    search_package_deprecations,
    search_new_package_apis,
    search_package_security,
    search_code_best_practices,
    search_python_package_changes,
    search_general_web,
    get_all_search_tools,
    get_search_cache_stats,
)

from .package_intelligence import (
    analyze_package_changes,
    get_package_upgrade_context,
    get_all_package_intelligence_tools,
    parse_package_json_diff,
    parse_requirements_txt_diff,
    parse_pyproject_toml_diff,
    build_package_context,
    analyze_diff_for_packages,
    PackageIntelligenceResult,
    VersionChange,
    NewImport,
    PackageEcosystem,
)

__all__ = [
    # Web search tools
    "search_package_breaking_changes",
    "search_package_deprecations",
    "search_new_package_apis",
    "search_package_security",
    "search_code_best_practices",
    "search_python_package_changes",
    "search_general_web",
    "get_all_search_tools",
    "get_search_cache_stats",
    # Package intelligence tools
    "analyze_package_changes",
    "get_package_upgrade_context",
    "get_all_package_intelligence_tools",
    "parse_package_json_diff",
    "parse_requirements_txt_diff",
    "parse_pyproject_toml_diff",
    "build_package_context",
    "analyze_diff_for_packages",
    "PackageIntelligenceResult",
    "VersionChange",
    "NewImport",
    "PackageEcosystem",
]
