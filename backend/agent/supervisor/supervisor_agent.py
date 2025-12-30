"""
Supervisor Agent

The main orchestration agent that coordinates the multi-agent code review pipeline:
1. Parser Agent - Static analysis (AST, security, complexity)
2. Review Agent - LLM-powered code review
3. Reducer - Merge and deduplicate issues
4. KB Filter - Filter based on past learnings

This agent manages the full lifecycle of a PR review.
"""

import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.subagents.base_agent import BaseAgent
from agent.subagents.parser_agent import ParserAgent
from agent.subagents.review_agent import ReviewAgent
from agent.supervisor.reducer import Reducer
from agent.supervisor.kb_filter import KBFilter
from agent.services.kb_client import KnowledgeBaseClient, get_kb_client

from agent.schemas.common import (
    AgentStatus,
    AgentCheckpoint,
    ReviewRequest,
    ReviewIssue,
    SupervisorConfig,
    SupervisorOutput,
    FilterResult,
    KBContext,
    Severity,
    IssueCategory,
)
from agent.schemas.parser_output import ParserInput, ParserOutput, FileAnalysis
from agent.schemas.review_output import ReviewInput, ReviewOutput


logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent[ReviewRequest, SupervisorOutput]):
    """
    Supervisor Agent orchestrates the multi-agent code review pipeline.
    
    Pipeline:
    1. Parser Agent: Analyze changed files for structure, security issues, complexity
    2. Review Agent: LLM-powered code review with KB context enrichment
    3. Reducer: Merge and deduplicate issues from both agents
    4. KB Filter: Filter suggestions based on past learnings (false positives, etc.)
    5. Generate summary and format output
    
    Features:
    - Checkpointing for resumability
    - Parallel file parsing
    - KB integration for context and filtering
    - Configurable via SupervisorConfig
    """
    
    def __init__(
        self,
        config: Optional[SupervisorConfig] = None,
        kb_client: Optional[KnowledgeBaseClient] = None,
    ):
        """
        Initialize supervisor agent.
        
        Args:
            config: Supervisor configuration (uses defaults if None)
            kb_client: Knowledge Base client (uses global if None)
        """
        self.config = config or SupervisorConfig()
        super().__init__(enable_checkpointing=self.config.enable_checkpointing)
        
        self.kb_client = kb_client
        self._parser_agent: Optional[ParserAgent] = None
        self._review_agent: Optional[ReviewAgent] = None
        self._reducer: Optional[Reducer] = None
        self._kb_filter: Optional[KBFilter] = None
        
        self._logger = logging.getLogger("agent.supervisor")
    
    @property
    def name(self) -> str:
        return "supervisor"
    
    def _get_parser_agent(self) -> ParserAgent:
        """Get or create Parser Agent."""
        if self._parser_agent is None:
            self._parser_agent = ParserAgent(
                enable_checkpointing=self.config.enable_checkpointing,
                max_workers=4 if self.config.parallel_parsing else 1,
            )
        return self._parser_agent
    
    def _get_review_agent(self) -> ReviewAgent:
        """Get or create Review Agent."""
        if self._review_agent is None:
            self._review_agent = ReviewAgent(
                enable_checkpointing=self.config.enable_checkpointing,
                llm_provider=self.config.llm_provider,
                llm_model=self.config.llm_model,
                use_mock=self.config.use_mock,
                kb_client=self.kb_client,
            )
        return self._review_agent
    
    def _get_reducer(self) -> Reducer:
        """Get or create Reducer."""
        if self._reducer is None:
            self._reducer = Reducer()
        return self._reducer
    
    def _get_kb_filter(self) -> KBFilter:
        """Get or create KB Filter."""
        if self._kb_filter is None:
            self._kb_filter = KBFilter(
                kb_client=self.kb_client,
                confidence_threshold=self.config.kb_confidence_threshold,
            )
        return self._kb_filter
    
    def _get_kb_client(self) -> Optional[KnowledgeBaseClient]:
        """Get KB client if enabled."""
        if not self.config.kb_enabled:
            return None
        
        if self.kb_client:
            return self.kb_client
        
        try:
            return get_kb_client()
        except Exception as e:
            self._logger.warning(f"Failed to get KB client: {e}")
            return None
    
    def _validate_input(self, input_data: ReviewRequest) -> None:
        """Validate review request."""
        if not input_data.owner:
            raise ValueError("Repository owner is required")
        
        if not input_data.repo:
            raise ValueError("Repository name is required")
        
        if not input_data.changed_files:
            raise ValueError("No changed files provided")
        
        if not input_data.repo_path:
            raise ValueError("Repository path is required")
        
        if not os.path.isdir(input_data.repo_path):
            raise ValueError(f"Repository path does not exist: {input_data.repo_path}")
    
    def _execute(self, input_data: ReviewRequest) -> SupervisorOutput:
        """Execute the full code review pipeline."""
        start_time = time.time()
        checkpoints: List[AgentCheckpoint] = []
        errors: List[str] = []
        
        self._logger.info(
            f"Starting review for {input_data.owner}/{input_data.repo} "
            f"PR #{input_data.pr_number} ({len(input_data.changed_files)} files)"
        )
        
        # Filter files by size and count limits
        files_to_analyze = self._filter_files(input_data)
        
        if not files_to_analyze:
            return SupervisorOutput(
                status=AgentStatus.SUCCESS,
                summary="No files to analyze after filtering.",
                files_analyzed=0,
                duration_seconds=time.time() - start_time,
            )
        
        # ========== PHASE 1: Parser Agent ==========
        parser_output, parser_checkpoint, parser_error = self._run_parser(
            input_data, files_to_analyze
        )
        
        if parser_checkpoint:
            checkpoints.append(parser_checkpoint)
        
        if parser_error:
            errors.append(f"Parser: {parser_error}")
        
        # Convert parser issues to ReviewIssues
        parser_issues = self._convert_parser_to_review_issues(parser_output)
        
        # ========== PHASE 2: Review Agent ==========
        review_output, review_checkpoint, review_error = self._run_review(
            input_data, files_to_analyze, parser_output
        )
        
        if review_checkpoint:
            checkpoints.append(review_checkpoint)
        
        if review_error:
            errors.append(f"Review: {review_error}")
        
        review_issues = review_output.issues if review_output else []
        
        # ========== PHASE 3: Reducer ==========
        reduced_issues = self._run_reducer(parser_issues, review_issues)
        
        # ========== PHASE 4: KB Filter ==========
        filter_result, kb_learnings_applied = self._run_kb_filter(
            reduced_issues, input_data.owner, input_data.repo
        )
        
        final_issues = filter_result.kept
        suggestions_filtered = len(filter_result.removed)
        
        # ========== PHASE 5: Generate Summary ==========
        summary = self._generate_summary(
            final_issues,
            len(files_to_analyze),
            parser_output,
            review_output,
            suggestions_filtered,
        )
        
        # Build output
        duration = time.time() - start_time
        
        output = SupervisorOutput(
            status=AgentStatus.SUCCESS if not errors else AgentStatus.SUCCESS,  # Partial success is still success
            issues=final_issues,
            summary=summary,
            files_analyzed=len(files_to_analyze),
            kb_learnings_applied=kb_learnings_applied,
            suggestions_filtered=suggestions_filtered,
            duration_seconds=duration,
            parser_summary=self._build_parser_summary(parser_output),
            review_summary=self._build_review_summary(review_output),
            checkpoints=checkpoints,
            errors=errors,
        )
        
        self._logger.info(
            f"Review completed in {duration:.2f}s: "
            f"{len(final_issues)} issues, {suggestions_filtered} filtered"
        )
        
        return output
    
    def _filter_files(self, input_data: ReviewRequest) -> List[Any]:
        """Filter files by size and count limits."""
        filtered = []
        
        for fc in input_data.changed_files:
            # Skip deleted files
            if fc.is_deleted:
                continue
            
            # Check file exists and size
            full_path = os.path.join(input_data.repo_path, fc.path)
            if not os.path.exists(full_path):
                continue
            
            try:
                size = os.path.getsize(full_path)
                if size > self.config.max_file_size:
                    self._logger.debug(f"Skipping large file: {fc.path} ({size} bytes)")
                    continue
            except OSError:
                continue
            
            filtered.append(fc)
            
            # Check count limit
            if len(filtered) >= self.config.max_files:
                self._logger.warning(
                    f"File limit reached ({self.config.max_files}), "
                    f"skipping remaining files"
                )
                break
        
        return filtered
    
    def _run_parser(
        self,
        input_data: ReviewRequest,
        files_to_analyze: List[Any],
    ) -> Tuple[Optional[ParserOutput], Optional[AgentCheckpoint], Optional[str]]:
        """Run the Parser Agent."""
        self._logger.info("Running Parser Agent...")
        
        try:
            parser = self._get_parser_agent()
            
            parser_input = ParserInput(
                changed_files=files_to_analyze,
                repo_path=input_data.repo_path,
                enable_security_scan=True,
                enable_dead_code_detection=True,
                complexity_threshold=10,
            )
            
            output, checkpoint = parser.run(parser_input)
            
            self._logger.info(
                f"Parser completed: {output.total_files} files, "
                f"{output.total_security_issues} security issues, "
                f"{output.total_complexity_issues} complexity issues"
            )
            
            return output, checkpoint, None
            
        except Exception as e:
            self._logger.error(f"Parser Agent failed: {e}")
            return None, None, str(e)
    
    def _run_review(
        self,
        input_data: ReviewRequest,
        files_to_analyze: List[Any],
        parser_output: Optional[ParserOutput],
    ) -> Tuple[Optional[ReviewOutput], Optional[AgentCheckpoint], Optional[str]]:
        """Run the Review Agent."""
        self._logger.info("Running Review Agent...")
        
        try:
            reviewer = self._get_review_agent()
            
            # Build parser outputs map for context
            parser_outputs: Dict[str, FileAnalysis] = {}
            if parser_output:
                for fa in parser_output.files:
                    parser_outputs[fa.file_path] = fa
            
            # Get KB context
            kb_context = self._get_kb_context(input_data, files_to_analyze)
            
            review_input = ReviewInput(
                owner=input_data.owner,
                repo=input_data.repo,
                changed_files=files_to_analyze,
                repo_path=input_data.repo_path,
                pr_context=input_data.pr_context,
                kb_context=kb_context,
                parser_outputs=parser_outputs,
            )
            
            output, checkpoint = reviewer.run(review_input)
            
            self._logger.info(
                f"Review completed: {len(output.issues)} issues, "
                f"KB context: {output.kb_context_used}"
            )
            
            return output, checkpoint, None
            
        except Exception as e:
            self._logger.error(f"Review Agent failed: {e}")
            return None, None, str(e)
    
    def _get_kb_context(
        self,
        input_data: ReviewRequest,
        files_to_analyze: List[Any],
    ) -> Optional[KBContext]:
        """Get KB context for review enrichment."""
        if not self.config.kb_enabled:
            return None
        
        client = self._get_kb_client()
        if not client or not client.enabled:
            return None
        
        try:
            learnings = client.get_pr_context_learnings(
                owner=input_data.owner,
                repo=input_data.repo,
                pr_description=input_data.pr_description or input_data.pr_title,
                changed_files=[f.path for f in files_to_analyze],
                k=10,
            )
            
            if not learnings:
                return KBContext(enabled=True)
            
            formatted = client.format_learnings_for_prompt(learnings)
            
            return KBContext(
                learnings=learnings,
                formatted=formatted,
                enabled=True,
            )
            
        except Exception as e:
            self._logger.warning(f"Failed to get KB context: {e}")
            return KBContext(enabled=True)
    
    def _convert_parser_to_review_issues(
        self,
        parser_output: Optional[ParserOutput],
    ) -> List[ReviewIssue]:
        """Convert parser output to ReviewIssue format."""
        if not parser_output:
            return []
        
        issues = []
        
        for fa in parser_output.files:
            # Convert security issues
            for si in fa.security_issues:
                issues.append(ReviewIssue(
                    file_path=fa.file_path,
                    line_start=si.line,
                    severity=si.severity,
                    category=IssueCategory.SECURITY,
                    title=f"Security: {si.type.value}",
                    message=si.description,
                    suggestion=si.recommendation,
                    code_snippet=si.code_snippet,
                    confidence=0.9,
                    source="parser",
                ))
            
            # Convert complexity issues
            for ci in fa.complexity_issues:
                issues.append(ReviewIssue(
                    file_path=fa.file_path,
                    line_start=ci.line,
                    severity=Severity.MEDIUM,
                    category=IssueCategory.COMPLEXITY,
                    title=f"High Complexity: {ci.function_name}",
                    message=f"Function has cyclomatic complexity of {ci.complexity} (threshold: {ci.threshold})",
                    suggestion="Consider breaking this function into smaller, more focused functions.",
                    confidence=0.95,
                    source="parser",
                ))
            
            # Convert dead code
            for dc in fa.dead_code:
                issues.append(ReviewIssue(
                    file_path=fa.file_path,
                    line_start=dc.line,
                    severity=Severity.LOW,
                    category=IssueCategory.DEAD_CODE,
                    title=f"Unused {dc.type.value}: {dc.name}",
                    message=f"The {dc.type.value} '{dc.name}' appears to be unused.",
                    suggestion="Consider removing this unused code or adding a comment explaining why it's kept.",
                    confidence=0.7,
                    source="parser",
                ))
        
        return issues
    
    def _run_reducer(
        self,
        parser_issues: List[ReviewIssue],
        review_issues: List[ReviewIssue],
    ) -> List[ReviewIssue]:
        """Run the Reducer to merge and deduplicate issues."""
        self._logger.info(
            f"Reducing issues: {len(parser_issues)} parser + {len(review_issues)} review"
        )
        
        reducer = self._get_reducer()
        reduced = reducer.reduce(parser_issues, review_issues)
        
        self._logger.info(f"Reduced to {len(reduced)} issues")
        return reduced
    
    def _run_kb_filter(
        self,
        issues: List[ReviewIssue],
        owner: str,
        repo: str,
    ) -> Tuple[FilterResult, int]:
        """Run KB filter on issues."""
        if not self.config.kb_enabled:
            return FilterResult(kept=issues, removed=[], modifications=0), 0
        
        self._logger.info(f"Filtering {len(issues)} issues with KB...")
        
        kb_filter = self._get_kb_filter()
        result = kb_filter.filter(issues, owner, repo)
        
        self._logger.info(
            f"KB filter: {len(result.kept)} kept, {len(result.removed)} removed, "
            f"{result.modifications} modified"
        )
        
        # Count learnings applied (removed + modified)
        kb_learnings_applied = len(result.removed) + result.modifications
        
        return result, kb_learnings_applied
    
    def _generate_summary(
        self,
        issues: List[ReviewIssue],
        files_analyzed: int,
        parser_output: Optional[ParserOutput],
        review_output: Optional[ReviewOutput],
        suggestions_filtered: int,
    ) -> str:
        """Generate a summary of the review."""
        if not issues:
            return f"✅ No issues found in {files_analyzed} files analyzed."
        
        # Count by severity
        severity_counts = {}
        for issue in issues:
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Count by category
        category_counts = {}
        for issue in issues:
            cat = issue.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Build summary
        lines = [f"📋 **Code Review Summary**"]
        lines.append(f"- Files analyzed: {files_analyzed}")
        lines.append(f"- Issues found: {len(issues)}")
        
        if suggestions_filtered > 0:
            lines.append(f"- Suggestions filtered (based on past learnings): {suggestions_filtered}")
        
        # Severity breakdown
        if severity_counts:
            lines.append("\n**By Severity:**")
            for sev in ["critical", "high", "medium", "low", "info"]:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(sev, "⚪")
                    lines.append(f"  {emoji} {sev.capitalize()}: {count}")
        
        # Category breakdown
        if category_counts:
            lines.append("\n**By Category:**")
            for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  - {cat}: {count}")
        
        return "\n".join(lines)
    
    def _build_parser_summary(
        self,
        parser_output: Optional[ParserOutput],
    ) -> Optional[Dict[str, Any]]:
        """Build parser summary for output."""
        if not parser_output:
            return None
        
        return {
            "total_files": parser_output.total_files,
            "failed_files": len(parser_output.failed_files),
            "total_functions": parser_output.total_functions,
            "total_classes": parser_output.total_classes,
            "security_issues": parser_output.total_security_issues,
            "dead_code": parser_output.total_dead_code,
            "complexity_issues": parser_output.total_complexity_issues,
            "avg_complexity": parser_output.avg_complexity,
        }
    
    def _build_review_summary(
        self,
        review_output: Optional[ReviewOutput],
    ) -> Optional[Dict[str, Any]]:
        """Build review summary for output."""
        if not review_output:
            return None
        
        return {
            "files_reviewed": review_output.files_reviewed,
            "issues_found": len(review_output.issues),
            "kb_context_used": review_output.kb_context_used,
            "kb_learnings_count": review_output.kb_learnings_count,
            "total_tokens_used": review_output.total_tokens_used,
        }


def run_code_review(
    request: ReviewRequest,
    config: Optional[SupervisorConfig] = None,
    kb_client: Optional[KnowledgeBaseClient] = None,
) -> SupervisorOutput:
    """
    Convenience function to run a full code review.
    
    Args:
        request: Review request with PR details and changed files
        config: Optional supervisor configuration
        kb_client: Optional KB client
        
    Returns:
        SupervisorOutput with review results
    """
    supervisor = SupervisorAgent(config=config, kb_client=kb_client)
    output, _ = supervisor.run(request)
    return output
