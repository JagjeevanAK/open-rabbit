"""
Common Schema Definitions

Shared types used across all agents.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class AgentStatus(str, Enum):
    """Status of an agent execution"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Severity(str, Enum):
    """Severity levels for issues"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    """Categories of code issues"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    BUG = "bug"
    STYLE = "style"
    DEAD_CODE = "dead_code"
    COMPLEXITY = "complexity"
    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    TYPE_SAFETY = "type_safety"
    NAMING = "naming"
    OTHER = "other"


class FileChange(BaseModel):
    """Represents a changed file in a PR"""
    path: str = Field(..., description="File path relative to repo root")
    status: str = Field(..., description="Change status: added, modified, deleted, renamed")
    additions: int = Field(default=0, description="Number of lines added")
    deletions: int = Field(default=0, description="Number of lines deleted")
    patch: Optional[str] = Field(default=None, description="Git diff patch content")
    previous_path: Optional[str] = Field(default=None, description="Previous path if renamed")
    
    @property
    def is_new(self) -> bool:
        return self.status == "added"
    
    @property
    def is_deleted(self) -> bool:
        return self.status == "deleted"
    
    @property
    def is_modified(self) -> bool:
        return self.status in ("modified", "renamed")


class PRContext(BaseModel):
    """Pull request context information"""
    title: str
    description: Optional[str] = None
    base_branch: str = "main"
    head_branch: str = ""
    author: Optional[str] = None
    labels: List[str] = Field(default_factory=list)


class KBContext(BaseModel):
    """Knowledge Base context for review enrichment"""
    learnings: List[Dict[str, Any]] = Field(default_factory=list)
    formatted: str = Field(default="", description="Formatted learnings for prompt")
    enabled: bool = Field(default=False)
    
    @property
    def has_learnings(self) -> bool:
        return len(self.learnings) > 0


class ReviewRequest(BaseModel):
    """Input to the supervisor agent for code review"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")
    branch: str = Field(..., description="Branch being reviewed")
    changed_files: List[FileChange] = Field(..., description="List of changed files")
    pr_title: str = Field(..., description="PR title")
    pr_description: Optional[str] = Field(default=None, description="PR description")
    repo_path: Optional[str] = Field(default=None, description="Local path to cloned repo")
    generate_tests: bool = Field(default=False, description="Whether to generate unit tests")
    
    @property
    def pr_context(self) -> PRContext:
        return PRContext(
            title=self.pr_title,
            description=self.pr_description,
            head_branch=self.branch
        )


class ReviewIssue(BaseModel):
    """A single review issue/suggestion"""
    file_path: str = Field(..., description="Path to the file")
    line_start: int = Field(..., description="Starting line number")
    line_end: Optional[int] = Field(default=None, description="Ending line number")
    severity: Severity = Field(..., description="Issue severity")
    category: IssueCategory = Field(..., description="Issue category")
    title: str = Field(..., description="Short issue title")
    message: str = Field(..., description="Detailed issue description")
    suggestion: Optional[str] = Field(default=None, description="Suggested fix")
    code_snippet: Optional[str] = Field(default=None, description="Relevant code snippet")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(default="review", description="Source agent: parser, review, test")
    
    def to_github_comment(self) -> Dict[str, Any]:
        """Format as GitHub PR review comment"""
        emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
            Severity.INFO: "ℹ️"
        }.get(self.severity, "⚪")
        
        body = f"{emoji} **{self.title}**\n\n{self.message}"
        if self.suggestion:
            body += f"\n\n💡 **Suggestion:** {self.suggestion}"
        
        comment = {
            "path": self.file_path,
            "line": self.line_start,
            "body": body
        }
        
        if self.line_end and self.line_end != self.line_start:
            comment["start_line"] = self.line_start
            comment["line"] = self.line_end
        
        return comment


class AgentCheckpoint(BaseModel):
    """Checkpoint state for an agent"""
    agent_name: str
    status: AgentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_hash: str = Field(default="", description="Hash of input for cache validation")
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SupervisorConfig(BaseModel):
    """Configuration for the Supervisor Agent"""
    use_mock: bool = Field(default=False, description="Use mock agents for testing")
    llm_provider: str = Field(default="openai", description="LLM provider: openai, anthropic, openrouter")
    llm_model: Optional[str] = Field(default=None, description="Model override")
    kb_enabled: bool = Field(default=True, description="Enable Knowledge Base integration")
    kb_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    enable_checkpointing: bool = Field(default=True, description="Enable agent checkpointing")
    timeout_seconds: float = Field(default=600.0, description="Overall timeout")
    max_files: int = Field(default=50, description="Maximum files to analyze")
    max_file_size: int = Field(default=100_000, description="Max file size in bytes")
    parallel_parsing: bool = Field(default=True, description="Parse files in parallel")


class FilterResult(BaseModel):
    """Result from KB filtering"""
    kept: List[ReviewIssue] = Field(default_factory=list)
    removed: List[tuple] = Field(default_factory=list, description="(issue, reason) pairs")
    modifications: int = Field(default=0, description="Number of issues modified with notes")


class SupervisorOutput(BaseModel):
    """Final output from the Supervisor Agent"""
    status: AgentStatus
    issues: List[ReviewIssue] = Field(default_factory=list)
    summary: str = Field(default="")
    files_analyzed: int = Field(default=0)
    kb_learnings_applied: int = Field(default=0)
    suggestions_filtered: int = Field(default=0)
    duration_seconds: float = Field(default=0.0)
    
    # Subagent outputs (optional, for debugging)
    parser_summary: Optional[Dict[str, Any]] = None
    review_summary: Optional[Dict[str, Any]] = None
    test_summary: Optional[Dict[str, Any]] = None
    
    # Checkpoints
    checkpoints: List[AgentCheckpoint] = Field(default_factory=list)
    
    # Errors
    errors: List[str] = Field(default_factory=list)
    
    def to_github_review(self) -> Dict[str, Any]:
        """Format as GitHub PR review"""
        comments = [issue.to_github_comment() for issue in self.issues]
        
        return {
            "summary": self.summary,
            "comments": comments,
            "files_analyzed": self.files_analyzed,
            "issues_found": len(self.issues),
            "kb_applied": self.kb_learnings_applied > 0,
            "filtered": self.suggestions_filtered
        }
