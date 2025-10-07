from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool

from dotenv import load_dotenv

# Import knowledge base tools
from agent.tools.knowledgeBase import (
    search_knowledge_base,
    get_pr_learnings,
    format_review_context
)

load_dotenv()

class AgentState(TypedDict):
    message: Annotated[Sequence[BaseMessage], add_messages]
    
graph = StateGraph(AgentState)

# Bind tools to the LLM
tools = [search_knowledge_base, get_pr_learnings, format_review_context]
llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)

systemPrompt = SystemMessage(
    content="""
    You are an expert code reviewing agent that helps developers follow best practices and improve code quality.
    
    Your review process consists of 3 enriched sections:
    
    1. **Knowledge Base Context** (Human Feedback & Learnings):
       - Use the knowledge base tools to retrieve relevant learnings from past code reviews
       - Access accepted/rejected suggestions and user comments from previous PRs
       - Apply project-specific patterns and best practices learned from history
       - Use search_knowledge_base() to find topic-specific learnings
       - Use get_pr_learnings() to get context specific to this PR
    
    2. **Static Analysis Context** (AST, CFG, PDG):
       - Review Abstract Syntax Tree (AST) analysis outputs
       - Examine Control Flow Graph (CFG) for logic flow issues
       - Analyze Program Dependency Graph (PDG) for dependencies and potential issues
       - Use these analyses to identify deeper code quality concerns
    
    3. **Code Changes Context** (Files & Diffs):
       - Review the actual code files and their diffs
       - Understand what changed and why
       - Provide specific, actionable feedback on the changes
    
    **Your Responsibilities**:
    - Always check the knowledge base first for relevant project learnings
    - Provide constructive, specific feedback with examples
    - Reference past learnings when they apply to current changes
    - Ensure consistency with previously accepted patterns
    - Flag deviations from established project practices
    - Suggest improvements based on historical feedback
    
    **Tools Available**:
    - search_knowledge_base: Search for topic-specific learnings
    - get_pr_learnings: Get learnings specific to this PR's context
    - format_review_context: Generate comprehensive review context
    
    Start each review by gathering relevant knowledge base context!
""")

def get_file(state: AgentState) -> AgentState:
    
    return state

# graph.add_node()
app = graph.compile()