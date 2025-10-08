from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
import os
from pathlib import Path

load_dotenv()

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ast_analysis: Optional[str]
    cfg_analysis: Optional[str] 
    pdg_analysis: Optional[str]
    combined_review: Optional[str]
    output_directory: Optional[str]

llm = ChatOpenAI(
    model="gpt-5", 
    # output_version = "responses/v1"
)
graph = StateGraph(AgentState)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for GPT models."""
    return len(text) // 4

def smart_chunk_json(data: Dict[str, Any], max_tokens: int = 80000) -> List[Dict[str, Any]]:
    """
    Intelligently chunk JSON data to stay within token limits.
    Prioritizes keeping related data together (e.g., functions, dependencies).
    """
    if not data:
        return []
    
    # Calculate full size first
    full_text = json.dumps(data, ensure_ascii=False, indent=None)
    total_tokens = estimate_tokens(full_text)
    print("estimated token are ", total_tokens)
    
    # If small enough, return as single chunk
    if total_tokens <= max_tokens:
        return [data]
    
    chunks = []
    
    # Handle different data structures
    if 'functions' in data and isinstance(data['functions'], list):
        # AST data - chunk by functions
        chunks.extend(_chunk_ast_data(data, max_tokens))
    elif 'data_dependencies' in data and 'control_dependencies' in data:
        # PDG data - chunk by dependency types
        chunks.extend(_chunk_pdg_data(data, max_tokens))
    elif 'unreachable_blocks' in data and 'condition_blocks' in data:
        # CFG data - chunk by block types
        chunks.extend(_chunk_cfg_data(data, max_tokens))
    else:
        # Generic chunking fallback
        chunks.extend(_chunk_generic_data(data, max_tokens))
    
    return chunks

def _chunk_ast_data(data: Dict[str, Any], max_tokens: int) -> List[Dict[str, Any]]:
    """Chunk AST data by grouping related functions."""
    base_data = {k: v for k, v in data.items() if k != 'functions'}
    functions = data.get('functions', [])
    
    chunks = []
    current_chunk = dict(base_data)
    current_chunk['functions'] = []
    current_tokens = estimate_tokens(json.dumps(current_chunk))
    
    for func in functions:
        func_tokens = estimate_tokens(json.dumps(func))
        if current_tokens + func_tokens > max_tokens and current_chunk['functions']:
            # Start new chunk
            chunks.append(current_chunk)
            current_chunk = dict(base_data)
            current_chunk['functions'] = [func]
            current_tokens = estimate_tokens(json.dumps(current_chunk))
        else:
            current_chunk['functions'].append(func)
            current_tokens += func_tokens
    
    if current_chunk['functions']:
        chunks.append(current_chunk)
    
    return chunks

def _chunk_pdg_data(data: Dict[str, Any], max_tokens: int) -> List[Dict[str, Any]]:
    """Chunk PDG data by dependency types."""
    base_data = {k: v for k, v in data.items() if k not in ['data_dependencies', 'control_dependencies']}
    
    chunks = []
    
    # Chunk data dependencies
    data_deps = data.get('data_dependencies', [])
    if data_deps:
        dep_chunks = _chunk_list_items(data_deps, max_tokens // 2)
        for chunk_deps in dep_chunks:
            chunk = dict(base_data)
            chunk['data_dependencies'] = chunk_deps
            chunk['control_dependencies'] = []
            chunks.append(chunk)
    
    # Chunk control dependencies
    ctrl_deps = data.get('control_dependencies', [])
    if ctrl_deps:
        dep_chunks = _chunk_list_items(ctrl_deps, max_tokens // 2)
        for chunk_deps in dep_chunks:
            chunk = dict(base_data)
            chunk['control_dependencies'] = chunk_deps
            chunk['data_dependencies'] = []
            chunks.append(chunk)
    
    return chunks

def _chunk_cfg_data(data: Dict[str, Any], max_tokens: int) -> List[Dict[str, Any]]:
    """Chunk CFG data by block categories."""
    base_data = {k: v for k, v in data.items() if k not in ['condition_blocks', 'path_conditions']}
    
    chunks = []
    
    # Chunk condition blocks
    cond_blocks = data.get('condition_blocks', [])
    if cond_blocks:
        block_chunks = _chunk_list_items(cond_blocks, max_tokens // 2)
        for chunk_blocks in block_chunks:
            chunk = dict(base_data)
            chunk['condition_blocks'] = chunk_blocks
            chunks.append(chunk)
    
    # Chunk path conditions
    path_conds = data.get('path_conditions', [])
    if path_conds:
        path_chunks = _chunk_list_items(path_conds, max_tokens // 2)
        for chunk_paths in path_chunks:
            chunk = dict(base_data)
            chunk['path_conditions'] = chunk_paths
            chunks.append(chunk)
    
    return chunks

def _chunk_list_items(items: List[Any], max_tokens: int) -> List[List[Any]]:
    """Chunk a list of items to stay within token limits."""
    if not items:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for item in items:
        item_tokens = estimate_tokens(json.dumps(item))
        if current_tokens + item_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [item]
            current_tokens = item_tokens
        else:
            current_chunk.append(item)
            current_tokens += item_tokens
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def _chunk_generic_data(data: Dict[str, Any], max_tokens: int) -> List[Dict[str, Any]]:
    """Generic fallback chunking for unknown data structures."""
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
    
    # Consolidate chunks into final summary
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

def load_json(path: str) -> dict:
    with open(path, "r", encoding='utf-8') as f:
        return json.load(f)

def set_output_directory(output_dir: str = "output") -> None:
    """Set the global output directory for analysis."""
    global CURRENT_OUTPUT_DIR
    CURRENT_OUTPUT_DIR = output_dir

# Global variable to track current output directory
CURRENT_OUTPUT_DIR = "output"

@tool  
def analyze_ast_report() -> str:
    """Analyze the focused AST report (*_ast.json)."""
    # Find the AST report file
    output_path = Path(CURRENT_OUTPUT_DIR)
    ast_files = list(output_path.glob("*_ast.json"))
    
    if not ast_files:
        return "No AST report file found."
    
    ast_file = ast_files[0]  # Use first found file
    ast_data = load_json(str(ast_file))
    
    # Smart chunking for large files
    chunks = smart_chunk_json(ast_data, max_tokens=80000)
    
    return analyze_component_chunks(llm, chunks, "AST")

@tool
def analyze_cfg_report() -> str:
    """Analyze the focused CFG report (*_cfg.json)."""
    output_path = Path(CURRENT_OUTPUT_DIR)
    cfg_files = list(output_path.glob("*_cfg.json"))
    
    if not cfg_files:
        return "No CFG report file found."
    
    cfg_file = cfg_files[0]
    cfg_data = load_json(str(cfg_file))
    
    chunks = smart_chunk_json(cfg_data, max_tokens=80000)
    
    return analyze_component_chunks(llm, chunks, "CFG")

@tool
def analyze_pdg_report() -> str:
    """Analyze the focused PDG report (*_pdg.json)."""
    output_path = Path(CURRENT_OUTPUT_DIR)
    pdg_files = list(output_path.glob("*_pdg.json"))
    
    if not pdg_files:
        return "No PDG report file found."
    
    pdg_file = pdg_files[0]
    pdg_data = load_json(str(pdg_file))
    
    chunks = smart_chunk_json(pdg_data, max_tokens=80000)
    
    return analyze_component_chunks(llm, chunks, "PDG")

def run_ast_analysis(state: AgentState) -> AgentState:
    """Analyze AST report and update state."""
    print("running ast_analysis")
    result = analyze_ast_report.invoke({})
    state["ast_analysis"] = result
    return state

def run_cfg_analysis(state: AgentState) -> AgentState:
    """Analyze CFG report and update state.""" 
    print("running cfg_analysis")
    result = analyze_cfg_report.invoke({})
    state["cfg_analysis"] = result
    return state

def run_pdg_analysis(state: AgentState) -> AgentState:
    """Analyze PDG report and update state."""
    print("running pdg_analysis")
    result = analyze_pdg_report.invoke({})
    state["pdg_analysis"] = result
    return state

def create_code_review(state: AgentState) -> AgentState:
    """Generate final code review from all analyses."""
    ast_analysis = state.get("ast_analysis") or "No AST analysis available."
    cfg_analysis = state.get("cfg_analysis") or "No CFG analysis available."
    pdg_analysis = state.get("pdg_analysis") or "No PDG analysis available."
    
    # Calculate total content size to ensure we stay within limits
    total_content = f"{ast_analysis}\n\n{cfg_analysis}\n\n{pdg_analysis}"
    total_tokens = estimate_tokens(total_content)
    
    # If too large, summarize each component first
    if total_tokens > 200000:  # Leave room for prompt and response (50K buffer)
        ast_summary = _summarize_analysis(ast_analysis, "AST")
        cfg_summary = _summarize_analysis(cfg_analysis, "CFG") 
        pdg_summary = _summarize_analysis(pdg_analysis, "PDG")
        
        review_prompt = f"""
