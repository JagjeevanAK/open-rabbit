"""
CodeRabbit-like Recursive Code Review Agent

This agent implements a comprehensive, recursive code review workflow similar to CodeRabbit:
1. Reads code files one by one
2. Generates parser reports (AST, CFG, PDG, Semantic)
3. Analyzes code + parser reports recursively
4. Checks knowledge base for past learnings
5. Comments on PR only after validation

The agent loops through files until full analysis is complete.
"""

from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict, Literal, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
import json

# Import all tools
from agent.tools.knowledgeBase import (
    search_knowledge_base,
    get_pr_learnings,
    format_review_context
)
from agent.tools.Parsers import (
    parse_code_file,
    analyze_changed_files,
    get_parser_capabilities
)
from agent.tools.parserReports import (
    read_parser_reports,
    get_parser_report_summary,
    check_specific_issue_in_reports
)
from agent.tools.git import (
    git_get_pr_files,
    git_get_pr_diff,
    git_get_file_content,
    git_add_tool,
    git_commit_tool,
    git_branch_tool,
    git_push_tool
)
from agent.tools.fileSearch import (
    file_reader_tool,
    list_files_tool,
    search_in_file_tool,
    find_test_framework_tool
)
from agent.tools.fileUpdates import (
    file_writer_tool
)
from agent.tools.gitClone import (
    git_clone_tool,
    get_repo_structure
)

load_dotenv()


