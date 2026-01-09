"""
Langfuse Integration Module

Provides tracing and evaluation capabilities for the agent using Langfuse Cloud.
Uses the observe decorator for automatic tracing without requiring langchain package.
"""

import os
from typing import Optional
from functools import lru_cache

from langfuse import Langfuse
from langfuse import observe

from .logging_config import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_langfuse_client() -> Optional[Langfuse]:
    """
    Get or create a Langfuse client singleton.
    
    Returns None if Langfuse is not configured.
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
    
    if not enabled:
        logger.info("Langfuse is disabled via LANGFUSE_ENABLED=false")
        return None
    
    if not public_key or not secret_key:
        logger.warning(
            "Langfuse credentials not configured. "
            "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing."
        )
        return None
    
    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info(f"Langfuse client initialized (host: {host})")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse client: {e}")
        return None


def create_langfuse_trace(
    name: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
):
    """
    Create a Langfuse trace for a workflow run.
    
    Args:
        name: Name for the trace
        session_id: Session ID for grouping related traces
        user_id: User ID for attribution
        tags: Optional tags for filtering in Langfuse UI
        metadata: Optional metadata dict
        
    Returns:
        Trace object if Langfuse is configured, None otherwise
    """
    client = get_langfuse_client()
    if not client:
        return None
    
    try:
        trace = client.trace(
            name=name,
            session_id=session_id,
            user_id=user_id,
            tags=tags or ["open-rabbit"],
            metadata=metadata or {},
        )
        return trace
    except Exception as e:
        logger.error(f"Failed to create Langfuse trace: {e}")
        return None


def score_trace(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
) -> bool:
    """
    Add a score to a Langfuse trace.
    
    Args:
        trace_id: The trace ID to score
        name: Name of the score (e.g., "quality", "accuracy")
        value: Score value (0.0 - 1.0)
        comment: Optional comment explaining the score
        
    Returns:
        True if score was added successfully
    """
    client = get_langfuse_client()
    if not client:
        return False
    
    try:
        client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )
        logger.debug(f"Added score '{name}={value}' to trace {trace_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add score to trace: {e}")
        return False


def flush_langfuse() -> None:
    """Flush any pending Langfuse events."""
    client = get_langfuse_client()
    if client:
        try:
            client.flush()
        except Exception as e:
            logger.error(f"Failed to flush Langfuse: {e}")


__all__ = [
    "get_langfuse_client",
    "create_langfuse_trace",
    "score_trace",
    "flush_langfuse",
    "observe",
]
