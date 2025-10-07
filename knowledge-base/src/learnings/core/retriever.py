"""
Retriever module for semantic search and context injection.

Provides high-level API for retrieving relevant learnings
and formatting them for LLM context injection.
"""

from typing import List, Optional
import time

from src.learnings.core.models import Learning, LearningSearchRequest, LearningSearchResponse
from src.learnings.core.storage import LearningStorage
from src.learnings.core.config import Settings


def get_short_file_path(learning: Learning) -> str:
    """Get shortened file path for display."""
    parts = learning.source.file_path.split('/')
    if len(parts) > 2:
        return f".../{'/'.join(parts[-2:])}"
    return learning.source.file_path

class LearningRetriever:
    """
    High-level interface for learning retrieval and context formatting.
    
    This class abstracts the storage layer and provides:
    1. Semantic search with filtering
    2. Context formatting for LLM prompt injection
    3. Ranking and deduplication logic
    
    """
    
    def __init__(self, storage: LearningStorage, settings: Settings):
        self.storage = storage
        self.settings = settings
    
    def search(
        self,
        request: LearningSearchRequest
    ) -> LearningSearchResponse:
        """
        Perform semantic search for relevant learnings.
        
        Args:
            request: Search request with query and filters
        
        Returns:
            Search response with ranked results and metadata
        """
        start_time = time.time()
        
        results = self.storage.search_similar(
            query=request.query,
            k=request.k,
            repo_filter=request.repo_filter,
            language_filter=request.language_filter,
            min_confidence=request.min_confidence
        )
        
        # Apply additional ranking/filtering logic here if needed
        # e.g., boost recent learnings, weight by feedback type, etc.
        ranked_results = self._rank_results(results, request.query)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return LearningSearchResponse(
            query=request.query,
            results=ranked_results,
            total_results=len(ranked_results),
            search_time_ms=round(elapsed_ms, 2)
        )
    
    def _rank_results(
        self,
        results: List[Learning],
        query: str
    ) -> List[Learning]:
        """
        Apply custom ranking logic beyond vector similarity.
        
        Considerations:
        - Boost learnings with positive feedback (ACCEPTED, THANKED)
        - Penalize learnings with negative feedback (REJECTED)
        - Favor recent learnings over old ones
        - Weight by confidence score
        
        For now, we rely on vector similarity + confidence score.
        """
        # Simple confidence-based filtering
        return [l for l in results if l.confidence_score >= 0.3]
    
    def format_for_context(
        self,
        learnings: List[Learning],
        max_learnings: int = 5
    ) -> str:
        """
        Format retrieved learnings for LLM context injection.
        
        Returns a formatted string ready to be inserted into a review prompt.
        
        Example output:
        ```
        ## Relevant Project Learnings:
        
        1. [JavaScript | package.json] The project requires regular dependency 
           updates with security audits to ensure stability.
           
        2. [Python | config.py] The project enforces type hints on all function
           signatures for better IDE support.
        ```
        """
        if not learnings:
            return "## Relevant Project Learnings:\nNo prior learnings found for this context."
        
        # Limit to max_learnings
        learnings = learnings[:max_learnings]
        
        lines = ["## Relevant Project Learnings:\n"]
        
        for i, learning in enumerate(learnings, 1):
            # Format metadata
            lang = learning.language or "Unknown"
            file = get_short_file_path(learning)
            
            # Format feedback signal
            feedback_emoji = self._feedback_emoji(learning.feedback_type)
            
            # Build learning entry
            entry = f"{i}. [{lang} | {file}] {feedback_emoji}\n   {learning.learning_text}\n"
            
            # Optionally include code context
            if learning.code_context and len(learning.code_context) < 200:
                entry += f"   Context: `{learning.code_context[:150]}...`\n"
            
            lines.append(entry)
        
        return "\n".join(lines)
    
    def _feedback_emoji(self, feedback_type) -> str:
        """Map feedback type to emoji for visual clarity."""
        if not feedback_type:
            return ""
        
        emoji_map = {
            "ACCEPTED": "✅",
            "THANKED": "🙏",
            "MODIFIED": "🔄",
            "REJECTED": "❌",
            "DEBATED": "💬",
            "IGNORED": "👀"
        }
        
        return emoji_map.get(feedback_type.value.upper(), "")
    
    def get_learnings_for_pr_context(
        self,
        pr_description: str,
        changed_files: List[str],
        repo_name: str,
        k: int = 5
    ) -> List[Learning]:
        """
        Retrieve learnings relevant to a specific PR context.
        
        This is the primary method used by the review agent to inject
        context-aware learnings into review prompts.
        
        Args:
            pr_description: PR title and description
            changed_files: List of file paths in the PR
            repo_name: Repository identifier
            k: Number of learnings to retrieve
        
        Returns:
            List of relevant learnings
        """
        # Build composite query from PR context
        query_parts = [pr_description]
        
        # Extract file types for language filtering
        languages = set()
        for file_path in changed_files:
            lang = self._infer_language(file_path)
            if lang:
                languages.add(lang)
        
        # Perform search (no language filter to allow cross-language learnings)
        request = LearningSearchRequest(
            query=" ".join(query_parts),
            k=k * 2,  # Retrieve more, then filter
            repo_filter=repo_name,
            min_confidence=0.5
        )
        
        response = self.search(request)
        
        # Prioritize learnings from files in this PR
        prioritized = self._prioritize_by_file_relevance(
            response.results,
            changed_files
        )
        
        return prioritized[:k]
    
    def _prioritize_by_file_relevance(
        self,
        learnings: List[Learning],
        changed_files: List[str]
    ) -> List[Learning]:
        """
        Rerank learnings based on file path similarity.
        
        Learnings from the same file or directory get higher priority.
        """
        scored_learnings = []
        
        for learning in learnings:
            score = learning.confidence_score
            
            # Boost if same file
            if any(learning.source.file_path == f for f in changed_files):
                score += 0.3
            
            # Boost if same directory
            elif any(learning.source.file_path.split('/')[0] == f.split('/')[0] for f in changed_files):
                score += 0.1
            
            scored_learnings.append((score, learning))
        
        # Sort by score descending
        scored_learnings.sort(key=lambda x: x[0], reverse=True)
        
        return [l for _, l in scored_learnings]
    
    def _infer_language(self, file_path: str) -> Optional[str]:
        """Infer programming language from file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".md": "markdown",
        }
        
        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang
        
        return None