You are a senior code reviewer conducting a comprehensive code analysis.

Based on the following focused analysis summaries, provide a professional code review:

## AST Analysis Summary
{ast_summary}

## CFG Analysis Summary  
{cfg_summary}

## PDG Analysis Summary
{pdg_summary}

## Required Output Format:

### Executive Summary
- Overall code quality assessment
- Key architectural concerns

### Critical Issues (High Priority)
- List 3-5 most severe issues
- Include specific recommendations

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

Keep the review actionable and specific with line references when possible.
"""
    else:
        review_prompt = f"""
You are a senior code reviewer conducting a comprehensive code analysis.

Based on the detailed analysis below, provide a professional code review:

## AST Analysis
{ast_analysis}

## CFG Analysis
{cfg_analysis}

## PDG Analysis  
{pdg_analysis}

## Required Output Format:

### Executive Summary
- Overall code quality assessment
- Key architectural concerns

### Critical Issues (High Priority)
- List 3-5 most severe issues with line numbers
- Include specific fix recommendations

### Improvement Opportunities (Medium Priority)
- List 3-5 areas for enhancement
- Include refactoring suggestions with examples

### Code Quality Metrics
- Complexity assessment
- Maintainability score (1-10)
- Technical debt indicators

### Recommendations
- Immediate action items (next sprint)
- Long-term improvements (next quarter)
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
    if estimate_tokens(analysis_text) <= 60000:  # Increased from 20000
        return analysis_text
    
    prompt = f"""
Summarize this {component_type} analysis, preserving the most critical findings:

{analysis_text[:120000]}  # Increased from 40000 to use more context

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
graph.add_node("cfg_analysis", run_cfg_analysis) 
graph.add_node("pdg_analysis", run_pdg_analysis)
graph.add_node("code_review", create_code_review)

# Set up workflow sequence
graph.set_entry_point("ast_analysis")
graph.add_edge("ast_analysis", "cfg_analysis")
graph.add_edge("cfg_analysis", "pdg_analysis")
graph.add_edge("pdg_analysis", "code_review")

app = graph.compile()

def run_workflow_analysis(output_dir: str = "output") -> Dict[str, Any]:
    """
    Run the complete workflow analysis on the generated reports.
    
    Args:
        output_dir: Directory containing the *_ast.json, *_cfg.json, *_pdg.json files
        
    Returns:
        Dictionary containing all analysis results
    """
    # Set the output directory for the tools to find files
    set_output_directory(output_dir)
    
    # Initialize state
    initial_state: AgentState = {
        "messages": [],
        "output_directory": output_dir
    }
    
    # Run the workflow
    result = app.invoke(initial_state)
    
    return {
        "status": "success",
        "output_directory": output_dir,
        "ast_analysis": result.get("ast_analysis"),
        "cfg_analysis": result.get("cfg_analysis"), 
        "pdg_analysis": result.get("pdg_analysis"),
        "combined_review": result.get("combined_review"),
        "messages": result.get("messages", [])
    }

if __name__ == "__main__":
    # Example usage
    result = run_workflow_analysis("output")
    
    if result["status"] == "success":
        print("=== CODE REVIEW RESULTS ===")
        if result.get("combined_review"):
            print(result["combined_review"])
        else:
            print("No review generated")
    else:
        print(f"Workflow failed: {result.get('error', 'Unknown error')}")
