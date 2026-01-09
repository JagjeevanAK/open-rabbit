"""
Code Review Agent

Sub-agent responsible for reviewing code changes and identifying issues.
Works like CodeRabbit/Greptile - focuses on code quality, not structure.

Responsibilities:
- Analyze code smells and anti-patterns
- Identify logical issues and bugs
- Check style violations against KB conventions
- Generate actionable review comments
- Detect package changes and search for breaking changes/deprecations

Constraints:
- Does NOT generate unit tests
- Does NOT parse code (receives parsed metadata)
- Outputs actionable review comments only
"""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from .base_agent import BaseAgent, AgentConfig
from ..schemas.common import FileInfo, KBContext
from ..schemas.parser_output import ParserOutput
from ..schemas.review_output import (
    ReviewOutput,
    ReviewIssue,
    Severity,
    IssueCategory,
)
from ..llm_factory import LLMFactory, LLMProvider
from ..logging_config import (
    get_logger,
    get_session_id,
    log_with_data,
    log_llm_call,
)
from ..tools.package_intelligence import (
    analyze_diff_for_packages,
    build_package_context,
    PackageIntelligenceResult,
)
from ..tools.web_search import get_all_search_tools

logger = get_logger(__name__)


# System prompt for code review
# Note: Curly braces in JSON examples are doubled to escape them from Python's .format()
CODE_REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review code changes and identify issues.

## Your Role
- Analyze code for bugs, security issues, and code smells
- Identify anti-patterns and logical issues
- Check for style violations based on provided conventions
- Provide actionable, constructive feedback
- Pay attention to package version changes and potential breaking changes

## Review Focus Areas
1. **Security**: SQL injection, XSS, hardcoded secrets, insecure patterns
2. **Bugs**: Logic errors, off-by-one, null handling, race conditions
3. **Performance**: N+1 queries, memory leaks, inefficient algorithms
4. **Maintainability**: Complex code, poor naming, missing documentation
5. **Style**: Violations of project conventions and best practices
6. **Dependencies**: Breaking changes from package upgrades, deprecated APIs

## Knowledge Base Context
{kb_context}

## Package Intelligence
{package_context}

## Parsed Code Structure
{parsed_context}

## Output Format
Respond with a JSON array of issues. Each issue must have:
- file: string (file path)
- line: integer (line number)
- severity: "critical" | "high" | "medium" | "low" | "info"
- category: "security" | "bug" | "performance" | "maintainability" | "style" | "best_practice" | "documentation" | "error_handling"
- message: string (clear description of the issue)
- suggestion: string (how to fix it)

Example:
```json
[
  {{
    "file": "src/utils.py",
    "line": 42,
    "severity": "medium",
    "category": "maintainability",
    "message": "Function 'process_data' has high cyclomatic complexity (15), making it difficult to test and maintain.",
    "suggestion": "Consider breaking this function into smaller, focused helper functions."
  }}
]
```

If no issues are found, return an empty array: []

