"""
Common Schemas

Defines shared data types used across the multi-agent system:
- Request types
- Knowledge Base context
- User intent
- Supervisor output
- Checkpointing data
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime


class AgentStatus(str, Enum):
    """Status of agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IntentType(str, Enum):
    """Types of user intents."""
    REVIEW_ONLY = "review_only"
    REVIEW_AND_TESTS = "review_and_tests"
    TESTS_ONLY = "tests_only"


@dataclass
class FileInfo:
    """
    Information about a file to be reviewed.
    
    Can include full content, diff, or just metadata.
    """
    path: str
    content: Optional[str] = None
    diff: Optional[str] = None
    language: Optional[str] = None
    
    # Change information
    is_new: bool = False
    is_deleted: bool = False
    is_modified: bool = True
    
    # Line range (for partial review)
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "diff": self.diff,
            "language": self.language,
            "is_new": self.is_new,
            "is_deleted": self.is_deleted,
            "is_modified": self.is_modified,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileInfo":
        return cls(
            path=data["path"],
            content=data.get("content"),
            diff=data.get("diff"),
            language=data.get("language"),
            is_new=data.get("is_new", False),
            is_deleted=data.get("is_deleted", False),
            is_modified=data.get("is_modified", True),
            start_line=data.get("start_line"),
            end_line=data.get("end_line"),
        )


@dataclass
class KBContext:
    """
    Knowledge Base context for review.
    
    Contains relevant excerpts from the KB that inform the review.
    Only the Supervisor can read from KB; sub-agents receive this context.
    """
    coding_style: List[str] = field(default_factory=list)
    conventions: List[str] = field(default_factory=list)
    testing_patterns: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    
    # Raw learnings for reference
    learnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Query metadata
    query_used: Optional[str] = None
    relevance_scores: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "coding_style": self.coding_style,
            "conventions": self.conventions,
            "testing_patterns": self.testing_patterns,
            "best_practices": self.best_practices,
            "learnings": self.learnings,
            "query_used": self.query_used,
            "relevance_scores": self.relevance_scores,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KBContext":
        return cls(
            coding_style=data.get("coding_style", []),
            conventions=data.get("conventions", []),
            testing_patterns=data.get("testing_patterns", []),
            best_practices=data.get("best_practices", []),
            learnings=data.get("learnings", []),
            query_used=data.get("query_used"),
            relevance_scores=data.get("relevance_scores", {}),
        )
    
    def to_prompt_context(self) -> str:
        """Format KB context for injection into agent prompts."""
        parts = []
        
        if self.coding_style:
            parts.append("## Coding Style Guidelines")
            for item in self.coding_style:
                parts.append(f"- {item}")
            parts.append("")
        
        if self.conventions:
            parts.append("## Project Conventions")
            for item in self.conventions:
                parts.append(f"- {item}")
            parts.append("")
        
        if self.testing_patterns:
            parts.append("## Testing Patterns")
            for item in self.testing_patterns:
                parts.append(f"- {item}")
            parts.append("")
        
        if self.best_practices:
            parts.append("## Best Practices")
            for item in self.best_practices:
                parts.append(f"- {item}")
            parts.append("")
        
        return "\n".join(parts) if parts else "No specific KB context available."
    
    def is_empty(self) -> bool:
        """Check if KB context is empty."""
        return not (
            self.coding_style or
            self.conventions or
            self.testing_patterns or
            self.best_practices or
            self.learnings
        )


@dataclass
class UserIntent:
    """
    Parsed user intent from the request.
    
    Determines which agents to invoke.
    """
    intent_type: IntentType = IntentType.REVIEW_ONLY
    should_review: bool = True
    should_generate_tests: bool = False
    
    # Specific targets for test generation
    test_targets: List[str] = field(default_factory=list)  # File paths or function names
    
    # Review scope
    review_scope: str = "diff"  # "diff", "full_file", "directory"
    
    # Raw request text
    raw_request: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "should_review": self.should_review,
            "should_generate_tests": self.should_generate_tests,
            "test_targets": self.test_targets,
            "review_scope": self.review_scope,
            "raw_request": self.raw_request,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserIntent":
        return cls(
            intent_type=IntentType(data.get("intent_type", "review_only")),
            should_review=data.get("should_review", True),
            should_generate_tests=data.get("should_generate_tests", False),
            test_targets=data.get("test_targets", []),
            review_scope=data.get("review_scope", "diff"),
            raw_request=data.get("raw_request"),
        )


