"""
Subagents module

Contains specialized agents for specific tasks within the code review pipeline.
"""

from .feedback_agent import FeedbackProcessor, LearningType, LearningCategory

__all__ = [
    "FeedbackProcessor",
    "LearningType", 
    "LearningCategory",
]
