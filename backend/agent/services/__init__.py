"""
Services module for the agent.

Contains external service integrations.
"""

from .kb_client import KBClient, KBClientConfig

__all__ = [
    "KBClient",
    "KBClientConfig",
]
