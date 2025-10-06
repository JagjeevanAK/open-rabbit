from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence, Optional, List
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
import os

load_dotenv()

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ast_data: Optional[dict]
    pdg_data: Optional[dict]
    analysis_summary: Optional[str]
    pdg_summary: Optional[str]

llm = ChatOpenAI(
    model="gpt-5", 
    # output_version = "responses/v1"
)
graph = StateGraph(AgentState)


def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def chunk_text(text: str, chunk_size: int = 20000) -> List[str]:
    """Split text into character-based chunks."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def summarize_chunks_for_role(llm, text: str, role_description: str, chunk_size: int = 20000) -> List[str]:
    """Summarize long text in small LLM calls (chunked)."""
    if not text:
        return []

    chunks = chunk_text(text, chunk_size)
    summaries: List[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        prompt = f"""
You are {role_description}.
This is chunk {idx} of {len(chunks)}.
1) Provide a compact 2–4 sentence summary of what's in this chunk.
2) List up to 5 concise findings (bullet points) relevant to code structure, control flow, or dependencies.
3) Respond in plain text only.

CHUNK:
{chunk}
"""
        resp = llm.invoke([
            SystemMessage(content=f"Role: {role_description}"),
            HumanMessage(content=prompt),
        ])
        summaries.append(resp.content.strip() if isinstance(resp.content, str) else str(resp.content))

    return summaries

@tool
def analyze_ast_json() -> str:
    """Analyze and summarize AST (analysis.json)."""
    ast_path = os.path.join("output", "analysis.json")
    ast_data = load_json(ast_path)
    ast_text = json.dumps(ast_data, ensure_ascii=False, indent=None)

    summaries = summarize_chunks_for_role(
        llm,
        ast_text,
        "an expert code structure analyzer (AST-level)",
        chunk_size=5000,
    )

    aggregated = "\n\n".join([f"--- Chunk {i+1} ---\n{s}" for i, s in enumerate(summaries)])
    return aggregated


@tool
def analyze_pdg_json() -> str:
    """Analyze and summarize PDG (detailed_pdg.json)."""
    pdg_path = os.path.join("output", "detailed_pdg.json")
    pdg_data = load_json(pdg_path)
    pdg_text = json.dumps(pdg_data, ensure_ascii=False, indent=None)

    summaries = summarize_chunks_for_role(
        llm,
        pdg_text,
        "a control-flow and data-dependency expert (PDG-level)",
        chunk_size=5000,
    )

    aggregated = "\n\n".join([f"--- Chunk {i+1} ---\n{s}" for i, s in enumerate(summaries)])
    return aggregated

def run_ast_tool(state: AgentState) -> AgentState:
    result = analyze_ast_json.invoke({})
    state["analysis_summary"] = result
    return state

def run_pdg_tool(state: AgentState) -> AgentState:
    result = analyze_pdg_json.invoke({})
    state["pdg_summary"] = result
    return state

def review_agent(state: AgentState) -> AgentState:
    combined_prompt = f"""
You are a senior AI code reviewer. Use the following aggregated analyses to produce:
1) Up to 8 prioritized, actionable suggestions for readability, safety, correctness, and performance.
2) Include: short description, affected lines (if possible), severity (low/medium/high), and quick fix hints.
3) Provide a short GitHub PR summary at the end.

AST Summary:
{state.get("analysis_summary", "N/A")}

PDG Summary:
{state.get("pdg_summary", "N/A")}
"""

    resp = llm.invoke([
        SystemMessage(content="You are a senior AI code reviewer."),
        HumanMessage(content=combined_prompt),
    ])
    state["messages"] = [AIMessage(content=resp.content)]
    return state

graph.add_node("ast_analysis", run_ast_tool)
graph.add_node("pdg_analysis", run_pdg_tool)
graph.add_node("review_agent", review_agent)

graph.set_entry_point("ast_analysis")
graph.add_edge("ast_analysis", "pdg_analysis")
graph.add_edge("pdg_analysis", "review_agent")

app = graph.compile()

if __name__ == "__main__":
    initial_state: AgentState = {"messages": []}
    result = app.invoke(initial_state)

    msgs = result.get("messages") or []
    if msgs:
        print(msgs[-1].content)
    else:
        print("No messages generated.")
