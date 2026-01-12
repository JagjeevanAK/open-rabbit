"""
Redis Task Store

Provides persistent task storage using Redis for the bot webhook.
Supports both Redis and in-memory fallback for development/testing.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TaskData:
    """Task data structure."""
    task_id: str
    status: str  # pending, running, completed, failed
    owner: str
    repo: str
    pr_number: Optional[int] = None
    issue_number: Optional[int] = None
    test_branch: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskData":
        return cls(**data)


class TaskStore:
    """
    Abstract base for task storage.
    """
    
    def save_task(self, task: TaskData) -> bool:
        raise NotImplementedError
    
    def get_task(self, task_id: str) -> Optional[TaskData]:
        raise NotImplementedError
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        raise NotImplementedError
    
    def delete_task(self, task_id: str) -> bool:
        raise NotImplementedError
    
    def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[TaskData]:
        raise NotImplementedError
    
    def health_check(self) -> bool:
        raise NotImplementedError


class RedisTaskStore(TaskStore):
    """
    Redis-backed task storage.
    
    Tasks are stored as JSON with a TTL for automatic cleanup.
    """
    
    # Key prefixes
    TASK_PREFIX = "openrabbit:task:"
    TASK_LIST_KEY = "openrabbit:task_list"
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        task_ttl_hours: int = 24,
    ):
        """
        Initialize Redis task store.
        
        Args:
            redis_url: Redis connection URL (defaults to env var or localhost)
            task_ttl_hours: Hours to keep tasks before expiry
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.task_ttl = timedelta(hours=task_ttl_hours)
        self._client = None
        
    def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
                # Test connection
                self._client.ping()
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._client
    
    def _task_key(self, task_id: str) -> str:
        """Get Redis key for a task."""
        return f"{self.TASK_PREFIX}{task_id}"
    
    def save_task(self, task: TaskData) -> bool:
        """Save a task to Redis."""
        try:
            client = self._get_client()
            key = self._task_key(task.task_id)
            
            # Save task data
            client.setex(
                key,
                self.task_ttl,
                json.dumps(task.to_dict())
            )
            
            # Add to task list (sorted set by creation time)
            score = datetime.fromisoformat(task.created_at).timestamp()
            client.zadd(self.TASK_LIST_KEY, {task.task_id: score})
            
            logger.debug(f"Saved task {task.task_id} to Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[TaskData]:
        """Get a task from Redis."""
        try:
            client = self._get_client()
            key = self._task_key(task_id)
            
            data = client.get(key)
            if not data:
                return None
            
            return TaskData.from_dict(json.loads(data))
            
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update a task in Redis."""
        try:
            task = self.get_task(task_id)
            if not task:
                return False
            
            # Apply updates
            task_dict = task.to_dict()
            task_dict.update(updates)
            
            # Save back
            updated_task = TaskData.from_dict(task_dict)
            return self.save_task(updated_task)
            
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task from Redis."""
        try:
            client = self._get_client()
            key = self._task_key(task_id)
            
            # Remove from both key and list
            client.delete(key)
            client.zrem(self.TASK_LIST_KEY, task_id)
            
            logger.debug(f"Deleted task {task_id} from Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
    
    def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[TaskData]:
        """List tasks from Redis."""
        try:
            client = self._get_client()
            
            # Get task IDs (most recent first)
            task_ids = client.zrevrange(self.TASK_LIST_KEY, 0, limit * 2)  # Get more to filter
            
            tasks = []
            for task_id in task_ids:
                task = self.get_task(task_id)
                if task:
                    if status is None or task.status == status:
                        tasks.append(task)
                        if len(tasks) >= limit:
                            break
                else:
                    # Task expired, remove from list
                    client.zrem(self.TASK_LIST_KEY, task_id)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check Redis connection."""
        try:
            client = self._get_client()
            return client.ping()
        except Exception:
            return False
    
    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


class InMemoryTaskStore(TaskStore):
    """
    In-memory task storage for development/testing.
    """
    
    def __init__(self):
        self._tasks: Dict[str, TaskData] = {}
    
    def save_task(self, task: TaskData) -> bool:
        self._tasks[task.task_id] = task
        return True
    
    def get_task(self, task_id: str) -> Optional[TaskData]:
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task_dict = task.to_dict()
        task_dict.update(updates)
        self._tasks[task_id] = TaskData.from_dict(task_dict)
        return True
    
    def delete_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[TaskData]:
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by creation time (most recent first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def health_check(self) -> bool:
        return True


# Global task store instance
_task_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    """
    Get the global task store instance.
    
    Uses Redis if REDIS_URL is set, otherwise falls back to in-memory.
    """
    global _task_store
    
    if _task_store is None:
        redis_url = os.getenv("REDIS_URL")
        use_redis = os.getenv("USE_REDIS", "true").lower() == "true"
        
        if use_redis and redis_url:
            try:
                _task_store = RedisTaskStore(redis_url=redis_url)
                # Test connection
                if _task_store.health_check():
                    logger.info("Using Redis task store")
                else:
                    raise Exception("Redis health check failed")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis, falling back to in-memory: {e}")
                _task_store = InMemoryTaskStore()
        else:
            logger.info("Using in-memory task store")
            _task_store = InMemoryTaskStore()
    
    return _task_store


def reset_task_store():
    """Reset the global task store (for testing)."""
    global _task_store
    if _task_store and hasattr(_task_store, 'close'):
        _task_store.close()
    _task_store = None
