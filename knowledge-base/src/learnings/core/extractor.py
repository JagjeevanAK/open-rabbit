"""
Learning extraction logic using LLM-based summarization.

This module handles the conversion of raw code review comments into
normalized, actionable project learnings using OpenAI's chat models.
"""

from typing import Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import re

from src.learnings.core.config import Settings


class LearningExtractor:
    """
    Extracts structured learnings from raw review comments using LLM.
    
    Design rationale:
    - Uses LangChain for clean LLM abstraction and testability
    - Applies consistent prompt engineering to ensure quality extractions
    - Returns None if comment is not actionable (e.g., "lgtm", "+1")
    
    This matches CodeRabbit's approach of distilling review feedback into
    reusable knowledge that can inform future reviews.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            # api_key=settings.openai_api_key
        )
        self.system_prompt = SystemMessage(content=settings.extraction_system_prompt)
    
    def extract_learning(
        self,
        raw_comment: str,
        code_snippet: Optional[str] = None,
        language: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract a normalized learning from a raw review comment.
        
        Args:
            raw_comment: The original review comment text
            code_snippet: Optional code context
            language: Optional programming language
        
        Returns:
            Extracted learning text or None if not actionable
        
        Example:
            >>> extractor.extract_learning("Use const instead of let here.")
            "The project enforces immutable variable declarations using const."
        """
        # Pre-filter obvious non-learnings
        if self._is_trivial_comment(raw_comment):
            return None
        
        # Build context-aware prompt
        user_content = self._build_extraction_prompt(raw_comment, code_snippet, language)
        
        try:
            messages = [self.system_prompt, HumanMessage(content=user_content)]
            response = self.llm.invoke(messages)
            
            learning_text = self._get_response_text(response.content)
            
            # Check if LLM indicated no learning
            if learning_text == "NO_LEARNING" or learning_text.startswith("NO_LEARNING"):
                return None
            
            # Truncate if too long
            if len(learning_text) > self.settings.max_learning_length:
                learning_text = learning_text[:self.settings.max_learning_length] + "..."
            
            return learning_text
            
        except Exception as e:
            # Log error in production; return None to avoid breaking the pipeline
            print(f"Error extracting learning: {e}")
            return None
    
    def _get_response_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "".join(parts).strip()
        return str(content).strip()
    
    def _is_trivial_comment(self, comment: str) -> bool:
        """
        Quick heuristic filter for obviously non-actionable comments.
        
        Avoids wasting LLM calls on "lgtm", "+1", "thanks", etc.
        """
        trivial_patterns = [
            r"^lgtm\s*$",
            r"^\+1\s*$",
            r"^👍\s*$",
            r"^thanks?\s*!?\s*$",
            r"^ok\s*$",
            r"^approved\s*$",
            r"^nice\s*!?\s*$",
        ]
        
        comment_lower = comment.lower().strip()
        
        for pattern in trivial_patterns:
            if re.match(pattern, comment_lower, re.IGNORECASE):
                return True
        
        # Also filter very short comments (likely not substantive)
        if len(comment_lower) < 10:
            return True
        
        return False
    
    def _build_extraction_prompt(
        self,
        raw_comment: str,
        code_snippet: Optional[str],
        language: Optional[str]
    ) -> str:
        """Build the user prompt with all available context."""
        parts = [f"Review Comment:\n{raw_comment}"]
        
        if code_snippet:
            parts.append(f"\nCode Context:\n```{language or ''}\n{code_snippet}\n```")
        
        if language:
            parts.append(f"\nLanguage: {language}")
        
        parts.append("\nExtract the learning:")
        
        return "\n".join(parts)
