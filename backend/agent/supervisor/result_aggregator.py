"""
Result Aggregator

Merges outputs from sub-agents into a unified SupervisorOutput.
Handles:
- Normalization of formats
- Deduplication of issues
- Summary generation
"""

import logging
from typing import Optional, List, Dict, Any

from ..schemas.common import (
    SupervisorOutput,
    AgentResult,
    AgentStatus,
    UserIntent,
    KBContext,
)
from ..schemas.parser_output import ParserOutput
from ..schemas.review_output import ReviewOutput, ReviewIssue, Severity
from ..schemas.test_output import TestOutput

logger = logging.getLogger(__name__)


class ResultAggregator:
    """
    Aggregates results from sub-agents into a unified output.
    
    Responsibilities:
    - Merge parser, review, and test outputs
    - Normalize formats
    - Remove duplicate issues
    - Generate final summary
    """
    
    def merge(
        self,
        parser_result: Optional[AgentResult] = None,
        review_result: Optional[AgentResult] = None,
        test_result: Optional[AgentResult] = None,
        kb_context: Optional[KBContext] = None,
        intent: Optional[UserIntent] = None,
    ) -> SupervisorOutput:
        """
        Merge results from all sub-agents.
        
        Args:
            parser_result: Result from Parser Agent
            review_result: Result from Code Review Agent
            test_result: Result from Unit Test Agent
            kb_context: Knowledge Base context used
            intent: Parsed user intent
            
        Returns:
            SupervisorOutput with aggregated results
        """
        output = SupervisorOutput()
        output.kb_context = kb_context
        output.intent = intent
        
        # Store individual results
        output.parser_result = parser_result
        output.review_result = review_result
        output.test_result = test_result
        
        # Extract outputs
        if parser_result and parser_result.status == AgentStatus.COMPLETED:
            output.parser_output = parser_result.output
        
        if review_result and review_result.status == AgentStatus.COMPLETED:
            output.review_output = review_result.output
        
        if test_result and test_result.status == AgentStatus.COMPLETED:
            output.test_output = test_result.output
        
        # Collect errors
        output.errors = self._collect_errors(parser_result, review_result, test_result)
        
        # Determine overall status
        output.status = self._determine_status(parser_result, review_result, test_result)
        
        # Post-process: deduplicate and enhance
        if output.review_output:
            output.review_output = self._deduplicate_issues(output.review_output)
            output.review_output = self._enrich_with_parser_data(
                output.review_output,
                output.parser_output
            )
        
        return output
    
    def _collect_errors(
        self,
        parser_result: Optional[AgentResult],
        review_result: Optional[AgentResult],
        test_result: Optional[AgentResult],
    ) -> List[str]:
        """Collect all errors from sub-agents."""
        errors = []
        
        for result in [parser_result, review_result, test_result]:
            if result and result.error:
                errors.append(f"{result.agent_name}: {result.error}")
        
        return errors
    
    def _determine_status(
        self,
        parser_result: Optional[AgentResult],
        review_result: Optional[AgentResult],
        test_result: Optional[AgentResult],
    ) -> AgentStatus:
        """Determine overall status based on sub-agent results."""
        results = [r for r in [parser_result, review_result, test_result] if r is not None]
        
        if not results:
            return AgentStatus.PENDING
        
        # If any critical agent failed, overall is failed
        # Parser is always critical
        if parser_result and parser_result.status == AgentStatus.FAILED:
            return AgentStatus.FAILED
        
        # If all completed, overall is completed
        if all(r.status == AgentStatus.COMPLETED for r in results):
            return AgentStatus.COMPLETED
        
        # If any running, overall is running
        if any(r.status == AgentStatus.RUNNING for r in results):
            return AgentStatus.RUNNING
        
        # Mixed results - partial completion
        if any(r.status == AgentStatus.COMPLETED for r in results):
            return AgentStatus.COMPLETED  # Partial success
        
        return AgentStatus.FAILED
    
    def _deduplicate_issues(self, review_output: ReviewOutput) -> ReviewOutput:
        """Remove duplicate issues from review output."""
        if not review_output or not review_output.issues:
            return review_output
        
        seen = set()
        unique_issues = []
        
        for issue in review_output.issues:
            # Create a key based on file, line, and message
            key = (issue.file, issue.line, issue.message[:100])
            
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
            else:
                logger.debug(f"Removed duplicate issue: {issue.file}:{issue.line}")
        
        # Update review output
        review_output.issues = unique_issues
        review_output._recalculate_stats()
        
        return review_output
    
    def _enrich_with_parser_data(
        self,
        review_output: ReviewOutput,
        parser_output: Optional[ParserOutput]
    ) -> ReviewOutput:
        """Enrich review issues with parser metadata."""
        if not review_output or not parser_output:
            return review_output
        
        # Add hotspot issues that weren't caught by review
        existing_locations = {(i.file, i.line) for i in review_output.issues}
        
        for hotspot in parser_output.hotspots:
            if (hotspot.file_path, hotspot.start_line) not in existing_locations:
                # Add hotspot as a review issue
                issue = ReviewIssue(
                    file=hotspot.file_path,
                    line=hotspot.start_line,
                    severity=Severity.MEDIUM if hotspot.severity == "warning" else Severity.HIGH,
                    message=hotspot.message,
                    suggestion="Consider refactoring to improve maintainability.",
                    rule_id=f"HOTSPOT_{hotspot.hotspot_type.upper()}",
                )
                review_output.issues.append(issue)
        
        review_output._recalculate_stats()
        return review_output
    
    def merge_incremental(
        self,
        existing_output: SupervisorOutput,
        new_result: AgentResult,
        agent_type: str,  # "parser", "review", "test"
    ) -> SupervisorOutput:
        """
        Incrementally merge a new result into existing output.
        
        Useful for streaming updates or checkpoint restoration.
        """
        if agent_type == "parser":
            existing_output.parser_result = new_result
            if new_result.status == AgentStatus.COMPLETED:
                existing_output.parser_output = new_result.output
        
        elif agent_type == "review":
            existing_output.review_result = new_result
            if new_result.status == AgentStatus.COMPLETED:
                existing_output.review_output = new_result.output
                if existing_output.parser_output:
                    existing_output.review_output = self._enrich_with_parser_data(
                        existing_output.review_output,
                        existing_output.parser_output
                    )
        
        elif agent_type == "test":
            existing_output.test_result = new_result
            if new_result.status == AgentStatus.COMPLETED:
                existing_output.test_output = new_result.output
        
        # Recalculate errors and status
        existing_output.errors = self._collect_errors(
            existing_output.parser_result,
            existing_output.review_result,
            existing_output.test_result,
        )
        existing_output.status = self._determine_status(
            existing_output.parser_result,
            existing_output.review_result,
            existing_output.test_result,
        )
        
        return existing_output
