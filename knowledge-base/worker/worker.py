from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from client.client import app

load_dotenv()

llm = ChatOpenAI(model="gpt-5", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

vector_store = QdrantVectorStore.from_existing_collection(
    embedding=embeddings,
    url="http://localhost:6333/",
    collection_name='rabbit-knowledgeBase'
)

system_prompt = SystemMessage(
    content="""
You are an AI code reviewer that learns from prior human feedback. 
Your goal is to provide concise, actionable, and professional review comments on pull request code snippets.

You will be given:
1. The current code snippet.
2. Retrieved past snippets with their review suggestions and human responses 
   (accepted, rejected, modified, thanked, debated).
3. A summary of trends from past feedback.

Instructions:
- Use the retrieved history to guide your suggestion, aligning with patterns humans previously preferred.
- If past similar suggestions were often rejected, adjust your recommendation accordingly or explain the tradeoff.
- Always give a clear, specific, and helpful suggestion in 40–50 words.
- Avoid generic praise; focus on concrete improvements in readability, performance, maintainability, or correctness.
- Be professional and constructive.
Your output should be a single, concise review comment.
"""
)

@app.task
def process_query(query: str, k: int = 5):
    """
    Process a new code snippet query:
    1. Retrieve top-k similar snippets from vector store
    2. Construct context with human feedback
    3. Ask LLM for final review suggestion
    """
    
    search_results = vector_store.similarity_search(query=query, k=k)
    
    if not search_results:
        # fallback if no similar snippets
        messages = [system_prompt, HumanMessage(content=f"New snippet:\n{query}\nNo past feedback available.")]
        res = llm(messages)
        return res.content
    
    # Build enriched context from retrieved snippets
    context_texts = []
    for i, doc in enumerate(search_results, start=1):
        snippet = doc.metadata.get("snippet", doc.page_content)
        suggestion = doc.metadata.get("suggestion", "N/A")
        human_response = doc.metadata.get("human_response", "N/A")
        language = doc.metadata.get("language", "N/A")
        
        context_texts.append(
            f"Case {i} | Language: {language}\n"
            f"Code Snippet:\n{snippet}\n"
            f"Bot Suggestion:\n{suggestion}\n"
            f"Human Response: {human_response}\n"
        )
    
    context_summary = "\n---\n".join(context_texts)
    
    augmented_query = f"Current Snippet:\n{query}\n\nRetrieved Past Cases:\n{context_summary}"
    
    messages = [system_prompt, HumanMessage(content=augmented_query)]
    res = llm(messages)
    return res.content
