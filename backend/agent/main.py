from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
import json

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
from systemPrompt import systemPrompt
from messageTypePrompt import systemPrompt as messageTypeSystemPrompt
from unit_testPrompt import systemPrompt as unitTestSystemPrompt

load_dotenv()


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    pr_context: dict
    knowledge_context: dict
    parser_results: dict
    review_output: dict
    unit_tests: dict
    current_stage: str
    generate_tests: bool


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


def context_enrichment_node(state: AgentState) -> AgentState:
    """
    Stage 1: Context Enrichment
    Gathers information from Knowledge Base and clones/reads repository files
    """
    messages = state["messages"]
    
    enrichment_prompt = SystemMessage(
        content="""You are in the CONTEXT ENRICHMENT stage of code review.
        
Your tasks:
1. Extract PR information (repo URL, branch, files changed)
2. Clone the repository if needed using git_clone_tool
3. Use get_pr_learnings to fetch relevant historical context
4. Use search_knowledge_base to find topic-specific learnings
5. Read the changed files using file_reader_tool

Gather comprehensive context before analysis. Call the necessary tools."""
    )
    
    response = llm_with_tools.invoke([enrichment_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "context_enrichment"
    }


def static_analysis_node(state: AgentState) -> AgentState:
    """
    Stage 2: Static Analysis
    Triggers Parsers agent for AST, CFG, PDG, Semantic analysis
    """
    messages = state["messages"]
    
    analysis_prompt = SystemMessage(
        content="""You are in the STATIC ANALYSIS stage of code review.

Your tasks:
1. Use analyze_changed_files to trigger batch analysis of all changed files (generates reports)
2. Use parse_code_file for detailed analysis of critical files
3. Use read_parser_reports to read AST, CFG, PDG, and Semantic reports from Parsers/output
4. Use get_parser_report_summary for quick overview of analysis results
5. Use check_specific_issue_in_reports to validate specific issues against parser findings
6. Identify code quality issues, potential bugs, and architectural concerns

The new parser reports tools allow you to:
- Read reports directly from output directory
- Cross-reference code with parser findings
- Validate issues recursively

Perform comprehensive static analysis on the codebase."""
    )
    
    response = llm_with_tools.invoke([analysis_prompt] + messages)
    
    return {
        "messages": [response],
        "current_stage": "static_analysis"
    }


def code_review_node(state: AgentState) -> AgentState:
    """
    Stage 3: Code Review Generation
    Synthesizes all context to generate comprehensive review comments
    """
    messages = state["messages"]
    
    review_prompt = [
        systemPrompt,
        SystemMessage(
            content="""You are in the CODE REVIEW GENERATION stage.

You now have:
1. Knowledge base context with historical learnings
2. Static analysis results (AST, CFG, PDG)
3. The actual code changes

Generate a comprehensive code review focusing on:
- Issues identified by static analysis
- Violations of learned patterns from knowledge base
- Best practices and code quality
- Security vulnerabilities
- Performance concerns
- Maintainability issues

Provide specific, actionable feedback with examples."""
        )
    ]
    
    response = llm.invoke(review_prompt + messages)
    
    return {
        "messages": [response],
        "current_stage": "code_review"
    }


def format_output_node(state: AgentState) -> AgentState:
    """
    Stage 4: Format Output
    Formats the review into structured JSON following GitHub comment format
    """
    messages = state["messages"]
    
    format_prompt = [
        messageTypeSystemPrompt,
        SystemMessage(
            content="""You are in the OUTPUT FORMATTING stage.

Convert the code review into structured JSON format following the exact schema:
{
  "summary": "Brief overview",
  "comments": [
    {
      "path": "file/path.py",
      "line": 42,
      "body": "Comment with suggestions"
    }
  ]
}

Use appropriate comment types (inline, diff, range) based on the complexity."""
        )
    ]
    
    response = llm.invoke(format_prompt + messages)
    
    return {
        "messages": [response],
        "current_stage": "complete",
        "review_output": {"formatted": True}
    }


def unit_test_generation_node(state: AgentState) -> AgentState:
    """
    Stage 5 (Optional): Unit Test Generation
    Generates comprehensive unit tests for changed files and commits them to a new branch
    """
    messages = state["messages"]
    pr_context = state.get("pr_context", {})
    
    test_prompt = [
        unitTestSystemPrompt,
        SystemMessage(
            content=f"""You are in the UNIT TEST GENERATION stage.

Your tasks:
1. Use git_branch_tool to create and switch to a new test branch
2. Use find_test_framework_tool to detect the testing framework used in the project
3. For each changed file that needs tests:
   - Read the source file using file_reader_tool
   - Analyze the code and plan test cases (think step-by-step)
   - Use file_writer_tool to create comprehensive unit tests
4. After generating tests:
   - Use git_add_tool to stage the test files
   - Use git_commit_tool to commit with a descriptive message
   - Use git_push_tool to push the test branch to remote
5. Follow the existing testing patterns and conventions
6. Ensure tests cover:
   - Happy paths
   - Edge cases
   - Error handling
   - Async operations (if applicable)

Generate production-ready unit tests that match the project's testing style.

Repository context:
- Repo: {pr_context.get('repo_url', 'N/A')}
- Base branch: {pr_context.get('branch', 'main')}
"""
        )
    ]
    
    response = llm_with_tools.invoke(test_prompt + messages)
    
    return {
        "messages": [response],
        "current_stage": "unit_test_generation"
    }


def route_after_context_enrichment(state: AgentState) -> Literal["tools", "static_analysis"]:
    """Router after context enrichment"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "static_analysis"


def route_after_static_analysis(state: AgentState) -> Literal["tools", "code_review"]:
    """Router after static analysis"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "code_review"


def route_after_code_review(state: AgentState) -> Literal["tools", "unit_test_generation", "format_output"]:
    """Router after code review - checks for tools or test generation"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    generate_tests = state.get("generate_tests", False)
    if generate_tests:
        return "unit_test_generation"
    
    return "format_output"


def route_after_unit_tests(state: AgentState) -> Literal["tools", "format_output"]:
    """Router after unit test generation"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "format_output"


def route_after_tools(state: AgentState) -> str:
    """Router after tool execution"""
    current_stage = state.get("current_stage", "context_enrichment")
    
    if current_stage == "context_enrichment":
        return "context_enrichment"
    elif current_stage == "static_analysis":
        return "static_analysis"
    elif current_stage == "code_review":
        return "code_review"
    elif current_stage == "unit_test_generation":
        return "unit_test_generation"
    else:
        return "context_enrichment"


graph = StateGraph(AgentState)

graph.add_node("context_enrichment", context_enrichment_node)
graph.add_node("static_analysis", static_analysis_node)
graph.add_node("code_review", code_review_node)
graph.add_node("unit_test_generation", unit_test_generation_node)
graph.add_node("format_output", format_output_node)
graph.add_node("tools", tool_node)

graph.set_entry_point("context_enrichment")

graph.add_conditional_edges(
    "context_enrichment",
    route_after_context_enrichment,
    {
        "tools": "tools",
        "static_analysis": "static_analysis"
    }
)

graph.add_conditional_edges(
    "static_analysis",
    route_after_static_analysis,
    {
        "tools": "tools",
        "code_review": "code_review"
    }
)

graph.add_conditional_edges(
    "code_review",
    route_after_code_review,
    {
        "tools": "tools",
        "unit_test_generation": "unit_test_generation",
        "format_output": "format_output"
    }
)

graph.add_conditional_edges(
    "unit_test_generation",
    route_after_unit_tests,
    {
        "tools": "tools",
        "format_output": "format_output"
    }
)

graph.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "context_enrichment": "context_enrichment",
        "static_analysis": "static_analysis",
        "code_review": "code_review",
        "unit_test_generation": "unit_test_generation"
    }
)

graph.add_edge("format_output", END)

app = graph.compile()