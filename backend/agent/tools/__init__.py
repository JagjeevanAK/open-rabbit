"""
Agent Tools Module

LangChain tools for file operations, git, and parser reports.
"""

from .file import (
    file_reader_tool,
    file_writer_tool,
    file_delete_tool,
    list_files_tool,
    find_test_framework_tool
)

from .git import (
    git_add_tool,
    git_commit_tool,
    git_branch_tool,
    git_status_tool,
    git_log_tool,
    git_push_tool,
    git_diff_tool,
    git_current_branch_tool,
    git_list_branches_tool
)

from .gitClone import git_clone_tool

from .parserReports import (
    read_parser_reports,
    get_parser_report_summary,
    check_specific_issue_in_reports,
    ParserReportsReader
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

from .smart_file_reader import (
    SmartFileReader,
    SmartReadResult,
    smart_read_content,
    read_content_for_review,
    read_files_from_sandbox,
)

from .diff_parser import (
    parse_diff_hunks,
    parse_unified_diff,
    get_pr_diff,
    get_diff_text_per_file,
)

__all__ = [
    # File tools
    "file_reader_tool",
    "file_writer_tool",
    "file_delete_tool",
    "list_files_tool",
    "find_test_framework_tool",
    # Git tools
    "git_add_tool",
    "git_commit_tool",
    "git_branch_tool",
    "git_status_tool",
    "git_log_tool",
    "git_push_tool",
    "git_diff_tool",
    "git_current_branch_tool",
    "git_list_branches_tool",
    "git_clone_tool",
    # Parser tools
    "read_parser_reports",
    "get_parser_report_summary",
    "check_specific_issue_in_reports",
    "ParserReportsReader",
    # Sandbox file tools
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
    # Smart file reader
    "SmartFileReader",
    "SmartReadResult",
    "smart_read_content",
    "read_content_for_review",
    "read_files_from_sandbox",
    # Diff parser
    "parse_diff_hunks",
    "parse_unified_diff",
    "get_pr_diff",
    "get_diff_text_per_file",
]
