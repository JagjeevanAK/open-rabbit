"""
Storage layer for persisting and retrieving learnings.

Handles interactions with:
1. Qdrant vector database for semantic search
2. Optional relational DB for structured queries (future enhancement)

Design follows repository pattern for clean separation of concerns.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain.schema import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range

from src.learnings.core.models import Learning, LearningSource, FeedbackType
from src.learnings.core.config import Settings


class LearningStorage:
    """
    Repository for storing and retrieving learnings from vector database.
    
    Architecture:
    - Uses Qdrant for vector storage and similarity search
    - Stores rich metadata alongside embeddings for filtering
    - Provides both semantic search and metadata filtering capabilities
    
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Initialize OpenAI embeddings
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            # openai_api_key=settings.openai_api_key
        )
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key
        )
        
        # Initialize or connect to existing collection
        self._ensure_collection_exists()
        
        # LangChain wrapper for convenience
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=settings.qdrant_collection_name,
            embedding=self.embeddings
        )
    
    def _ensure_collection_exists(self):
        """
        Create Qdrant collection if it doesn't exist.
        
        Collection schema:
        - Vector dimension matches embedding model
        - Uses cosine similarity for semantic search
        - Indexes metadata for efficient filtering
        """
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.settings.qdrant_collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.settings.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=self.settings.embedding_dimensions,
                    distance=Distance.COSINE
                )
            )
            print(f"Created Qdrant collection: {self.settings.qdrant_collection_name}")
    
    def store_learning(self, learning: Learning) -> str:
        """
        Store a learning in the vector database.
        
        Args:
            learning: Learning object with text, metadata, and optional embedding
        
        Returns:
            The learning_id that was stored
        
        Process:
        1. Generate embedding if not provided
        2. Convert to Qdrant point with metadata
        3. Upsert to collection
        """
        # Generate embedding if not present
        if not learning.embedding:
            learning.embedding = self.embeddings.embed_query(learning.learning_text)
        
        # Generate ID if not present
        if not learning.learning_id:
            learning.learning_id = str(uuid.uuid4())
        
        # Prepare metadata payload
        payload = {
            "learning_id": learning.learning_id,
            "learning_text": learning.learning_text,
            "original_comment": learning.original_comment,
            "code_context": learning.code_context,
            "language": learning.language,
            
            # Source metadata
            "repo_name": learning.source.repo_name,
            "pr_number": learning.source.pr_number,
            "pr_title": learning.source.pr_title,
            "file_path": learning.source.file_path,
            "author": learning.source.author,
            "reviewer": learning.source.reviewer,
            
            # Quality signals
            "feedback_type": learning.feedback_type.value if learning.feedback_type else None,
            "confidence_score": learning.confidence_score,
            
            # Timestamps
            "created_at": learning.created_at.isoformat(),
            "updated_at": learning.updated_at.isoformat(),
        }
        
        # Create Qdrant point
        point = PointStruct(
            id=learning.learning_id,
            vector=learning.embedding,
            payload=payload
        )
        
        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.settings.qdrant_collection_name,
            points=[point]
        )
        
        return learning.learning_id
    
    def search_similar(
        self,
        query: str,
        k: int = 5,
        repo_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Learning]:
        """
        Search for similar learnings using semantic search.
        
        Args:
            query: Search query text
            k: Number of results to return
            repo_filter: Optional repository name filter
            language_filter: Optional language filter
            min_confidence: Minimum confidence score threshold
        
        Returns:
            List of Learning objects ranked by similarity
        
        Implementation:
        - Embeds the query using the same model
        - Performs vector similarity search in Qdrant
        - Applies metadata filters
        - Reconstructs Learning objects from results
        """
        # Build Qdrant filters
        must_conditions = []
        
        if repo_filter:
            must_conditions.append(
                FieldCondition(key="repo_name", match=MatchValue(value=repo_filter))
            )
        
        if language_filter:
            must_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=language_filter))
            )
        
        if min_confidence > 0.0:
            must_conditions.append(
                FieldCondition(key="confidence_score", range=Range(gte=min_confidence))
            )
        
        # Perform search using LangChain wrapper (simpler API)
        filter_obj = Filter(must=must_conditions) if must_conditions else None
        
        results = self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter_obj
        )
        
        # Convert results to Learning objects
        learnings = []
        for doc in results:
            learning = self._document_to_learning(doc)
            if learning:
                learnings.append(learning)
        
        return learnings
    
    def get_learning_by_id(self, learning_id: str) -> Optional[Learning]:
        """Retrieve a specific learning by ID."""
        try:
            point = self.client.retrieve(
                collection_name=self.settings.qdrant_collection_name,
                ids=[learning_id]
            )
            
            if not point:
                return None
            
            payload = point[0].payload

            if payload is None:
                return None

            return self._payload_to_learning(payload)
            
        except Exception as e:
            print(f"Error retrieving learning {learning_id}: {e}")
            return None
    
    def delete_learning(self, learning_id: str) -> bool:
        """Delete a learning by ID."""
        try:
            self.client.delete(
                collection_name=self.settings.qdrant_collection_name,
                points_selector=[learning_id]
            )
            return True
        except Exception as e:
            print(f"Error deleting learning {learning_id}: {e}")
            return False
    
    def _document_to_learning(self, doc: Document) -> Optional[Learning]:
        """Convert LangChain Document to Learning object."""
        try:
            metadata = doc.metadata
            return self._payload_to_learning(metadata)
        except Exception as e:
            print(f"Error converting document to learning: {e}")
            return None
    
    def _payload_to_learning(self, payload: Dict[str, Any]) -> Learning:
        """Convert Qdrant payload to Learning object."""
        source = LearningSource(
            repo_name=payload["repo_name"],
            pr_number=payload["pr_number"],
            pr_title=payload.get("pr_title"),
            file_path=payload["file_path"],
            author=payload["author"],
            reviewer=payload.get("reviewer"),
            timestamp=datetime.fromisoformat(payload.get("created_at", datetime.utcnow().isoformat()))
        )
        
        feedback_type = None
        if payload.get("feedback_type"):
            feedback_type = FeedbackType(payload["feedback_type"])
        
        return Learning(
            learning_id=payload["learning_id"],
            learning_text=payload["learning_text"],
            original_comment=payload["original_comment"],
            code_context=payload.get("code_context"),
            language=payload.get("language"),
            source=source,
            feedback_type=feedback_type,
            confidence_score=payload.get("confidence_score", 1.0),
            created_at=datetime.fromisoformat(payload.get("created_at", datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(payload.get("updated_at", datetime.utcnow().isoformat()))
        )
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the learnings collection."""
        try:
            collection_info = self.client.get_collection(
                collection_name=self.settings.qdrant_collection_name
            )
            vectors_config = collection_info.config.params.vectors

            if isinstance(vectors_config, dict):
                first_vector = next(iter(vectors_config.values()), None)
            else:
                first_vector = vectors_config

            vector_size = first_vector.size if first_vector else None
            distance_metric = (
                first_vector.distance.name
                if first_vector and getattr(first_vector, "distance", None)
                else None
            )

            return {
                "total_learnings": collection_info.points_count,
                "collection_name": self.settings.qdrant_collection_name,
                "vector_size": vector_size,
                "distance_metric": distance_metric
            }
        except Exception as e:
            print(f"Error getting collection stats: {e}")
            return {}
