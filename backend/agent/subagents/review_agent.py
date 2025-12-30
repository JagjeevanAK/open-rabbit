"""
Review Agent

LLM-powered code review agent that:
- Reads files intelligently using smart file reader
- Enriches context with Knowledge Base learnings
- Uses LLM to generate review comments
- Supports multiple LLM providers (OpenAI, Anthropic, OpenRouter)
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from pydantic import BaseModel, Field

from agent.subagents.base_agent import BaseAgent
from agent.schemas.common import (
    Severity,
    IssueCategory,
    FileChange,
    PRContext,
    KBContext,
    ReviewIssue,
)
from agent.schemas.review_output import ReviewInput, ReviewOutput, FileContent, FileChunk
from agent.schemas.parser_output import FileAnalysis
from agent.tools.smart_file_reader import SmartFileReader, parse_diff_for_changed_lines
from agent.tools.token_utils import TokenCounter, TokenBudget
from agent.services.kb_client import KnowledgeBaseClient, get_kb_client


# Review prompt template
REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review code changes and provide actionable, constructive feedback.

## Your Responsibilities:
1. Identify bugs, security issues, and potential runtime errors
2. Suggest performance improvements where applicable
3. Point out code style and maintainability issues
4. Recognize good patterns and practices (don't just criticize)
5. Be specific - reference exact line numbers and provide examples

## Guidelines:
- Be concise but thorough
- Prioritize issues by severity (critical > high > medium > low)
- Only flag real issues, not stylistic preferences unless they impact readability significantly
- If the code looks good, say so briefly
- Consider the context provided by the PR description

## Output Format:
Respond with a JSON array of review comments. Each comment should have:
- file_path: string (the file being reviewed)
- line_start: number (1-indexed line number where issue starts)
- line_end: number or null (1-indexed line number where issue ends, null if single line)
- severity: "critical" | "high" | "medium" | "low" | "info"
- category: "security" | "bug" | "performance" | "maintainability" | "style" | "error_handling" | "type_safety" | "documentation" | "other"
- title: string (short title, max 50 chars)
- message: string (detailed explanation)
- suggestion: string or null (suggested fix if applicable)
- confidence: number (0.0-1.0, how confident you are)

Example response:
```json
[
  {
    "file_path": "src/utils.py",
    "line_start": 42,
    "line_end": 45,
    "severity": "high",
    "category": "security",
    "title": "SQL Injection Risk",
    "message": "User input is directly concatenated into the SQL query without sanitization.",
    "suggestion": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "confidence": 0.95
  }
]
```

If there are no issues, return an empty array: []
"""

REVIEW_USER_PROMPT_TEMPLATE = """## Pull Request Context
**Title:** {pr_title}
**Description:** {pr_description}

{kb_context}

{parser_context}

## Files to Review

{files_content}

---

Please review the code changes above and provide your feedback as a JSON array of review comments.
Focus on the most important issues first. If the code looks good overall, you can return an empty array or just informational comments.
"""


