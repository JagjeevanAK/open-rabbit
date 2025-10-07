"""
Knowledge Base Retrieval Tool for LangChain Agent

This tool integrates with the knowledge-base service to retrieve
relevant learnings from past code reviews and inject them into
the agent's context for enhanced code review suggestions.
"""

from langchain_core.tools import tool
from typing import Optional, List, Dict, Any
import os
import httpx
from datetime import datetime


# Configuration
KNOWLEDGE_BASE_URL = os.getenv("KNOWLEDGE_BASE_URL", "http://localhost:8000")
KNOWLEDGE_BASE_TIMEOUT = int(os.getenv("KNOWLEDGE_BASE_TIMEOUT", "10"))


class KnowledgeBaseClient:
    """Client for interacting with the knowledge-base service."""
    
    def __init__(self, base_url: str = KNOWLEDGE_BASE_URL, timeout: int = KNOWLEDGE_BASE_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    def search_learnings(
        self,
        query: str,
        k: int = 5,
        repo_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        min_confidence: float = 0.3
    ) -> Dict[str, Any]:
        """
        Search for relevant learnings using semantic similarity.
        
        Args:
            query: Search query text
            k: Number of results to return (1-50)
            repo_filter: Filter by repository name
            language_filter: Filter by programming language
            min_confidence: Minimum confidence score (0.0-1.0)
        
        Returns:
            Dictionary with search results
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                params = {
                    "q": query,
                    "k": k,
                    "min_confidence": min_confidence
                }
                
                if repo_filter:
                    params["repo"] = repo_filter
                if language_filter:
                    params["language"] = language_filter
                
                response = client.get(
                    f"{self.base_url}/learnings/search",
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            return {
                "error": f"Failed to search learnings: {str(e)}",
                "query": query,
                "results": [],
                "total_results": 0
            }
    
    def get_pr_context_learnings(
        self,
        pr_description: str,
        changed_files: List[str],
        repo_name: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve learnings relevant to a specific PR context.
        
        Args:
            pr_description: Description of the pull request
            changed_files: List of files changed in the PR
            repo_name: Repository name
            k: Number of results to return
        
        Returns:
            List of relevant learnings
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                payload = {
                    "pr_description": pr_description,
                    "changed_files": changed_files,
                    "repo_name": repo_name,
                    "k": k
                }
                
                response = client.post(
                    f"{self.base_url}/learnings/pr-context",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            return []


def format_learnings_for_context(learnings: List[Dict[str, Any]]) -> str:
    """
    Format retrieved learnings into a structured prompt section.
    
    Args:
        learnings: List of learning dictionaries
    
    Returns:
        Formatted string for prompt injection
    """
    if not learnings:
        return "No relevant project learnings found for this context."
    
    formatted = "## 📚 Relevant Project Learnings\n\n"
    formatted += "The following learnings have been extracted from past code reviews in this project:\n\n"
    
    for idx, learning in enumerate(learnings, 1):
        learning_text = learning.get("learning_text", "")
        language = learning.get("language", "unknown")
        feedback_type = learning.get("feedback_type", "unknown")
        confidence = learning.get("confidence_score", 0.0)
        source = learning.get("source", {})
        
        # Get short file path
        file_path = source.get("file_path", "unknown")
        path_parts = file_path.split('/')
        if len(path_parts) > 2:
            short_path = f".../{'/'.join(path_parts[-2:])}"
        else:
            short_path = file_path
        
        formatted += f"### Learning {idx} ({language})\n"
        formatted += f"**Context**: {short_path} (PR #{source.get('pr_number', 'N/A')})\n"
        formatted += f"**Feedback**: {feedback_type} | **Confidence**: {confidence:.2f}\n\n"
        formatted += f"{learning_text}\n\n"
        
        # Add code context if available
        code_context = learning.get("code_context")
        if code_context:
            formatted += f"```{language}\n{code_context}\n```\n\n"
        
        formatted += "---\n\n"
    
    return formatted


# Initialize client
kb_client = KnowledgeBaseClient()


@tool
def search_knowledge_base(
    query: str,
    k: int = 5,
    repo_filter: Optional[str] = None,
    language_filter: Optional[str] = None
) -> str:
    """
    Search the knowledge base for relevant learnings from past code reviews.
    
    Use this tool to find project-specific best practices, coding patterns,
    and lessons learned from previous pull requests that can help inform
    your code review suggestions.
    
    Args:
        query: Natural language search query describing what to look for
               (e.g., "error handling patterns", "dependency management", "testing practices")
        k: Number of results to return (default: 5, max: 20)
        repo_filter: Optional repository filter (e.g., "owner/repo-name")
        language_filter: Optional language filter (e.g., "python", "javascript", "typescript")
    
    Returns:
        Formatted string containing relevant learnings with context
    
    Example usage:
        - "dependency management best practices"
        - "error handling in async functions"
        - "testing patterns for API endpoints"
    """
    # Limit k to reasonable bounds
    k = max(1, min(k, 20))
    
    # Search the knowledge base
    result = kb_client.search_learnings(
        query=query,
        k=k,
        repo_filter=repo_filter,
        language_filter=language_filter,
        min_confidence=0.3
    )
    
    # Check for errors
    if "error" in result:
        return f"⚠️ Knowledge base search failed: {result['error']}\n\nProceeding without historical context."
    
    # Format and return results
    learnings = result.get("results", [])
    total = result.get("total_results", 0)
    search_time = result.get("search_time_ms", 0)
    
    if total == 0:
        return f"No learnings found for query: '{query}'\n\nConsider using general best practices for this review."
    
    formatted = format_learnings_for_context(learnings)
    formatted += f"\n*Retrieved {total} learnings in {search_time:.2f}ms*\n"
    
    return formatted


@tool
def get_pr_learnings(
    pr_description: str,
    changed_files: List[str],
    repo_name: str,
    k: int = 5
) -> str:
    """
    Retrieve learnings specifically relevant to a pull request context.
    
    This tool analyzes the PR description and changed files to find the most
    relevant past learnings that apply to this specific code review scenario.
    
    Args:
        pr_description: Description or title of the pull request
        changed_files: List of file paths that were modified (e.g., ["src/main.py", "tests/test_main.py"])
        repo_name: Repository name in format "owner/repo"
        k: Number of learnings to retrieve (default: 5, max: 10)
    
    Returns:
        Formatted string containing relevant learnings for this PR
    
    Example usage:
        pr_description = "Add authentication middleware"
        changed_files = ["src/middleware/auth.py", "tests/test_auth.py"]
        repo_name = "acme/api-service"
    """
    # Limit k to reasonable bounds
    k = max(1, min(k, 10))
    
    # Get PR-specific learnings
    learnings = kb_client.get_pr_context_learnings(
        pr_description=pr_description,
        changed_files=changed_files,
        repo_name=repo_name,
        k=k
    )
    
    if not learnings:
        return f"No specific learnings found for this PR context.\n\n**PR**: {pr_description}\n**Files**: {', '.join(changed_files)}"
    
    formatted = f"## 🎯 PR-Specific Learnings\n\n"
    formatted += f"**Pull Request**: {pr_description}\n"
    formatted += f"**Modified Files**: {', '.join(changed_files[:3])}"
    if len(changed_files) > 3:
        formatted += f" and {len(changed_files) - 3} more"
    formatted += "\n\n"
    
    formatted += format_learnings_for_context(learnings)
    
    return formatted


@tool
def format_review_context(
    pr_description: str,
    changed_files: List[str],
    repo_name: str,
    additional_queries: Optional[List[str]] = None
) -> str:
    """
    Generate a comprehensive knowledge base context for code review.
    
    This is a high-level tool that combines both PR-specific learnings and
    additional topical searches to create a rich context for the review agent.
    
    Args:
        pr_description: Description of the pull request
        changed_files: List of modified file paths
        repo_name: Repository name
        additional_queries: Optional list of additional search queries for specific topics
    
    Returns:
        Comprehensive formatted context with all relevant learnings
    
    Example:
        format_review_context(
            pr_description="Add rate limiting to API endpoints",
            changed_files=["src/api/middleware.py", "tests/test_ratelimit.py"],
            repo_name="acme/api",
            additional_queries=["rate limiting best practices", "middleware patterns"]
        )
    """
    context = "# 🧠 Knowledge Base Context\n\n"
    context += f"*Retrieved on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*\n\n"
    
    # Get PR-specific learnings
    pr_learnings = kb_client.get_pr_context_learnings(
        pr_description=pr_description,
        changed_files=changed_files,
        repo_name=repo_name,
        k=5
    )
    
    if pr_learnings:
        context += "## 📋 Pull Request Context\n\n"
        context += f"**Description**: {pr_description}\n"
        context += f"**Files Changed**: {len(changed_files)}\n\n"
        context += format_learnings_for_context(pr_learnings)
    else:
        context += "## 📋 Pull Request Context\n\n"
        context += "No specific learnings found for this PR context.\n\n"
    
    # Get additional topical learnings
    if additional_queries:
        context += "## 🔍 Additional Relevant Topics\n\n"
        
        for query in additional_queries[:3]:  # Limit to 3 additional queries
            search_result = kb_client.search_learnings(
                query=query,
                k=3,
                repo_filter=repo_name,
                language_filter=None,
                min_confidence=0.4
            )
            
            learnings = search_result.get("results", [])
            if learnings:
                context += f"### Topic: {query}\n\n"
                context += format_learnings_for_context(learnings[:2])  # Show top 2
    
    context += "\n---\n\n"
    context += "*Use these learnings to inform your code review suggestions and ensure consistency with past feedback.*\n"
    
    return context


# Export all tools
__all__ = [
    "search_knowledge_base",
    "get_pr_learnings",
    "format_review_context",
    "KnowledgeBaseClient",
    "format_learnings_for_context"
]
