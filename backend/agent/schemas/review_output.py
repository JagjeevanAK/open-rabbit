"""
Review Agent Output Schemas

Defines the output structures for the Review Agent including:
- Smart file content reading
- LLM review inputs/outputs
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .common import FileChange, PRContext, KBContext, ReviewIssue
from .parser_output import ParserOutput, FileAnalysis


class LineRange(BaseModel):
    """A range of lines in a file"""
    start: int
    end: int
    
    @property
    def count(self) -> int:
        return self.end - self.start + 1


class FileChunk(BaseModel):
    """A chunk of file content with line numbers"""
    start_line: int
    end_line: int
    content: str
    is_truncated: bool = False
    truncation_reason: Optional[str] = None


class FileContent(BaseModel):
    """Smart file content with line numbers and metadata"""
    file_path: str
    language: str
    total_lines: int
    total_tokens: int = Field(default=0, description="Estimated token count")
    
    # Content chunks (may be partial for large files)
    chunks: List[FileChunk] = Field(default_factory=list)
    
    # Reading strategy used
    strategy: str = Field(default="full", description="full, truncated, context_only")
    
    # Changed lines (from git diff)
    changed_lines: List[int] = Field(default_factory=list)
    
    @property
    def full_content(self) -> str:
        """Get full content with line numbers"""
        lines = []
        for chunk in self.chunks:
            chunk_lines = chunk.content.split('\n')
            for i, line in enumerate(chunk_lines):
                line_num = chunk.start_line + i
                lines.append(f"{line_num:4d} | {line}")
        return '\n'.join(lines)
    
    @property
    def content_only(self) -> str:
        """Get content without line numbers"""
        return '\n'.join(chunk.content for chunk in self.chunks)


class ReviewInput(BaseModel):
    """Input to the Review Agent"""
    changed_files: List[FileChange]
    repo_path: str
    owner: str
    repo: str
    
    # Parser output for each file (keyed by file path)
    parser_outputs: Dict[str, FileAnalysis] = Field(default_factory=dict)
    
    # Context
    pr_context: PRContext
    kb_context: Optional[KBContext] = None
    
    # Configuration
    max_tokens_per_file: int = Field(default=8000)
    include_suggestions: bool = Field(default=True)


class ReviewOutput(BaseModel):
    """Output from the Review Agent"""
    issues: List[ReviewIssue] = Field(default_factory=list)
    files_reviewed: int = Field(default=0)
    
    # KB usage
    kb_context_used: bool = Field(default=False)
    kb_learnings_count: int = Field(default=0)
    
    # Token usage (for monitoring)
    total_tokens_used: int = Field(default=0)
    
    # Files that couldn't be reviewed
    skipped_files: List[str] = Field(default_factory=list)
    skip_reasons: Dict[str, str] = Field(default_factory=dict)
    
    # Raw LLM responses (for debugging)
    raw_responses: Optional[Dict[str, str]] = None
