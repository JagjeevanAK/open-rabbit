"""
Query interface for the knowledge base.
This module provides functions to query stored learnings.
"""

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_elasticsearch import ElasticsearchStore
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .config import settings


def create_retriever():
    """Create a retriever for querying the knowledge base."""
    embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)
    
    vectorstore = ElasticsearchStore(
        es_url=settings.elasticsearch_url,
        index_name=settings.index_name,
        embedding=embeddings
    )
    
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})


def query_knowledge_base(query: str) -> str:
    """
    Query the knowledge base with a question.
    
    Args:
        query: The question to ask
        
    Returns:
        The AI-generated response based on stored learnings
    """
    retriever = create_retriever()
    llm = ChatOpenAI(model=settings.openai_chat_model, temperature=0.2)
    
    prompt = ChatPromptTemplate.from_template(
        """Answer the question based only on the following context:

{context}

Question: {question}
"""
    )
    
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain.invoke(query)


if __name__ == "__main__":
    query = "Why does the Zero project prefer Dependabot for dependency updates?"
    response = query_knowledge_base(query)
    print(response)