class LLMReviewResponse(BaseModel):
    """Structured response from LLM review."""
    issues: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewAgent(BaseAgent[ReviewInput, ReviewOutput]):
    """
    Review Agent for LLM-powered code review.
    
    Uses smart file reading to efficiently read code,
    enriches prompts with KB context, and generates
    structured review comments.
    """
    
    def __init__(
        self,
        enable_checkpointing: bool = True,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
        max_tokens_per_file: int = 4000,
        max_total_tokens: int = 32000,
        temperature: float = 0.1,
        use_mock: bool = False,
        kb_client: Optional[KnowledgeBaseClient] = None,
    ):
        """
        Initialize review agent.
        
        Args:
            enable_checkpointing: Enable state checkpointing
            llm_provider: LLM provider (openai, anthropic, openrouter)
            llm_model: Specific model to use (None for default)
            max_tokens_per_file: Max tokens per file content
            max_total_tokens: Max total tokens for prompt
            temperature: LLM temperature
            use_mock: Use mock responses for testing
            kb_client: Knowledge Base client (uses global if None)
        """
        super().__init__(enable_checkpointing=enable_checkpointing)
        
        self.llm_provider = llm_provider
        self.llm_model = llm_model or self._get_default_model(llm_provider)
        self.max_tokens_per_file = max_tokens_per_file
        self.max_total_tokens = max_total_tokens
        self.temperature = temperature
        self.use_mock = use_mock
        
        self.kb_client = kb_client
        self.file_reader = SmartFileReader(
            model=self._get_tiktoken_model(),
            max_tokens_per_file=max_tokens_per_file
        )
        self.token_counter = TokenCounter(self._get_tiktoken_model())
        
        self._logger = logging.getLogger("agent.review")
        self._llm = None
    
    @property
    def name(self) -> str:
        return "review"
    
    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20241022",
            "openrouter": "anthropic/claude-3.5-sonnet",
        }
        return defaults.get(provider, "gpt-4o")
    
    def _get_tiktoken_model(self) -> str:
        """Get tiktoken model name for token counting."""
        # Map to tiktoken-compatible model names
        if "gpt-4" in self.llm_model or "gpt-3.5" in self.llm_model:
            return self.llm_model
        # For Claude and other models, use gpt-4o encoding as approximation
        return "gpt-4o"
    
    def _get_llm(self):
        """Get or create LLM instance."""
        if self._llm is not None:
            return self._llm
        
        if self.use_mock:
            return None
        
        if self.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model=self.llm_model,
                temperature=self.temperature,
            )
        elif self.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            self._llm = ChatAnthropic(
                model=self.llm_model,
                temperature=self.temperature,
            )
        elif self.llm_provider == "openrouter":
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model=self.llm_model,
                temperature=self.temperature,
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        
        return self._llm
    
    def _validate_input(self, input_data: ReviewInput) -> None:
        """Validate review input."""
        if not input_data.changed_files:
            raise ValueError("No changed files provided")
        
        if not input_data.repo_path:
            raise ValueError("Repository path is required")
        
        if not os.path.isdir(input_data.repo_path):
            raise ValueError(f"Repository path does not exist: {input_data.repo_path}")
    
    def _execute(self, input_data: ReviewInput) -> ReviewOutput:
        """Execute the review."""
        output = ReviewOutput()
        
        # Get KB context if available
        kb_context = self._get_kb_context(input_data)
        
        # Read files with smart reader
        file_contents = self._read_files(input_data)
        
        if not file_contents:
            self._logger.warning("No files could be read for review")
            return output
        
        # Build prompt
        prompt = self._build_prompt(input_data, file_contents, kb_context)
        
        # Get LLM response
        if self.use_mock:
            response = self._get_mock_response(file_contents)
        else:
            response = self._call_llm(prompt)
        
        # Parse response into ReviewIssues
        output.issues = self._parse_response(response)
        output.files_reviewed = len(file_contents)
        output.kb_context_used = bool(kb_context)
        output.kb_learnings_count = len(input_data.kb_context.learnings) if input_data.kb_context else 0
        output.total_tokens_used = self.token_counter.count_tokens(prompt)
        
        return output
    
    def _get_kb_context(self, input_data: ReviewInput) -> str:
        """Get formatted KB context for the prompt."""
        if not input_data.kb_context or not input_data.kb_context.has_learnings:
            # Try to fetch from KB if client available
            if self.kb_client or os.getenv("KB_ENABLED", "").lower() == "true":
                try:
                    client = self.kb_client or get_kb_client()
                    learnings = client.get_pr_context_learnings(
                        owner=input_data.owner,
                        repo=input_data.repo,
                        pr_description=input_data.pr_context.description or input_data.pr_context.title,
                        changed_files=[f.path for f in input_data.changed_files],
                        k=5
                    )
                    if learnings:
                        return client.format_learnings_for_prompt(learnings)
                except Exception as e:
                    self._logger.warning(f"Failed to get KB context: {e}")
            return ""
        
        return input_data.kb_context.formatted
    
    def _read_files(self, input_data: ReviewInput) -> List[FileContent]:
        """Read files using smart file reader."""
        file_contents = []
        
        # Parse diffs for changed lines if available
        changed_lines_map: Dict[str, List[int]] = {}
        for fc in input_data.changed_files:
            if fc.patch:
                parsed = parse_diff_for_changed_lines(fc.patch)
                # The diff parser returns the filename from the diff header
                # We need to map it to our file path
                for path, lines in parsed.items():
                    if path.endswith(fc.path) or fc.path.endswith(path):
                        changed_lines_map[fc.path] = lines
                        break
                else:
                    # If no match, use the file path directly
                    if fc.path in parsed:
                        changed_lines_map[fc.path] = parsed[fc.path]
        
        for fc in input_data.changed_files:
            if fc.is_deleted:
                continue
            
            full_path = os.path.join(input_data.repo_path, fc.path)
            if not os.path.exists(full_path):
                self._logger.warning(f"File not found: {full_path}")
                continue
            
            # Get changed lines for this file
            changed_lines = changed_lines_map.get(fc.path)
            
            # Smart read the file
            result = self.file_reader.smart_read(
                full_path,
                changed_lines=changed_lines,
                max_tokens=input_data.max_tokens_per_file
            )
            
            if result.error:
                self._logger.warning(f"Error reading {fc.path}: {result.error}")
                continue
            
            # Convert to FileContent schema
            chunks = [
                FileChunk(
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    is_truncated=not c.is_complete,
                )
                for c in result.chunks
            ]
            
            # Detect language from extension
            ext = Path(fc.path).suffix.lower()
            language_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "tsx",
                ".jsx": "javascript",
            }
            language = language_map.get(ext, "unknown")
            
            file_contents.append(FileContent(
                file_path=fc.path,
                language=language,
                total_lines=result.total_lines,
                total_tokens=result.total_tokens,
                chunks=chunks,
                strategy=result.strategy_used,
                changed_lines=changed_lines or [],
            ))
        
        return file_contents
    
    def _build_prompt(
        self,
        input_data: ReviewInput,
        file_contents: List[FileContent],
        kb_context: str
    ) -> str:
        """Build the full prompt for LLM."""
        # Format parser context if available
        parser_context = ""
        if input_data.parser_outputs:
            parser_context = self._format_parser_context(input_data.parser_outputs)
        
        # Format file contents
        files_content = self._format_files_content(file_contents)
        
        # Build user prompt
        user_prompt = REVIEW_USER_PROMPT_TEMPLATE.format(
            pr_title=input_data.pr_context.title,
            pr_description=input_data.pr_context.description or "No description provided.",
            kb_context=kb_context,
            parser_context=parser_context,
            files_content=files_content,
        )
        
        # Combine system and user prompts
        full_prompt = f"{REVIEW_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # Check token budget
        total_tokens = self.token_counter.count_tokens(full_prompt)
        if total_tokens > self.max_total_tokens:
            self._logger.warning(
                f"Prompt exceeds token budget: {total_tokens} > {self.max_total_tokens}"
            )
            # Truncate file contents if needed
            truncated, _ = self.token_counter.truncate_to_tokens(
                files_content,
                self.max_total_tokens - self.token_counter.count_tokens(REVIEW_SYSTEM_PROMPT) - 2000
            )
            user_prompt = REVIEW_USER_PROMPT_TEMPLATE.format(
                pr_title=input_data.pr_context.title,
                pr_description=input_data.pr_context.description or "No description provided.",
                kb_context=kb_context,
                parser_context=parser_context,
                files_content=truncated,
            )
            full_prompt = f"{REVIEW_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        return full_prompt
    
    def _format_parser_context(self, parser_outputs: Dict[str, FileAnalysis]) -> str:
        """Format parser outputs for prompt context."""
        if not parser_outputs:
            return ""
        
        lines = ["\n## Static Analysis Summary\n"]
        
        for file_path, analysis in parser_outputs.items():
            if analysis.security_issues or analysis.complexity_issues:
                lines.append(f"### {file_path}")
                
                if analysis.security_issues:
                    lines.append("**Security Issues Found:**")
                    for issue in analysis.security_issues[:3]:  # Limit to top 3
                        lines.append(f"- Line {issue.line}: {issue.type.value} ({issue.severity.value})")
                
                if analysis.complexity_issues:
                    lines.append("**High Complexity:**")
                    for issue in analysis.complexity_issues[:3]:
                        lines.append(f"- {issue.function_name}: complexity {issue.complexity}")
                
                lines.append("")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_files_content(self, file_contents: List[FileContent]) -> str:
        """Format file contents for prompt."""
        parts = []
        
        for fc in file_contents:
            parts.append(f"### File: {fc.file_path}")
            parts.append(f"Language: {fc.language} | Lines: {fc.total_lines} | Strategy: {fc.strategy}")
            
            if fc.changed_lines:
                parts.append(f"Changed lines: {fc.changed_lines[:10]}{'...' if len(fc.changed_lines) > 10 else ''}")
            
            parts.append("```" + fc.language)
            parts.append(fc.full_content)
            parts.append("```\n")
        
        return "\n".join(parts)
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and get response."""
        llm = self._get_llm()
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                HumanMessage(content=prompt.replace(REVIEW_SYSTEM_PROMPT, "").strip()),
            ]
            
            response = llm.invoke(messages)
            return response.content
            
        except Exception as e:
            self._logger.error(f"LLM call failed: {e}")
            raise
    
    def _get_mock_response(self, file_contents: List[FileContent]) -> str:
        """Generate mock response for testing."""
        mock_issues = []
        
        for fc in file_contents:
            # Generate a mock issue for each file
            mock_issues.append({
                "file_path": fc.file_path,
                "line_start": 1,
                "line_end": None,
                "severity": "info",
                "category": "style",
                "title": "Mock Review Comment",
                "message": f"This is a mock review comment for {fc.file_path}. The code looks good overall.",
                "suggestion": None,
                "confidence": 0.5
            })
        
        return json.dumps(mock_issues)
    
    def _parse_response(self, response: str) -> List[ReviewIssue]:
        """Parse LLM response into ReviewIssue objects."""
        issues = []
        
        try:
            # Extract JSON from response (it might be wrapped in markdown code blocks)
            json_str = response
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            
            parsed = json.loads(json_str)
            
            if not isinstance(parsed, list):
                parsed = [parsed]
            
            for item in parsed:
                try:
                    # Map severity string to enum
                    severity_map = {
                        "critical": Severity.CRITICAL,
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                        "info": Severity.INFO,
                    }
                    severity = severity_map.get(
                        item.get("severity", "medium").lower(),
                        Severity.MEDIUM
                    )
                    
                    # Map category string to enum
                    category_map = {
                        "security": IssueCategory.SECURITY,
                        "bug": IssueCategory.BUG,
                        "performance": IssueCategory.PERFORMANCE,
                        "maintainability": IssueCategory.MAINTAINABILITY,
                        "style": IssueCategory.STYLE,
                        "error_handling": IssueCategory.ERROR_HANDLING,
                        "type_safety": IssueCategory.TYPE_SAFETY,
                        "documentation": IssueCategory.DOCUMENTATION,
                        "other": IssueCategory.OTHER,
                    }
                    category = category_map.get(
                        item.get("category", "other").lower(),
                        IssueCategory.OTHER
                    )
                    
                    issue = ReviewIssue(
                        file_path=item.get("file_path", "unknown"),
                        line_start=item.get("line_start", 1),
                        line_end=item.get("line_end"),
                        severity=severity,
                        category=category,
                        title=item.get("title", "Review Comment"),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion"),
                        confidence=item.get("confidence", 0.8),
                        source="review"
                    )
                    issues.append(issue)
                    
                except Exception as e:
                    self._logger.warning(f"Failed to parse issue: {e}")
                    continue
                    
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse LLM response as JSON: {e}")
            self._logger.debug(f"Response was: {response[:500]}...")
            
            # Try to extract any useful feedback from non-JSON response
            if response.strip():
                issues.append(ReviewIssue(
                    file_path="general",
                    line_start=1,
                    severity=Severity.INFO,
                    category=IssueCategory.OTHER,
                    title="Review Summary",
                    message=response[:1000],
                    confidence=0.5,
                    source="review"
                ))
        
        return issues
