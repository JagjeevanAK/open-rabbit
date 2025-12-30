"""
Subagents module

Contains specialized agents for specific tasks within the code review pipeline.
"""

from .feedback_agent import FeedbackProcessor, LearningType, LearningCategory
from .base_agent import BaseAgent, MockAgent
from .parser_agent import ParserAgent, SECURITY_PATTERNS
from .review_agent import ReviewAgent

# Alias for consistency
FeedbackAgent = FeedbackProcessor

__all__ = [
    # Feedback
    "FeedbackProcessor",
    "FeedbackAgent",  # Alias
    "LearningType", 
    "LearningCategory",
    # Base
    "BaseAgent",
    "MockAgent",
    # Parser
    "ParserAgent",
    "SECURITY_PATTERNS",
    # Review
    "ReviewAgent",
]
