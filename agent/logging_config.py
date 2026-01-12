"""
Production Logging Configuration for Open Rabbit Agent

Provides:
- Structured JSON logging for production
- Correlation ID (session_id) tracking across all logs
- Timing decorators for performance monitoring
- Consistent log levels across all components
"""

import logging
import json
import time
import functools
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from contextvars import ContextVar
import os
import sys

# Context variable for session_id - allows tracking across async calls
current_session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)

# Log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"


class SessionContextFilter(logging.Filter):
    """Filter that adds session_id to all log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = current_session_id.get() or "no-session"
        return True


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Outputs logs in JSON format for easy parsing by log aggregation systems
    like ELK, Datadog, or CloudWatch.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, 'session_id', 'no-session'),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        extra_data = getattr(record, 'extra_data', None)
        if extra_data is not None:
            log_data["data"] = extra_data
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add duration if present (from timing decorator)
        duration_ms = getattr(record, 'duration_ms', None)
        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms
        
        return json.dumps(log_data)


class ColoredTextFormatter(logging.Formatter):
    """
    Colored text formatter for development/debugging.
    
    More readable than JSON for local development.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        session_id = getattr(record, 'session_id', 'no-session')
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Format: [TIME] [LEVEL] [SESSION] logger - message
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        
        msg = (
            f"{color}[{timestamp}] [{record.levelname:8}]{self.RESET} "
            f"[{session_id[:8]}] {record.name} - {record.getMessage()}"
        )
        
        # Add duration if present
        duration_ms = getattr(record, 'duration_ms', None)
        if duration_ms is not None:
            msg += f" ({duration_ms:.1f}ms)"
        
        # Add exception info if present
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"
        
        return msg


def setup_logging() -> None:
    """
    Configure logging for the entire agent system.
    
    Call this once at application startup.
    """
    # Get root logger for agent module
    agent_logger = logging.getLogger("agent")
    agent_logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Remove existing handlers
    agent_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Choose formatter based on environment
    if LOG_FORMAT == "json":
        formatter = JSONFormatter()
    else:
        formatter = ColoredTextFormatter()
    
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SessionContextFilter())
    
    agent_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    agent_logger.propagate = False
    
    # Also configure related loggers
    for logger_name in ["routes", "services", "db"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, LOG_LEVEL))
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the agent namespace.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing file", extra={"extra_data": {"file": "foo.py"}})
    """
    # Ensure name is under agent namespace
    if not name.startswith("agent"):
        name = f"agent.{name}"
    return logging.getLogger(name)


def set_session_id(session_id: str) -> None:
    """Set the current session ID for log correlation."""
    current_session_id.set(session_id)


def get_session_id() -> Optional[str]:
    """Get the current session ID."""
    return current_session_id.get()


def log_with_data(
    logger: logging.Logger,
    level: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Log a message with structured data.
    
    Usage:
        log_with_data(logger, logging.INFO, "File processed", {"file": "foo.py", "issues": 5})
    """
    extra = kwargs.get('extra', {})
    if data:
        extra['extra_data'] = data
    kwargs['extra'] = extra
    logger.log(level, message, **kwargs)


