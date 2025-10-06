from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    message: Annotated[Sequence[BaseMessage], add_messages]
    
graph = StateGraph(AgentState)

llm = ChatOpenAI(model="gpt-5")



app = graph.compile()