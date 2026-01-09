from elasticsearch import Elasticsearch
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import settings


def init_index():
    """Initialize Elasticsearch index with proper mappings."""
    es = Elasticsearch(settings.elasticsearch_url)
    
    if es.indices.exists(index=settings.index_name):
        print(f"Index '{settings.index_name}' already exists")
        return
    
    mapping = {
        "mappings": {
            "properties": {
                "learning": {"type": "text"},
                "learnt_from": {"type": "keyword"},
                "pr": {"type": "keyword"},
                "file": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 1536,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    es.indices.create(index=settings.index_name, body=mapping)
    print(f"Created index: {settings.index_name}")


if __name__ == "__main__":
    init_index()