"""
LangGraph Workflow for Code Analysis

Orchestrates AST and Semantic analysis using LangGraph state machine.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
import os
from pathlib import Path

load_dotenv()


class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ast_analysis: Optional[str]
    semantic_analysis: Optional[str]
    combined_review: Optional[str]
    output_directory: Optional[str]


llm = ChatOpenAI(model="gpt-4o")

# Global variable to track current output directory
CURRENT_OUTPUT_DIR = "output"


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for GPT models."""
    return len(text) // 4


def smart_chunk_json(data: Dict[str, Any], max_tokens: int = 80000) -> List[Dict[str, Any]]:
    """Intelligently chunk JSON data to stay within token limits."""
    if not data:
        return []
    
    full_text = json.dumps(data, ensure_ascii=False, indent=None)
    total_tokens = estimate_tokens(full_text)
    
    if total_tokens <= max_tokens:
        return [data]
    
    # Chunk by functions if available (AST data)
    if 'functions' in data and isinstance(data['functions'], list):
        return _chunk_by_key(data, 'functions', max_tokens)
    
    # Generic fallback
    return _chunk_generic(data, max_tokens)


def _chunk_by_key(data: Dict[str, Any], key: str, max_tokens: int) -> List[Dict[str, Any]]:
    """Chunk data by a specific list key."""
    base_data = {k: v for k, v in data.items() if k != key}
    items = data.get(key, [])
    
    chunks = []
    current_chunk = dict(base_data)
    current_chunk[key] = []
    current_tokens = estimate_tokens(json.dumps(current_chunk))
    
    for item in items:
        item_tokens = estimate_tokens(json.dumps(item))
        if current_tokens + item_tokens > max_tokens and current_chunk[key]:
            chunks.append(current_chunk)
            current_chunk = dict(base_data)
            current_chunk[key] = [item]
            current_tokens = estimate_tokens(json.dumps(current_chunk))
        else:
            current_chunk[key].append(item)
            current_tokens += item_tokens
    
    if current_chunk[key]:
        chunks.append(current_chunk)
    
    return chunks


def _chunk_generic(data: Dict[str, Any], max_tokens: int) -> List[Dict[str, Any]]:
    """Generic chunking for unknown data structures."""
    items = list(data.items())
    chunks = []
    current_chunk = {}
    current_tokens = 0
    
    for key, value in items:
        item_tokens = estimate_tokens(json.dumps({key: value}))
        if current_tokens + item_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = {key: value}
            current_tokens = item_tokens
        else:
            current_chunk[key] = value
            current_tokens += item_tokens
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def analyze_component_chunks(llm, chunks: List[Dict[str, Any]], component_type: str) -> str:
    """Analyze chunked component data and return consolidated summary."""
    if not chunks:
        return f"No {component_type} data available."
    
    chunk_summaries = []
    
    for idx, chunk in enumerate(chunks, 1):
        chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)
        
        prompt = f"""
You are analyzing {component_type} data (chunk {idx} of {len(chunks)}).

Focus on:
- Code structure and organization patterns
- Potential issues or anti-patterns  
- Complexity metrics and problematic areas
- Dependencies and coupling issues

Provide:
1. Brief overview of this chunk's contents
2. 3-5 specific findings with line numbers when available
3. Severity assessment (low/medium/high) for each finding

{component_type.upper()} DATA:
{chunk_json}
"""
        
        resp = llm.invoke([
            SystemMessage(content=f"You are a code analysis expert specializing in {component_type} analysis."),
            HumanMessage(content=prompt)
        ])
        
        chunk_summaries.append(f"--- {component_type.upper()} Chunk {idx} ---\n{resp.content}")
    
    # Consolidate chunks
    if len(chunk_summaries) > 1:
        consolidated_prompt = f"""
Consolidate these {component_type} analysis chunks into a unified summary:

{chr(10).join(chunk_summaries)}

Provide:
1. Overall {component_type} assessment 
2. Top 5 most critical findings across all chunks
3. Recommendations for improvement
"""
        
        final_resp = llm.invoke([
            SystemMessage(content=f"You are consolidating {component_type} analysis results."),
            HumanMessage(content=consolidated_prompt)
        ])
        
        return final_resp.content
    else:
        return chunk_summaries[0] if chunk_summaries else ""


def load_json(path: str) -> dict:
    with open(path, "r", encoding='utf-8') as f:
        return json.load(f)


def set_output_directory(output_dir: str = "output") -> None:
    """Set the global output directory for analysis."""
    global CURRENT_OUTPUT_DIR
    CURRENT_OUTPUT_DIR = output_dir


@tool  
def analyze_ast_report() -> str:
    """Analyze the focused AST report (*_ast.json)."""
    output_path = Path(CURRENT_OUTPUT_DIR)
    ast_files = list(output_path.glob("*_ast.json"))
    
    if not ast_files:
        return "No AST report file found."
    
    ast_file = ast_files[0]
    ast_data = load_json(str(ast_file))
    chunks = smart_chunk_json(ast_data, max_tokens=80000)
    
    return analyze_component_chunks(llm, chunks, "AST")


