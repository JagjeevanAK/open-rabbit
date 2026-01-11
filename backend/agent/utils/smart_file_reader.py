"""
Smart File Reader for Code Review
Implements intelligent file reading strategies similar to Claude Code / Cursor.

Key features:
- Line numbers in output for precise references
- Token-aware chunking
- Context windows around changed lines
- Adaptive reading based on file size
- Support for reading specific line ranges
- Sandbox support for E2B cloud environments
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set, TYPE_CHECKING
from dataclasses import dataclass, field

from .token_utils import TokenCounter, count_tokens

if TYPE_CHECKING:
    from agent.services.sandbox_manager import SandboxManager

if TYPE_CHECKING:
    from agent.services.sandbox_manager import SandboxManager


@dataclass
class LineRange:
    """Represents a range of lines."""
    start: int  # 1-indexed, inclusive
    end: int    # 1-indexed, inclusive
    
    def __post_init__(self):
        if self.start < 1:
            self.start = 1
        if self.end < self.start:
            self.end = self.start
    
    def overlaps(self, other: "LineRange") -> bool:
        """Check if this range overlaps with another."""
        return not (self.end < other.start or self.start > other.end)
    
    def merge(self, other: "LineRange") -> "LineRange":
        """Merge with another range."""
        return LineRange(
            start=min(self.start, other.start),
            end=max(self.end, other.end)
        )
    
    def expand(self, context_lines: int) -> "LineRange":
        """Expand range by context lines on both sides."""
        return LineRange(
            start=max(1, self.start - context_lines),
            end=self.end + context_lines
        )
    
    def __len__(self) -> int:
        return self.end - self.start + 1


@dataclass
class FileChunk:
    """Represents a chunk of a file with metadata."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    total_lines: int
    token_count: int = 0
    is_complete: bool = False
    context_type: str = "full"  # full, changed, context, truncated
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "total_lines": self.total_lines,
            "token_count": self.token_count,
            "is_complete": self.is_complete,
            "context_type": self.context_type,
            "content": self.content,
        }


@dataclass
class SmartReadResult:
    """Result of smart file reading."""
    file_path: str
    chunks: List[FileChunk] = field(default_factory=list)
    total_lines: int = 0
    total_tokens: int = 0
    is_complete: bool = False
    strategy_used: str = "unknown"
    error: Optional[str] = None
    
    def get_formatted_content(self) -> str:
        """Get formatted content with line numbers."""
        if self.error:
            return f"Error reading {self.file_path}: {self.error}"
        
        parts = []
        for chunk in self.chunks:
            parts.append(chunk.content)
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_lines": self.total_lines,
            "total_tokens": self.total_tokens,
            "is_complete": self.is_complete,
            "strategy_used": self.strategy_used,
            "error": self.error,
            "chunks": [c.to_dict() for c in self.chunks],
        }


