"""
Reducer Module

Merges and deduplicates review issues from multiple sources (Parser, Review agents).
Handles:
- Deduplication of similar issues
- Priority-based merging
- Consolidation of overlapping line ranges
"""

from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
import logging

from agent.schemas.common import ReviewIssue, Severity, IssueCategory


logger = logging.getLogger(__name__)


@dataclass
class IssueKey:
    """Key for identifying similar issues."""
    file_path: str
    line_start: int
    category: IssueCategory
    
    def __hash__(self):
        return hash((self.file_path, self.line_start, self.category))
    
    def __eq__(self, other):
        if not isinstance(other, IssueKey):
            return False
        return (
            self.file_path == other.file_path and
            self.line_start == other.line_start and
            self.category == other.category
        )


class Reducer:
    """
    Reduces and merges review issues from multiple agents.
    
    Strategies:
    1. Exact deduplication: Remove identical issues
    2. Similar deduplication: Merge issues on same line with same category
    3. Priority merging: Keep highest severity when merging
    4. Confidence boosting: Increase confidence when multiple agents agree
    """
    
    # Severity ranking (higher = more severe)
    SEVERITY_RANK = {
        Severity.CRITICAL: 5,
        Severity.HIGH: 4,
        Severity.MEDIUM: 3,
        Severity.LOW: 2,
        Severity.INFO: 1,
    }
    
    def __init__(
        self,
        line_proximity_threshold: int = 3,
        confidence_boost: float = 0.1,
        max_issues_per_file: int = 20,
        max_total_issues: int = 50,
    ):
        """
        Initialize reducer.
        
        Args:
            line_proximity_threshold: Lines within this range are considered "same location"
            confidence_boost: Boost applied when multiple agents find same issue
            max_issues_per_file: Maximum issues to keep per file
            max_total_issues: Maximum total issues to return
        """
        self.line_proximity_threshold = line_proximity_threshold
        self.confidence_boost = confidence_boost
        self.max_issues_per_file = max_issues_per_file
        self.max_total_issues = max_total_issues
    
    def reduce(
        self,
        parser_issues: List[ReviewIssue],
        review_issues: List[ReviewIssue],
    ) -> List[ReviewIssue]:
        """
        Reduce issues from parser and review agents.
        
        Args:
            parser_issues: Issues from Parser Agent (static analysis)
            review_issues: Issues from Review Agent (LLM review)
            
        Returns:
            Deduplicated and merged list of issues
        """
        all_issues = parser_issues + review_issues
        
        if not all_issues:
            return []
        
        logger.info(f"Reducing {len(all_issues)} issues ({len(parser_issues)} parser, {len(review_issues)} review)")
        
        # Step 1: Group by file
        by_file: Dict[str, List[ReviewIssue]] = {}
        for issue in all_issues:
            if issue.file_path not in by_file:
                by_file[issue.file_path] = []
            by_file[issue.file_path].append(issue)
        
        # Step 2: Deduplicate within each file
        reduced_issues = []
        for file_path, file_issues in by_file.items():
            file_reduced = self._deduplicate_file_issues(file_issues)
            
            # Limit per file
            if len(file_reduced) > self.max_issues_per_file:
                file_reduced = self._prioritize_issues(file_reduced, self.max_issues_per_file)
            
            reduced_issues.extend(file_reduced)
        
        # Step 3: Global limit
        if len(reduced_issues) > self.max_total_issues:
            reduced_issues = self._prioritize_issues(reduced_issues, self.max_total_issues)
        
        # Step 4: Sort by file and line
        reduced_issues.sort(key=lambda i: (i.file_path, i.line_start))
        
        logger.info(f"Reduced to {len(reduced_issues)} issues")
        return reduced_issues
    
    def _deduplicate_file_issues(self, issues: List[ReviewIssue]) -> List[ReviewIssue]:
        """Deduplicate issues within a single file."""
        if not issues:
            return []
        
        # Group by approximate key (line range + category)
        groups: Dict[IssueKey, List[ReviewIssue]] = {}
        
        for issue in issues:
            key = IssueKey(
                file_path=issue.file_path,
                line_start=self._normalize_line(issue.line_start),
                category=issue.category,
            )
            
            if key not in groups:
                groups[key] = []
            groups[key].append(issue)
        
        # Merge each group
        merged = []
        for key, group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged.append(self._merge_issues(group))
        
        return merged
    
    def _normalize_line(self, line: int) -> int:
        """Normalize line number to bucket for grouping."""
        # Round to nearest threshold
        return (line // self.line_proximity_threshold) * self.line_proximity_threshold
    
    def _merge_issues(self, issues: List[ReviewIssue]) -> ReviewIssue:
        """Merge multiple similar issues into one."""
        if len(issues) == 1:
            return issues[0]
        
        # Sort by severity (highest first) then confidence
        sorted_issues = sorted(
            issues,
            key=lambda i: (self.SEVERITY_RANK.get(i.severity, 0), i.confidence),
            reverse=True
        )
        
        # Take the most severe issue as base
        base = sorted_issues[0]
        
        # Boost confidence if multiple agents found it
        sources = set(i.source for i in issues)
        if len(sources) > 1:
            boosted_confidence = min(1.0, base.confidence + self.confidence_boost)
        else:
            boosted_confidence = base.confidence
        
        # Combine messages if they're different
        messages = list(set(i.message for i in issues))
        if len(messages) > 1:
            combined_message = base.message
            other_messages = [m for m in messages if m != base.message]
            if other_messages:
                combined_message += f"\n\nAdditional context: {other_messages[0][:200]}"
        else:
            combined_message = base.message
        
        # Combine suggestions
        suggestions = [i.suggestion for i in issues if i.suggestion]
        combined_suggestion = suggestions[0] if suggestions else None
        
        # Create merged issue
        return ReviewIssue(
            file_path=base.file_path,
            line_start=base.line_start,
            line_end=base.line_end,
            severity=base.severity,
            category=base.category,
            title=base.title,
            message=combined_message,
            suggestion=combined_suggestion,
            code_snippet=base.code_snippet,
            confidence=boosted_confidence,
            source=f"merged({','.join(sources)})"
        )
    
    def _prioritize_issues(self, issues: List[ReviewIssue], limit: int) -> List[ReviewIssue]:
        """Select top issues by priority."""
        # Sort by severity (desc), confidence (desc), line (asc)
        sorted_issues = sorted(
            issues,
            key=lambda i: (
                -self.SEVERITY_RANK.get(i.severity, 0),
                -i.confidence,
                i.line_start
            )
        )
        return sorted_issues[:limit]


def reduce_issues(
    parser_issues: List[ReviewIssue],
    review_issues: List[ReviewIssue],
    **kwargs
) -> List[ReviewIssue]:
    """
    Convenience function to reduce issues.
    
    Args:
        parser_issues: Issues from Parser Agent
        review_issues: Issues from Review Agent
        **kwargs: Additional arguments for Reducer
        
    Returns:
        Reduced list of issues
    """
    reducer = Reducer(**kwargs)
    return reducer.reduce(parser_issues, review_issues)
