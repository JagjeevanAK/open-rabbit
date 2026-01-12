"""
Token Utilities for Code Review
Provides token counting, budget management, and text truncation utilities.
"""

from typing import Optional, List, Tuple, Dict, Any
import tiktoken


# Default encoding for various models
# Note: tiktoken only supports OpenAI encodings, Claude models use cl100k as approximation
MODEL_ENCODINGS = {
    # OpenAI GPT-5+ models
    "gpt-5": "o200k_base",
    # OpenAI Codex models
    "gpt-5.1-codex": "o200k_base",
    "gpt-5.1-codex-max": "o200k_base",
    # OpenAI reasoning models (o-series)
    "o4-mini": "o200k_base",
    # Anthropic Claude 4 models
    "claude-4-opus": "cl100k_base",
    "claude-4-sonnet": "cl100k_base",
    "claude-4-haiku": "cl100k_base",
    "claude-4.5-opus": "cl100k_base",
    "claude-4.5-sonnet": "cl100k_base",
    "claude-4.5-haiku": "cl100k_base",
    # Default
    "default": "o200k_base",
}

# Token limits (context window) for various models
MODEL_TOKEN_LIMITS = {
    # OpenAI GPT-5+ models
    "gpt-5": 400000,
    # OpenAI Codex models
    "gpt-5.1-codex": 400000,
    "gpt-5.1-codex-max": 272000,
    # OpenAI reasoning models (o-series)
    "o4-mini": 200000,
    # Anthropic Claude 4 models
    "claude-4-opus": 200000,
    "claude-4-sonnet": 200000,  # Can go up to 1M in beta
    "claude-4-haiku": 200000,
    "claude-4.5-opus": 200000,
    "claude-4.5-sonnet": 200000,
    "claude-4.5-haiku": 200000,
    # Default
    "default": 128000,
}


class TokenCounter:
    """Token counter using tiktoken for accurate token counting."""
    
    def __init__(self, model: str = "gpt-5"):
        """
        Initialize token counter for a specific model.
        
        Args:
            model: Model name to use for encoding selection
        """
        self.model = model
        self._encoding_name = MODEL_ENCODINGS.get(model, MODEL_ENCODINGS["default"])
        self._encoding = tiktoken.get_encoding(self._encoding_name)
        self._token_limit = MODEL_TOKEN_LIMITS.get(model, MODEL_TOKEN_LIMITS["default"])
    
    @property
    def token_limit(self) -> int:
        """Get the token limit for the current model."""
        return self._token_limit
    
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self._encoding.encode(text))
    
    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        Count tokens for multiple texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of token counts
        """
        return [self.count_tokens(text) for text in texts]
    
    def truncate_to_tokens(
        self, 
        text: str, 
        max_tokens: int,
        truncation_marker: str = "\n... [truncated]"
    ) -> Tuple[str, int]:
        """
        Truncate text to fit within a token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens
            truncation_marker: Marker to add when truncation occurs
            
        Returns:
            Tuple of (truncated text, actual token count)
        """
        tokens = self._encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text, len(tokens)
        
        # Reserve tokens for the truncation marker
        marker_tokens = len(self._encoding.encode(truncation_marker))
        available_tokens = max_tokens - marker_tokens
        
        if available_tokens <= 0:
            return "", 0
        
        truncated_tokens = tokens[:available_tokens]
        truncated_text = self._encoding.decode(truncated_tokens) + truncation_marker
        
        return truncated_text, self.count_tokens(truncated_text)
    
    def truncate_from_middle(
        self,
        text: str,
        max_tokens: int,
        keep_start_ratio: float = 0.3,
        separator: str = "\n\n... [content truncated] ...\n\n"
    ) -> Tuple[str, int]:
        """
        Truncate text from the middle, keeping start and end.
        Useful for preserving function signatures and return statements.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens
            keep_start_ratio: Ratio of tokens to keep from the start (0.0-1.0)
            separator: Separator to insert in the middle
            
        Returns:
            Tuple of (truncated text, actual token count)
        """
        tokens = self._encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text, len(tokens)
        
        separator_tokens = len(self._encoding.encode(separator))
        available_tokens = max_tokens - separator_tokens
        
        if available_tokens <= 0:
            return separator, separator_tokens
        
        start_tokens = int(available_tokens * keep_start_ratio)
        end_tokens = available_tokens - start_tokens
        
        start_text = self._encoding.decode(tokens[:start_tokens])
        end_text = self._encoding.decode(tokens[-end_tokens:]) if end_tokens > 0 else ""
        
        truncated_text = start_text + separator + end_text
        return truncated_text, self.count_tokens(truncated_text)
    
    def fits_in_budget(self, text: str, budget: int) -> bool:
        """
        Check if text fits within a token budget.
        
        Args:
            text: Text to check
            budget: Token budget
            
        Returns:
            True if text fits within budget
        """
        return self.count_tokens(text) <= budget
    
    def estimate_tokens_from_chars(self, char_count: int) -> int:
        """
        Estimate token count from character count.
        Rough estimate: ~4 characters per token for English text.
        Code tends to be ~3.5 characters per token.
        
        Args:
            char_count: Number of characters
            
        Returns:
            Estimated token count
        """
        return int(char_count / 3.5)
    
    def estimate_chars_from_tokens(self, token_count: int) -> int:
        """
        Estimate character count from token count.
        
        Args:
            token_count: Number of tokens
            
        Returns:
            Estimated character count
        """
        return int(token_count * 3.5)


class TokenBudget:
    """
    Token budget manager for distributing tokens across multiple sections.
    Useful for allocating tokens to different parts of a prompt.
    """
    
    def __init__(self, total_budget: int, model: str = "gpt-5"):
        """
        Initialize token budget manager.
        
        Args:
            total_budget: Total token budget to manage
            model: Model name for token counting
        """
        self.total_budget = total_budget
        self.counter = TokenCounter(model)
        self._allocations: Dict[str, int] = {}
        self._used: Dict[str, int] = {}
    
    def allocate(self, section: str, tokens: int) -> None:
        """
        Allocate tokens to a section.
        
        Args:
            section: Section name
            tokens: Number of tokens to allocate
        """
        self._allocations[section] = tokens
        self._used[section] = 0
    
    def allocate_percentage(self, section: str, percentage: float) -> None:
        """
        Allocate a percentage of total budget to a section.
        
        Args:
            section: Section name
            percentage: Percentage of total budget (0.0-1.0)
        """
        tokens = int(self.total_budget * percentage)
        self.allocate(section, tokens)
    
    def use(self, section: str, text: str) -> Tuple[str, int]:
        """
        Use tokens from a section's allocation.
        Returns truncated text if it exceeds allocation.
        
        Args:
            section: Section name
            text: Text to use tokens for
            
        Returns:
            Tuple of (possibly truncated text, tokens used)
        """
        if section not in self._allocations:
            raise ValueError(f"Section '{section}' has no allocation")
        
        allocation = self._allocations[section]
        remaining = allocation - self._used[section]
        
        tokens = self.counter.count_tokens(text)
        
        if tokens <= remaining:
            self._used[section] += tokens
            return text, tokens
        
        # Truncate to fit
        truncated, actual_tokens = self.counter.truncate_to_tokens(text, remaining)
        self._used[section] += actual_tokens
        return truncated, actual_tokens
    
    def get_remaining(self, section: str) -> int:
        """Get remaining tokens for a section."""
        if section not in self._allocations:
            return 0
        return self._allocations[section] - self._used.get(section, 0)
    
    def get_total_remaining(self) -> int:
        """Get total remaining tokens across all sections."""
        total_allocated = sum(self._allocations.values())
        total_used = sum(self._used.values())
        return self.total_budget - total_used
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of budget usage."""
        return {
            "total_budget": self.total_budget,
            "total_allocated": sum(self._allocations.values()),
            "total_used": sum(self._used.values()),
            "sections": {
                section: {
                    "allocated": self._allocations[section],
                    "used": self._used.get(section, 0),
                    "remaining": self.get_remaining(section),
                }
                for section in self._allocations
            }
        }