class SmartFileReader:
    """
    Smart file reader with token-aware chunking and context windows.
    
    Implements intelligent reading strategies:
    1. Small files: Read entire file with line numbers
    2. Medium files: Read with optional context around changes
    3. Large files: Read only changed sections with context
    """
    
    # Thresholds for different reading strategies
    SMALL_FILE_TOKENS = 2000      # Files under this are read fully
    MEDIUM_FILE_TOKENS = 8000     # Files under this get basic chunking
    LARGE_FILE_TOKENS = 20000     # Files above this get aggressive chunking
    
    DEFAULT_CONTEXT_LINES = 10    # Lines of context around changes
    MAX_CONTEXT_LINES = 50        # Maximum context lines
    
    def __init__(
        self,
        model: str = "gpt-4o",
        max_tokens_per_file: int = 8000,
        context_lines: int = 10
    ):
        """
        Initialize smart file reader.
        
        Args:
            model: Model name for token counting
            max_tokens_per_file: Maximum tokens to use per file
            context_lines: Lines of context around changes
        """
        self.counter = TokenCounter(model)
        self.max_tokens_per_file = max_tokens_per_file
        self.context_lines = min(context_lines, self.MAX_CONTEXT_LINES)
    
    def read_file_with_line_numbers(
        self,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> Tuple[str, int]:
        """
        Read a file and format with line numbers.
        
        Args:
            file_path: Path to file
            start_line: Starting line (1-indexed)
            end_line: Ending line (1-indexed, None for end of file)
            encoding: File encoding
            
        Returns:
            Tuple of (formatted content, total lines in file)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = path.read_text(encoding=encoding)
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Adjust indices
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(end_line, total_lines)
        
        # Format with line numbers
        formatted_lines = []
        max_line_num = end_idx
        line_num_width = len(str(max_line_num))
        
        for i in range(start_idx, end_idx):
            line_num = i + 1
            formatted_lines.append(f"{line_num:>{line_num_width}} | {lines[i]}")
        
        return "\n".join(formatted_lines), total_lines
    
    def read_full_file(
        self,
        file_path: str,
        max_tokens: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> SmartReadResult:
        """
        Read entire file with line numbers.
        
        Args:
            file_path: Path to file
            max_tokens: Maximum tokens (uses instance default if None)
            encoding: File encoding
            
        Returns:
            SmartReadResult with file content
        """
        max_tokens = max_tokens or self.max_tokens_per_file
        result = SmartReadResult(file_path=file_path)
        
        try:
            formatted_content, total_lines = self.read_file_with_line_numbers(
                file_path, encoding=encoding
            )
            result.total_lines = total_lines
            
            token_count = self.counter.count_tokens(formatted_content)
            result.total_tokens = token_count
            
            if token_count <= max_tokens:
                result.is_complete = True
                result.strategy_used = "full"
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=total_lines,
                    content=formatted_content,
                    total_lines=total_lines,
                    token_count=token_count,
                    is_complete=True,
                    context_type="full"
                ))
            else:
                # Truncate to fit
                truncated, actual_tokens = self.counter.truncate_to_tokens(
                    formatted_content, max_tokens
                )
                result.is_complete = False
                result.strategy_used = "truncated"
                result.total_tokens = actual_tokens
                
                # Estimate how many lines we got
                estimated_lines = int(total_lines * (actual_tokens / token_count))
                
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=estimated_lines,
                    content=truncated,
                    total_lines=total_lines,
                    token_count=actual_tokens,
                    is_complete=False,
                    context_type="truncated"
                ))
            
        except Exception as e:
            result.error = str(e)
            result.strategy_used = "error"
        
        return result
    
    def read_line_ranges(
        self,
        file_path: str,
        ranges: List[LineRange],
        include_context: bool = True,
        max_tokens: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> SmartReadResult:
        """
        Read specific line ranges from a file with optional context.
        
        Args:
            file_path: Path to file
            ranges: List of LineRange objects to read
            include_context: Whether to include context lines
            max_tokens: Maximum tokens to use
            encoding: File encoding
            
        Returns:
            SmartReadResult with requested ranges
        """
        max_tokens = max_tokens or self.max_tokens_per_file
        result = SmartReadResult(file_path=file_path)
        
        try:
            path = Path(file_path)
            content = path.read_text(encoding=encoding)
            lines = content.splitlines()
            result.total_lines = len(lines)
            
            # Expand ranges with context if requested
            if include_context:
                ranges = [r.expand(self.context_lines) for r in ranges]
            
            # Merge overlapping ranges
            ranges = self._merge_ranges(ranges, result.total_lines)
            
            # Calculate line number width for formatting
            max_line = max(r.end for r in ranges) if ranges else 1
            line_num_width = len(str(max_line))
            
            total_tokens_used = 0
            
            for range_obj in ranges:
                if total_tokens_used >= max_tokens:
                    break
                
                # Extract lines for this range
                start_idx = max(0, range_obj.start - 1)
                end_idx = min(range_obj.end, len(lines))
                
                formatted_lines = []
                for i in range(start_idx, end_idx):
                    line_num = i + 1
                    formatted_lines.append(f"{line_num:>{line_num_width}} | {lines[i]}")
                
                chunk_content = "\n".join(formatted_lines)
                chunk_tokens = self.counter.count_tokens(chunk_content)
                
                # Check if we need to truncate
                remaining_tokens = max_tokens - total_tokens_used
                if chunk_tokens > remaining_tokens:
                    chunk_content, chunk_tokens = self.counter.truncate_to_tokens(
                        chunk_content, remaining_tokens
                    )
                
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=range_obj.start,
                    end_line=range_obj.end,
                    content=chunk_content,
                    total_lines=result.total_lines,
                    token_count=chunk_tokens,
                    is_complete=chunk_tokens == self.counter.count_tokens("\n".join(formatted_lines)),
                    context_type="context" if include_context else "changed"
                ))
                
                total_tokens_used += chunk_tokens
            
            result.total_tokens = total_tokens_used
            result.is_complete = all(c.is_complete for c in result.chunks)
            result.strategy_used = "ranges_with_context" if include_context else "ranges"
            
        except Exception as e:
            result.error = str(e)
            result.strategy_used = "error"
        
        return result
    
    def read_with_changed_lines(
        self,
        file_path: str,
        changed_lines: List[int],
        max_tokens: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> SmartReadResult:
        """
        Read file focusing on changed lines with context.
        
        Args:
            file_path: Path to file
            changed_lines: List of line numbers that were changed
            max_tokens: Maximum tokens to use
            encoding: File encoding
            
        Returns:
            SmartReadResult focused on changes
        """
        if not changed_lines:
            return self.read_full_file(file_path, max_tokens, encoding)
        
        # Convert changed lines to ranges
        ranges = self._lines_to_ranges(changed_lines)
        
        return self.read_line_ranges(
            file_path=file_path,
            ranges=ranges,
            include_context=True,
            max_tokens=max_tokens,
            encoding=encoding
        )
    
    def smart_read(
        self,
        file_path: str,
        changed_lines: Optional[List[int]] = None,
        max_tokens: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> SmartReadResult:
        """
        Intelligently read a file based on size and changes.
        
        Strategy:
        1. If file is small (<2000 tokens), read fully
        2. If changed_lines provided, focus on those with context
        3. Otherwise, read as much as token budget allows
        
        Args:
            file_path: Path to file
            changed_lines: Optional list of changed line numbers
            max_tokens: Maximum tokens to use
            encoding: File encoding
            
        Returns:
            SmartReadResult with appropriate content
        """
        max_tokens = max_tokens or self.max_tokens_per_file
        
        # First, check file size
        try:
            path = Path(file_path)
            if not path.exists():
                return SmartReadResult(
                    file_path=file_path,
                    error=f"File not found: {file_path}",
                    strategy_used="error"
                )
            
            file_size = path.stat().st_size
            estimated_tokens = int(file_size / 3.5)  # Rough estimate
            
            # Small file - read fully
            if estimated_tokens < self.SMALL_FILE_TOKENS:
                return self.read_full_file(file_path, max_tokens, encoding)
            
            # Have changed lines - focus on those
            if changed_lines:
                return self.read_with_changed_lines(
                    file_path, changed_lines, max_tokens, encoding
                )
            
            # Medium file without changes - try to read fully
            if estimated_tokens < self.MEDIUM_FILE_TOKENS:
                return self.read_full_file(file_path, max_tokens, encoding)
            
            # Large file without specific changes - read start with truncation
            return self.read_full_file(file_path, max_tokens, encoding)
            
        except Exception as e:
            return SmartReadResult(
                file_path=file_path,
                error=str(e),
                strategy_used="error"
            )
    
    def _merge_ranges(self, ranges: List[LineRange], total_lines: int) -> List[LineRange]:
        """Merge overlapping ranges and clamp to file bounds."""
        if not ranges:
            return []
        
        # Clamp to file bounds
        clamped = [
            LineRange(
                start=max(1, r.start),
                end=min(total_lines, r.end)
            )
            for r in ranges
        ]
        
        # Sort by start line
        sorted_ranges = sorted(clamped, key=lambda r: r.start)
        
        # Merge overlapping
        merged = [sorted_ranges[0]]
        for current in sorted_ranges[1:]:
            last = merged[-1]
            # Allow merging if ranges are adjacent or overlapping
            if current.start <= last.end + 1:
                merged[-1] = last.merge(current)
            else:
                merged.append(current)
        
        return merged
    
    def _lines_to_ranges(self, lines: List[int]) -> List[LineRange]:
        """Convert a list of line numbers to consolidated ranges."""
        if not lines:
            return []
        
        sorted_lines = sorted(set(lines))
        ranges = []
        start = sorted_lines[0]
        end = sorted_lines[0]
        
        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append(LineRange(start=start, end=end))
                start = line
                end = line
        
        ranges.append(LineRange(start=start, end=end))
        return ranges
    

    # Sandbox Support Methods
    def read_content_with_line_numbers(
        self,
        content: str,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> Tuple[str, int]:
        """
        Format content string with line numbers.
        
        This method works with content that's already been read (e.g., from sandbox).
        
        Args:
            content: Raw file content as string
            file_path: Path to file (for metadata)
            start_line: Starting line (1-indexed)
            end_line: Ending line (1-indexed, None for end of file)
            
        Returns:
            Tuple of (formatted content, total lines in content)
        """
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Adjust indices
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(end_line, total_lines)
        
        # Format with line numbers
        formatted_lines = []
        max_line_num = end_idx
        line_num_width = len(str(max_line_num))
        
        for i in range(start_idx, end_idx):
            line_num = i + 1
            formatted_lines.append(f"{line_num:>{line_num_width}} | {lines[i]}")
        
        return "\n".join(formatted_lines), total_lines
    
    def read_from_content(
        self,
        content: str,
        file_path: str,
        max_tokens: Optional[int] = None,
    ) -> SmartReadResult:
        """
        Create SmartReadResult from content string.
        
        This method is for content that's already been read (e.g., from sandbox).
        
        Args:
            content: Raw file content as string
            file_path: Path to file (for metadata)
            max_tokens: Maximum tokens (uses instance default if None)
            
        Returns:
            SmartReadResult with file content
        """
        max_tokens = max_tokens or self.max_tokens_per_file
        result = SmartReadResult(file_path=file_path)
        
        try:
            formatted_content, total_lines = self.read_content_with_line_numbers(
                content, file_path
            )
            result.total_lines = total_lines
            
            token_count = self.counter.count_tokens(formatted_content)
            result.total_tokens = token_count
            
            if token_count <= max_tokens:
                result.is_complete = True
                result.strategy_used = "full"
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=total_lines,
                    content=formatted_content,
                    total_lines=total_lines,
                    token_count=token_count,
                    is_complete=True,
                    context_type="full"
                ))
            else:
                # Truncate to fit
                truncated, actual_tokens = self.counter.truncate_to_tokens(
                    formatted_content, max_tokens
                )
                result.is_complete = False
                result.strategy_used = "truncated"
                result.total_tokens = actual_tokens
                
                # Estimate how many lines we got
                estimated_lines = int(total_lines * (actual_tokens / token_count))
                
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=estimated_lines,
                    content=truncated,
                    total_lines=total_lines,
                    token_count=actual_tokens,
                    is_complete=False,
                    context_type="truncated"
                ))
            
        except Exception as e:
            result.error = str(e)
            result.strategy_used = "error"
        
        return result
    
    def read_content_with_changed_lines(
        self,
        content: str,
        file_path: str,
        changed_lines: List[int],
        max_tokens: Optional[int] = None,
    ) -> SmartReadResult:
        """
        Read content focusing on changed lines with context.
        
        Args:
            content: Raw file content as string
            file_path: Path to file
            changed_lines: List of line numbers that were changed
            max_tokens: Maximum tokens to use
            
        Returns:
            SmartReadResult focused on changes
        """
        if not changed_lines:
            return self.read_from_content(content, file_path, max_tokens)
        
        max_tokens = max_tokens or self.max_tokens_per_file
        result = SmartReadResult(file_path=file_path)
        
        try:
            lines = content.splitlines()
            result.total_lines = len(lines)
            
            # Convert changed lines to ranges and expand with context
            ranges = self._lines_to_ranges(changed_lines)
            ranges = [r.expand(self.context_lines) for r in ranges]
            
            # Merge overlapping ranges
            ranges = self._merge_ranges(ranges, result.total_lines)
            
            # Calculate line number width for formatting
            max_line = max(r.end for r in ranges) if ranges else 1
            line_num_width = len(str(max_line))
            
            total_tokens_used = 0
            
            for range_obj in ranges:
                if total_tokens_used >= max_tokens:
                    break
                
                # Extract lines for this range
                start_idx = max(0, range_obj.start - 1)
                end_idx = min(range_obj.end, len(lines))
                
                formatted_lines = []
                for i in range(start_idx, end_idx):
                    line_num = i + 1
                    formatted_lines.append(f"{line_num:>{line_num_width}} | {lines[i]}")
                
                chunk_content = "\n".join(formatted_lines)
                chunk_tokens = self.counter.count_tokens(chunk_content)
                
                # Check if we need to truncate
                remaining_tokens = max_tokens - total_tokens_used
                if chunk_tokens > remaining_tokens:
                    chunk_content, chunk_tokens = self.counter.truncate_to_tokens(
                        chunk_content, remaining_tokens
                    )
                
                result.chunks.append(FileChunk(
                    file_path=file_path,
                    start_line=range_obj.start,
                    end_line=range_obj.end,
                    content=chunk_content,
                    total_lines=result.total_lines,
                    token_count=chunk_tokens,
                    is_complete=chunk_tokens == self.counter.count_tokens("\n".join(formatted_lines)),
                    context_type="context"
                ))
                
                total_tokens_used += chunk_tokens
            
            result.total_tokens = total_tokens_used
            result.is_complete = all(c.is_complete for c in result.chunks)
            result.strategy_used = "ranges_with_context"
            
        except Exception as e:
            result.error = str(e)
            result.strategy_used = "error"
        
        return result
    
    def smart_read_content(
        self,
        content: str,
        file_path: str,
        changed_lines: Optional[List[int]] = None,
        max_tokens: Optional[int] = None,
    ) -> SmartReadResult:
        """
        Intelligently read content based on size and changes.
        
        This is the sandbox-compatible version of smart_read().
        
        Strategy:
        1. If content is small (<2000 tokens), read fully
        2. If changed_lines provided, focus on those with context
        3. Otherwise, read as much as token budget allows
        
        Args:
            content: Raw file content as string
            file_path: Path to file
            changed_lines: Optional list of changed line numbers
            max_tokens: Maximum tokens to use
            
        Returns:
            SmartReadResult with appropriate content
        """
        max_tokens = max_tokens or self.max_tokens_per_file
        
        try:
            # Estimate tokens
            estimated_tokens = len(content) // 3  # Rough estimate
            
            # Small content - read fully
            if estimated_tokens < self.SMALL_FILE_TOKENS:
                return self.read_from_content(content, file_path, max_tokens)
            
            # Have changed lines - focus on those
            if changed_lines:
                return self.read_content_with_changed_lines(
                    content, file_path, changed_lines, max_tokens
                )
            
            # Medium content without changes - try to read fully
            if estimated_tokens < self.MEDIUM_FILE_TOKENS:
                return self.read_from_content(content, file_path, max_tokens)
            
            # Large content - read start with truncation
            return self.read_from_content(content, file_path, max_tokens)
            
        except Exception as e:
            return SmartReadResult(
                file_path=file_path,
                error=str(e),
                strategy_used="error"
            )


def parse_diff_for_changed_lines(diff_content: str) -> Dict[str, List[int]]:
    """
    Parse a unified diff to extract changed line numbers per file.
    
    Args:
        diff_content: Unified diff string
        
    Returns:
        Dictionary mapping file paths to lists of changed line numbers
    """
    changed_lines: Dict[str, List[int]] = {}
    current_file: Optional[str] = None
    current_line: int = 0
    
    for line in diff_content.splitlines():
        # New file
        if line.startswith("+++ b/"):
            current_file = line[6:]
            changed_lines[current_file] = []
        elif line.startswith("+++ "):
            current_file = line[4:]
            changed_lines[current_file] = []
        
        # Hunk header
        elif line.startswith("@@"):
            # Parse @@ -old_start,old_count +new_start,new_count @@
            try:
                parts = line.split()
                new_range = parts[2]  # +new_start,new_count
                if "," in new_range:
                    current_line = int(new_range.split(",")[0][1:])
                else:
                    current_line = int(new_range[1:])
            except (IndexError, ValueError):
                pass
        
        # Added or modified line
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file:
                changed_lines[current_file].append(current_line)
            current_line += 1
        
        # Context line
        elif line.startswith(" "):
            current_line += 1
        
        # Removed line (don't increment line counter for new file)
        elif line.startswith("-") and not line.startswith("---"):
            pass
    
    return changed_lines


# Convenience functions
def smart_read_file(
    file_path: str,
    changed_lines: Optional[List[int]] = None,
    max_tokens: int = 8000,
    model: str = "gpt-4o"
) -> SmartReadResult:
    """
    Convenience function for smart file reading.
    
    Args:
        file_path: Path to file
        changed_lines: Optional list of changed line numbers
        max_tokens: Maximum tokens to use
        model: Model for token counting
        
    Returns:
        SmartReadResult
    """
    reader = SmartFileReader(model=model, max_tokens_per_file=max_tokens)
    return reader.smart_read(file_path, changed_lines)


def read_files_for_review(
    files: List[Dict[str, Any]],
    max_total_tokens: int = 50000,
    model: str = "gpt-4o"
) -> List[SmartReadResult]:
    """
    Read multiple files for code review with token budget distribution.
    
    Args:
        files: List of file info dicts with 'path' and optional 'changed_lines'
        max_total_tokens: Total token budget for all files
        model: Model for token counting
        
    Returns:
        List of SmartReadResult objects
    """
    if not files:
        return []
    
    # Distribute tokens evenly with minimum per file
    min_tokens_per_file = 1000
    tokens_per_file = max(min_tokens_per_file, max_total_tokens // len(files))
    
    reader = SmartFileReader(model=model, max_tokens_per_file=tokens_per_file)
    results = []
    
    for file_info in files:
        file_path = file_info.get("path") or file_info.get("file_path")
        changed_lines = file_info.get("changed_lines")
        
        if file_path:
            result = reader.smart_read(file_path, changed_lines)
            results.append(result)
    
    return results


# Sandbox-Compatible Convenience Functions
def smart_read_content(
    content: str,
    file_path: str,
    changed_lines: Optional[List[int]] = None,
    max_tokens: int = 8000,
    model: str = "gpt-4o"
) -> SmartReadResult:
    """
    Convenience function for smart reading from content string (sandbox-compatible).
    
    Args:
        content: Raw file content as string
        file_path: Path to file (for metadata)
        changed_lines: Optional list of changed line numbers
        max_tokens: Maximum tokens to use
        model: Model for token counting
        
    Returns:
        SmartReadResult
    """
    reader = SmartFileReader(model=model, max_tokens_per_file=max_tokens)
    return reader.smart_read_content(content, file_path, changed_lines)


def read_content_for_review(
    files_with_content: List[Dict[str, Any]],
    max_total_tokens: int = 50000,
    model: str = "gpt-4o"
) -> List[SmartReadResult]:
    """
    Read multiple files from content for code review (sandbox-compatible).
    
    Args:
        files_with_content: List of dicts with 'path', 'content', and optional 'changed_lines'
        max_total_tokens: Total token budget for all files
        model: Model for token counting
        
    Returns:
        List of SmartReadResult objects
    """
    if not files_with_content:
        return []
    
    # Distribute tokens evenly with minimum per file
    min_tokens_per_file = 1000
    tokens_per_file = max(min_tokens_per_file, max_total_tokens // len(files_with_content))
    
    reader = SmartFileReader(model=model, max_tokens_per_file=tokens_per_file)
    results = []
    
    for file_info in files_with_content:
        file_path = file_info.get("path") or file_info.get("file_path")
        content = file_info.get("content")
        changed_lines = file_info.get("changed_lines")
        
        if file_path and content is not None:
            result = reader.smart_read_content(content, file_path, changed_lines)
            results.append(result)
        elif file_path:
            # No content provided, try to read from filesystem
            result = reader.smart_read(file_path, changed_lines)
            results.append(result)
    
    return results


async def read_files_from_sandbox(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_paths: List[str],
    changed_lines_map: Optional[Dict[str, List[int]]] = None,
    max_total_tokens: int = 50000,
    model: str = "gpt-4o"
) -> List[SmartReadResult]:
    """
    Read multiple files from E2B sandbox for code review.
    
    This is the primary function for sandbox-based file reading.
    
    Args:
        sandbox_manager: The SandboxManager instance
        session_id: Current session ID
        file_paths: List of file paths inside sandbox
        changed_lines_map: Optional dict mapping file paths to changed line numbers
        max_total_tokens: Total token budget for all files
        model: Model for token counting
        
    Returns:
        List of SmartReadResult objects
    """
    if not file_paths:
        return []
    
    # Distribute tokens evenly with minimum per file
    min_tokens_per_file = 1000
    tokens_per_file = max(min_tokens_per_file, max_total_tokens // len(file_paths))
    
    reader = SmartFileReader(model=model, max_tokens_per_file=tokens_per_file)
    results = []
    changed_lines_map = changed_lines_map or {}
    
    for file_path in file_paths:
        try:
            # Read content from sandbox
            content = await sandbox_manager.read_file(session_id, file_path)
            changed_lines = changed_lines_map.get(file_path)
            
            result = reader.smart_read_content(content, file_path, changed_lines)
            results.append(result)
            
        except Exception as e:
            # Create error result for this file
            results.append(SmartReadResult(
                file_path=file_path,
                error=f"Failed to read from sandbox: {str(e)}",
                strategy_used="error"
            ))
    
    return results
