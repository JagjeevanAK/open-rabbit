from langchain_openai import ChatOpenAI
from typing import Annotated, Sequence, TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool

from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    message: Annotated[Sequence[BaseMessage], add_messages]
    
graph = StateGraph(AgentState)

llm = ChatOpenAI(model="gpt-5")

systemPrompt = SystemMessage(
    content="""
    Hey you are a code reviewing agent which help's and suggest users the better practices to be followed on the pull request and code suggewstion as this prompt consiste 3 
    section where you will be given the knowledge graph aka the human feedback where there will accepted user suggestions and and not accepted user suggestions and comment left
    by the user on the suggestions
    
    2nd section will consist of the analysis of the AST (Abstract Syantx tree) and CFG (Control flow graph) and PDG (program depndency graph) so agent will give the review of 
    thoses output files to give the context of it 
    
    and 3rd section will the code it self where there will be the code file and diff of that file where code was change in that file so that will help you to understand what things
    were changed and on what we have to make review
""")

def get_file(state: AgentState) -> AgentState:
    
    return state

# graph.add_node()
app = graph.compile()