"""
Base Agent

Abstract base class for all sub-agents in the multi-agent system.
Provides common functionality for:
- Async execution
- Error handling
- Status tracking
- Production logging with timing
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar

from ..schemas.common import AgentStatus, AgentResult
from ..logging_config import (
    get_logger,
    get_session_id,
    log_with_data,
    log_agent_start,
    log_agent_complete,
)

logger = get_logger(__name__)


# Type variable for output type
TOutput = TypeVar("TOutput")


@dataclass
class AgentConfig:
    """Configuration for agent execution."""
    name: str
    timeout_seconds: float = 300.0  # 5 minutes default
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    enable_logging: bool = True
    extra_config: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC, Generic[TOutput]):
    """
    Abstract base class for all sub-agents.
    
    Sub-agents must implement:
    - _execute(): The main execution logic (async)
    - name property: Agent name for logging/tracking
    
    Provides:
    - Async run() method with error handling
    - Status tracking
    - Timing information
    - Retry logic
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration. If None, uses defaults.
        """
        self.config = config or AgentConfig(name=self.name)
        self._status = AgentStatus.PENDING
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for identification."""
        pass
    
    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        return self._status
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Execution duration in seconds."""
        if self._started_at and self._completed_at:
            return (self._completed_at - self._started_at).total_seconds()
        return None
    
    async def run(self, *args, **kwargs) -> AgentResult:
        """
        Run the agent with error handling and status tracking.
        
        Returns:
            AgentResult with status, output, and timing information.
        """
        self._status = AgentStatus.RUNNING
        self._started_at = datetime.utcnow()
        self._last_error = None
        start_time = time.perf_counter()
        
        session_id = get_session_id() or "unknown"
        
        log_with_data(logger, 20, f"Agent starting: {self.name}", {
            "agent": self.name,
            "session_id": session_id,
            "timeout_seconds": self.config.timeout_seconds,
        })
        
        output = None
        error = None
        
        try:
            # Execute with timeout
            output = await asyncio.wait_for(
                self._execute(*args, **kwargs),
                timeout=self.config.timeout_seconds
            )
            self._status = AgentStatus.COMPLETED
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_with_data(logger, 20, f"Agent completed: {self.name}", {
                "agent": self.name,
                "session_id": session_id,
                "status": "completed",
                "duration_ms": round(duration_ms, 2),
            })
                
        except asyncio.TimeoutError:
            self._status = AgentStatus.FAILED
            error = f"Execution timed out after {self.config.timeout_seconds} seconds"
            self._last_error = error
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_with_data(logger, 40, f"Agent timed out: {self.name}", {
                "agent": self.name,
                "session_id": session_id,
                "status": "timeout",
                "timeout_seconds": self.config.timeout_seconds,
                "duration_ms": round(duration_ms, 2),
            })
                
        except Exception as e:
            self._status = AgentStatus.FAILED
            error = str(e)
            self._last_error = error
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_with_data(logger, 40, f"Agent failed: {self.name} - {error}", {
                "agent": self.name,
                "session_id": session_id,
                "status": "failed",
                "error": error,
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
            })
        
        finally:
            self._completed_at = datetime.utcnow()
        
        return AgentResult(
            agent_name=self.name,
            status=self._status,
            output=output,
            error=error,
            started_at=self._started_at.isoformat() if self._started_at else None,
            completed_at=self._completed_at.isoformat() if self._completed_at else None,
            duration_seconds=self.duration_seconds,
        )
    
    async def run_with_retry(self, *args, **kwargs) -> AgentResult:
        """
        Run the agent with retry logic.
        
        Retries on failure up to max_retries times.
        """
        last_result = None
        session_id = get_session_id() or "unknown"
        
        for attempt in range(self.config.max_retries):
            if attempt > 0:
                log_with_data(logger, 30, f"Agent retry attempt: {self.name}", {
                    "agent": self.name,
                    "session_id": session_id,
                    "attempt": attempt + 1,
                    "max_retries": self.config.max_retries,
                    "delay_seconds": self.config.retry_delay_seconds * attempt,
                })
                await asyncio.sleep(self.config.retry_delay_seconds * attempt)
            
            result = await self.run(*args, **kwargs)
            last_result = result
            
            if result.status == AgentStatus.COMPLETED:
                return result
        
        # All retries failed
        log_with_data(logger, 40, f"Agent all retries failed: {self.name}", {
            "agent": self.name,
            "session_id": session_id,
            "total_attempts": self.config.max_retries,
            "last_error": last_result.error if last_result else "unknown",
        })
        
        return last_result or AgentResult(
            agent_name=self.name,
            status=AgentStatus.FAILED,
            error="All retry attempts failed",
        )
    
    @abstractmethod
    async def _execute(self, *args, **kwargs) -> TOutput:
        """
        Execute the agent's main logic.
        
        Must be implemented by subclasses.
        
        Returns:
            Agent-specific output type (ParserOutput, ReviewOutput, TestOutput)
        """
        pass
    
    def reset(self):
        """Reset agent state for reuse."""
        self._status = AgentStatus.PENDING
        self._started_at = None
        self._completed_at = None
        self._last_error = None


class MockBaseAgent(BaseAgent[TOutput]):
    """
    Mock base agent for testing.
    
    Returns predefined output without executing real logic.
    """
    
    def __init__(
        self,
        name: str,
        mock_output: TOutput,
        should_fail: bool = False,
        fail_message: str = "Mock failure",
        delay_seconds: float = 0.0,
    ):
        self._name = name
        self._mock_output = mock_output
        self._should_fail = should_fail
        self._fail_message = fail_message
        self._delay_seconds = delay_seconds
        super().__init__()
    
    @property
    def name(self) -> str:
        return self._name
    
    async def _execute(self, *args, **kwargs) -> TOutput:
        if self._delay_seconds > 0:
            await asyncio.sleep(self._delay_seconds)
        
        if self._should_fail:
            raise RuntimeError(self._fail_message)
        
        return self._mock_output
