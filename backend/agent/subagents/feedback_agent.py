"""
Feedback Processor Agent

LLM-powered agent that processes user feedback on AI review comments
and extracts structured learnings for the Knowledge Base.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LearningType(str, Enum):
    """Types of learnings extracted from feedback"""
    CORRECTION = "correction"
    FALSE_POSITIVE = "false_positive"
    STYLE_PREFERENCE = "style_preference"
    BEST_PRACTICE = "best_practice"
    CLARIFICATION = "clarification"
    APPRECIATION = "appreciation"
    OTHER = "other"


class LearningCategory(str, Enum):
    """Categories for learnings"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error_handling"
    ARCHITECTURE = "architecture"
    NAMING = "naming"
    OTHER = "other"


from ..prompt import FEEDBACK_PROCESSOR_PROMPT



class FeedbackProcessor:
    """
    Processes user feedback on AI review comments and extracts learnings.
    
    Uses LLM to understand the context and extract actionable learnings
    that can improve future code reviews.
    """
    
    def __init__(self, use_mock: bool = True):
        """
        Initialize the feedback processor.
        
        Args:
            use_mock: If True, use mock responses instead of real LLM API calls
        """
        self.use_mock = use_mock
        self._llm_client = None
        
        if not use_mock:
            self._init_llm_client()
    
    def _init_llm_client(self):
        """Initialize the real LLM client (OpenAI/Anthropic)"""
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self._llm_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                self._llm_provider = "anthropic"
                logger.info("Initialized Anthropic client for feedback processing")
            except ImportError:
                logger.warning("anthropic package not installed, falling back to mock")
                self.use_mock = True
        elif os.getenv("OPENAI_API_KEY"):
            try:
                import openai
                self._llm_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self._llm_provider = "openai"
                logger.info("Initialized OpenAI client for feedback processing")
            except ImportError:
                logger.warning("openai package not installed, falling back to mock")
                self.use_mock = True
        else:
            logger.warning("No API key found, using mock LLM for feedback processing")
            self.use_mock = True
    
    def process_feedback(
        self,
        ai_comment: str,
        feedback_type: str,
        user_feedback: Optional[str] = None,
        reaction_type: Optional[str] = None,
        file_path: Optional[str] = None,
        owner: str = "",
        repo: str = ""
    ) -> Dict[str, Any]:
        """
        Process user feedback and extract learning.
        
        Args:
            ai_comment: The original AI-generated review comment
            feedback_type: 'reaction' or 'reply'
            user_feedback: User's reply text (if reply type)
            reaction_type: Reaction emoji type (if reaction type)
            file_path: Path of the file being reviewed
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Extracted learning information
        """
        logger.info(f"Processing feedback: type={feedback_type}, reaction={reaction_type}, has_reply={bool(user_feedback)}")
        
        if self.use_mock:
            return self._mock_process(
                ai_comment, feedback_type, user_feedback, 
                reaction_type, file_path, owner, repo
            )
        
        return self._llm_process(
            ai_comment, feedback_type, user_feedback,
            reaction_type, file_path, owner, repo
        )
    
    def _build_prompt(
        self,
        ai_comment: str,
        feedback_type: str,
        user_feedback: Optional[str],
        reaction_type: Optional[str],
        file_path: Optional[str],
        owner: str,
        repo: str
    ) -> str:
        """Build the prompt for LLM processing"""
        feedback_info = f"""
## Feedback to Analyze

**Repository**: {owner}/{repo}
**File Path**: {file_path or "N/A (general comment)"}

**AI Comment**:
{ai_comment}

**Feedback Type**: {feedback_type}
"""
        if feedback_type == "reaction":
            feedback_info += f"**Reaction**: {reaction_type}\n"
        
        if user_feedback:
            feedback_info += f"""
**User Reply**:
{user_feedback}
"""
        
        return FEEDBACK_PROCESSOR_PROMPT + feedback_info
    
    def _llm_process(
        self,
        ai_comment: str,
        feedback_type: str,
        user_feedback: Optional[str],
        reaction_type: Optional[str],
        file_path: Optional[str],
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """Process feedback using real LLM"""
        prompt = self._build_prompt(
            ai_comment, feedback_type, user_feedback,
            reaction_type, file_path, owner, repo
        )
        
        try:
            content: str = ""
            if self._llm_provider == "anthropic" and self._llm_client:
                response = self._llm_client.messages.create(  # type: ignore
                    model="claude-3-haiku-20240307",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text  # type: ignore
            elif self._llm_client:  # openai
                response = self._llm_client.chat.completions.create(  # type: ignore
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024
                )
                content = response.choices[0].message.content or ""  # type: ignore
            
            if not content:
                raise ValueError("Empty response from LLM")
            
            # Parse JSON from response
            result = self._parse_llm_response(content)
            result["processed_at"] = datetime.utcnow().isoformat()
            result["mock"] = False
            
            return result
            
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            # Fall back to mock on error
            return self._mock_process(
                ai_comment, feedback_type, user_feedback,
                reaction_type, file_path, owner, repo
            )
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        # Try to extract JSON from the response
        try:
            # Look for JSON block
            if "```json" in content:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.index("```") + 3
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content:
                json_start = content.index("{")
                json_end = content.rindex("}") + 1
                json_str = content[json_start:json_end]
            else:
                raise ValueError("No JSON found in response")
            
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return {
                "should_create_learning": False,
                "learning": "",
                "learning_type": "other",
                "category": "other",
                "confidence": 0.0,
                "language": None,
                "file_pattern": None,
                "reasoning": f"Failed to parse response: {str(e)}"
            }
    
    def _mock_process(
        self,
        ai_comment: str,
        feedback_type: str,
        user_feedback: Optional[str],
        reaction_type: Optional[str],
        file_path: Optional[str],
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """Generate mock learning extraction for testing"""
        logger.info("Using mock feedback processing")
        
        # Infer language from file path
        language = None
        if file_path:
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".jsx": "javascript",
                ".go": "go",
                ".rs": "rust",
                ".java": "java",
            }
            for ext, lang in ext_map.items():
                if file_path.endswith(ext):
                    language = lang
                    break
        
        # Handle reaction-only feedback
        if feedback_type == "reaction" and not user_feedback:
            positive_reactions = {"thumbs_up", "heart", "hooray", "rocket"}
            negative_reactions = {"thumbs_down", "confused"}
            
            if reaction_type in positive_reactions:
                return {
                    "should_create_learning": True,
                    "learning": f"Comment style was well-received: '{ai_comment[:100]}...'",
                    "learning_type": LearningType.APPRECIATION.value,
                    "category": LearningCategory.OTHER.value,
                    "confidence": 0.4,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": f"Positive reaction ({reaction_type}) indicates helpful comment",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
            elif reaction_type in negative_reactions:
                return {
                    "should_create_learning": False,
                    "learning": "",
                    "learning_type": LearningType.FALSE_POSITIVE.value,
                    "category": LearningCategory.OTHER.value,
                    "confidence": 0.0,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": f"Negative reaction ({reaction_type}) but no explanation provided",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
            else:
                return {
                    "should_create_learning": False,
                    "learning": "",
                    "learning_type": LearningType.OTHER.value,
                    "category": LearningCategory.OTHER.value,
                    "confidence": 0.0,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": f"Neutral reaction ({reaction_type})",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
        
        # Handle reply feedback
        if user_feedback:
            # Simple heuristics for mock
            feedback_lower = user_feedback.lower()
            
            # Detect correction patterns
            if any(phrase in feedback_lower for phrase in [
                "actually", "that's not", "incorrect", "wrong", "no,", "but "
            ]):
                return {
                    "should_create_learning": True,
                    "learning": f"Review correction from {owner}/{repo}: {user_feedback[:200]}",
                    "learning_type": LearningType.CORRECTION.value,
                    "category": self._infer_category(ai_comment, user_feedback),
                    "confidence": 0.75,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": "User reply contains correction language",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
            
            # Detect style preference patterns
            if any(phrase in feedback_lower for phrase in [
                "we prefer", "our style", "in this repo", "our convention", "team prefers"
            ]):
                return {
                    "should_create_learning": True,
                    "learning": f"Style preference for {owner}/{repo}: {user_feedback[:200]}",
                    "learning_type": LearningType.STYLE_PREFERENCE.value,
                    "category": LearningCategory.STYLE.value,
                    "confidence": 0.85,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": "User reply indicates team style preference",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
            
            # Detect false positive patterns
            if any(phrase in feedback_lower for phrase in [
                "not an issue", "intentional", "by design", "false positive"
            ]):
                return {
                    "should_create_learning": True,
                    "learning": f"False positive pattern in {owner}/{repo}: {user_feedback[:200]}",
                    "learning_type": LearningType.FALSE_POSITIVE.value,
                    "category": self._infer_category(ai_comment, user_feedback),
                    "confidence": 0.8,
                    "language": language,
                    "file_pattern": None,
                    "reasoning": "User indicates the flagged issue was intentional/not an issue",
                    "processed_at": datetime.utcnow().isoformat(),
                    "mock": True
                }
            
            # Default: treat as clarification
            return {
                "should_create_learning": True,
                "learning": f"User clarification on review comment: {user_feedback[:200]}",
                "learning_type": LearningType.CLARIFICATION.value,
                "category": self._infer_category(ai_comment, user_feedback),
                "confidence": 0.6,
                "language": language,
                "file_pattern": None,
                "reasoning": "User provided additional context via reply",
                "processed_at": datetime.utcnow().isoformat(),
                "mock": True
            }
        
        # Default case
        return {
            "should_create_learning": False,
            "learning": "",
            "learning_type": LearningType.OTHER.value,
            "category": LearningCategory.OTHER.value,
            "confidence": 0.0,
            "language": language,
            "file_pattern": None,
            "reasoning": "Insufficient information to extract learning",
            "processed_at": datetime.utcnow().isoformat(),
            "mock": True
        }
    
    def _infer_category(self, ai_comment: str, user_feedback: str) -> str:
        """Infer category from comment and feedback content"""
        combined = (ai_comment + " " + user_feedback).lower()
        
        category_keywords = {
            LearningCategory.SECURITY.value: [
                "security", "vulnerability", "injection", "xss", "csrf", 
                "authentication", "authorization", "secret", "password"
            ],
            LearningCategory.PERFORMANCE.value: [
                "performance", "slow", "optimize", "cache", "memory", 
                "cpu", "latency", "efficient"
            ],
            LearningCategory.TESTING.value: [
                "test", "coverage", "mock", "assert", "spec", "unit test"
            ],
            LearningCategory.ERROR_HANDLING.value: [
                "error", "exception", "try", "catch", "handle", "throw"
            ],
            LearningCategory.DOCUMENTATION.value: [
                "document", "comment", "readme", "docstring", "jsdoc"
            ],
            LearningCategory.NAMING.value: [
                "name", "naming", "variable name", "function name", "convention"
            ],
            LearningCategory.ARCHITECTURE.value: [
                "architecture", "structure", "pattern", "design", "module"
            ],
            LearningCategory.STYLE.value: [
                "style", "format", "indent", "lint", "prettier", "eslint"
            ],
            LearningCategory.MAINTAINABILITY.value: [
                "maintain", "readable", "clean", "refactor", "complexity"
            ],
        }
        
        for category, keywords in category_keywords.items():
            if any(kw in combined for kw in keywords):
                return category
        
        return LearningCategory.OTHER.value