class CodeRabbitAgentState(TypedDict):
    """Enhanced state for CodeRabbit-like analysis"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # PR Context
    pr_context: Dict[str, Any]  # repo, branch, files, etc
    
    # Knowledge Base
    knowledge_context: Dict[str, Any]  # Past learnings
    
    # File Analysis State
    files_to_analyze: List[str]  # Queue of files
    current_file: Optional[str]  # File being analyzed
    file_analysis: Dict[str, Any]  # Per-file analysis results
    
    # Parser Results
    parser_reports: Dict[str, Any]  # Parser reports per file
    
    # Issues Found
    issues_found: List[Dict[str, Any]]  # All issues discovered
    validated_issues: List[Dict[str, Any]]  # Issues after KB check
    
    # Review Output
    comments_to_post: List[Dict[str, Any]]  # Final comments
    
    # Workflow Control
    current_stage: str  # Current stage of workflow
    iteration_count: int  # Number of recursive iterations
    max_iterations: int  # Maximum iterations per file


# Define all tools
tools = [
    search_knowledge_base,
    get_pr_learnings,
    format_review_context,
    parse_code_file,
    analyze_changed_files,
    get_parser_capabilities,
    read_parser_reports,
    get_parser_report_summary,
    check_specific_issue_in_reports,
    git_get_pr_files,
    git_get_pr_diff,
    git_get_file_content,
    git_add_tool,
    git_commit_tool,
    git_branch_tool,
    git_push_tool,
    file_reader_tool,
    list_files_tool,
    search_in_file_tool,
    find_test_framework_tool,
    file_writer_tool,
    git_clone_tool,
    get_repo_structure
]

llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)


def initialize_analysis_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 1: Initialize Analysis
    - Clone repository
    - Get list of changed files
    - Load knowledge base context
    """
    messages = state["messages"]
    
    init_prompt = SystemMessage(
        content="""You are initializing a CodeRabbit-style code review analysis.

**Your tasks:**

1. **Extract PR Information**:
   - Repository URL
   - Branch name
   - List of changed files

2. **Clone Repository**:
   - Use git_clone_tool to clone the repo
   - Get repository structure using get_repo_structure

3. **Load Knowledge Base Context**:
   - Use get_pr_learnings to fetch past review patterns
   - Use search_knowledge_base to find relevant learnings
   - This will help avoid commenting on issues maintainers have previously accepted

4. **Prepare File Queue**:
   - Create a list of files to analyze
   - Prioritize critical files (main logic, not tests/configs)

Call the necessary tools to set up the analysis environment."""
    )
    
    response = llm_with_tools.invoke([init_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "initialize",
        "iteration_count": 0,
        "max_iterations": 10
    }


def generate_parser_reports_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 2: Generate Parser Reports
    - Trigger parser analysis for current file
    - Wait for AST, CFG, PDG, Semantic reports
    """
    messages = state["messages"]
    current_file = state.get("current_file")
    
    if not current_file:
        # No current file, move to next
        return {
            "messages": messages,
            "current_stage": "file_analysis"
        }
    
    parser_prompt = SystemMessage(
        content=f"""You are generating parser reports for: {current_file}

**Your tasks:**

1. **Trigger Parser Analysis**:
   - Use parse_code_file tool on {current_file}
   - This generates AST, CFG, PDG, and Semantic Graph reports
   - Reports will be saved to Parsers/output directory

2. **Wait for Completion**:
   - The tool will wait for analysis to complete
   - Confirm reports are generated successfully

Once reports are ready, we'll proceed to read and analyze them."""
    )
    
    response = llm_with_tools.invoke([parser_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "generate_reports"
    }


def recursive_file_analysis_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 3: Recursive File Analysis
    - Read current file
    - Read parser reports
    - Analyze recursively: code <-> reports
    - Find issues
    """
    messages = state["messages"]
    current_file = state.get("current_file")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 10)
    
    analysis_prompt = SystemMessage(
        content=f"""You are performing RECURSIVE ANALYSIS on: {current_file}
**Iteration: {iteration_count + 1}/{max_iterations}**

This is the core CodeRabbit-style analysis. Analyze back-and-forth between code and reports.

**Your analysis workflow:**

1. **Read the Code**:
   - Use file_reader_tool to read {current_file}
   - Understand the code structure

2. **Read Parser Reports**:
   - Use read_parser_reports to get AST, CFG, PDG, Semantic reports
   - Use get_parser_report_summary for quick overview

3. **Cross-Reference Analysis**:
   - Compare code with parser findings
   - Look for issues in code
   - Check if parser reports confirm these issues
   - Use check_specific_issue_in_reports to validate

4. **Identify Issues**:
   - Code quality problems
   - Potential bugs
   - Security vulnerabilities
   - Performance issues
   - Style violations
   - Complexity problems (from CFG)
   - Unreachable code (from CFG)
   - Complex dependencies (from PDG)
   - Missing documentation (from Semantic)

5. **Recursive Refinement**:
   - If you find new issues, dig deeper
   - Cross-check with parser reports
   - Look for related issues
   - Continue until confident

**After analysis, list all issues found with:**
- Issue type
- Line number
- Severity (high/medium/low)
- Description
- Supporting evidence from parser reports

Think step-by-step. Be thorough."""
    )
    
    response = llm_with_tools.invoke([analysis_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "file_analysis",
        "iteration_count": iteration_count + 1
    }


def validate_with_knowledge_base_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 4: Validate Issues with Knowledge Base
    - Check each issue against knowledge base
    - Filter out issues maintainers have previously accepted
    - Only keep valid issues
    """
    messages = state["messages"]
    issues_found = state.get("issues_found", [])
    
    validation_prompt = SystemMessage(
        content=f"""You are VALIDATING ISSUES against the knowledge base.

**Issues found:** {len(issues_found)}

**Your validation tasks:**

1. **Check Knowledge Base**:
   - Use search_knowledge_base for each issue type
   - Use get_pr_learnings for past patterns
   - Look for cases where maintainers accepted similar code

2. **Filter Issues**:
   - **SKIP** issues if:
     * Knowledge base shows maintainer previously accepted it
     * It's a style preference the team doesn't follow
     * Past PRs show this pattern is intentional
   - **KEEP** issues if:
     * It's a genuine bug or security issue
     * No past acceptance found
     * It's a new type of issue

3. **Categorize Valid Issues**:
   - critical: Must fix (bugs, security)
   - important: Should fix (quality, performance)
   - minor: Consider fixing (style, docs)

**Output: List of validated issues ready for commenting.**

Be conservative - when in doubt, check knowledge base again.
Don't comment on issues maintainers explicitly accepted before."""
    )
    
    response = llm_with_tools.invoke([validation_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "validation"
    }


def prepare_comments_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 5: Prepare PR Comments
    - Format validated issues as PR comments
    - Include code suggestions
    - Reference parser reports as evidence
    """
    messages = state["messages"]
    validated_issues = state.get("validated_issues", [])
    
    comment_prompt = SystemMessage(
        content=f"""You are preparing PR COMMENTS for validated issues.

**Validated issues:** {len(validated_issues)}

**Your tasks:**

1. **Format Each Issue as Comment**:
   ```json
   {{
     "path": "file/path.py",
     "line": 42,
     "body": "Issue description with suggestion",
     "severity": "high/medium/low"
   }}
   ```

2. **Include in Comments**:
   - Clear description of the issue
   - Why it's a problem
   - Suggested fix (code example if possible)
   - Reference to parser report evidence
   - Links to docs/best practices if relevant

3. **Be Helpful, Not Pushy**:
   - Use constructive language
   - Explain the reasoning
   - Offer alternatives when applicable
   - Respect the maintainer's choices

4. **Group Related Issues**:
   - If multiple issues in same area, combine them
   - Provide context for the overall problem

**Output: Structured list of PR comments ready to post.**"""
    )
    
    response = llm.invoke([comment_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "prepare_comments"
    }


def move_to_next_file_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 6: Move to Next File
    - Pop next file from queue
    - Reset iteration counter
    - Continue analysis
    """
    messages = state["messages"]
    files_to_analyze = state.get("files_to_analyze", [])
    
    if not files_to_analyze:
        # No more files, finish
        return {
            "messages": messages,
            "current_stage": "complete",
            "current_file": None
        }
    
    # Get next file
    next_file = files_to_analyze[0]
    remaining_files = files_to_analyze[1:]
    
    next_file_prompt = SystemMessage(
        content=f"""Moving to next file: {next_file}

**Remaining files:** {len(remaining_files)}

Starting fresh analysis for this file. Reset iteration counter."""
    )
    
    return {
        "messages": messages + [next_file_prompt],
        "current_stage": "generate_reports",
        "current_file": next_file,
        "files_to_analyze": remaining_files,
        "iteration_count": 0
    }


def finalize_review_node(state: CodeRabbitAgentState) -> CodeRabbitAgentState:
    """
    Stage 7: Finalize Review
    - Compile all comments
    - Generate summary
    - Prepare final output
    """
    messages = state["messages"]
    comments_to_post = state.get("comments_to_post", [])
    
    finalize_prompt = SystemMessage(
        content=f"""You are FINALIZING the code review.

**Total comments prepared:** {len(comments_to_post)}

**Your final tasks:**

1. **Generate Review Summary**:
   - Overall code quality assessment
   - Key issues found
   - Statistics (files analyzed, issues by severity)

2. **Format Final Output**:
   ```json
   {{
     "summary": "Review summary here",
     "statistics": {{
       "files_analyzed": N,
       "total_issues": N,
       "critical": N,
       "important": N,
       "minor": N
     }},
     "comments": [...]
   }}
   ```

3. **Quality Check**:
   - Ensure all comments are helpful
   - Verify line numbers are correct
   - Check that evidence is included

**Output: Final formatted review ready for PR posting.**"""
    )
    
    response = llm.invoke([finalize_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "complete"
    }


# Routing functions

def route_after_initialize(state: CodeRabbitAgentState) -> Literal["tools", "generate_reports"]:
    """Route after initialization"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Check if we have files to analyze
    files_to_analyze = state.get("files_to_analyze", [])
    if files_to_analyze:
        return "generate_reports"
    
    return "tools"


def route_after_generate_reports(state: CodeRabbitAgentState) -> Literal["tools", "file_analysis"]:
    """Route after report generation"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "file_analysis"


def route_after_file_analysis(state: CodeRabbitAgentState) -> Literal["tools", "file_analysis", "validation"]:
    """Route after file analysis - may loop or proceed"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 10)
    
    # Check if analysis is complete or need more iterations
    # This is a simple heuristic - in production, use more sophisticated logic
    if iteration_count >= max_iterations:
        return "validation"
    
    # Check if analysis found issues - if yes, proceed to validation
    # Otherwise, continue analysis
    content = str(last_message.content).lower()
    if "issue" in content or "found" in content or "problem" in content:
        return "validation"
    
    return "file_analysis"


def route_after_validation(state: CodeRabbitAgentState) -> Literal["tools", "prepare_comments"]:
    """Route after validation"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "prepare_comments"


def route_after_prepare_comments(state: CodeRabbitAgentState) -> Literal["next_file", "finalize"]:
    """Route after preparing comments"""
    files_to_analyze = state.get("files_to_analyze", [])
    
    if files_to_analyze:
        return "next_file"
    return "finalize"


def route_after_tools(state: CodeRabbitAgentState) -> str:
    """Route after tool execution"""
    current_stage = state.get("current_stage", "initialize")
    
    stage_map = {
        "initialize": "initialize",
        "generate_reports": "generate_reports",
        "file_analysis": "file_analysis",
        "validation": "validation",
        "prepare_comments": "prepare_comments"
    }
    
    return stage_map.get(current_stage, "initialize")


# Build the graph

coderabbit_graph = StateGraph(CodeRabbitAgentState)

# Add nodes
coderabbit_graph.add_node("initialize", initialize_analysis_node)
coderabbit_graph.add_node("generate_reports", generate_parser_reports_node)
coderabbit_graph.add_node("file_analysis", recursive_file_analysis_node)
coderabbit_graph.add_node("validation", validate_with_knowledge_base_node)
coderabbit_graph.add_node("prepare_comments", prepare_comments_node)
coderabbit_graph.add_node("next_file", move_to_next_file_node)
coderabbit_graph.add_node("finalize", finalize_review_node)
coderabbit_graph.add_node("tools", tool_node)

# Set entry point
coderabbit_graph.set_entry_point("initialize")

# Add conditional edges
coderabbit_graph.add_conditional_edges(
    "initialize",
    route_after_initialize,
    {
        "tools": "tools",
        "generate_reports": "generate_reports"
    }
)

coderabbit_graph.add_conditional_edges(
    "generate_reports",
    route_after_generate_reports,
    {
        "tools": "tools",
        "file_analysis": "file_analysis"
    }
)

coderabbit_graph.add_conditional_edges(
    "file_analysis",
    route_after_file_analysis,
    {
        "tools": "tools",
        "file_analysis": "file_analysis",  # Loop for recursive analysis
        "validation": "validation"
    }
)

coderabbit_graph.add_conditional_edges(
    "validation",
    route_after_validation,
    {
        "tools": "tools",
        "prepare_comments": "prepare_comments"
    }
)

coderabbit_graph.add_conditional_edges(
    "prepare_comments",
    route_after_prepare_comments,
    {
        "next_file": "next_file",
        "finalize": "finalize"
    }
)

coderabbit_graph.add_edge("next_file", "generate_reports")
coderabbit_graph.add_edge("finalize", END)

coderabbit_graph.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "initialize": "initialize",
        "generate_reports": "generate_reports",
        "file_analysis": "file_analysis",
        "validation": "validation",
        "prepare_comments": "prepare_comments"
    }
)

# Compile the graph
coderabbit_app = coderabbit_graph.compile()


# Export for use
__all__ = ['coderabbit_app', 'CodeRabbitAgentState']

