"""
Web Search LangChain Tools

LangChain tools for searching package information, breaking changes,
deprecations, and API updates using Brave Search API.
"""

from typing import List

from langchain_core.tools import tool

from .config import is_search_enabled
from .brave_client import brave_search_sync, format_search_results


@tool
def search_package_breaking_changes(
    package_name: str,
    from_version: str,
    to_version: str,
    ecosystem: str = "npm"
) -> str:
    """
    Search for breaking changes when upgrading a package between versions.
    
    Use this tool when reviewing PRs that update package versions to find
    breaking changes, migration guides, and upgrade requirements.
    
    Args:
        package_name: Name of the package (e.g., 'react', 'typescript', 'django', 'requests')
        from_version: The version being upgraded from (e.g., '17.0.2')
        to_version: The version being upgraded to (e.g., '18.0.0')
        ecosystem: Package ecosystem - 'npm' for JavaScript/TypeScript, 'python' for Python/pip
    
    Returns:
        Formatted search results with breaking changes and migration info
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for breaking changes."
    
    # Build ecosystem-specific query
    if ecosystem == "python":
        query = f"{package_name} breaking changes {from_version} to {to_version} python migration guide"
    else:
        query = f"{package_name} breaking changes {from_version} to {to_version} npm migration guide"
    
    results = brave_search_sync(query, count=5, freshness="py")
    return format_search_results(results)


@tool
def search_package_deprecations(
    package_name: str,
    version: str,
    ecosystem: str = "npm"
) -> str:
    """
    Search for deprecated APIs and features in a specific package version.
    
    Use this tool when reviewing code that uses packages that have been updated,
    to identify deprecated APIs that should be avoided or migrated.
    
    Args:
        package_name: Name of the package (e.g., 'react', 'lodash', 'django', 'flask')
        version: The package version to check
        ecosystem: Package ecosystem - 'npm' for JavaScript/TypeScript, 'python' for Python/pip
    
    Returns:
        Formatted search results with deprecation warnings and alternatives
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for deprecations."
    
    if ecosystem == "python":
        query = f"{package_name} {version} deprecated API python"
    else:
        query = f"{package_name} {version} deprecated API methods"
    
    results = brave_search_sync(query, count=5, freshness="py")
    return format_search_results(results)


@tool
def search_new_package_apis(
    package_name: str,
    version: str,
    ecosystem: str = "npm"
) -> str:
    """
    Search for new APIs and features introduced in a package version.
    
    Use this tool when reviewing PRs that add new dependencies or upgrade
    existing ones, to understand what new capabilities are available.
    
    Args:
        package_name: Name of the package (e.g., 'react', 'next', 'django', 'fastapi')
        version: The package version to check
        ecosystem: Package ecosystem - 'npm' for JavaScript/TypeScript, 'python' for Python/pip
    
    Returns:
        Formatted search results with new features and APIs
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for new APIs."
    
    if ecosystem == "python":
        query = f"{package_name} {version} new features changelog python release notes"
    else:
        query = f"{package_name} {version} new features changelog release notes"
    
    results = brave_search_sync(query, count=5, freshness="py")
    return format_search_results(results)


@tool
def search_package_security(
    package_name: str,
    version: str,
    ecosystem: str = "npm"
) -> str:
    """
    Search for known security vulnerabilities in a package version.
    
    Use this tool when reviewing PRs that add or update dependencies to
    check for known security issues.
    
    Args:
        package_name: Name of the package
        version: The package version to check
        ecosystem: Package ecosystem - 'npm' for JavaScript/TypeScript, 'python' for Python/pip
    
    Returns:
        Formatted search results with security advisories
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for security issues."
    
    if ecosystem == "python":
        query = f"{package_name} {version} CVE security vulnerability python pypi advisory"
    else:
        query = f"{package_name} {version} CVE security vulnerability npm advisory"
    
    results = brave_search_sync(query, count=5, freshness="pm")
    return format_search_results(results)


@tool
def search_code_best_practices(
    technology: str,
    topic: str
) -> str:
    """
    Search for current best practices on a specific coding topic.
    
    Use this tool when reviewing code and you want to verify current
    best practices or find authoritative guidance.
    
    Args:
        technology: The technology/framework (e.g., 'React', 'TypeScript', 'Python', 'Django', 'FastAPI')
        topic: The specific topic (e.g., 'error handling', 'state management', 'testing')
    
    Returns:
        Formatted search results with best practice guides
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for best practices."
    
    query = f"{technology} {topic} best practices 2024"
    results = brave_search_sync(query, count=5, freshness="py")
    return format_search_results(results)


@tool
def search_python_package_changes(
    package_name: str,
    from_version: str,
    to_version: str
) -> str:
    """
    Search for changes and migration guides for Python package upgrades.
    
    Use this tool specifically for Python package upgrades to find breaking
    changes, API differences, and migration requirements.
    
    Args:
        package_name: Python package name (e.g., 'django', 'fastapi', 'pydantic')
        from_version: Version upgrading from (e.g., '3.2')
        to_version: Version upgrading to (e.g., '4.0')
    
    Returns:
        Formatted search results with Python package upgrade info
    """
    if not is_search_enabled():
        return "Web search is disabled. Unable to search for Python package changes."
    
    query = f"{package_name} upgrade {from_version} to {to_version} breaking changes migration guide python"
    results = brave_search_sync(query, count=5, freshness="py")
    return format_search_results(results)


@tool 
def search_general_web(query: str) -> str:
    """
    Perform a general web search for any coding-related question.
    
    Use this as a fallback when other specialized search tools don't
    fit your needs. Best for searching documentation, tutorials, or
    answers to specific technical questions.
    
    Args:
        query: The search query
    
    Returns:
        Formatted search results
    """
    if not is_search_enabled():
        return "Web search is disabled."
    
    results = brave_search_sync(query, count=5)
    return format_search_results(results)


def get_all_search_tools() -> List:
    """Return all web search tools for agent registration."""
    return [
        search_package_breaking_changes,
        search_package_deprecations,
        search_new_package_apis,
        search_package_security,
        search_code_best_practices,
        search_python_package_changes,
        search_general_web,
    ]
