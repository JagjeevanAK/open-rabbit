"""
Web Search Tool for Code Review Agent.

Provides LangChain tools for searching package information, breaking changes,
deprecations, and API updates using Brave Search API.

This enables the LLM to have up-to-date information about packages being
reviewed, preventing outdated suggestions based on stale training data.

Supported ecosystems:
- npm (JavaScript/TypeScript)
- pip/pypi (Python)
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool

from ..services.cache import get_search_cache, TTLCache

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Base exception for web search errors."""
    pass


class PackageEcosystem(str, Enum):
    """Supported package ecosystems."""
    NPM = "npm"
    PYTHON = "python"


@dataclass
class SearchConfig:
    """Configuration for web search."""
    api_key: str
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    timeout: int = 10
    max_results: int = 5
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "SearchConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("BRAVE_API_KEY", ""),
            timeout=int(os.getenv("SEARCH_TIMEOUT", "10")),
            max_results=int(os.getenv("SEARCH_MAX_RESULTS", "5")),
            enabled=os.getenv("SEARCH_ENABLED", "true").lower() == "true"
        )


def _get_config() -> SearchConfig:
    """Get the search configuration."""
    return SearchConfig.from_env()


def _is_search_enabled() -> bool:
    """Check if web search is enabled and configured."""
    config = _get_config()
    if not config.enabled:
        logger.debug("Web search is disabled")
        return False
    if not config.api_key:
        logger.warning("BRAVE_API_KEY not set, web search disabled")
        return False
    return True


def _generate_cache_key(query: str, **kwargs) -> str:
    """Generate a cache key for a search query."""
    key_data = json.dumps({"query": query, **kwargs}, sort_keys=True)
    return f"search:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"


async def _brave_search(
    query: str,
    count: int = 5,
    freshness: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a search using Brave Search API.
    
    Args:
        query: The search query
        count: Number of results to return
        freshness: Time filter ('pd' = past day, 'pw' = past week, 
                   'pm' = past month, 'py' = past year)
    
    Returns:
        Dict containing search results or error info
    """
    config = _get_config()
    
    # Check cache first
    cache = get_search_cache()
    cache_key = _generate_cache_key(query, count=count, freshness=freshness)
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for query: {query[:50]}...")
        return cached
    
    # Execute search
    params = {
        "q": query,
        "count": count,
        "text_decorations": False,
        "search_lang": "en",
    }
    
    if freshness:
        params["freshness"] = freshness
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.api_key
    }
    
    try:
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.get(
                config.base_url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant results
            results = []
            web_results = data.get("web", {}).get("results", [])
            
            for result in web_results[:count]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "age": result.get("age", "")
                })
            
            result_data = {
                "success": True,
                "query": query,
                "results": results,
                "total_results": len(results)
            }
            
            # Cache the results
            cache.set(cache_key, result_data)
            logger.info(f"Search completed: '{query[:50]}...' returned {len(results)} results")
            
            return result_data
            
    except httpx.TimeoutException:
        logger.warning(f"Search timeout for query: {query[:50]}...")
        return {"success": False, "error": "Search timeout", "query": query, "results": []}
    except httpx.HTTPStatusError as e:
        logger.error(f"Search HTTP error: {e.response.status_code}")
        return {"success": False, "error": f"HTTP {e.response.status_code}", "query": query, "results": []}
    except Exception as e:
        logger.error(f"Search error: {type(e).__name__}: {str(e)}")
        return {"success": False, "error": str(e), "query": query, "results": []}


def _brave_search_sync(
    query: str,
    count: int = 5,
    freshness: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous version of Brave search for use in @tool functions.
    """
    config = _get_config()
    
    # Check cache first
    cache = get_search_cache()
    cache_key = _generate_cache_key(query, count=count, freshness=freshness)
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for query: {query[:50]}...")
        return cached
    
    # Execute search
    params = {
        "q": query,
        "count": count,
        "text_decorations": False,
        "search_lang": "en",
    }
    
    if freshness:
        params["freshness"] = freshness
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.api_key
    }
    
    try:
        with httpx.Client(timeout=config.timeout) as client:
            response = client.get(
                config.base_url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant results
            results = []
            web_results = data.get("web", {}).get("results", [])
            
            for result in web_results[:count]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "age": result.get("age", "")
                })
            
            result_data = {
                "success": True,
                "query": query,
                "results": results,
                "total_results": len(results)
            }
            
            # Cache the results
            cache.set(cache_key, result_data)
            logger.info(f"Search completed: '{query[:50]}...' returned {len(results)} results")
            
            return result_data
            
    except httpx.TimeoutException:
        logger.warning(f"Search timeout for query: {query[:50]}...")
        return {"success": False, "error": "Search timeout", "query": query, "results": []}
    except httpx.HTTPStatusError as e:
        logger.error(f"Search HTTP error: {e.response.status_code}")
        return {"success": False, "error": f"HTTP {e.response.status_code}", "query": query, "results": []}
    except Exception as e:
        logger.error(f"Search error: {type(e).__name__}: {str(e)}")
        return {"success": False, "error": str(e), "query": query, "results": []}


def _format_search_results(results: Dict[str, Any]) -> str:
    """Format search results for LLM consumption."""
    if not results.get("success") or not results.get("results"):
        return f"No results found for: {results.get('query', 'unknown query')}"
    
    output = [f"Search results for: {results['query']}\n"]
    
    for i, result in enumerate(results["results"], 1):
        output.append(f"{i}. {result['title']}")
        output.append(f"   URL: {result['url']}")
        if result.get("description"):
            output.append(f"   {result['description'][:200]}...")
        if result.get("age"):
            output.append(f"   Age: {result['age']}")
        output.append("")
    
    return "\n".join(output)


# =============================================================================
# LangChain Tools
# =============================================================================

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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for breaking changes."
    
    # Build ecosystem-specific query
    if ecosystem == "python":
        query = f"{package_name} breaking changes {from_version} to {to_version} python migration guide"
    else:
        query = f"{package_name} breaking changes {from_version} to {to_version} npm migration guide"
    
    results = _brave_search_sync(query, count=5, freshness="py")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for deprecations."
    
    if ecosystem == "python":
        query = f"{package_name} {version} deprecated API python"
    else:
        query = f"{package_name} {version} deprecated API methods"
    
    results = _brave_search_sync(query, count=5, freshness="py")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for new APIs."
    
    if ecosystem == "python":
        query = f"{package_name} {version} new features changelog python release notes"
    else:
        query = f"{package_name} {version} new features changelog release notes"
    
    results = _brave_search_sync(query, count=5, freshness="py")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for security issues."
    
    if ecosystem == "python":
        query = f"{package_name} {version} CVE security vulnerability python pypi advisory"
    else:
        query = f"{package_name} {version} CVE security vulnerability npm advisory"
    
    results = _brave_search_sync(query, count=5, freshness="pm")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for best practices."
    
    query = f"{technology} {topic} best practices 2024"
    results = _brave_search_sync(query, count=5, freshness="py")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled. Unable to search for Python package changes."
    
    query = f"{package_name} upgrade {from_version} to {to_version} breaking changes migration guide python"
    results = _brave_search_sync(query, count=5, freshness="py")
    return _format_search_results(results)


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
    if not _is_search_enabled():
        return "Web search is disabled."
    
    results = _brave_search_sync(query, count=5)
    return _format_search_results(results)


# =============================================================================
# Utility Functions for Agent Integration  
# =============================================================================

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


def get_search_cache_stats() -> Dict[str, Any]:
    """Get statistics from the search cache."""
    cache = get_search_cache()
    return cache.stats.to_dict()