# Convenience functions
_default_counter: Optional[TokenCounter] = None


def get_default_counter() -> TokenCounter:
    """Get or create the default token counter."""
    global _default_counter
    if _default_counter is None:
        _default_counter = TokenCounter()
    return _default_counter


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """
    Count tokens in text.
    
    Args:
        text: Text to count tokens for
        model: Optional model name (uses default if not specified)
        
    Returns:
        Number of tokens
    """
    if model:
        counter = TokenCounter(model)
        return counter.count_tokens(text)
    return get_default_counter().count_tokens(text)


def truncate_text(
    text: str, 
    max_tokens: int,
    model: Optional[str] = None
) -> str:
    """
    Truncate text to fit within token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum tokens
        model: Optional model name
        
    Returns:
        Truncated text
    """
    if model:
        counter = TokenCounter(model)
    else:
        counter = get_default_counter()
    
    truncated, _ = counter.truncate_to_tokens(text, max_tokens)
    return truncated


def estimate_file_tokens(file_path: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Estimate token count for a file without reading entire contents.
    
    Args:
        file_path: Path to the file
        model: Optional model name
        
    Returns:
        Dictionary with size info and token estimates
    """
    from pathlib import Path
    
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    file_size = path.stat().st_size
    
    # For small files, count exactly
    if file_size < 100_000:  # ~100KB
        try:
            content = path.read_text(encoding="utf-8")
            if model:
                counter = TokenCounter(model)
            else:
                counter = get_default_counter()
            
            actual_tokens = counter.count_tokens(content)
            return {
                "file_path": str(file_path),
                "file_size_bytes": file_size,
                "line_count": content.count("\n") + 1,
                "char_count": len(content),
                "token_count": actual_tokens,
                "is_estimate": False,
            }
        except UnicodeDecodeError:
            return {
                "file_path": str(file_path),
                "file_size_bytes": file_size,
                "error": "Binary file, cannot count tokens",
            }
    
    # For large files, estimate
    estimated_tokens = int(file_size / 3.5)
    return {
        "file_path": str(file_path),
        "file_size_bytes": file_size,
        "estimated_tokens": estimated_tokens,
        "is_estimate": True,
        "note": "Large file, token count is estimated",
    }
