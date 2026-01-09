"""
Comment Formatter Agent

Sub-agent responsible for formatting raw review comments into GitHub-ready output.
Handles:
- Filtering to valid diff lines
- Merging duplicate comments on same line
- Limiting to top N comments by severity
- Rich markdown formatting
- Impact-focused summary generation
"""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from .base_agent import BaseAgent, AgentConfig
from ..schemas.comment_format import (
    RawReviewComment,
    FormattedInlineComment,
    DroppedComment,
    FormatterInput,
    FormatterOutput,
    SEVERITY_EMOJI,
    CATEGORY_EMOJI,
    SEVERITY_LABEL,
)
from ..schemas.review_output import ReviewIssue, ReviewOutput
from ..prompt.comment_formatter_prompt import (
    COMMENT_FORMATTER_SYSTEM_PROMPT,
    COMMENT_FORMATTER_USER_PROMPT,
)
from ..llm_factory import LLMFactory, LLMProvider
from ..logging_config import (
    get_logger,
    get_session_id,
    log_with_data,
    log_llm_call,
)

logger = get_logger(__name__)


class CommentFormatterAgent(BaseAgent[FormatterOutput]):
    """
    Comment Formatter Agent for transforming raw review comments.
    
    Takes raw comments from Review Agent and produces:
    - Impact-focused PR summary
    - Formatted inline comments (max 20)
    - List of dropped comments with reasons
    
    Uses LLM for intelligent merging and summary generation.
    """
    
    MAX_COMMENTS_DEFAULT = 20
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        provider: LLMProvider = LLMProvider.OPENAI,
        model: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        max_comments: int = MAX_COMMENTS_DEFAULT,
    ):
        """
        Initialize the Comment Formatter Agent.
        
        Args:
            llm: Pre-configured LLM instance (optional)
            provider: LLM provider if llm not provided
            model: Model name if llm not provided
            config: Agent configuration
            max_comments: Maximum inline comments to include (default 20)
        """
        if config is None:
            config = AgentConfig(
                name="comment_formatter_agent",
                timeout_seconds=60.0,  # 1 minute for formatting
                max_retries=2,
            )
        super().__init__(config)
        
        self._llm = llm
        self._provider = provider
        self._model = model
        self._max_comments = max_comments
    
    @property
    def name(self) -> str:
        return "comment_formatter_agent"
    
    @property
    def llm(self) -> BaseChatModel:
        """Lazy-load LLM instance."""
        if self._llm is None:
            self._llm = LLMFactory.create(
                provider=self._provider,
                model=self._model,
                temperature=0.3,  # Slightly creative for summaries
            )
        return self._llm
    
    async def _execute(
        self,
        formatter_input: FormatterInput,
    ) -> FormatterOutput:
        """
        Execute comment formatting.
        
        Args:
            formatter_input: Input containing raw comments, valid lines, and diff text
            
        Returns:
            FormatterOutput with summary, inline comments, and dropped comments
        """
        session_id = get_session_id() or "unknown"
        start_time = time.perf_counter()
        
        log_with_data(logger, 20, "Starting comment formatting", {
            "session_id": session_id,
            "raw_comments_count": len(formatter_input.raw_comments),
            "files_with_valid_lines": len(formatter_input.valid_lines),
            "max_comments": formatter_input.max_comments,
        })
        
        # Step 1: Pre-filter comments to valid lines only
        valid_comments, invalid_comments = self._filter_to_valid_lines(
            formatter_input.raw_comments,
            formatter_input.valid_lines,
        )
        
        log_with_data(logger, 20, "Pre-filtered comments", {
            "session_id": session_id,
            "valid_comments": len(valid_comments),
            "invalid_comments": len(invalid_comments),
        })
        
        # If no valid comments, return early with summary only
        if not valid_comments:
            return self._build_no_comments_output(
                formatter_input,
                invalid_comments,
            )
        
        # Step 2: Use LLM to format and generate summary
        output = await self._format_with_llm(
            valid_comments,
            invalid_comments,
            formatter_input,
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        log_with_data(logger, 20, "Comment formatting completed", {
            "session_id": session_id,
            "inline_comments": len(output.inline_comments),
            "dropped_comments": len(output.dropped_comments),
            "duration_ms": round(duration_ms, 2),
        })
        
        return output
    
    def _filter_to_valid_lines(
        self,
        raw_comments: List[RawReviewComment],
        valid_lines: Dict[str, List[int]],
    ) -> tuple[List[RawReviewComment], List[DroppedComment]]:
        """
        Filter comments to only those on valid diff lines.
        
        Returns:
            Tuple of (valid_comments, dropped_comments)
        """
        valid = []
        dropped = []
        
        for comment in raw_comments:
            file_valid_lines = valid_lines.get(comment.file, [])
            
            if not file_valid_lines:
                # File not in diff at all
                dropped.append(DroppedComment(
                    file=comment.file,
                    line=comment.line,
                    severity=comment.severity,
                    message=comment.message[:100],
                    reason="file_not_in_diff",
                ))
            elif comment.line not in file_valid_lines:
                # Line not in diff
                dropped.append(DroppedComment(
                    file=comment.file,
                    line=comment.line,
                    severity=comment.severity,
                    message=comment.message[:100],
                    reason="not_in_diff",
                ))
            else:
                valid.append(comment)
        
        return valid, dropped
    
    def _build_no_comments_output(
        self,
        formatter_input: FormatterInput,
        dropped_comments: List[DroppedComment],
    ) -> FormatterOutput:
        """Build output when there are no valid comments to post."""
        
        summary = """## Code Review Summary

### Impact Analysis
This PR has been reviewed. No issues were found on the changed lines.

### Observations
The changes appear to follow good practices. Any potential issues identified were in unchanged portions of the code.

---
*No inline comments to post. All identified issues were on lines not part of this diff.*
"""
        
        if dropped_comments:
            summary += f"\n\n<details>\n<summary>Issues found outside diff ({len(dropped_comments)})</summary>\n\n"
            for dc in dropped_comments[:10]:  # Show first 10
                summary += f"- **{dc.file}:{dc.line}** [{dc.severity}]: {dc.message}\n"
            if len(dropped_comments) > 10:
                summary += f"\n...and {len(dropped_comments) - 10} more\n"
            summary += "\n</details>"
        
        return FormatterOutput(
            summary_body=summary,
            inline_comments=[],
            dropped_comments=dropped_comments,
            total_raw_comments=len(formatter_input.raw_comments),
            comments_on_valid_lines=0,
            comments_merged=0,
            comments_limited=0,
        )
    
    async def _format_with_llm(
        self,
        valid_comments: List[RawReviewComment],
        already_dropped: List[DroppedComment],
        formatter_input: FormatterInput,
    ) -> FormatterOutput:
        """
        Use LLM to format comments and generate summary.
        """
        session_id = get_session_id() or "unknown"
        
        # Prepare input for LLM
        raw_comments_json = json.dumps(
            [c.to_dict() for c in valid_comments],
            indent=2
        )
        
        valid_lines_json = json.dumps(formatter_input.valid_lines, indent=2)
        
        # Truncate diff context if too long
        diff_context = ""
        for file, diff in formatter_input.diff_text_per_file.items():
            if len(diff_context) + len(diff) > 8000:
                diff_context += f"\n\n### {file}\n(diff truncated)\n"
            else:
                diff_context += f"\n\n### {file}\n```diff\n{diff[:2000]}\n```"
        
        # Build messages
        system_prompt = COMMENT_FORMATTER_SYSTEM_PROMPT.format(
            max_comments=formatter_input.max_comments
        )
        
        user_prompt = COMMENT_FORMATTER_USER_PROMPT.format(
            files_changed=formatter_input.files_changed,
            total_comments=len(valid_comments),
            max_comments=formatter_input.max_comments,
            valid_lines_json=valid_lines_json,
            raw_comments_json=raw_comments_json,
            diff_context=diff_context[:10000],  # Limit context
        )
        
        system_message = SystemMessage(content=system_prompt)
        human_message = HumanMessage(content=user_prompt)
        
        # Call LLM
        llm_start = time.perf_counter()
        
        try:
            response = await asyncio.to_thread(
                self.llm.invoke,
                [system_message, human_message]
            )
            
            llm_duration_ms = (time.perf_counter() - llm_start) * 1000
            
            # Log LLM call
            prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
            completion_tokens = len(str(response.content)) // 4
            
            log_llm_call(
                logger,
                model=self._model or "default",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=llm_duration_ms,
            )
            
            # Parse response
            return self._parse_llm_response(
                response.content,
                valid_comments,
                already_dropped,
                formatter_input,
            )
            
        except Exception as e:
            log_with_data(logger, 40, f"LLM formatting failed: {e}", {
                "session_id": session_id,
                "error": str(e),
            })
            
            # Fallback to basic formatting
            return self._fallback_format(
                valid_comments,
                already_dropped,
                formatter_input,
            )
    
    def _parse_llm_response(
        self,
        response_content: Any,
        valid_comments: List[RawReviewComment],
        already_dropped: List[DroppedComment],
        formatter_input: FormatterInput,
    ) -> FormatterOutput:
        """Parse LLM response into FormatterOutput."""
        
        # Handle different response formats
        if isinstance(response_content, list):
            # Responses API format
            text_content = ""
            for block in response_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content = block.get("text", "")
                    break
            response_content = text_content
        
        try:
            # Extract JSON from response
            content = str(response_content).strip()
            
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            data = json.loads(content)
            
            # Extract summary
            summary_body = data.get("summary_body", "## Code Review Summary\n\nReview completed.")
            
            # Extract inline comments
            inline_comments = []
            for c in data.get("inline_comments", []):
                inline_comments.append(FormattedInlineComment(
                    path=c.get("path", ""),
                    line=c.get("line", 1),
                    body=c.get("body", ""),
                    side=c.get("side", "RIGHT"),
                    severity=c.get("severity", "medium"),
                    start_line=c.get("start_line"),
                    start_side=c.get("start_side"),
                ))
            
            # Extract dropped comments from LLM and merge with already dropped
            dropped_comments = list(already_dropped)
            for dc in data.get("dropped_comments", []):
                dropped_comments.append(DroppedComment(
                    file=dc.get("file", ""),
                    line=dc.get("line", 0),
                    severity=dc.get("severity", "medium"),
                    message=dc.get("message", ""),
                    reason=dc.get("reason", "unknown"),
                ))
            
            # Calculate stats
            merged_count = sum(1 for dc in dropped_comments if dc.reason == "merged")
            limited_count = sum(1 for dc in dropped_comments if dc.reason == "limit_exceeded")
            
            return FormatterOutput(
                summary_body=summary_body,
                inline_comments=inline_comments,
                dropped_comments=dropped_comments,
                total_raw_comments=len(formatter_input.raw_comments),
                comments_on_valid_lines=len(valid_comments),
                comments_merged=merged_count,
                comments_limited=limited_count,
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._fallback_format(
                valid_comments,
                already_dropped,
                formatter_input,
            )
    
    def _fallback_format(
        self,
        valid_comments: List[RawReviewComment],
        already_dropped: List[DroppedComment],
        formatter_input: FormatterInput,
    ) -> FormatterOutput:
        """
        Fallback formatting without LLM.
        
        Used when LLM call fails or for simple cases.
        """
        session_id = get_session_id() or "unknown"
        
        log_with_data(logger, 20, "Using fallback formatting", {
            "session_id": session_id,
            "comments_count": len(valid_comments),
        })
        
        # Sort by severity priority
        sorted_comments = sorted(valid_comments, key=lambda c: c.priority)
        
        # Group comments by file:line (multiple comments on same line will be merged)
        grouped = self._merge_comments(sorted_comments)
        
        # Sort grouped items by highest severity in each group
        sorted_groups = sorted(
            grouped.items(),
            key=lambda item: min(c.priority for c in item[1])
        )
        
        # Limit to max comment locations
        limited_groups = sorted_groups[:formatter_input.max_comments]
        dropped_groups = sorted_groups[formatter_input.max_comments:]
        
        # Count merged comments for stats
        total_comments_in_limited = sum(len(comments) for _, comments in limited_groups)
        merged_count = total_comments_in_limited - len(limited_groups)
        
        # Format inline comments (one per unique file:line location)
        inline_comments = []
        for key, comments in limited_groups:
            # Use the new merged formatting for multiple comments
            body = self._format_merged_comments(comments)
            
            # Get the representative comment for line info (first one, sorted by priority)
            rep_comment = comments[0]
            
            # For multi-line comments: start_line should be < line
            # If end_line is provided and different from line, use line as start and end_line as the actual line
            if rep_comment.end_line and rep_comment.end_line != rep_comment.line and rep_comment.end_line > rep_comment.line:
                start_line = rep_comment.line
                end_line = rep_comment.end_line
            else:
                start_line = None
                end_line = rep_comment.line
            
            # Get highest severity from all merged comments
            highest_severity = min(comments, key=lambda c: c.priority).severity
            
            inline_comments.append(FormattedInlineComment(
                path=rep_comment.file,
                line=end_line,
                body=body,
                side="RIGHT",  # Comment on new code side (new version)
                severity=highest_severity,
                start_line=start_line,
                start_side="RIGHT" if start_line else None,
            ))
        
        # Build dropped list
        dropped_comments = list(already_dropped)
        for key, comments in dropped_groups:
            for comment in comments:
                dropped_comments.append(DroppedComment(
                    file=comment.file,
                    line=comment.line,
                    severity=comment.severity,
                    message=comment.message[:100],
                    reason="limit_exceeded",
                ))
        
        # Build summary
        summary_body = self._build_fallback_summary(
            valid_comments,
            inline_comments,
            dropped_comments,
            formatter_input,
        )
        
        return FormatterOutput(
            summary_body=summary_body,
            inline_comments=inline_comments,
            dropped_comments=dropped_comments,
            total_raw_comments=len(formatter_input.raw_comments),
            comments_on_valid_lines=len(valid_comments),
            comments_merged=merged_count,
            comments_limited=sum(len(comments) for _, comments in dropped_groups),
        )
    
    def _merge_comments(
        self,
        comments: List[RawReviewComment],
    ) -> Dict[str, List[RawReviewComment]]:
        """
        Group comments by file:line.
        
        Returns:
            Dict mapping "file:line" to list of comments on that line
        """
        grouped: Dict[str, List[RawReviewComment]] = {}
        
        for comment in comments:
            key = f"{comment.file}:{comment.line}"
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(comment)
        
        return grouped
    
    def _format_merged_comments(self, comments: List[RawReviewComment]) -> str:
        """
        Format multiple comments on the same line into a single rich comment.
        
        Uses collapsible <details> sections for each issue, similar to CodeRabbit/Greptile.
        """
        if len(comments) == 1:
            # Single comment - use simple format
            return self._format_single_comment(comments[0])
        
        # Multiple comments - use collapsible sections for each
        parts = [
            "**🛠️ Refactor suggestion / ⚠️ Potential issues**",
            "",
        ]
        
        for comment in comments:
            sev_emoji = SEVERITY_EMOJI.get(comment.severity.lower(), "💬")
            sev_label = SEVERITY_LABEL.get(comment.severity.lower(), "Issue")
            cat_emoji = CATEGORY_EMOJI.get(comment.category.lower(), "💬") if comment.category else "💬"
            cat_name = comment.category.replace("_", " ").title() if comment.category else "Issue"
            
            # Create collapsible section for each issue
            summary_text = f"{sev_emoji} {sev_label}: {cat_name}"
            if comment.message:
                # Use first line or first 50 chars as summary preview
                preview = comment.message.split('\n')[0][:50]
                if len(preview) < len(comment.message.split('\n')[0]):
                    preview += "..."
                summary_text = f"{sev_emoji} {sev_label}: {preview}"
            
            parts.append("<details>")
            parts.append(f"<summary>{summary_text}</summary>")
            parts.append("")
            parts.append(comment.message)
            
            # Add suggestion/code inside the details block
            if comment.suggested_code:
                parts.extend([
                    "",
                    "```suggestion",
                    comment.suggested_code,
                    "```",
                ])
            elif comment.suggestion:
                parts.extend([
                    "",
                    f"**Suggestion:** {comment.suggestion}",
                ])
            
            parts.append("</details>")
            parts.append("")
        
        return "\n".join(parts)
    
    def _format_single_comment(self, comment: RawReviewComment) -> str:
        """Format a single comment with rich markdown."""
        
        sev_emoji = SEVERITY_EMOJI.get(comment.severity.lower(), "💬")
        sev_label = SEVERITY_LABEL.get(comment.severity.lower(), "Issue")
        cat_emoji = CATEGORY_EMOJI.get(comment.category.lower(), "💬") if comment.category else "💬"
        cat_name = comment.category.replace("_", " ").title() if comment.category else "Issue"
        
        parts = [
            f"**{sev_emoji} {sev_label}** | {cat_emoji} {cat_name}",
            "",
            comment.message,
        ]
        
        # Add suggestion block if we have suggested code
        if comment.suggested_code:
            parts.extend([
                "",
                "<details>",
                "<summary>Suggested Fix</summary>",
                "",
                "```suggestion",
                comment.suggested_code,
                "```",
                "",
                "</details>",
            ])
        elif comment.suggestion:
            parts.extend([
                "",
                f"**Suggestion:** {comment.suggestion}",
            ])
        
        return "\n".join(parts)
    
    def _build_fallback_summary(
        self,
        valid_comments: List[RawReviewComment],
        inline_comments: List[FormattedInlineComment],
        dropped_comments: List[DroppedComment],
        formatter_input: FormatterInput,
    ) -> str:
        """Build a summary for fallback formatting."""
        
        # Count by severity
        severity_counts = {}
        for comment in valid_comments:
            sev = comment.severity.lower()
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Count by category
        category_counts = {}
        for comment in valid_comments:
            cat = comment.category or "other"
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        parts = [
            "## Code Review Summary",
            "",
            "### Impact Analysis",
            f"Reviewed {formatter_input.files_changed} file(s) with code changes.",
            "",
        ]
        
        # Add severity breakdown
        if severity_counts:
            parts.append("### Issue Breakdown")
            for sev in ["critical", "high", "medium", "low", "info"]:
                if sev in severity_counts:
                    emoji = SEVERITY_EMOJI.get(sev, "")
                    parts.append(f"- {emoji} **{sev.title()}**: {severity_counts[sev]}")
            parts.append("")
        
        # Add main categories
        if category_counts:
            parts.append("### Categories")
            top_cats = sorted(category_counts.items(), key=lambda x: -x[1])[:5]
            for cat, count in top_cats:
                emoji = CATEGORY_EMOJI.get(cat, "💬")
                parts.append(f"- {emoji} {cat.replace('_', ' ').title()}: {count}")
            parts.append("")
        
        # Footer
        parts.extend([
            "---",
            f"*Found {len(valid_comments)} issues. Showing {len(inline_comments)} inline comments.*",
        ])
        
        if dropped_comments:
            not_in_diff = sum(1 for d in dropped_comments if d.reason in ("not_in_diff", "file_not_in_diff"))
            if not_in_diff > 0:
                parts.append(f"*{not_in_diff} issues were on lines not in this diff.*")
        
        return "\n".join(parts)
    
    @classmethod
    def from_review_output(
        cls,
        review_output: ReviewOutput,
        valid_lines: Dict[str, List[int]],
        diff_text_per_file: Dict[str, str],
        max_comments: int = 20,
        **kwargs,
    ) -> FormatterInput:
        """
        Create FormatterInput from ReviewOutput.
        
        Convenience method for integration with existing review flow.
        """
        raw_comments = [
            RawReviewComment(
                file=issue.file,
                line=issue.line,
                severity=issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
                category=issue.category.value if hasattr(issue.category, 'value') else (str(issue.category) if issue.category else None),
                message=issue.message,
                suggestion=issue.suggestion,
                code_snippet=issue.code_snippet,
                suggested_code=issue.suggested_code,
                end_line=issue.end_line,
                confidence=issue.confidence,
            )
            for issue in review_output.issues
        ]
        
        return FormatterInput(
            raw_comments=raw_comments,
            valid_lines=valid_lines,
            diff_text_per_file=diff_text_per_file,
            files_changed=review_output.files_reviewed,
            max_comments=max_comments,
        )
