"""
Redis Job Queue for Retrying Failed Operations

Provides a reliable job queue for sandbox operations that need retry capability.
Uses Redis for persistence and supports:
- Job submission with priority
- Automatic retries with exponential backoff
- Dead letter queue for permanently failed jobs
- Job status tracking

This is used by the supervisor to queue operations that may fail transiently
(e.g., sandbox creation, git clone, API calls) and need retry logic.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable, Union, cast
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # Max retries exceeded


class JobPriority(int, Enum):
    """Job priority levels (lower = higher priority)."""
    HIGH = 1
    NORMAL = 5
    LOW = 10


@dataclass
class JobData:
    """
    Job data structure.
    
    Stores all information needed to execute and track a job.
    """
    job_id: str
    job_type: str  # e.g., "sandbox_create", "clone_repo", "parse_file"
    status: str = JobStatus.PENDING.value
    priority: int = JobPriority.NORMAL.value
    
    # Job payload
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Execution context
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None  # For grouping related jobs
    
    # Retry configuration
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_seconds: float = 5.0
    retry_backoff_multiplier: float = 2.0
    next_retry_at: Optional[str] = None
    
    # Timing
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_history: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.job_id:
            self.job_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobData":
        # Handle enum conversions
        return cls(
            job_id=data.get("job_id", str(uuid.uuid4())),
            job_type=data["job_type"],
            status=data.get("status", JobStatus.PENDING.value),
            priority=data.get("priority", JobPriority.NORMAL.value),
            payload=data.get("payload", {}),
            session_id=data.get("session_id"),
            correlation_id=data.get("correlation_id"),
            max_retries=data.get("max_retries", 3),
            retry_count=data.get("retry_count", 0),
            retry_delay_seconds=data.get("retry_delay_seconds", 5.0),
            retry_backoff_multiplier=data.get("retry_backoff_multiplier", 2.0),
            next_retry_at=data.get("next_retry_at"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error=data.get("error"),
            error_history=data.get("error_history", []),
        )
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries
    
    def calculate_next_retry_delay(self) -> float:
        """Calculate delay for next retry using exponential backoff."""
        return self.retry_delay_seconds * (self.retry_backoff_multiplier ** self.retry_count)
    
    def schedule_retry(self):
        """Schedule the next retry."""
        delay = self.calculate_next_retry_delay()
        self.next_retry_at = (datetime.utcnow() + timedelta(seconds=delay)).isoformat()
        self.retry_count += 1
        self.status = JobStatus.RETRYING.value
        if self.error:
            self.error_history.append(f"[{datetime.utcnow().isoformat()}] {self.error}")


class RedisJobQueue:
    """
    Redis-backed job queue with retry support.
    
    Uses Redis sorted sets for priority queue implementation and
    separate keys for job data storage.
    """
    
    # Key prefixes
    QUEUE_KEY = "openrabbit:jobs:queue"           # Sorted set: job_id -> priority
    RETRY_QUEUE_KEY = "openrabbit:jobs:retry"     # Sorted set: job_id -> retry_timestamp
    JOB_PREFIX = "openrabbit:jobs:data:"          # Hash: job_id -> job data
    DEAD_LETTER_KEY = "openrabbit:jobs:dead"      # List of dead job IDs
    PROCESSING_KEY = "openrabbit:jobs:processing" # Set of jobs currently being processed
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        job_ttl_hours: int = 48,
    ):
        """
        Initialize Redis job queue.
        
        Args:
            redis_url: Redis connection URL
            job_ttl_hours: Hours to keep completed jobs
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.job_ttl = timedelta(hours=job_ttl_hours)
        self._client = None
        self._handlers: Dict[str, Callable[[JobData], Awaitable[Dict[str, Any]]]] = {}
        self._running = False
        
    def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                )
                self._client.ping()
                logger.info(f"Job queue connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis for job queue: {e}")
                raise
        return self._client
    
    def _job_key(self, job_id: str) -> str:
        """Get Redis key for job data."""
        return f"{self.JOB_PREFIX}{job_id}"
    
    def register_handler(
        self, 
        job_type: str, 
        handler: Callable[[JobData], Awaitable[Dict[str, Any]]]
    ):
        """
        Register a handler for a job type.
        
        Args:
            job_type: Type of job (e.g., "sandbox_create")
            handler: Async function that processes the job and returns result dict
        """
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    async def submit(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Submit a new job to the queue.
        
        Args:
            job_type: Type of job
            payload: Job payload data
            priority: Job priority
            session_id: Associated session ID
            correlation_id: Correlation ID for grouping
            max_retries: Maximum retry attempts
            
        Returns:
            Job ID
        """
        job = JobData(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            priority=priority.value,
            session_id=session_id,
            correlation_id=correlation_id,
            max_retries=max_retries,
        )
        
        client = self._get_client()
        
        # Store job data
        client.setex(
            self._job_key(job.job_id),
            self.job_ttl,
            json.dumps(job.to_dict())
        )
        
        # Add to queue with priority score
        client.zadd(self.QUEUE_KEY, {job.job_id: job.priority})
        
        logger.info(f"Job submitted: {job.job_id} (type={job_type}, priority={priority.name})")
        return job.job_id
    
    async def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job by ID."""
        client = self._get_client()
        data = client.get(self._job_key(job_id))
        
        if not data:
            return None
        
        return JobData.from_dict(json.loads(str(data)))
    
    async def update_job(self, job: JobData):
        """Update job data."""
        client = self._get_client()
        client.setex(
            self._job_key(job.job_id),
            self.job_ttl,
            json.dumps(job.to_dict())
        )
    
    async def pop_next_job(self) -> Optional[JobData]:
        """
        Pop the next job from the queue (highest priority first).
        
        Also checks retry queue for jobs ready to retry.
        
        Returns:
            JobData or None if queue is empty
        """
        client = self._get_client()
        
        # First check retry queue for due jobs
        now = datetime.utcnow().timestamp()
        due_retries: List[str] = client.zrangebyscore(self.RETRY_QUEUE_KEY, 0, now, start=0, num=1)  # type: ignore[assignment]
        
        if due_retries:
            job_id = due_retries[0]
            client.zrem(self.RETRY_QUEUE_KEY, job_id)
            job = await self.get_job(job_id)
            if job:
                client.sadd(self.PROCESSING_KEY, job_id)
                return job
        
        # Then check main queue
        next_jobs: List[str] = client.zrange(self.QUEUE_KEY, 0, 0)  # type: ignore[assignment]
        
        if not next_jobs:
            return None
        
        job_id = next_jobs[0]
        client.zrem(self.QUEUE_KEY, job_id)
        client.sadd(self.PROCESSING_KEY, job_id)
        
        return await self.get_job(job_id)
    
    async def complete_job(self, job: JobData, result: Dict[str, Any]):
        """Mark job as completed."""
        client = self._get_client()
        
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.utcnow().isoformat()
        job.result = result
        job.error = None
        
        await self.update_job(job)
        client.srem(self.PROCESSING_KEY, job.job_id)
        
        logger.info(f"Job completed: {job.job_id}")
    
    async def fail_job(self, job: JobData, error: str):
        """
        Mark job as failed. Schedules retry if allowed.
        
        Args:
            job: The job that failed
            error: Error message
        """
        client = self._get_client()
        
        job.error = error
        
        if job.can_retry():
            job.schedule_retry()
            await self.update_job(job)
            
            # Add to retry queue (next_retry_at is guaranteed to be set by schedule_retry)
            if job.next_retry_at:
                retry_time = datetime.fromisoformat(job.next_retry_at).timestamp()
                client.zadd(self.RETRY_QUEUE_KEY, {job.job_id: retry_time})
            client.srem(self.PROCESSING_KEY, job.job_id)
            
            logger.warning(
                f"Job failed, scheduling retry: {job.job_id} "
                f"(attempt {job.retry_count}/{job.max_retries})"
            )
        else:
            # Max retries exceeded - move to dead letter queue
            job.status = JobStatus.DEAD.value
            job.completed_at = datetime.utcnow().isoformat()
            
            await self.update_job(job)
            client.lpush(self.DEAD_LETTER_KEY, job.job_id)
            client.srem(self.PROCESSING_KEY, job.job_id)
            
            logger.error(f"Job dead (max retries exceeded): {job.job_id}")
    
    async def process_one(self) -> bool:
        """
        Process one job from the queue.
        
        Returns:
            True if a job was processed, False if queue is empty
        """
        job = await self.pop_next_job()
        
        if not job:
            return False
        
        handler = self._handlers.get(job.job_type)
        
        if not handler:
            logger.error(f"No handler for job type: {job.job_type}")
            await self.fail_job(job, f"No handler for job type: {job.job_type}")
            return True
        
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.utcnow().isoformat()
        await self.update_job(job)
        
        try:
            result = await handler(job)
            await self.complete_job(job, result)
        except Exception as e:
            logger.exception(f"Job failed: {job.job_id}")
            await self.fail_job(job, str(e))
        
        return True
    
    async def run_worker(self, poll_interval: float = 1.0):
        """
        Run a worker loop that processes jobs.
        
        Args:
            poll_interval: Seconds between queue checks when empty
        """
        self._running = True
        logger.info("Job queue worker started")
        
        while self._running:
            try:
                processed = await self.process_one()
                
                if not processed:
                    await asyncio.sleep(poll_interval)
                    
            except Exception as e:
                logger.exception("Worker error")
                await asyncio.sleep(poll_interval)
        
        logger.info("Job queue worker stopped")
    
    def stop_worker(self):
        """Stop the worker loop."""
        self._running = False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        client = self._get_client()
        
        return {
            "pending": client.zcard(self.QUEUE_KEY),
            "retrying": client.zcard(self.RETRY_QUEUE_KEY),
            "processing": client.scard(self.PROCESSING_KEY),
            "dead": client.llen(self.DEAD_LETTER_KEY),
        }
    
    async def get_dead_jobs(self, limit: int = 50) -> List[JobData]:
        """Get jobs from dead letter queue."""
        client = self._get_client()
        job_ids: List[str] = client.lrange(self.DEAD_LETTER_KEY, 0, limit - 1)  # type: ignore[assignment]
        
        jobs = []
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)
        
        return jobs
    
    async def retry_dead_job(self, job_id: str) -> bool:
        """
        Manually retry a dead job.
        
        Args:
            job_id: ID of the dead job
            
        Returns:
            True if job was requeued
        """
        client = self._get_client()
        job = await self.get_job(job_id)
        
        if not job:
            return False
        
        # Reset retry state
        job.status = JobStatus.PENDING.value
        job.retry_count = 0
        job.error = None
        job.next_retry_at = None
        
        await self.update_job(job)
        
        # Remove from dead letter, add back to queue
        client.lrem(self.DEAD_LETTER_KEY, 1, job_id)
        client.zadd(self.QUEUE_KEY, {job_id: job.priority})
        
        logger.info(f"Dead job requeued: {job_id}")
        return True
    
    def health_check(self) -> bool:
        """Check Redis connection."""
        try:
            result = self._get_client().ping()
            return bool(result)
        except Exception:
            return False
    
    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


