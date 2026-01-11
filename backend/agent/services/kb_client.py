"""
Knowledge Base Client

Async client for interacting with the Knowledge Base service.
Supports:
- Querying for relevant learnings based on code context
- Adding new learnings from reviews
- Health checks
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from ..schemas.common import KBContext, FileInfo

logger = logging.getLogger(__name__)


@dataclass
class KBClientConfig:
    """Configuration for Knowledge Base client."""
    
    # KB service URL (defaults to localhost for development)
    base_url: str = field(
        default_factory=lambda: os.getenv("KB_SERVICE_URL", "http://localhost:8000")
    )
    
    # Elasticsearch direct connection (optional, for advanced queries)
    elasticsearch_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ELASTICSEARCH_URL")
    )
    
    # Timeouts
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # OpenAI settings for embeddings (used for direct ES queries)
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    embedding_model: str = "text-embedding-3-small"


class KBClient:
    """
    Async client for the Knowledge Base service.
    
    The KB stores code learnings and insights that can be used
    to provide context-aware code reviews.
    
    Example:
        ```python
        client = KBClient()
        
        # Query for relevant learnings
        context = await client.query_context(
            file_paths=["src/main.py"],
            code_snippets=["def process_data(...)"],
            pr_context="Adding caching layer"
        )
        
        # Add a new learning
        await client.add_learning(
            learning="Always use connection pooling for database connections",
            learnt_from="JohnDoe",
            pr="org/repo#123",
            file="src/db.py:45-60"
        )
        ```
    """
    
    def __init__(self, config: Optional[KBClientConfig] = None):
        """
        Initialize the KB client.
        
        Args:
            config: Client configuration. Uses defaults if not provided.
        """
        self.config = config or KBClientConfig()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._es_store = None
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazy-initialize HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.read_timeout,
                    pool=self.config.connect_timeout,
                ),
            )
        return self._http_client
    
    async def close(self):
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def health_check(self) -> bool:
        """
        Check if the KB service is healthy.
        
        Returns:
            True if service is available, False otherwise.
        """
        try:
            response = await self.http_client.get("/")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"KB health check failed: {e}")
            return False
    
    async def query_context(
        self,
        file_paths: Optional[List[str]] = None,
        code_snippets: Optional[List[str]] = None,
        pr_context: Optional[str] = None,
        max_learnings: int = 5,
    ) -> KBContext:
        """
        Query the Knowledge Base for relevant context.
        
        Builds a query from the provided code context and retrieves
        relevant learnings that can inform the code review.
        
        Args:
            file_paths: List of file paths being reviewed
            code_snippets: Key code snippets for context
            pr_context: PR title/description for additional context
            max_learnings: Maximum number of learnings to retrieve
            
        Returns:
            KBContext with relevant learnings
        """
        # Build query from context
        query_parts = []
        
        if pr_context:
            query_parts.append(pr_context)
        
        if file_paths:
            # Extract meaningful parts from file paths
            for path in file_paths:
                # Get file name and parent directory
                parts = path.split("/")
                if len(parts) >= 2:
                    query_parts.append(" ".join(parts[-2:]))
                else:
                    query_parts.append(parts[-1])
        
        if code_snippets:
            # Add first 200 chars of each snippet
            for snippet in code_snippets[:3]:  # Limit to 3 snippets
                query_parts.append(snippet[:200])
        
        if not query_parts:
            logger.debug("No query context provided, returning empty KBContext")
            return KBContext()
        
        query = " ".join(query_parts)
        
        # Try direct Elasticsearch query first (more control)
        if self.config.elasticsearch_url and self.config.openai_api_key:
            try:
                return await self._query_elasticsearch(query, max_learnings)
            except Exception as e:
                logger.warning(f"Direct ES query failed, falling back to API: {e}")
        
        return await self._query_api(query, max_learnings)
    
    async def _query_elasticsearch(
        self,
        query: str,
        max_learnings: int,
    ) -> KBContext:
        """
        Query Elasticsearch directly using vector similarity.
        
        This provides more control over the query and results.
        """
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_elasticsearch import ElasticsearchStore
        except ImportError:
            logger.warning("langchain-elasticsearch not installed, using API fallback")
            return await self._query_api(query, max_learnings)
        
        # Create embeddings instance (uses OPENAI_API_KEY env var by default)
        embeddings = OpenAIEmbeddings(
            model=self.config.embedding_model,
        )
        
        # Connect to Elasticsearch
        vectorstore = ElasticsearchStore(
            es_url=self.config.elasticsearch_url,
            index_name=os.getenv("KB_INDEX_NAME", "open_rabbit_knowledge_base"),
            embedding=embeddings,
        )
        
        # Perform similarity search
        docs = await asyncio.to_thread(
            vectorstore.similarity_search,
            query,
            k=max_learnings,
        )
        
        # Convert to Learning dicts (matching KBContext.learnings schema)
        learnings = []
        for doc in docs:
            learning = {
                "content": doc.page_content,
                "learnt_from": doc.metadata.get("learnt_from"),
                "pr": doc.metadata.get("pr"),
                "file": doc.metadata.get("file"),
                "timestamp": doc.metadata.get("timestamp"),
                "relevance_score": doc.metadata.get("score", 0.0),
            }
            learnings.append(learning)
        
        return KBContext(
            learnings=learnings,
            query_used=query,
        )
    
    async def _query_api(
        self,
        query: str,
        max_learnings: int,
    ) -> KBContext:
        """
        Query the KB API for relevant learnings.
        
        Note: The current KB API doesn't have a query endpoint,
        so this is a placeholder for future implementation.
        """
        # The KB service currently only has write endpoints
        # A query endpoint would need to be added
        logger.info(f"KB API query not implemented, query: {query[:100]}...")
        
        # Return empty context for now
        return KBContext(
            learnings=[],
            query_used=query,
            source="api",
        )
    
    async def add_learning(
        self,
        learning: str,
        learnt_from: Optional[str] = None,
        pr: Optional[str] = None,
        file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a new learning to the Knowledge Base.
        
        Args:
            learning: The insight or learning to store
            learnt_from: Source/author of the learning
            pr: Related PR reference (e.g., "org/repo#123")
            file: Related file reference (e.g., "path/to/file.py:10-20")
            
        Returns:
            Task ID for tracking the async processing, or None on failure
        """
        payload = {
            "learning": learning,
            "learnt_from": learnt_from,
            "pr": pr,
            "file": file,
        }
        
        payload = {k: v for k, v in payload.items() if v is not None}
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self.http_client.post(
                    "/learnings",
                    json=payload,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Learning queued with task ID: {data.get('task_id')}")
                    return data.get("task_id")
                else:
                    logger.warning(
                        f"Failed to add learning: {response.status_code} - {response.text}"
                    )
                    
            except httpx.RequestError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        return None
    
    async def add_learnings_batch(
        self,
        learnings: List[Dict[str, Any]],
    ) -> List[Optional[str]]:
        """
        Add multiple learnings in batch.
        
        Args:
            learnings: List of learning dicts with keys:
                - learning: str (required)
                - learnt_from: str (optional)
                - pr: str (optional)
                - file: str (optional)
                
        Returns:
            List of task IDs (None for failed submissions)
        """
        payload = [
            {k: v for k, v in learning.items() if v is not None}
            for learning in learnings
        ]
        
        try:
            response = await self.http_client.post(
                "/learnings/batch",
                json=payload,
            )
            
            if response.status_code == 200:
                results = response.json()
                return [r.get("task_id") if r.get("status") == "queued" else None for r in results]
            else:
                logger.warning(f"Batch add failed: {response.status_code}")
                return [None] * len(learnings)
                
        except httpx.RequestError as e:
            logger.warning(f"Batch request failed: {e}")
            return [None] * len(learnings)
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Check the status of a learning processing task.
        
        Args:
            task_id: The task ID returned from add_learning
            
        Returns:
            Task status dict with keys: task_id, status, result
        """
        try:
            response = await self.http_client.get(f"/tasks/{task_id}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get task status: {response.status_code}")
                return None
                
        except httpx.RequestError as e:
            logger.warning(f"Task status request failed: {e}")
            return None
    
    @staticmethod
    def build_file_reference(path: str, start_line: int, end_line: int) -> str:
        """
        Build a file reference string for a learning.
        
        Args:
            path: File path
            start_line: Starting line number
            end_line: Ending line number
            
        Returns:
            File reference in format "path/to/file.py:10-20"
        """
        return f"{path}:{start_line}-{end_line}"
    
    @staticmethod
    def build_pr_reference(owner: str, repo: str, pr_number: int) -> str:
        """
        Build a PR reference string for a learning.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            PR reference in format "owner/repo#123"
        """
        return f"{owner}/{repo}#{pr_number}"
