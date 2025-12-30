"""
Knowledge Base Client

Backend client for communicating with the Knowledge Base service.
Used to store and retrieve learnings from user feedback.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class KnowledgeBaseClient:
    """
    Client for interacting with the Knowledge Base service.
    
    The KB service stores learnings extracted from user feedback
    and provides semantic search for context during reviews.
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize the KB client.
        
        Args:
            base_url: Base URL of the KB service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("KNOWLEDGE_BASE_URL", "http://localhost:8000")
        self.timeout = timeout
        # KB_ENABLED=true to enable, anything else (or missing) disables
        self.enabled = os.getenv("KB_ENABLED", "false").lower() == "true"
        
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"KB client initialized: url={self.base_url}, enabled={self.enabled}")
    
    async def _async_client(self) -> httpx.AsyncClient:
        """Get async client for async operations"""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
    
    def health_check(self) -> bool:
        """Check if KB service is healthy"""
        if not self.enabled:
            return False
        
        try:
            response = self._client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"KB health check failed: {e}")
            return False
    
    async def async_health_check(self) -> bool:
        """Async health check"""
        if not self.enabled:
            return False
        
        try:
            async with await self._async_client() as client:
                response = await client.get("/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"KB async health check failed: {e}")
            return False
    
    def store_learning(
        self,
        learning: str,
        category: str,
        learning_type: str,
        owner: str,
        repo: str,
        source_pr: str,
        learnt_from: str,
        confidence: float = 0.5,
        language: Optional[str] = None,
        file_pattern: Optional[str] = None,
        scope: str = "repo",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Store a new learning in the Knowledge Base.
        
        Args:
            learning: The learning statement
            category: Category (security, style, performance, etc.)
            learning_type: Type (correction, false_positive, etc.)
            owner: Repository owner
            repo: Repository name
            source_pr: Source PR reference (owner/repo#number)
            learnt_from: GitHub username who provided feedback
            confidence: Confidence score (0.0 - 1.0)
            language: Programming language (optional)
            file_pattern: File pattern (optional)
            scope: Scope of learning (repo, org, global)
            metadata: Additional metadata
            
        Returns:
            Response from KB service with learning_id, or None on failure
        """
        if not self.enabled:
            logger.debug("KB disabled, skipping store_learning")
            return None
        
        # Format payload to match KB service's LearningRequest schema
        payload = {
            "learning": learning,
            "learnt_from": learnt_from,
            "pr": source_pr,
            "file": file_pattern,
            "timestamp": datetime.utcnow().isoformat(),
            # Store additional metadata in the learning text itself for now
            # since KB service has a simpler schema
        }
        
        # Enrich the learning text with category/type info
        enriched_learning = f"[{category}] [{learning_type}] {learning}"
        if language:
            enriched_learning = f"[{language}] {enriched_learning}"
        payload["learning"] = enriched_learning
        
        try:
            response = self._client.post("/learnings", json=payload)
            response.raise_for_status()
            result = response.json()
            # KB service returns task_id, use that as learning_id
            learning_id = result.get("task_id")
            logger.info(f"Stored learning in KB: {learning_id}")
            return {"learning_id": learning_id, **result}
        except httpx.HTTPStatusError as e:
            logger.error(f"KB store_learning HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"KB store_learning failed: {e}")
            return None
    
    async def async_store_learning(
        self,
        learning: str,
        category: str,
        learning_type: str,
        owner: str,
        repo: str,
        source_pr: str,
        learnt_from: str,
        confidence: float = 0.5,
        language: Optional[str] = None,
        file_pattern: Optional[str] = None,
        scope: str = "repo",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Async version of store_learning"""
        if not self.enabled:
            return None
        
        # Format payload to match KB service's LearningRequest schema
        payload = {
            "learning": learning,
            "learnt_from": learnt_from,
            "pr": source_pr,
            "file": file_pattern,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Enrich the learning text with category/type info
        enriched_learning = f"[{category}] [{learning_type}] {learning}"
        if language:
            enriched_learning = f"[{language}] {enriched_learning}"
        payload["learning"] = enriched_learning
        
        try:
            async with await self._async_client() as client:
                response = await client.post("/learnings", json=payload)
                response.raise_for_status()
                result = response.json()
                learning_id = result.get("task_id")
                logger.info(f"Stored learning in KB: {learning_id}")
                return {"learning_id": learning_id, **result}
        except Exception as e:
            logger.error(f"KB async_store_learning failed: {e}")
            return None
    
    def search_learnings(
        self,
        query: str,
        owner: str,
        repo: str,
        k: int = 5,
        category: Optional[str] = None,
        language: Optional[str] = None,
        min_confidence: float = 0.3,
        include_org_learnings: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant learnings in the Knowledge Base.
        
        Args:
            query: Search query (semantic search)
            owner: Repository owner
            repo: Repository name
            k: Number of results to return
            category: Filter by category
            language: Filter by language
            min_confidence: Minimum confidence threshold
            include_org_learnings: Include org-level learnings
            
        Returns:
            List of matching learnings
        """
        if not self.enabled:
            return []
        
        params = {
            "q": query,
            "owner": owner,
            "repo": repo,
            "k": k,
            "min_confidence": min_confidence,
            "include_org": include_org_learnings
        }
        
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        
        try:
            response = self._client.get("/learnings/search", params=params)
            response.raise_for_status()
            result = response.json()
            learnings = result.get("learnings", [])
            logger.info(f"Found {len(learnings)} learnings for query: {query[:50]}...")
            return learnings
        except Exception as e:
            logger.error(f"KB search_learnings failed: {e}")
            return []
    
    async def async_search_learnings(
        self,
        query: str,
        owner: str,
        repo: str,
        k: int = 5,
        category: Optional[str] = None,
        language: Optional[str] = None,
        min_confidence: float = 0.3,
        include_org_learnings: bool = True
    ) -> List[Dict[str, Any]]:
        """Async version of search_learnings"""
        if not self.enabled:
            return []
        
        params = {
            "q": query,
            "owner": owner,
            "repo": repo,
            "k": k,
            "min_confidence": min_confidence,
            "include_org": include_org_learnings
        }
        
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        
        try:
            async with await self._async_client() as client:
                response = await client.get("/learnings/search", params=params)
                response.raise_for_status()
                result = response.json()
                return result.get("learnings", [])
        except Exception as e:
            logger.error(f"KB async_search_learnings failed: {e}")
            return []
    
    def get_pr_context_learnings(
        self,
        owner: str,
        repo: str,
        pr_description: str,
        changed_files: List[str],
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get contextual learnings relevant to a PR.
        
        This is used during code review to fetch learnings
        that might be relevant to the current PR being reviewed.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_description: PR description/title
            changed_files: List of changed file paths
            k: Number of learnings to retrieve
            
        Returns:
            List of relevant learnings
        """
        if not self.enabled:
            return []
        
        payload = {
            "owner": owner,
            "repo": repo,
            "pr_description": pr_description,
            "changed_files": changed_files,
            "k": k
        }
        
        try:
            response = self._client.post("/learnings/pr-context", json=payload)
            response.raise_for_status()
            result = response.json()
            # Response is {"query": "...", "total": N, "learnings": [...]}
            learnings = result.get("learnings", [])
            logger.info(f"Retrieved {len(learnings)} contextual learnings for PR")
            return learnings
        except Exception as e:
            logger.error(f"KB get_pr_context_learnings failed: {e}")
            return []
    
    async def async_get_pr_context_learnings(
        self,
        owner: str,
        repo: str,
        pr_description: str,
        changed_files: List[str],
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """Async version of get_pr_context_learnings"""
        if not self.enabled:
            return []
        
        payload = {
            "owner": owner,
            "repo": repo,
            "pr_description": pr_description,
            "changed_files": changed_files,
            "k": k
        }
        
        try:
            async with await self._async_client() as client:
                response = await client.post("/learnings/pr-context", json=payload)
                response.raise_for_status()
                result = response.json()
                # Response is {"query": "...", "total": N, "learnings": [...]}
                return result.get("learnings", [])
        except Exception as e:
            logger.error(f"KB async_get_pr_context_learnings failed: {e}")
            return []
    
    def update_learning_feedback(
        self,
        learning_id: str,
        positive: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Update a learning based on additional feedback.
        
        Args:
            learning_id: ID of the learning in KB
            positive: True for positive feedback, False for negative
            
        Returns:
            Updated learning info or None on failure
        """
        if not self.enabled:
            return None
        
        payload = {
            "learning_id": learning_id,
            "feedback": "positive" if positive else "negative",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            response = self._client.post("/learnings/feedback", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"KB update_learning_feedback failed: {e}")
            return None
    
    def deactivate_learning(self, learning_id: str) -> bool:
        """
        Deactivate a learning (soft delete).
        
        Args:
            learning_id: ID of the learning to deactivate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            response = self._client.delete(f"/learnings/{learning_id}")
            response.raise_for_status()
            logger.info(f"Deactivated learning: {learning_id}")
            return True
        except Exception as e:
            logger.error(f"KB deactivate_learning failed: {e}")
            return False
    
    def format_learnings_for_prompt(
        self,
        learnings: List[Dict[str, Any]],
        max_learnings: int = 5
    ) -> str:
        """
        Format learnings for inclusion in LLM prompt.
        
        Args:
            learnings: List of learnings from KB
            max_learnings: Maximum number to include
            
        Returns:
            Formatted string for prompt
        """
        if not learnings:
            return ""
        
        lines = ["\n## Relevant Learnings from Past Reviews\n"]
        lines.append("Consider these learnings when reviewing:\n")
        
        for i, learning in enumerate(learnings[:max_learnings], 1):
            text = learning.get("learning", learning.get("learning_text", ""))
            # KB returns 'score' from search, use that as confidence
            score = learning.get("score", learning.get("confidence", learning.get("confidence_score", 0.5)))
            learnt_from = learning.get("learnt_from", "unknown")
            
            lines.append(f"{i}. {text}")
            lines.append(f"   _(Source: {learnt_from}, Relevance: {score:.0%})_\n")
        
        return "\n".join(lines)
    
    def close(self):
        """Close the HTTP client"""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Singleton instance
_kb_client: Optional[KnowledgeBaseClient] = None


def get_kb_client() -> KnowledgeBaseClient:
    """Get the global KB client instance"""
    global _kb_client
    if _kb_client is None:
        _kb_client = KnowledgeBaseClient()
    return _kb_client