class InMemoryJobQueue:
    """
    In-memory job queue for development/testing.
    
    Provides the same interface as RedisJobQueue but stores everything in memory.
    """
    
    def __init__(self):
        self._jobs: Dict[str, JobData] = {}
        self._queue: List[str] = []  # Sorted by priority
        self._retry_queue: Dict[str, float] = {}  # job_id -> retry_timestamp
        self._processing: set = set()
        self._dead_letter: List[str] = []
        self._handlers: Dict[str, Callable[[JobData], Awaitable[Dict[str, Any]]]] = {}
        self._running = False
    
    def register_handler(
        self, 
        job_type: str, 
        handler: Callable[[JobData], Awaitable[Dict[str, Any]]]
    ):
        self._handlers[job_type] = handler
    
    async def submit(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        job = JobData(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            priority=priority.value,
            session_id=session_id,
            correlation_id=correlation_id,
            max_retries=max_retries,
        )
        
        self._jobs[job.job_id] = job
        self._queue.append(job.job_id)
        self._queue.sort(key=lambda jid: self._jobs[jid].priority)
        
        return job.job_id
    
    async def get_job(self, job_id: str) -> Optional[JobData]:
        return self._jobs.get(job_id)
    
    async def update_job(self, job: JobData):
        self._jobs[job.job_id] = job
    
    async def pop_next_job(self) -> Optional[JobData]:
        # Check retry queue
        now = datetime.utcnow().timestamp()
        for job_id, retry_time in list(self._retry_queue.items()):
            if retry_time <= now:
                del self._retry_queue[job_id]
                self._processing.add(job_id)
                return self._jobs.get(job_id)
        
        # Check main queue
        if not self._queue:
            return None
        
        job_id = self._queue.pop(0)
        self._processing.add(job_id)
        return self._jobs.get(job_id)
    
    async def complete_job(self, job: JobData, result: Dict[str, Any]):
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.utcnow().isoformat()
        job.result = result
        self._processing.discard(job.job_id)
    
    async def fail_job(self, job: JobData, error: str):
        job.error = error
        self._processing.discard(job.job_id)
        
        if job.can_retry():
            job.schedule_retry()
            # next_retry_at is guaranteed to be set by schedule_retry
            if job.next_retry_at:
                retry_time = datetime.fromisoformat(job.next_retry_at).timestamp()
                self._retry_queue[job.job_id] = retry_time
        else:
            job.status = JobStatus.DEAD.value
            job.completed_at = datetime.utcnow().isoformat()
            self._dead_letter.append(job.job_id)
    
    async def process_one(self) -> bool:
        job = await self.pop_next_job()
        if not job:
            return False
        
        handler = self._handlers.get(job.job_type)
        if not handler:
            await self.fail_job(job, f"No handler for job type: {job.job_type}")
            return True
        
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.utcnow().isoformat()
        
        try:
            result = await handler(job)
            await self.complete_job(job, result)
        except Exception as e:
            await self.fail_job(job, str(e))
        
        return True
    
    async def run_worker(self, poll_interval: float = 0.1):
        self._running = True
        while self._running:
            processed = await self.process_one()
            if not processed:
                await asyncio.sleep(poll_interval)
    
    def stop_worker(self):
        self._running = False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        return {
            "pending": len(self._queue),
            "retrying": len(self._retry_queue),
            "processing": len(self._processing),
            "dead": len(self._dead_letter),
        }
    
    async def get_dead_jobs(self, limit: int = 50) -> List[JobData]:
        jobs = []
        for job_id in self._dead_letter[:limit]:
            job = self._jobs.get(job_id)
            if job:
                jobs.append(job)
        return jobs
    
    async def retry_dead_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        job.status = JobStatus.PENDING.value
        job.retry_count = 0
        job.error = None
        
        if job_id in self._dead_letter:
            self._dead_letter.remove(job_id)
        
        self._queue.append(job_id)
        self._queue.sort(key=lambda jid: self._jobs[jid].priority)
        return True
    
    def health_check(self) -> bool:
        return True
    
    def close(self):
        pass


# Type alias for job queue
JobQueue = Union[RedisJobQueue, InMemoryJobQueue]

# Global job queue instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """
    Get the global job queue instance.
    
    Uses Redis if available, otherwise falls back to in-memory.
    """
    global _job_queue
    
    if _job_queue is None:
        redis_url = os.getenv("REDIS_URL")
        use_redis = os.getenv("USE_REDIS", "true").lower() == "true"
        
        if use_redis and redis_url:
            try:
                _job_queue = RedisJobQueue(redis_url=redis_url)
                if _job_queue.health_check():
                    logger.info("Using Redis job queue")
                else:
                    raise Exception("Redis health check failed")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis job queue: {e}")
                _job_queue = InMemoryJobQueue()
        else:
            logger.info("Using in-memory job queue")
            _job_queue = InMemoryJobQueue()
    
    return _job_queue


def reset_job_queue():
    """Reset the global job queue (for testing)."""
    global _job_queue
    if _job_queue:
        _job_queue.close()
    _job_queue = None
