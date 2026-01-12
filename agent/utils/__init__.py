"""
Agent Utilities Module

Utility functions and classes for the agent system.
"""

from .diff_parser import (
    parse_diff_hunks,
    parse_unified_diff,
    get_pr_diff,
    get_diff_text_per_file,
)

from .token_utils import (
    TokenCounter,
    TokenBudget,
    count_tokens,
    truncate_to_token_limit,
    estimate_tokens,
    MODEL_ENCODINGS,
    MODEL_TOKEN_LIMITS,
)

from .smart_file_reader import (
    SmartFileReader,
    SmartReadResult,
    FileChunk,
    LineRange,
    smart_read_content,
    read_content_for_review,
    read_files_from_sandbox,
)

from .sandbox_file import (
    sandbox_read_file,
    sandbox_read_file_raw,
    sandbox_read_file_with_line_numbers,
    sandbox_list_files,
    sandbox_list_files_raw,
    sandbox_write_file,
    sandbox_file_exists,
    sandbox_get_file_info,
    sandbox_find_test_framework,
    SandboxFileOperations,
)

__all__ = [
    # Diff parser
    "parse_diff_hunks",
    "parse_unified_diff",
    "get_pr_diff",
    "get_diff_text_per_file",
    # Token utils
    "TokenCounter",
    "TokenBudget",
    "count_tokens",
    "truncate_to_token_limit",
    "estimate_tokens",
    "MODEL_ENCODINGS",
    "MODEL_TOKEN_LIMITS",
    # Smart file reader
    "SmartFileReader",
    "SmartReadResult",
    "FileChunk",
    "LineRange",
    "smart_read_content",
    "read_content_for_review",
    "read_files_from_sandbox",
    # Sandbox file operations
    "sandbox_read_file",
    "sandbox_read_file_raw",
    "sandbox_read_file_with_line_numbers",
    "sandbox_list_files",
    "sandbox_list_files_raw",
    "sandbox_write_file",
    "sandbox_file_exists",
    "sandbox_get_file_info",
    "sandbox_find_test_framework",
    "SandboxFileOperations",
]
