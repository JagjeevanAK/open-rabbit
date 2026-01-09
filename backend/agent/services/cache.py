"""
TTL-based cache service for web search results.

Provides in-memory caching with automatic expiration to minimize
redundant API calls to external search services.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with TTL support."""
    value: T
    created_at: float
    ttl_seconds: int
    hits: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get the age of this entry in seconds."""
        return time.time() - self.created_at
    
    @property
    def remaining_ttl(self) -> float:
        """Get remaining TTL in seconds (0 if expired)."""
        remaining = (self.created_at + self.ttl_seconds) - time.time()
        return max(0, remaining)


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "hit_rate_percent": round(self.hit_rate, 2)
        }


class TTLCache(Generic[T]):
    """
    Thread-safe in-memory cache with TTL support.
    
    Features:
    - Automatic expiration of entries
    - Configurable default TTL
    - Per-entry TTL override
    - Statistics tracking
    - Thread-safe operations
    - Automatic cleanup of expired entries
    
    Usage:
        cache = TTLCache[str](default_ttl=3600)  # 1 hour default
        cache.set("key", "value")
        result = cache.get("key")  # Returns "value" or None if expired
    """
    
    def __init__(
        self,
        default_ttl: int = 86400,  # 24 hours
        max_entries: int = 1000,
        cleanup_interval: int = 300,  # 5 minutes
    ):
        """
        Initialize the cache.
        
        Args:
            default_ttl: Default TTL in seconds (default: 24 hours)
            max_entries: Maximum number of entries before LRU eviction
            cleanup_interval: How often to run cleanup in seconds
        """
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._stats = CacheStats()
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _maybe_cleanup(self) -> None:
        """Run cleanup if enough time has passed."""
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = time.time()
    
    def _cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        for key in expired_keys:
            del self._cache[key]
            self._stats.evictions += 1
        
        self._stats.total_entries = len(self._cache)
        
        if expired_keys:
            logger.debug(f"Cache cleanup: removed {len(expired_keys)} expired entries")
        
        return len(expired_keys)
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries if over max_entries."""
        if len(self._cache) <= self._max_entries:
            return
        
        # Sort by created_at (oldest first) and hits (least used first)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: (x[1].hits, -x[1].created_at)
        )
        
        # Remove oldest/least used entries
        entries_to_remove = len(self._cache) - self._max_entries
        for key, _ in sorted_entries[:entries_to_remove]:
            del self._cache[key]
            self._stats.evictions += 1
        
        self._stats.total_entries = len(self._cache)
        logger.debug(f"Cache LRU eviction: removed {entries_to_remove} entries")
    
    def get(self, key: str) -> Optional[T]:
        """
        Get a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            The cached value or None if not found/expired
        """
        with self._lock:
            self._maybe_cleanup()
            
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                self._stats.total_entries = len(self._cache)
                return None
            
            entry.hits += 1
            self._stats.hits += 1
            return entry.value
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Optional TTL override in seconds
        """
        with self._lock:
            self._maybe_cleanup()
            self._evict_lru()
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl or self._default_ttl
            )
            self._stats.total_entries = len(self._cache)
    
    def get_or_set(
        self,
        key: str,
        factory: Any,
        ttl: Optional[int] = None
    ) -> T:
        """
        Get a value from cache, or compute and store it if not present.
        
        Args:
            key: The cache key
            factory: A callable that returns the value to cache
            ttl: Optional TTL override in seconds
            
        Returns:
            The cached or newly computed value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Compute the value (outside the lock to avoid blocking)
        new_value = factory()
        self.set(key, new_value, ttl)
        return new_value
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            True if the key was found and deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.total_entries = len(self._cache)
                return True
            return False
    
    def clear(self) -> int:
        """
        Clear all entries from the cache.
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.total_entries = 0
            return count
    
    def has(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        return self.get(key) is not None
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.total_entries = len(self._cache)
            return self._stats
    
    def __len__(self) -> int:
        """Return the number of entries in the cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if a key is in the cache."""
        return self.has(key)


# Global cache instances for different purposes
_search_cache: Optional[TTLCache[Dict[str, Any]]] = None
_package_cache: Optional[TTLCache[Dict[str, Any]]] = None


def get_search_cache() -> TTLCache[Dict[str, Any]]:
    """Get or create the global search results cache."""
    global _search_cache
    if _search_cache is None:
        ttl = int(os.getenv("SEARCH_CACHE_TTL", "86400"))  # 24 hours default
        max_entries = int(os.getenv("SEARCH_CACHE_MAX_ENTRIES", "1000"))
        _search_cache = TTLCache[Dict[str, Any]](
            default_ttl=ttl,
            max_entries=max_entries
        )
        logger.info(f"Initialized search cache with TTL={ttl}s, max_entries={max_entries}")
    return _search_cache


def get_package_cache() -> TTLCache[Dict[str, Any]]:
    """Get or create the global package information cache."""
    global _package_cache
    if _package_cache is None:
        ttl = int(os.getenv("PACKAGE_CACHE_TTL", "43200"))  # 12 hours default
        max_entries = int(os.getenv("PACKAGE_CACHE_MAX_ENTRIES", "500"))
        _package_cache = TTLCache[Dict[str, Any]](
            default_ttl=ttl,
            max_entries=max_entries
        )
        logger.info(f"Initialized package cache with TTL={ttl}s, max_entries={max_entries}")
    return _package_cache


def reset_caches() -> None:
    """Reset all global caches. Useful for testing."""
    global _search_cache, _package_cache
    _search_cache = None
    _package_cache = None
