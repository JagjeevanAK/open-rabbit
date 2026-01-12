"""
KB Filter Module

Filters review suggestions using Knowledge Base learnings.
Removes or modifies suggestions that conflict with past learnings
(e.g., suggestions that were previously rejected by users).
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import re

from agent.schemas.common import ReviewIssue, Severity, IssueCategory, FilterResult
from agent.services.kb_client import KnowledgeBaseClient, get_kb_client


logger = logging.getLogger(__name__)


@dataclass
class FilteredIssue:
    """An issue that was filtered out."""
    issue: ReviewIssue
    reason: str
    learning_id: Optional[str] = None
    confidence: float = 0.0


class KBFilter:
    """
    Filters review issues using Knowledge Base learnings.
    
    This helps prevent the system from repeatedly making
    suggestions that have been rejected in the past.
    
    Filtering strategies:
    1. Exact match: Same file pattern + same issue type = reject
    2. Similar match: Similar description with high confidence = downgrade or reject
    3. False positive learnings: Issues matching known false positives = reject
    """
    
    def __init__(
        self,
        kb_client: Optional[KnowledgeBaseClient] = None,
        confidence_threshold: float = 0.7,
        similarity_threshold: float = 0.8,
        enable_downgrade: bool = True,
    ):
        """
        Initialize KB filter.
        
        Args:
            kb_client: Knowledge Base client (uses global if None)
            confidence_threshold: Minimum confidence to filter
            similarity_threshold: Minimum similarity for matching
            enable_downgrade: Allow downgrading instead of removing
        """
        self.kb_client = kb_client
        self.confidence_threshold = confidence_threshold
        self.similarity_threshold = similarity_threshold
        self.enable_downgrade = enable_downgrade
        self._learnings_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def _get_client(self) -> Optional[KnowledgeBaseClient]:
        """Get KB client, creating if needed."""
        if self.kb_client:
            return self.kb_client
        try:
            return get_kb_client()
        except Exception as e:
            logger.warning(f"Could not get KB client: {e}")
            return None
    
    def filter(
        self,
        issues: List[ReviewIssue],
        owner: str,
        repo: str,
    ) -> FilterResult:
        """
        Filter issues using KB learnings.
        
        Args:
            issues: List of review issues to filter
            owner: Repository owner
            repo: Repository name
            
        Returns:
            FilterResult with kept issues, removed issues, and stats
        """
        if not issues:
            return FilterResult(kept=[], removed=[], modifications=0)
        
        client = self._get_client()
        if not client or not client.enabled:
            logger.info("KB not available, skipping filter")
            return FilterResult(kept=issues, removed=[], modifications=0)
        
        # Get relevant learnings
        learnings = self._get_learnings(client, owner, repo, issues)
        
        if not learnings:
            logger.info("No relevant learnings found, keeping all issues")
            return FilterResult(kept=issues, removed=[], modifications=0)
        
        logger.info(f"Found {len(learnings)} relevant learnings for filtering")
        
        kept = []
        removed = []
        modifications = 0
        
        for issue in issues:
            # Check if issue should be filtered
            filter_result = self._should_filter(issue, learnings)
            
            if filter_result is None:
                # Keep as-is
                kept.append(issue)
            elif filter_result.reason == "downgrade":
                # Downgrade severity
                modified_issue = self._downgrade_issue(issue)
                kept.append(modified_issue)
                modifications += 1
            else:
                # Remove
                removed.append((issue, filter_result.reason))
        
        logger.info(
            f"Filter result: {len(kept)} kept, {len(removed)} removed, {modifications} modified"
        )
        
        return FilterResult(
            kept=kept,
            removed=removed,
            modifications=modifications
        )
    
    def _get_learnings(
        self,
        client: KnowledgeBaseClient,
        owner: str,
        repo: str,
        issues: List[ReviewIssue],
    ) -> List[Dict[str, Any]]:
        """Get relevant learnings from KB."""
        cache_key = f"{owner}/{repo}"
        
        if cache_key in self._learnings_cache:
            return self._learnings_cache[cache_key]
        
        # Build query from issue types and files
        file_paths = list(set(i.file_path for i in issues))
        categories = list(set(i.category.value for i in issues))
        
        query = f"code review issues in {', '.join(categories)} for files like {', '.join(file_paths[:5])}"
        
        try:
            learnings = client.search_learnings(
                query=query,
                owner=owner,
                repo=repo,
                k=20,
                min_confidence=self.confidence_threshold
            )
            self._learnings_cache[cache_key] = learnings
            return learnings
        except Exception as e:
            logger.error(f"Failed to get learnings: {e}")
            return []
    
    def _should_filter(
        self,
        issue: ReviewIssue,
        learnings: List[Dict[str, Any]]
    ) -> Optional[FilteredIssue]:
        """
        Check if an issue should be filtered based on learnings.
        
        Returns:
            FilteredIssue if should be filtered, None to keep
        """
        for learning in learnings:
            learning_text = learning.get("learning", learning.get("learning_text", ""))
            score = learning.get("score", learning.get("confidence", 0.5))
            learning_id = learning.get("id", learning.get("learning_id"))
            
            # Check for false positive indicators
            if self._is_false_positive_learning(learning_text, issue):
                if score >= self.confidence_threshold:
                    return FilteredIssue(
                        issue=issue,
                        reason=f"Known false positive: {learning_text[:100]}",
                        learning_id=learning_id,
                        confidence=score
                    )
            
            # Check for correction/rejection indicators
            if self._is_rejected_suggestion(learning_text, issue):
                if score >= self.similarity_threshold:
                    return FilteredIssue(
                        issue=issue,
                        reason=f"Previously rejected: {learning_text[:100]}",
                        learning_id=learning_id,
                        confidence=score
                    )
                elif score >= self.confidence_threshold and self.enable_downgrade:
                    return FilteredIssue(
                        issue=issue,
                        reason="downgrade",
                        learning_id=learning_id,
                        confidence=score
                    )
        
        return None
    
    def _is_false_positive_learning(
        self,
        learning_text: str,
        issue: ReviewIssue
    ) -> bool:
        """Check if learning indicates a false positive for this issue type."""
        learning_lower = learning_text.lower()
        
        # False positive indicators
        fp_indicators = [
            "false positive",
            "not actually",
            "not a real",
            "incorrect detection",
            "wrongly flagged",
            "mistakenly identified",
            "false alarm",
        ]
        
        if not any(ind in learning_lower for ind in fp_indicators):
            return False
        
        # Check if it matches the issue category
        category_keywords = {
            IssueCategory.SECURITY: ["security", "vulnerability", "injection", "xss"],
            IssueCategory.PERFORMANCE: ["performance", "slow", "optimization"],
            IssueCategory.STYLE: ["style", "formatting", "naming"],
            IssueCategory.DEAD_CODE: ["dead code", "unused", "unreachable"],
            IssueCategory.COMPLEXITY: ["complexity", "complex", "cyclomatic"],
        }
        
        keywords = category_keywords.get(issue.category, [issue.category.value])
        return any(kw in learning_lower for kw in keywords)
    
    def _is_rejected_suggestion(
        self,
        learning_text: str,
        issue: ReviewIssue
    ) -> bool:
        """Check if learning indicates a rejected suggestion similar to this issue."""
        learning_lower = learning_text.lower()
        
        # Rejection indicators
        rejection_indicators = [
            "[correction]",
            "[false_positive]",
            "user rejected",
            "not applicable",
            "unnecessary",
            "over-engineering",
            "acceptable pattern",
            "intentional",
        ]
        
        if not any(ind in learning_lower for ind in rejection_indicators):
            return False
        
        # Check for file pattern match
        file_name = issue.file_path.split("/")[-1]
        if file_name.lower() in learning_lower:
            return True
        
        # Check for issue title/message similarity
        issue_words = set(issue.title.lower().split() + issue.message.lower().split()[:20])
        learning_words = set(learning_lower.split())
        
        # Simple word overlap check
        overlap = len(issue_words & learning_words)
        if overlap >= 3:
            return True
        
        return False
    
    def _downgrade_issue(self, issue: ReviewIssue) -> ReviewIssue:
        """Downgrade an issue's severity by one level."""
        severity_downgrade = {
            Severity.CRITICAL: Severity.HIGH,
            Severity.HIGH: Severity.MEDIUM,
            Severity.MEDIUM: Severity.LOW,
            Severity.LOW: Severity.INFO,
            Severity.INFO: Severity.INFO,
        }
        
        new_severity = severity_downgrade.get(issue.severity, issue.severity)
        
        # Add note about downgrade
        new_message = issue.message
        if new_severity != issue.severity:
            new_message += "\n\n_Note: Severity downgraded based on past learnings._"
        
        return ReviewIssue(
            file_path=issue.file_path,
            line_start=issue.line_start,
            line_end=issue.line_end,
            severity=new_severity,
            category=issue.category,
            title=issue.title,
            message=new_message,
            suggestion=issue.suggestion,
            code_snippet=issue.code_snippet,
            confidence=issue.confidence * 0.9,  # Reduce confidence slightly
            source=issue.source
        )


def filter_with_kb(
    issues: List[ReviewIssue],
    owner: str,
    repo: str,
    **kwargs
) -> FilterResult:
    """
    Convenience function to filter issues with KB.
    
    Args:
        issues: Issues to filter
        owner: Repository owner
        repo: Repository name
        **kwargs: Additional arguments for KBFilter
        
    Returns:
        FilterResult
    """
    kb_filter = KBFilter(**kwargs)
    return kb_filter.filter(issues, owner, repo)