@tool
def analyze_semantic_report() -> str:
    """Analyze the focused Semantic Graph report (*_semantic.json)."""
    output_path = Path(CURRENT_OUTPUT_DIR)
    semantic_files = list(output_path.glob("*_semantic.json"))
    
    if not semantic_files:
        return "No Semantic Graph report file found."
    
    semantic_file = semantic_files[0]
    semantic_data = load_json(str(semantic_file))
    chunks = smart_chunk_json(semantic_data, max_tokens=80000)
    
    return analyze_component_chunks(llm, chunks, "Semantic Graph")


def run_ast_analysis(state: AgentState) -> AgentState:
    """Analyze AST report and update state."""
    print("Running AST analysis...")
    result = analyze_ast_report.invoke({})
    state["ast_analysis"] = result
    return state


def run_semantic_analysis(state: AgentState) -> AgentState:
    """Analyze Semantic Graph report and update state."""
    print("Running Semantic analysis...")
    result = analyze_semantic_report.invoke({})
    state["semantic_analysis"] = result
    return state


def create_code_review(state: AgentState) -> AgentState:
    """Generate final code review from all analyses."""
    ast_analysis = state.get("ast_analysis") or "No AST analysis available."
    semantic_analysis = state.get("semantic_analysis") or "No Semantic analysis available."
    
    total_content = f"{ast_analysis}\n\n{semantic_analysis}"
    total_tokens = estimate_tokens(total_content)
    
    # Summarize if too large
    if total_tokens > 150000:
        ast_analysis = _summarize_analysis(ast_analysis, "AST")
        semantic_analysis = _summarize_analysis(semantic_analysis, "Semantic Graph")
    
    review_prompt = f"""
You are a senior code reviewer conducting a comprehensive code analysis.

Based on the analysis below, provide a professional code review:

## AST Analysis
{ast_analysis}

## Semantic Graph Analysis
{semantic_analysis}

## Required Output Format:

### Executive Summary
- Overall code quality assessment
- Key architectural concerns

### Critical Issues (High Priority)
- List 3-5 most severe issues with line numbers
- Include specific fix recommendations

### Improvement Opportunities (Medium Priority)
- List 3-5 areas for enhancement
- Include refactoring suggestions

### Code Quality Metrics
- Complexity assessment
- Maintainability score (1-10)
- Technical debt indicators

### Recommendations
- Immediate action items
- Long-term improvements
- Best practice suggestions

Keep the review actionable and specific with clear examples.
"""
    
    resp = llm.invoke([
        SystemMessage(content="You are a senior software engineer conducting a thorough code review."),
        HumanMessage(content=review_prompt)
    ])
    
    review_content = resp.content if isinstance(resp.content, str) else str(resp.content)
    state["combined_review"] = review_content
    state["messages"] = [AIMessage(content=review_content)]
    return state


def _summarize_analysis(analysis_text: str, component_type: str) -> str:
    """Summarize analysis text if it's too long."""
    if estimate_tokens(analysis_text) <= 60000:
        return analysis_text
    
    prompt = f"""
Summarize this {component_type} analysis, preserving the most critical findings:

{analysis_text[:120000]}

Focus on:
- Most severe issues and their impact
- Key metrics and complexity indicators  
- Specific recommendations with line numbers
- Overall assessment

Keep the summary detailed enough for a code review but concise.
"""
    
    resp = llm.invoke([
        SystemMessage(content=f"You are summarizing {component_type} analysis results."),
        HumanMessage(content=prompt)
    ])
    
    return resp.content if isinstance(resp.content, str) else str(resp.content)


# Create and configure the workflow graph
graph = StateGraph(AgentState)

graph.add_node("ast_analysis", run_ast_analysis)
graph.add_node("semantic_analysis", run_semantic_analysis)
graph.add_node("code_review", create_code_review)

# Set up workflow sequence: AST -> Semantic -> Review
graph.set_entry_point("ast_analysis")
graph.add_edge("ast_analysis", "semantic_analysis")
graph.add_edge("semantic_analysis", "code_review")

app = graph.compile()


def run_workflow_analysis(output_dir: str = "output") -> Dict[str, Any]:
    """
    Run the complete workflow analysis on the generated reports.
    
    Args:
        output_dir: Directory containing the *_ast.json, *_semantic.json files
        
    Returns:
        Dictionary containing all analysis results
    """
    set_output_directory(output_dir)
    
    initial_state: AgentState = {
        "messages": [],
        "output_directory": output_dir
    }
    
    result = app.invoke(initial_state)
    
    return {
        "status": "success",
        "output_directory": output_dir,
        "ast_analysis": result.get("ast_analysis"),
        "semantic_analysis": result.get("semantic_analysis"),
        "combined_review": result.get("combined_review"),
        "messages": result.get("messages", [])
    }


if __name__ == "__main__":
    result = run_workflow_analysis("output")
    
    if result["status"] == "success":
        print("=== CODE REVIEW RESULTS ===")
        if result.get("combined_review"):
            print(result["combined_review"])
        else:
            print("No review generated")
    else:
        print(f"Workflow failed: {result.get('error', 'Unknown error')}")
