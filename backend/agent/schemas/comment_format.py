"""
Comment Formatter Agent Schemas

Defines input/output types for the Comment Formatter Agent which:
- Filters comments to valid diff lines only
- Merges duplicate comments on same line
- Limits to top 20 comments by severity
- Formats with rich GitHub markdown (badges, suggestions, collapsibles)
- Generates impact-focused PR summary
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class CommentPriority(int, Enum):
    """Priority ordering for comments (lower = higher priority)."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


@dataclass
class RawReviewComment:
    """
    Raw comment from Review Agent (before formatting).
    
    Input to the Comment Formatter Agent.
    """
    file: str
    line: int
    severity: str  # "critical", "high", "medium", "low", "info"
    category: Optional[str]  # "security", "bug", "performance", etc.
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    suggested_code: Optional[str] = None
    end_line: Optional[int] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
            "suggested_code": self.suggested_code,
            "end_line": self.end_line,
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawReviewComment":
        return cls(
            file=data["file"],
            line=data["line"],
            severity=data.get("severity", "medium"),
            category=data.get("category"),
            message=data.get("message", ""),
            suggestion=data.get("suggestion"),
            code_snippet=data.get("code_snippet"),
            suggested_code=data.get("suggested_code"),
            end_line=data.get("end_line"),
            confidence=data.get("confidence", 1.0),
        )
    
    @property
    def priority(self) -> int:
        """Get numeric priority for sorting (lower = higher priority)."""
        severity_map = {
            "critical": CommentPriority.CRITICAL,
            "high": CommentPriority.HIGH,
            "medium": CommentPriority.MEDIUM,
            "low": CommentPriority.LOW,
            "info": CommentPriority.INFO,
        }
        return severity_map.get(self.severity.lower(), CommentPriority.MEDIUM).value


@dataclass
class FormattedInlineComment:
    """
    Formatted inline comment ready for GitHub API.
    
    Matches GitHub's createReview API comment format.
    """
    path: str
    line: int
    body: str  # Rich markdown body with badges, suggestions, etc.
    side: str = "RIGHT"  # Comment on new code side
    start_line: Optional[int] = None  # For multi-line comments
    start_side: Optional[str] = None
    
    # Metadata for tracking
    severity: str = "medium"
    merged_count: int = 1  # How many raw comments were merged into this
    
    def to_github_comment(self) -> Dict[str, Any]:
        """Convert to GitHub API format."""
        comment = {
            "path": self.path,
            "line": self.line,
            "body": self.body,
            "side": self.side,
        }
        
        if self.start_line and self.start_line < self.line:
            comment["start_line"] = self.start_line
            comment["start_side"] = self.start_side or "RIGHT"
        
        return comment
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "body": self.body,
            "side": self.side,
            "start_line": self.start_line,
            "start_side": self.start_side,
            "severity": self.severity,
            "merged_count": self.merged_count,
        }


@dataclass
class DroppedComment:
    """
    Comment that was dropped (not on valid diff line).
    
    Included in summary for visibility.
    """
    file: str
    line: int
    severity: str
    message: str
    reason: str  # "not_in_diff", "merged", "limit_exceeded"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
            "reason": self.reason,
        }


@dataclass
class FormatterInput:
    """
    Input to the Comment Formatter Agent.
    """
    # Raw comments from Review Agent
    raw_comments: List[RawReviewComment]
    
    # Valid lines per file (from git diff)
    valid_lines: Dict[str, List[int]]
    
    # Diff text per file (for context)
    diff_text_per_file: Dict[str, str]
    
    # PR metadata for summary
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    files_changed: int = 0
    
    # Configuration
    max_comments: int = 20  # Maximum inline comments to post
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_comments": [c.to_dict() for c in self.raw_comments],
            "valid_lines": self.valid_lines,
            "diff_text_per_file": self.diff_text_per_file,
            "pr_title": self.pr_title,
            "pr_description": self.pr_description,
            "files_changed": self.files_changed,
            "max_comments": self.max_comments,
        }


@dataclass
class FormatterOutput:
    """
    Output from the Comment Formatter Agent.
    
    Ready for GitHub's createReview API.
    """
    # Summary body (impact analysis + improvement thoughts)
    summary_body: str
    
    # Formatted inline comments (max 20, sorted by severity)
    inline_comments: List[FormattedInlineComment] = field(default_factory=list)
    
    # Comments that were dropped (for logging/debugging)
    dropped_comments: List[DroppedComment] = field(default_factory=list)
    
    # Statistics
    total_raw_comments: int = 0
    comments_on_valid_lines: int = 0
    comments_merged: int = 0
    comments_limited: int = 0  # Dropped due to max limit
    
    def to_github_review(self) -> Dict[str, Any]:
        """
        Convert to GitHub createReview API payload.
        
        Returns dict with:
        - body: Summary markdown
        - comments: List of inline comment dicts
        - event: "COMMENT"
        """
        return {
            "body": self.summary_body,
            "comments": [c.to_github_comment() for c in self.inline_comments],
            "event": "COMMENT",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_body": self.summary_body,
            "inline_comments": [c.to_dict() for c in self.inline_comments],
            "dropped_comments": [c.to_dict() for c in self.dropped_comments],
            "total_raw_comments": self.total_raw_comments,
            "comments_on_valid_lines": self.comments_on_valid_lines,
            "comments_merged": self.comments_merged,
            "comments_limited": self.comments_limited,
        }


# Emoji mappings for formatting
SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠", 
    "medium": "🟡",
    "low": "🟢",
    "info": "💡",
}

CATEGORY_EMOJI = {
    "security": "🔒",
    "bug": "🐛",
    "performance": "⚡",
    "maintainability": "🛠️",
    "style": "🎨",
    "best_practice": "✨",
    "documentation": "📝",
    "error_handling": "🚨",
    "testing": "🧪",
    "complexity": "🔄",
}

SEVERITY_LABEL = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}
