"""
Web Search Configuration

Configuration, types, and exceptions for the web search module.
"""

import os
from dataclasses import dataclass
from enum import Enum


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


def get_config() -> SearchConfig:
    """Get the search configuration."""
    return SearchConfig.from_env()


def is_search_enabled() -> bool:
    """Check if web search is enabled and configured."""
    import logging
    logger = logging.getLogger(__name__)
    
    config = get_config()
    if not config.enabled:
        logger.debug("Web search is disabled")
        return False
    if not config.api_key:
        logger.warning("BRAVE_API_KEY not set, web search disabled")
        return False
    return True