IMPORTANT:
- Only report real issues, not style preferences
- Be specific about line numbers
- Provide actionable suggestions
- Focus on the most impactful issues first
- If package upgrades are detected, check for usage of deprecated APIs or breaking changes
{valid_lines_instruction}"""


class CodeReviewAgent(BaseAgent[ReviewOutput]):
    """
    Code Review Agent for analyzing code quality.
    
    Consumes:
    - Parsed metadata from Parser Agent
    - Knowledge Base context from Supervisor
    - File contents/diffs
    
    Outputs:
    - Actionable review comments with specific locations
    - Severity ratings for prioritization
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        provider: LLMProvider = LLMProvider.OPENAI,
        model: Optional[str] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the Code Review Agent.
        
        Args:
            llm: Pre-configured LLM instance (optional)
            provider: LLM provider if llm not provided
            model: Model name if llm not provided
            config: Agent configuration
        """
        if config is None:
            config = AgentConfig(
                name="code_review_agent",
                timeout_seconds=180.0,  # 3 minutes for review
                max_retries=2,
            )
        super().__init__(config)
        
        self._llm = llm
        self._provider = provider
        self._model = model
    
    @property
    def name(self) -> str:
        return "code_review_agent"
    
    @property
    def llm(self) -> BaseChatModel:
        """Lazy-load LLM instance."""
        if self._llm is None:
            self._llm = LLMFactory.create(
                provider=self._provider,
                model=self._model,
                temperature=0.2,  # Low temperature for consistent reviews
            )
        return self._llm
    
    async def _execute(
        self,
        parsed_metadata: ParserOutput,
        kb_context: KBContext,
        files: List[FileInfo],
        valid_lines: Optional[Dict[str, List[int]]] = None,
    ) -> ReviewOutput:
        """
        Execute code review on the provided files.
        
        Args:
            parsed_metadata: Output from Parser Agent
            kb_context: Knowledge Base context from Supervisor
            files: List of files to review
            valid_lines: Dict mapping file path -> list of line numbers that are in the diff.
                         If provided, only comments on these lines will be included.
            
        Returns:
            ReviewOutput with identified issues
        """
        output = ReviewOutput()
        session_id = get_session_id() or "unknown"
        start_time = time.perf_counter()
        
        reviewable_files = [f for f in files if not f.is_deleted]
        
        # Analyze files for package changes
        package_context = self._build_package_context(files)
        
        log_with_data(logger, 20, "Starting code review", {
            "session_id": session_id,
            "total_files": len(files),
            "reviewable_files": len(reviewable_files),
            "languages": list(set(f.language for f in reviewable_files if f.language)),
            "kb_context_size": len(kb_context.coding_style) + len(kb_context.conventions),
            "has_valid_lines": valid_lines is not None,
            "has_package_context": bool(package_context),
        })
        
        # Review each file
        tasks = [
            self._review_file(file_info, parsed_metadata, kb_context, valid_lines, package_context)
            for file_info in reviewable_files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        files_reviewed = 0
        files_failed = 0
        
        for file_info, result in zip(reviewable_files, results):
            if isinstance(result, Exception):
                files_failed += 1
                log_with_data(logger, 30, f"Failed to review file: {file_info.path}", {
                    "session_id": session_id,
                    "file": file_info.path,
                    "error": str(result),
                    "error_type": type(result).__name__,
                })
                continue
            
            files_reviewed += 1
            # Add issues from this file
            if isinstance(result, list):
                for issue in result:
                    output.add_issue(issue)
        
        # Add KB learnings that were applied
        if not kb_context.is_empty():
            output.kb_learnings_applied = kb_context.coding_style[:3] + kb_context.conventions[:3]
        
        # Generate summary
        output.summary_text = output._build_summary()
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        log_with_data(logger, 20, "Code review completed", {
            "session_id": session_id,
            "files_reviewed": files_reviewed,
            "files_failed": files_failed,
            "total_issues": output.total_issues,
            "critical_issues": sum(1 for fs in output.file_summaries for _ in range(fs.critical_count)),
            "duration_ms": round(duration_ms, 2),
        })
        
        return output
    
    async def _review_file(
        self,
        file_info: FileInfo,
        parsed_metadata: ParserOutput,
        kb_context: KBContext,
        valid_lines: Optional[Dict[str, List[int]]] = None,
        package_context: str = "",
    ) -> List[ReviewIssue]:
        """Review a single file.
        
        Args:
            file_info: File information including content
            parsed_metadata: Parsed code structure
            kb_context: Knowledge base context
            valid_lines: Dict mapping file path -> list of valid line numbers for comments.
                         If provided for this file, LLM will be instructed to only comment on those lines.
            package_context: Package intelligence context about dependency changes
        """
        session_id = get_session_id() or "unknown"
        start_time = time.perf_counter()
        
        # Get valid lines for this specific file
        file_valid_lines = None
        if valid_lines and file_info.path in valid_lines:
            file_valid_lines = valid_lines[file_info.path]
        
        log_with_data(logger, 10, f"Reviewing file: {file_info.path}", {
            "session_id": session_id,
            "file": file_info.path,
            "language": file_info.language,
            "content_length": len(file_info.content) if file_info.content else 0,
            "valid_lines_count": len(file_valid_lines) if file_valid_lines else "all",
        })
        
        try:
            # Build context for this file
            file_parsed = self._build_parsed_context(file_info, parsed_metadata)
            kb_text = kb_context.to_prompt_context()
            
            # Build valid_lines instruction if we have constraints
            valid_lines_instruction = ""
            if file_valid_lines:
                # Format line ranges for readability
                line_ranges = self._format_line_ranges(file_valid_lines)
                valid_lines_instruction = f"""