@dataclass
class ReviewRequest:
    """
    Input request for code review.
    
    Contains all information needed by the Supervisor to orchestrate the review.
    """
    files: List[FileInfo]
    
    # Optional context
    repo_url: Optional[str] = None
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    
    # User request
    user_request: Optional[str] = None  # e.g., "review this PR and generate unit tests"
    
    # Existing repo path (if already cloned)
    repo_path: Optional[str] = None
    
    # Session/tracking
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": [f.to_dict() for f in self.files],
            "repo_url": self.repo_url,
            "pr_number": self.pr_number,
            "pr_title": self.pr_title,
            "pr_description": self.pr_description,
            "branch": self.branch,
            "base_branch": self.base_branch,
            "user_request": self.user_request,
            "repo_path": self.repo_path,
            "session_id": self.session_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewRequest":
        return cls(
            files=[FileInfo.from_dict(f) for f in data.get("files", [])],
            repo_url=data.get("repo_url"),
            pr_number=data.get("pr_number"),
            pr_title=data.get("pr_title"),
            pr_description=data.get("pr_description"),
            branch=data.get("branch"),
            base_branch=data.get("base_branch"),
            user_request=data.get("user_request"),
            repo_path=data.get("repo_path"),
            session_id=data.get("session_id"),
        )


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    agent_name: str
    status: AgentStatus
    output: Optional[Any] = None  # ParserOutput, ReviewOutput, or TestOutput
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        output_dict = None
        if self.output is not None:
            if hasattr(self.output, 'to_dict'):
                output_dict = self.output.to_dict()
            else:
                output_dict = self.output
        
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "output": output_dict,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class SupervisorOutput:
    """
    Complete output from the Supervisor Agent.
    
    Aggregates results from all sub-agents into a single structured output.
    """
    # Overall status
    status: AgentStatus = AgentStatus.PENDING
    
    # Individual agent results
    parser_result: Optional[AgentResult] = None
    review_result: Optional[AgentResult] = None
    test_result: Optional[AgentResult] = None
    
    # Aggregated output (normalized, deduplicated)
    # These are imported from their respective modules
    parser_output: Optional[Any] = None  # ParserOutput
    review_output: Optional[Any] = None  # ReviewOutput
    test_output: Optional[Any] = None    # TestOutput
    
    # KB context used
    kb_context: Optional[KBContext] = None
    
    # Intent that was parsed
    intent: Optional[UserIntent] = None
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Error information
    error: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    # Session tracking for checkpointing
    session_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "parser_result": self.parser_result.to_dict() if self.parser_result else None,
            "review_result": self.review_result.to_dict() if self.review_result else None,
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "parser_output": self.parser_output.to_dict() if self.parser_output and hasattr(self.parser_output, 'to_dict') else None,
            "review_output": self.review_output.to_dict() if self.review_output and hasattr(self.review_output, 'to_dict') else None,
            "test_output": self.test_output.to_dict() if self.test_output and hasattr(self.test_output, 'to_dict') else None,
            "kb_context": self.kb_context.to_dict() if self.kb_context else None,
            "intent": self.intent.to_dict() if self.intent else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "errors": self.errors,
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
        }
    
    def to_github_review(self) -> Dict[str, Any]:
        """Format the output as a GitHub PR review."""
        if self.review_output and hasattr(self.review_output, 'to_github_review'):
            return self.review_output.to_github_review()
        return {"summary": "No review output available", "comments": []}
    
    def get_all_errors(self) -> List[str]:
        """Get all errors from the supervisor and sub-agents."""
        all_errors = list(self.errors)
        if self.error:
            all_errors.append(self.error)
        
        for result in [self.parser_result, self.review_result, self.test_result]:
            if result and result.error:
                all_errors.append(f"{result.agent_name}: {result.error}")
        
        return all_errors


@dataclass
class CheckpointData:
    """
    Checkpoint data for persistence and restart capability.
    
    Allows the workflow to resume from where it failed.
    """
    checkpoint_id: str
    session_id: str
    created_at: str
    
    # Current state
    current_step: str  # "intent_parsing", "kb_fetch", "parsing", "review", "tests", "aggregation"
    completed_steps: List[str] = field(default_factory=list)
    
    # Preserved data
    request: Optional[Dict[str, Any]] = None
    intent: Optional[Dict[str, Any]] = None
    kb_context: Optional[Dict[str, Any]] = None
    parser_output: Optional[Dict[str, Any]] = None
    review_output: Optional[Dict[str, Any]] = None
    test_output: Optional[Dict[str, Any]] = None
    
    # Error state
    last_error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "request": self.request,
            "intent": self.intent,
            "kb_context": self.kb_context,
            "parser_output": self.parser_output,
            "review_output": self.review_output,
            "test_output": self.test_output,
            "last_error": self.last_error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            session_id=data["session_id"],
            created_at=data["created_at"],
            current_step=data["current_step"],
            completed_steps=data.get("completed_steps", []),
            request=data.get("request"),
            intent=data.get("intent"),
            kb_context=data.get("kb_context"),
            parser_output=data.get("parser_output"),
            review_output=data.get("review_output"),
            test_output=data.get("test_output"),
            last_error=data.get("last_error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )
    
    def can_retry(self) -> bool:
        """Check if we can retry from this checkpoint."""
        return self.retry_count < self.max_retries
    
    def mark_step_complete(self, step: str):
        """Mark a step as completed."""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
    
    def is_step_complete(self, step: str) -> bool:
        """Check if a step has been completed."""
        return step in self.completed_steps
    
    @staticmethod
    def create_new(session_id: str) -> "CheckpointData":
        """Create a new checkpoint."""
        import uuid
        return CheckpointData(
            checkpoint_id=str(uuid.uuid4()),
            session_id=session_id,
            created_at=datetime.utcnow().isoformat(),
            current_step="intent_parsing",
        )