def timed(func: Callable) -> Callable:
    """
    Decorator to log execution time of a function.
    
    Works with both sync and async functions.
    
    Usage:
        @timed
        async def my_function():
            ...
    """
    logger = get_logger(func.__module__)
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        func_name = func.__qualname__
        
        logger.debug(f"Starting {func_name}")
        
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            
            # Create log record with duration
            logger.info(
                f"Completed {func_name}",
                extra={'duration_ms': duration_ms}
            )
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"Failed {func_name}: {e}",
                extra={'duration_ms': duration_ms},
                exc_info=True
            )
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        func_name = func.__qualname__
        
        logger.debug(f"Starting {func_name}")
        
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            
            logger.info(
                f"Completed {func_name}",
                extra={'duration_ms': duration_ms}
            )
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"Failed {func_name}: {e}",
                extra={'duration_ms': duration_ms},
                exc_info=True
            )
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class LogContext:
    """
    Context manager for scoped logging with additional context.
    
    Usage:
        with LogContext(logger, "Processing PR", pr_number=123):
            # All logs in this block will have the context
            logger.info("Found issues")
    """
    
    def __init__(self, logger: logging.Logger, operation: str, **context: Any):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: float = 0.0
    
    def __enter__(self) -> "LogContext":
        self.start_time = time.perf_counter()
        log_with_data(
            self.logger,
            logging.INFO,
            f"Starting: {self.operation}",
            self.context
        )
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        if exc_type:
            log_with_data(
                self.logger,
                logging.ERROR,
                f"Failed: {self.operation}",
                {**self.context, "error": str(exc_val), "duration_ms": duration_ms}
            )
        else:
            log_with_data(
                self.logger,
                logging.INFO,
                f"Completed: {self.operation}",
                {**self.context, "duration_ms": duration_ms}
            )
        
        return False  # Don't suppress exceptions


class AsyncLogContext:
    """
    Async context manager for scoped logging.
    
    Usage:
        async with AsyncLogContext(logger, "Processing PR", pr_number=123):
            await some_async_operation()
    """
    
    def __init__(self, logger: logging.Logger, operation: str, **context: Any):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: float = 0.0
    
    async def __aenter__(self) -> "AsyncLogContext":
        self.start_time = time.perf_counter()
        log_with_data(
            self.logger,
            logging.INFO,
            f"Starting: {self.operation}",
            self.context
        )
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        if exc_type:
            log_with_data(
                self.logger,
                logging.ERROR,
                f"Failed: {self.operation}",
                {**self.context, "error": str(exc_val), "duration_ms": duration_ms}
            )
        else:
            log_with_data(
                self.logger,
                logging.INFO,
                f"Completed: {self.operation}",
                {**self.context, "duration_ms": duration_ms}
            )
        
        return False


# Workflow state logging helpers
def log_workflow_transition(logger: logging.Logger, from_node: str, to_node: str, reason: str = "") -> None:
    """Log a workflow state transition."""
    log_with_data(
        logger,
        logging.INFO,
        f"Workflow transition: {from_node} -> {to_node}",
        {"from": from_node, "to": to_node, "reason": reason}
    )


def log_agent_start(logger: logging.Logger, agent_name: str, files_count: int, **context) -> None:
    """Log agent execution start."""
    log_with_data(
        logger,
        logging.INFO,
        f"Agent started: {agent_name}",
        {"agent": agent_name, "files_count": files_count, **context}
    )


def log_agent_complete(
    logger: logging.Logger,
    agent_name: str,
    duration_ms: float,
    results_summary: Dict[str, Any]
) -> None:
    """Log agent execution completion."""
    log_with_data(
        logger,
        logging.INFO,
        f"Agent completed: {agent_name}",
        {"agent": agent_name, "duration_ms": duration_ms, **results_summary}
    )


def log_llm_call(
    logger: logging.Logger,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float
) -> None:
    """Log an LLM API call."""
    log_with_data(
        logger,
        logging.INFO,
        f"LLM call: {model}",
        {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "duration_ms": duration_ms,
            "total_tokens": prompt_tokens + completion_tokens
        }
    )


def log_checkpoint_saved(logger: logging.Logger, session_id: str, node: str) -> None:
    """Log checkpoint save."""
    log_with_data(
        logger,
        logging.DEBUG,
        f"Checkpoint saved at node: {node}",
        {"session_id": session_id, "node": node}
    )


def log_checkpoint_restored(logger: logging.Logger, session_id: str, node: str) -> None:
    """Log checkpoint restore."""
    log_with_data(
        logger,
        logging.INFO,
        f"Checkpoint restored from node: {node}",
        {"session_id": session_id, "node": node}
    )
