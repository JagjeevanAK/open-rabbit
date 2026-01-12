from .celery_app import celery_app
from langchain_openai import OpenAIEmbeddings
from elasticsearch import Elasticsearch
from .config import settings


@celery_app.task(name="tasks.process_learning")
def process_learning(learning_data: dict) -> dict:
    """
    Process and index a learning document asynchronously.
    
    Args:
        learning_data: Dictionary containing:
            - learning: str (required)
            - learnt_from: str (optional)
            - pr: str (optional)
            - file: str (optional)
            - timestamp: str (required, ISO format)
    
    Returns:
        Dictionary with task status and indexed document ID
    """
    try:
        # Initialize Elasticsearch
        es = Elasticsearch(settings.elasticsearch_url)
        
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)
        
        # Prepare document
        doc = {
            "learning": learning_data["learning"],
            "learnt_from": learning_data.get("learnt_from", "unknown"),
            "pr": learning_data.get("pr", ""),
            "file": learning_data.get("file", ""),
            "timestamp": learning_data["timestamp"]
        }
        
        # Generate embedding
        vector = embeddings.embed_query(doc["learning"])
        doc["embedding"] = vector
        
        # Index document
        result = es.index(index=settings.index_name, document=doc)
        
        return {
            "status": "success",
            "document_id": result["_id"],
            "index": settings.index_name
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
