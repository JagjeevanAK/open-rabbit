"""
Brave Search Client

Core search functionality using Brave Search API with caching support.
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

import httpx

from .config import get_config
from ...services.cache import get_search_cache

logger = logging.getLogger(__name__)


def _generate_cache_key(query: str, **kwargs) -> str:
    """Generate a cache key for a search query."""
    key_data = json.dumps({"query": query, **kwargs}, sort_keys=True)
    return f"search:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"


async def brave_search_async(
    query: str,
    count: int = 5,
    freshness: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a search using Brave Search API (async version).
    
    Args:
        query: The search query
        count: Number of results to return
        freshness: Time filter ('pd' = past day, 'pw' = past week, 
                   'pm' = past month, 'py' = past year)
    
    Returns:
        Dict containing search results or error info
    """
    config = get_config()
    
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


def brave_search_sync(
    query: str,
    count: int = 5,
    freshness: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous version of Brave search for use in @tool functions.
    """
    config = get_config()
    
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


def format_search_results(results: Dict[str, Any]) -> str:
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
