"""
Services module for the agent.

Contains external service integrations.
"""

from .kb_client import KBClient, KBClientConfig
from .sandbox_manager import (
    SandboxManager,
    SandboxConfig,
    SandboxSession,
    SandboxStatus,
    SandboxError,
    SandboxCreationError,
    SandboxOperationError,
    SandboxNotFoundError,
)
from .job_queue import (
    RedisJobQueue,
    InMemoryJobQueue,
    JobQueue,
    JobData,
    JobStatus,
    JobPriority,
    get_job_queue,
    reset_job_queue,
)
from .cache import (
    TTLCache,
    CacheEntry,
    CacheStats,
    get_search_cache,
    get_package_cache,
    reset_caches,
)

__all__ = [
    # KB Client
    "KBClient",
    "KBClientConfig",
    # Sandbox Manager
    "SandboxManager",
    "SandboxConfig",
    "SandboxSession",
    "SandboxStatus",
    "SandboxError",
    "SandboxCreationError",
    "SandboxOperationError",
    "SandboxNotFoundError",
    # Job Queue
    "RedisJobQueue",
    "InMemoryJobQueue",
    "JobQueue",
    "JobData",
    "JobStatus",
    "JobPriority",
    "get_job_queue",
    "reset_job_queue",
    # Cache
    "TTLCache",
    "CacheEntry",
    "CacheStats",
    "get_search_cache",
    "get_package_cache",
    "reset_caches",
]
