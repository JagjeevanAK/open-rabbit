from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from systemPrompt import systemPrompt
from dotenv import load_dotenv

# Import knowledge base tools
from agent.tools.knowledgeBase import (
    search_knowledge_base,
    get_pr_learnings,
    format_review_context
)

# Import parser tools
from agent.tools.Parsers import (
    parse_code_file,
    analyze_changed_files,
    get_parser_capabilities
)

load_dotenv()

class AgentState(TypedDict):
    message: Annotated[Sequence[BaseMessage], add_messages]
    
graph = StateGraph(AgentState)

# Bind tools to the LLM
tools = [
    # Knowledge base tools
    search_knowledge_base,
    get_pr_learnings,
    format_review_context,
    # Parser tools
    parse_code_file,
    analyze_changed_files,
    get_parser_capabilities
]
llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)


def get_file(state: AgentState) -> AgentState:
    
    return state

# graph.add_node()
app = graph.compile()