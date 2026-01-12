"""
Code Review Agent Output Schemas

Defines structured output types for the Code Review Agent which handles:
- Code smell detection
- Anti-pattern identification
- Logical issue analysis
- Style violation checking
- Actionable review comments
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class Severity(str, Enum):
    """Severity levels for review issues."""
    CRITICAL = "critical"  # Security vulnerabilities, data loss risks
    HIGH = "high"          # Bugs, logic errors
    MEDIUM = "medium"      # Code smells, maintainability issues
    LOW = "low"            # Style issues, minor improvements
    INFO = "info"          # Suggestions, best practices


class IssueCategory(str, Enum):
    """Categories of code review issues."""
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    BEST_PRACTICE = "best_practice"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    COMPLEXITY = "complexity"


@dataclass
class ReviewIssue:
    """
    A single review issue/comment.
    
    Represents actionable feedback on a specific code location.
    """
    file: str
    line: int
    severity: Severity
    message: str
    suggestion: Optional[str] = None
    category: Optional[IssueCategory] = None
    end_line: Optional[int] = None  # For multi-line issues
    code_snippet: Optional[str] = None  # The problematic code
    suggested_code: Optional[str] = None  # The suggested fix
    rule_id: Optional[str] = None  # e.g., "COMPLEXITY_001", "SEC_SQL_INJECTION"
    confidence: float = 1.0  # 0.0 to 1.0, how confident the agent is
    
    # KB-related fields
    kb_reference: Optional[str] = None  # Reference to KB learning that informed this issue
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "category": self.category.value if self.category else None,
            "end_line": self.end_line,
            "code_snippet": self.code_snippet,
            "suggested_code": self.suggested_code,
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "kb_reference": self.kb_reference,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewIssue":
        """Reconstruct ReviewIssue from dictionary."""
        return cls(
            file=data["file"],
            line=data["line"],
            severity=Severity(data["severity"]),
            message=data["message"],
            suggestion=data.get("suggestion"),
            category=IssueCategory(data["category"]) if data.get("category") else None,
            end_line=data.get("end_line"),
            code_snippet=data.get("code_snippet"),
            suggested_code=data.get("suggested_code"),
            rule_id=data.get("rule_id"),
            confidence=data.get("confidence", 1.0),
            kb_reference=data.get("kb_reference"),
        )
    
    def to_github_comment(self) -> Dict[str, Any]:
        """
        Format as GitHub PR review comment with rich formatting.
        
        Uses:
        - Collapsible sections for detailed content
        - GitHub suggestion blocks for one-click apply
        - Diff blocks for showing changes
        - Category-specific emojis
        """
        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
            Severity.INFO: "💡",
        }.get(self.severity, "⚪")
        
        category_emoji = {
            IssueCategory.SECURITY: "🔒",
            IssueCategory.BUG: "🐛",
            IssueCategory.PERFORMANCE: "⚡",
            IssueCategory.MAINTAINABILITY: "🛠️",
            IssueCategory.STYLE: "🎨",
            IssueCategory.BEST_PRACTICE: "✨",
            IssueCategory.DOCUMENTATION: "📝",
            IssueCategory.ERROR_HANDLING: "🚨",
            IssueCategory.TESTING: "🧪",
            IssueCategory.COMPLEXITY: "🔄",
        }.get(self.category, "💬") if self.category else "💬"
        
        # Build the header with severity and category
        category_name = self.category.value.replace("_", " ").title() if self.category else "Issue"
        header = f"{severity_emoji} **{self.severity.value.upper()}** | {category_emoji} {category_name}"
        
        body_parts = [header, ""]
        
        # Main message
        body_parts.append(self.message)
        body_parts.append("")
        
        # If we have suggested_code, use GitHub's suggestion block (allows one-click apply)
        if self.suggested_code:
            body_parts.extend([
                "<details>",
                "<summary>💡 Suggested Fix (click to expand)</summary>",
                "",
                "```suggestion",
                self.suggested_code,
                "```",
                "</details>",
                ""
            ])
        # If we have both code_snippet and suggestion text, show as diff
        elif self.code_snippet and self.suggestion:
            body_parts.extend([
                "<details>",
                "<summary>💡 Suggestion (click to expand)</summary>",
                "",
                f"**Issue:** {self.suggestion}",
                "",
                "**Current code:**",
                "```",
                self.code_snippet,
                "```",
                "</details>",
                ""
            ])
        # Just a text suggestion
        elif self.suggestion:
            body_parts.extend([
                "<details>",
                "<summary>💡 Suggestion</summary>",
                "",
                self.suggestion,
                "</details>",
                ""
            ])
        
        # Add confidence indicator for lower confidence findings
        if self.confidence < 0.8:
            confidence_pct = int(self.confidence * 100)
            body_parts.append(f"_Confidence: {confidence_pct}%_")
        
        comment_data = {
            "path": self.file,
            "line": self.line,
            "body": "\n".join(body_parts).strip(),
            "side": "RIGHT",  # Comment on the new code side (added/modified lines)
        }
        
        # Add multi-line support if end_line is specified
        if self.end_line and self.end_line > self.line:
            comment_data["start_line"] = self.line
            comment_data["start_side"] = "RIGHT"
            comment_data["line"] = self.end_line
        
        return comment_data


@dataclass
class FileSummary:
    """Summary of issues for a single file."""
    file_path: str
    issue_count: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "issue_count": self.issue_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
        }


@dataclass
class ReviewOutput:
    """
    Complete output from the Code Review Agent.
    
    Contains all issues found during review, plus summary statistics.
    
    Example:
    {
        "issues": [
            {
                "file": "src/utils.py",
                "line": 42,
                "severity": "medium",
                "message": "Function has high cyclomatic complexity (15)",
                "suggestion": "Consider breaking this into smaller functions"
            }
        ]
    }
    """
    issues: List[ReviewIssue] = field(default_factory=list)
    
    # Summary statistics
    total_issues: int = 0
    files_reviewed: int = 0
    file_summaries: List[FileSummary] = field(default_factory=list)
    
    # Overall summary for PR comment
    summary_text: Optional[str] = None
    
    # Review metadata
    review_scope: Optional[str] = None  # "diff", "full_file", "directory"
    kb_learnings_applied: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate summary statistics."""
        self._recalculate_stats()
    
    def _recalculate_stats(self):
        """Recalculate summary statistics based on issues."""
        self.total_issues = len(self.issues)
        
        # Group by file
        file_issues: Dict[str, List[ReviewIssue]] = {}
        for issue in self.issues:
            if issue.file not in file_issues:
                file_issues[issue.file] = []
            file_issues[issue.file].append(issue)
        
        self.files_reviewed = len(file_issues)
        
        # Calculate file summaries
        self.file_summaries = []
        for file_path, issues in file_issues.items():
            summary = FileSummary(
                file_path=file_path,
                issue_count=len(issues),
                critical_count=sum(1 for i in issues if i.severity == Severity.CRITICAL),
                high_count=sum(1 for i in issues if i.severity == Severity.HIGH),
                medium_count=sum(1 for i in issues if i.severity == Severity.MEDIUM),
                low_count=sum(1 for i in issues if i.severity == Severity.LOW),
                info_count=sum(1 for i in issues if i.severity == Severity.INFO),
            )
            self.file_summaries.append(summary)
    
    def add_issue(self, issue: ReviewIssue):
        """Add an issue and recalculate stats."""
        self.issues.append(issue)
        self._recalculate_stats()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "total_issues": self.total_issues,
            "files_reviewed": self.files_reviewed,
            "file_summaries": [s.to_dict() for s in self.file_summaries],
            "summary_text": self.summary_text,
            "review_scope": self.review_scope,
            "kb_learnings_applied": self.kb_learnings_applied,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewOutput":
        """Reconstruct ReviewOutput from dictionary (for checkpointing)."""
        output = cls(
            issues=[ReviewIssue.from_dict(i) for i in data.get("issues", [])],
            summary_text=data.get("summary_text"),
            review_scope=data.get("review_scope"),
            kb_learnings_applied=data.get("kb_learnings_applied", []),
        )
        return output
    
    def get_issues_by_severity(self, severity: Severity) -> List[ReviewIssue]:
        """Get all issues with a specific severity."""
        return [i for i in self.issues if i.severity == severity]
    
    def get_issues_by_file(self, file_path: str) -> List[ReviewIssue]:
        """Get all issues for a specific file."""
        return [i for i in self.issues if i.file == file_path]
    
    def get_critical_issues(self) -> List[ReviewIssue]:
        """Get all critical and high severity issues."""
        return [
            i for i in self.issues
            if i.severity in (Severity.CRITICAL, Severity.HIGH)
        ]
    
    def to_github_review(self) -> Dict[str, Any]:
        """Format as GitHub PR review."""
        # Build summary
        if self.summary_text:
            summary = self.summary_text
        else:
            summary = self._build_summary()
        
        # Build comments
        comments = [issue.to_github_comment() for issue in self.issues]
        
        return {
            "summary": summary,
            "comments": comments,
        }
    
    def _build_summary(self) -> str:
        """
        Build a summary text for the review grouped by file.
        
        Format matches the bot's expected style with collapsible sections.
        """
        parts = [
            "## 🤖 Open Rabbit Code Review",
            "",
        ]
        
        if self.total_issues == 0:
            parts.append("✅ **No issues found!** Your code looks good.")
            return "\n".join(parts)
        
        # Overall stats
        parts.append(f"Found **{self.total_issues}** issue(s) across **{self.files_reviewed}** file(s).")
        parts.append("")
        
        # Severity breakdown
        severity_counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.MEDIUM: 0,
            Severity.LOW: 0,
            Severity.INFO: 0,
        }
        for issue in self.issues:
            severity_counts[issue.severity] += 1
        
        severity_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🟢",
            Severity.INFO: "💡",
        }
        
        severity_line = " | ".join([
            f"{severity_emoji[sev]} {count} {sev.value}"
            for sev, count in severity_counts.items()
            if count > 0
        ])
        parts.append(f"**Severity:** {severity_line}")
        parts.append("")
        
        # Issues grouped by file (collapsible)
        parts.append("<details>")
        parts.append("<summary>📁 Issues by File (click to expand)</summary>")
        parts.append("")
        
        # Group issues by file
        issues_by_file: Dict[str, List[ReviewIssue]] = {}
        for issue in self.issues:
            if issue.file not in issues_by_file:
                issues_by_file[issue.file] = []
            issues_by_file[issue.file].append(issue)
        
        for file_path, file_issues in issues_by_file.items():
            parts.append(f"### `{file_path}` ({len(file_issues)} issues)")
            parts.append("")
            
            # Sort by line number
            file_issues.sort(key=lambda x: x.line)
            
            for issue in file_issues:
                sev_emoji = severity_emoji.get(issue.severity, "⚪")
                category_str = f" [{issue.category.value}]" if issue.category else ""
                parts.append(f"- {sev_emoji} **Line {issue.line}**{category_str}: {issue.message[:100]}{'...' if len(issue.message) > 100 else ''}")
            
            parts.append("")
        
        parts.append("</details>")
        parts.append("")
        
        # Footer
        parts.append("---")
        parts.append("_See inline comments below for detailed suggestions._")
        
        return "\n".join(parts)
