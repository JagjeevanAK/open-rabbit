"""
Services module

Contains service clients for external integrations.
"""

from .kb_client import KnowledgeBaseClient, get_kb_client

__all__ = [
    "KnowledgeBaseClient",
    "get_kb_client",
]
