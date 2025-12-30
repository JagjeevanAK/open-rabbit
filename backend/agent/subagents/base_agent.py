"""
Base Agent Class

Abstract base class for all subagents in the code review pipeline.
Provides common functionality:
- Checkpointing for resumability
- Status tracking
- Error handling
- Logging
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar, Generic, Optional, Dict, Any
import hashlib
import json
import logging
import traceback

from agent.schemas.common import AgentStatus, AgentCheckpoint


# Type variables for input/output
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class BaseAgent(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for all subagents.
    
    Provides:
    - Checkpointing for state persistence and resumability
    - Consistent status tracking
    - Error handling with proper logging
    - Input validation
    
    Subclasses must implement:
    - name: Agent name property
    - _execute(): Core execution logic
    - _validate_input(): Input validation
    """
    
    def __init__(self, enable_checkpointing: bool = True):
        """
        Initialize base agent.
        
        Args:
            enable_checkpointing: Whether to create checkpoints
        """
        self.enable_checkpointing = enable_checkpointing
        self._checkpoint: Optional[AgentCheckpoint] = None
        self._logger = logging.getLogger(f"agent.{self.name}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for identification"""
        pass
    
    @abstractmethod
    def _execute(self, input_data: TInput) -> TOutput:
        """
        Core execution logic. Must be implemented by subclasses.
        
        Args:
            input_data: Validated input data
            
        Returns:
            Agent output
            
        Raises:
            Exception: If execution fails
        """
        pass
    
    @abstractmethod
    def _validate_input(self, input_data: TInput) -> None:
        """
        Validate input data before execution.
        
        Args:
            input_data: Input to validate
            
        Raises:
            ValueError: If input is invalid
        """
        pass
    
    def _compute_input_hash(self, input_data: TInput) -> str:
        """
        Compute a hash of the input for cache validation.
        
        Args:
            input_data: Input data to hash
            
        Returns:
            Hash string
        """
        try:
            # Try to serialize to JSON for hashing
            if hasattr(input_data, "model_dump"):
                data = input_data.model_dump()
            elif hasattr(input_data, "dict"):
                data = input_data.dict()
            else:
                data = str(input_data)
            
            json_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.md5(json_str.encode()).hexdigest()
        except Exception:
            return ""
    
    def _create_checkpoint(
        self,
        status: AgentStatus,
        input_hash: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> AgentCheckpoint:
        """
        Create a checkpoint for the current execution.
        
        Args:
            status: Current status
            input_hash: Hash of input data
            output: Optional output data
            error: Optional error message
            
        Returns:
            AgentCheckpoint object
        """
        now = datetime.now()
        
        return AgentCheckpoint(
            agent_name=self.name,
            status=status,
            started_at=self._checkpoint.started_at if self._checkpoint else now,
            completed_at=now if status in (AgentStatus.SUCCESS, AgentStatus.FAILED) else None,
            input_hash=input_hash,
            output=output,
            error=error
        )
    
    def run(self, input_data: TInput) -> tuple[TOutput, AgentCheckpoint]:
        """
        Execute the agent with full lifecycle management.
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            Tuple of (output, checkpoint)
        """
        input_hash = self._compute_input_hash(input_data)
        started_at = datetime.now()
        
        # Initialize checkpoint
        self._checkpoint = AgentCheckpoint(
            agent_name=self.name,
            status=AgentStatus.RUNNING,
            started_at=started_at,
            input_hash=input_hash
        )
        
        self._logger.info(f"Starting {self.name} agent")
        
        try:
            # Validate input
            self._validate_input(input_data)
            
            # Execute
            output = self._execute(input_data)
            
            # Create success checkpoint
            output_dict = None
            if hasattr(output, "model_dump"):
                output_dict = output.model_dump()
            elif hasattr(output, "dict"):
                output_dict = output.dict()
            
            checkpoint = self._create_checkpoint(
                status=AgentStatus.SUCCESS,
                input_hash=input_hash,
                output=output_dict
            )
            
            duration = (datetime.now() - started_at).total_seconds()
            self._logger.info(f"Completed {self.name} agent in {duration:.2f}s")
            
            return output, checkpoint
            
        except ValueError as e:
            # Validation error
            self._logger.error(f"Validation error in {self.name}: {str(e)}")
            checkpoint = self._create_checkpoint(
                status=AgentStatus.FAILED,
                input_hash=input_hash,
                error=f"Validation error: {str(e)}"
            )
            raise
            
        except Exception as e:
            # Execution error
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._logger.error(f"Error in {self.name}: {error_msg}")
            self._logger.debug(traceback.format_exc())
            
            checkpoint = self._create_checkpoint(
                status=AgentStatus.FAILED,
                input_hash=input_hash,
                error=error_msg
            )
            
            # Re-raise with checkpoint attached
            e.checkpoint = checkpoint  # type: ignore
            raise
    
    def get_checkpoint(self) -> Optional[AgentCheckpoint]:
        """Get the current checkpoint."""
        return self._checkpoint
    
    def can_resume_from_checkpoint(
        self,
        checkpoint: AgentCheckpoint,
        input_data: TInput
    ) -> bool:
        """
        Check if execution can be resumed from a checkpoint.
        
        Args:
            checkpoint: Previous checkpoint
            input_data: Current input data
            
        Returns:
            True if checkpoint is valid for resumption
        """
        if checkpoint.agent_name != self.name:
            return False
        
        if checkpoint.status != AgentStatus.SUCCESS:
            return False
        
        # Verify input hasn't changed
        current_hash = self._compute_input_hash(input_data)
        if current_hash != checkpoint.input_hash:
            return False
        
        return True


class MockAgent(BaseAgent[TInput, TOutput]):
    """
    Mock agent for testing purposes.
    
    Returns predefined output without actual execution.
    """
    
    def __init__(
        self,
        agent_name: str,
        mock_output: TOutput,
        should_fail: bool = False,
        failure_message: str = "Mock failure"
    ):
        """
        Initialize mock agent.
        
        Args:
            agent_name: Name for this mock agent
            mock_output: Output to return
            should_fail: Whether to simulate failure
            failure_message: Error message if failing
        """
        # Set name before calling super().__init__ since it accesses self.name
        self._name = agent_name
        self._mock_output = mock_output
        self._should_fail = should_fail
        self._failure_message = failure_message
        super().__init__(enable_checkpointing=True)
    
    @property
    def name(self) -> str:
        return self._name
    
    def _validate_input(self, input_data: TInput) -> None:
        # Mock validation always passes
        pass
    
    def _execute(self, input_data: TInput) -> TOutput:
        if self._should_fail:
            raise RuntimeError(self._failure_message)
        return self._mock_output