## CRITICAL: Valid Lines for Comments
You can ONLY comment on lines that are part of the PR diff. For this file, you can comment on these lines:
{line_ranges}

DO NOT comment on any lines outside this list. If you find an issue on a line not in this list, mention it in the suggestion of a nearby valid line instead."""
            
            # Build the review prompt
            system_prompt_formatted = CODE_REVIEW_SYSTEM_PROMPT.format(
                kb_context=kb_text,
                package_context=package_context if package_context else "No package changes detected.",
                parsed_context=file_parsed,
                valid_lines_instruction=valid_lines_instruction,
            )
            
            system_message = SystemMessage(content=system_prompt_formatted)
            
            # Include file content or diff
            file_content = self._build_file_content(file_info)
            
            human_message = HumanMessage(content=f"""Review this code:

**File:** {file_info.path}

{file_content}

Identify issues and respond with JSON only.""")
            
            # Calculate approximate token counts for logging
            prompt_chars = len(system_prompt_formatted) + len(file_content)
            estimated_prompt_tokens = prompt_chars // 4  # Rough estimate
            
            # Call LLM
            llm_start = time.perf_counter()
            response = await asyncio.to_thread(
                self.llm.invoke,
                [system_message, human_message]
            )
            llm_duration_ms = (time.perf_counter() - llm_start) * 1000
            
            # Log LLM call
            response_length = len(str(response.content)) if response.content else 0
            estimated_completion_tokens = response_length // 4
            
            log_llm_call(
                logger,
                model=self._model or "default",
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=estimated_completion_tokens,
                duration_ms=llm_duration_ms,
            )
            
            # Parse response
            issues = self._parse_review_response(response.content, file_info.path)
            
            # Filter issues to only those on valid lines (safety check even after prompting)
            if file_valid_lines:
                original_count = len(issues)
                issues = [
                    issue for issue in issues
                    if issue.line in file_valid_lines
                ]
                filtered_count = original_count - len(issues)
                if filtered_count > 0:
                    log_with_data(logger, 20, f"Filtered {filtered_count} issues outside valid lines", {
                        "session_id": session_id,
                        "file": file_info.path,
                        "filtered_count": filtered_count,
                        "remaining_count": len(issues),
                    })
            
            total_duration_ms = (time.perf_counter() - start_time) * 1000
            
            log_with_data(logger, 20, f"File review completed: {file_info.path}", {
                "session_id": session_id,
                "file": file_info.path,
                "issues_found": len(issues),
                "llm_duration_ms": round(llm_duration_ms, 2),
                "total_duration_ms": round(total_duration_ms, 2),
            })
            
            return issues
            
        except Exception as e:
            log_with_data(logger, 40, f"Exception reviewing file: {file_info.path}", {
                "session_id": session_id,
                "file": file_info.path,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            raise
    
    def _build_parsed_context(
        self,
        file_info: FileInfo,
        parsed_metadata: ParserOutput
    ) -> str:
        """Build parsed context string for the file."""
        parts = []
        
        # Get file metadata
        for file_meta in parsed_metadata.files:
            if file_meta.path == file_info.path:
                parts.append(f"**File Stats:**")
                parts.append(f"- Language: {file_meta.language}")
                parts.append(f"- Lines: {file_meta.line_count}")
                parts.append(f"- Functions: {file_meta.function_count}")
                parts.append(f"- Classes: {file_meta.class_count}")
                parts.append(f"- Avg Complexity: {file_meta.complexity_score}")
                parts.append("")
                break
        
        # Get symbols for this file
        symbols = parsed_metadata.get_symbols_by_file(file_info.path)
        if symbols:
            parts.append("**Symbols:**")
            for sym in symbols[:20]:  # Limit to 20
                parts.append(f"- {sym.symbol_type.value}: {sym.name} (line {sym.start_line})")
            parts.append("")
        
        # Get hotspots for this file
        file_hotspots = [h for h in parsed_metadata.hotspots if h.file_path == file_info.path]
        if file_hotspots:
            parts.append("**Hotspots (pre-identified):**")
            for hotspot in file_hotspots:
                parts.append(f"- {hotspot.message}")
            parts.append("")
        
        return "\n".join(parts) if parts else "No parsed metadata available."
    
    def _build_file_content(self, file_info: FileInfo) -> str:
        """Build file content for review."""
        if file_info.diff:
            return f"**Diff:**\n```diff\n{file_info.diff}\n```"
        elif file_info.content:
            # Truncate if too long
            content = file_info.content
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            return f"**Full Content:**\n```{file_info.language or ''}\n{content}\n```"
        else:
            return "No content available for review."
    
    def _build_package_context(self, files: List[FileInfo]) -> str:
        """
        Build package intelligence context from files.
        
        Analyzes dependency files (package.json, requirements.txt, pyproject.toml)
        and source files for package changes and new imports.
        
        Args:
            files: List of files to analyze
            
        Returns:
            Package context string for the review prompt
        """
        all_version_changes = []
        all_new_imports = []
        
        # Files that indicate package changes
        package_files = {
            "package.json",
            "requirements.txt", 
            "requirements-dev.txt",
            "pyproject.toml",
        }
        
        for file_info in files:
            # Check if this is a package/dependency file
            file_name = file_info.path.split("/")[-1]
            
            if file_name in package_files and file_info.diff:
                try:
                    result = analyze_diff_for_packages(file_info.diff, file_info.path)
                    all_version_changes.extend(result.version_changes)
                except Exception as e:
                    logger.warning(f"Failed to analyze package file {file_info.path}: {e}")
            
            # Check source files for new imports
            elif file_info.diff and file_info.path.endswith((".js", ".jsx", ".ts", ".tsx", ".py")):
                try:
                    result = analyze_diff_for_packages(file_info.diff, file_info.path)
                    all_new_imports.extend(result.new_imports)
                except Exception as e:
                    logger.warning(f"Failed to analyze imports in {file_info.path}: {e}")
        
        # Build context string
        return build_package_context(all_version_changes, all_new_imports)
    
    def _format_line_ranges(self, lines: List[int]) -> str:
        """
        Format a list of line numbers into readable ranges.
        
        Example: [1, 2, 3, 5, 6, 10] -> "1-3, 5-6, 10"
        """
        if not lines:
            return "No lines available"
        
        sorted_lines = sorted(set(lines))
        ranges = []
        start = sorted_lines[0]
        end = start
        
        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                start = line
                end = line
        
        # Add final range
        if start == end:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{end}")
        
        return ", ".join(ranges)
    
    def _parse_review_response(
        self,
        response_content,
        file_path: str
    ) -> List[ReviewIssue]:
        """Parse LLM response into ReviewIssue objects.
        
        Handles both string responses (Chat Completions API) and list responses
        (Responses API which returns [{type: 'reasoning', ...}, {type: 'text', text: '...'}]).
        """
        issues = []
        
        # Handle Responses API format (list of content blocks)
        if isinstance(response_content, list):
            # Extract text from the 'text' type block
            text_content = ""
            for block in response_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content = block.get("text", "")
                    break
            response_content = text_content
        
        logger.debug(f"Raw LLM response for {file_path}: {str(response_content)[:500]}...")
        
        try:
            # Try to extract JSON from response
            content = response_content.strip() if isinstance(response_content, str) else ""
            
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end == -1:
                    end = len(content)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end == -1:
                    end = len(content)
                content = content[start:end].strip()
            
            logger.debug(f"Extracted JSON content: {content[:300]}...")
            
            # Parse JSON
            data = json.loads(content)
            
            if not isinstance(data, list):
                data = [data]
            
            for item in data:
                try:
                    issue = ReviewIssue(
                        file=item.get("file", file_path),
                        line=int(item.get("line", 1)),
                        severity=Severity(item.get("severity", "medium").lower()),
                        message=item.get("message", "Issue detected"),
                        suggestion=item.get("suggestion"),
                        category=self._parse_category(item.get("category")),
                        code_snippet=item.get("code_snippet"),
                        suggested_code=item.get("suggested_code"),
                    )
                    issues.append(issue)
                except Exception as e:
                    logger.warning(f"Failed to parse issue: {e}")
                    continue
                    
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            # Try to extract any useful information
            if isinstance(response_content, str) and "no issues" in response_content.lower():
                return []
        
        return issues
    
    def _parse_category(self, category_str: Optional[str]) -> Optional[IssueCategory]:
        """Parse category string to enum."""
        if not category_str:
            return None
        
        category_map = {
            "security": IssueCategory.SECURITY,
            "bug": IssueCategory.BUG,
            "performance": IssueCategory.PERFORMANCE,
            "maintainability": IssueCategory.MAINTAINABILITY,
            "style": IssueCategory.STYLE,
            "best_practice": IssueCategory.BEST_PRACTICE,
            "best-practice": IssueCategory.BEST_PRACTICE,
            "documentation": IssueCategory.DOCUMENTATION,
            "error_handling": IssueCategory.ERROR_HANDLING,
            "error-handling": IssueCategory.ERROR_HANDLING,
            "testing": IssueCategory.TESTING,
            "complexity": IssueCategory.COMPLEXITY,
        }
        
        return category_map.get(category_str.lower().replace(" ", "_"))


class MockCodeReviewAgent(CodeReviewAgent):
    """
    Mock Code Review Agent for testing.
    
    Returns predefined issues without making LLM calls.
    """
    
    def __init__(
        self,
        mock_issues: Optional[List[Dict[str, Any]]] = None,
        config: Optional[AgentConfig] = None,
    ):
        super().__init__(config=config)
        self._mock_issues = mock_issues or []
    
    async def _execute(
        self,
        parsed_metadata: ParserOutput,
        kb_context: KBContext,
        files: List[FileInfo],
        valid_lines: Optional[Dict[str, List[int]]] = None,
    ) -> ReviewOutput:
        """Return mock issues without LLM call."""
        output = ReviewOutput()
        
        # Add predefined mock issues
        for issue_dict in self._mock_issues:
            issue = ReviewIssue(
                file=issue_dict.get("file", "mock_file.py"),
                line=issue_dict.get("line", 1),
                severity=Severity(issue_dict.get("severity", "medium")),
                message=issue_dict.get("message", "Mock issue"),
                suggestion=issue_dict.get("suggestion"),
            )
            output.add_issue(issue)
        
        # Generate issues from hotspots
        for hotspot in parsed_metadata.hotspots:
            issue = ReviewIssue(
                file=hotspot.file_path,
                line=hotspot.start_line,
                severity=Severity.MEDIUM if hotspot.severity == "warning" else Severity.HIGH,
                message=hotspot.message,
                suggestion="Consider refactoring to reduce complexity.",
                category=IssueCategory.COMPLEXITY,
            )
            output.add_issue(issue)
        
        output.summary_text = output._build_summary()
        return output
