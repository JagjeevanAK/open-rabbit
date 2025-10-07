"""
Configuration management for the Learnings subsystem.

Centralizes all environment variables and settings to ensure
clean dependency injection and testability.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Design principle: All external dependencies (DB URLs, API keys, model names)
    are configured here to enable easy testing and deployment.
    """
    
    # OpenAI Configuration
    openai_api_key: str = ""  # Required: Set in .env file
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    
    # Vector Database (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "learnings"
    qdrant_api_key: str | None = None
    
    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Application Settings
    max_learning_length: int = 500  # Max characters for a learning text
    embedding_dimensions: int = 3072  # text-embedding-3-large dimensions
    default_retrieval_k: int = 5
    
    # LLM Extraction Prompts
    extraction_system_prompt: str = """You are an expert at extracting actionable project learnings from code review comments.

Given a code review comment, extract the underlying best practice, convention, or learning that can be applied to future code reviews.

Guidelines:
- Extract the CORE INSIGHT, not just the specific fix
- Make it generalizable but still specific to the project's conventions
- Keep it concise (1-3 sentences max)
- Focus on "why" not just "what"
- If the comment is too vague or non-actionable, return "NO_LEARNING"

Examples:
Input: "Bump outdated dependencies to the latest stable versions and run npm audit."
Output: "The project requires regular dependency updates with security audits to ensure stability and security."

Input: "Use const instead of let for variables that don't change."
Output: "The project enforces immutable variable declarations using const to prevent accidental reassignments."

Input: "lgtm"
Output: "NO_LEARNING"
"""
    
    # FastAPI Configuration
    api_title: str = "Learnings API"
    api_description: str = "CodeRabbit-inspired learnings ingestion and retrieval system"
    api_version: str = "1.0.0"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.
    
    Using lru_cache ensures we only load environment variables once,
    improving performance and enabling easy dependency injection in FastAPI.
    """
    return Settings()
