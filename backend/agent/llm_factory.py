"""
LLM Factory Module

Provides a unified interface for creating LLM instances across different providers:
- OpenAI (including GPT-5.1-Codex models via Responses API)
- Anthropic
- OpenRouter (access to multiple models via single API)

Usage:
    from agent.llm_factory import LLMFactory, LLMProvider

    # Create OpenAI instance
    llm = LLMFactory.create(LLMProvider.OPENAI, model="gpt-4")

    # Create Codex instance (uses Responses API)
    llm = LLMFactory.create(LLMProvider.OPENAI, model="gpt-5.1-codex-max")

    # Create Anthropic instance
    llm = LLMFactory.create(LLMProvider.ANTHROPIC, model="claude-3-opus-20240229")

    # Create OpenRouter instance (access any model)
    llm = LLMFactory.create(LLMProvider.OPENROUTER, model="anthropic/claude-3-opus")
"""

import os
import logging
from enum import Enum
from typing import Optional, Dict, Any, Union, List, Iterator
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)

# Models that require the Responses API
CODEX_MODELS = [
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
    "gpt-5-codex",
    "codex",
]


def is_codex_model(model: str) -> bool:
    """Check if a model requires the Responses API."""
    model_lower = model.lower()
    return any(codex in model_lower for codex in CODEX_MODELS)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


@dataclass
class LLMConfig:
    """Configuration for LLM instances."""
    provider: LLMProvider
    model: str
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


# Default models for each provider
DEFAULT_MODELS = {
    LLMProvider.OPENAI: "gpt-4-turbo-preview",
    LLMProvider.ANTHROPIC: "claude-3-sonnet-20240229",
    LLMProvider.OPENROUTER: "anthropic/claude-3-sonnet",
}

# Environment variable names for API keys
API_KEY_ENV_VARS = {
    LLMProvider.OPENAI: "OPENAI_API_KEY",
    LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
}


class LLMFactory:
    """
    Factory for creating LLM instances across different providers.
    
    Supports:
    - OpenAI (GPT-4, GPT-3.5, etc.)
    - Anthropic (Claude 3 family)
    - OpenRouter (unified access to multiple providers)
    """

    @staticmethod
    def create(
        provider: Union[LLMProvider, str],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        Create an LLM instance for the specified provider.

        Args:
            provider: The LLM provider (openai, anthropic, openrouter)
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            api_key: API key (uses environment variable if not provided)
            **kwargs: Additional provider-specific parameters

        Returns:
            BaseChatModel: LangChain chat model instance

        Raises:
            ValueError: If provider is not supported
            ImportError: If required provider package is not installed
        """
        # Normalize provider to enum
        if isinstance(provider, str):
            provider = LLMProvider(provider.lower())

        # Use default model if not specified
        if model is None:
            model = DEFAULT_MODELS.get(provider, "gpt-4-turbo-preview")

        # Get API key from environment if not provided
        if api_key is None:
            env_var = API_KEY_ENV_VARS.get(provider)
            if env_var:
                api_key = os.getenv(env_var)

        # Create config
        config = LLMConfig(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            extra_params=kwargs
        )

        # Dispatch to appropriate creator
        creators = {
            LLMProvider.OPENAI: LLMFactory._create_openai,
            LLMProvider.ANTHROPIC: LLMFactory._create_anthropic,
            LLMProvider.OPENROUTER: LLMFactory._create_openrouter,
        }

        creator = creators.get(provider)
        if creator is None:
            raise ValueError(f"Unsupported provider: {provider}")

        return creator(config)

    @staticmethod
    def _create_openai(config: LLMConfig) -> BaseChatModel:
        """Create OpenAI chat model."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai package is required for OpenAI support. "
                "Install it with: pip install langchain-openai"
            )

        params = {
            "model": config.model,
            "temperature": config.temperature,
        }

        if config.api_key:
            params["api_key"] = config.api_key

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens

        if config.base_url:
            params["base_url"] = config.base_url

        # Enable Responses API for Codex models (gpt-5.1-codex-max, etc.)
        # The Responses API is required for these models and provides better
        # support for agentic coding tasks
        if is_codex_model(config.model):
            params["use_responses_api"] = True
            logger.info(f"Using Responses API for Codex model: {config.model}")

        # Add any extra parameters
        params.update(config.extra_params or {})

        return ChatOpenAI(**params)

    @staticmethod
    def _create_anthropic(config: LLMConfig) -> BaseChatModel:
        """Create Anthropic chat model."""
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic package is required for Anthropic support. "
                "Install it with: pip install langchain-anthropic"
            )

        params = {
            "model": config.model,
            "temperature": config.temperature,
        }

        if config.api_key:
            params["anthropic_api_key"] = config.api_key

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens

        # Add any extra parameters
        params.update(config.extra_params or {})

        return ChatAnthropic(**params)

    @staticmethod
    def _create_openrouter(config: LLMConfig) -> BaseChatModel:
        """
        Create OpenRouter chat model.
        
        OpenRouter provides a unified API for accessing multiple LLM providers.
        Uses OpenAI-compatible API with custom base URL.
        """
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai package is required for OpenRouter support. "
                "Install it with: pip install langchain-openai"
            )

        # OpenRouter base URL
        base_url = "https://openrouter.ai/api/v1"

        params = {
            "model": config.model,
            "temperature": config.temperature,
            "base_url": base_url,
        }

        if config.api_key:
            params["api_key"] = config.api_key

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens

        # OpenRouter-specific headers
        default_headers = {
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://github.com/open-rabbit"),
            "X-Title": os.getenv("OPENROUTER_TITLE", "Open Rabbit Code Review"),
        }

        # Merge with any provided headers
        extra_headers = config.extra_params.pop("default_headers", {}) if config.extra_params else {}
        default_headers.update(extra_headers)
        params["default_headers"] = default_headers

        # Add any extra parameters
        params.update(config.extra_params or {})

        return ChatOpenAI(**params)

    @staticmethod
    def get_available_providers() -> list[LLMProvider]:
        """Return list of available providers based on installed packages."""
        available = []

        try:
            from langchain_openai import ChatOpenAI
            available.append(LLMProvider.OPENAI)
            available.append(LLMProvider.OPENROUTER)  # Uses OpenAI client
        except ImportError:
            pass

        try:
            from langchain_anthropic import ChatAnthropic
            available.append(LLMProvider.ANTHROPIC)
        except ImportError:
            pass

        return available

    @staticmethod
    def validate_config(
        provider: Union[LLMProvider, str],
        api_key: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Validate that a provider is properly configured.

        Args:
            provider: The LLM provider to validate
            api_key: Optional API key to check

        Returns:
            Tuple of (is_valid, message)
        """
        if isinstance(provider, str):
            try:
                provider = LLMProvider(provider.lower())
            except ValueError:
                return False, f"Unknown provider: {provider}"

        # Check if provider package is installed
        available = LLMFactory.get_available_providers()
        if provider not in available:
            return False, f"Provider {provider.value} is not installed"

        # Check for API key
        if api_key is None:
            env_var = API_KEY_ENV_VARS.get(provider)
            api_key = os.getenv(env_var) if env_var else None

        if not api_key:
            env_var = API_KEY_ENV_VARS.get(provider, "unknown")
            return False, f"API key not found. Set {env_var} environment variable"

        return True, "Configuration valid"


# Convenience functions for common use cases
def create_openai_llm(
    model: str = "gpt-4-turbo-preview",
    temperature: float = 0.2,
    **kwargs
) -> BaseChatModel:
    """Create an OpenAI LLM instance."""
    return LLMFactory.create(LLMProvider.OPENAI, model=model, temperature=temperature, **kwargs)


def create_anthropic_llm(
    model: str = "claude-3-sonnet-20240229",
    temperature: float = 0.2,
    **kwargs
) -> BaseChatModel:
    """Create an Anthropic LLM instance."""
    return LLMFactory.create(LLMProvider.ANTHROPIC, model=model, temperature=temperature, **kwargs)


def create_openrouter_llm(
    model: str = "anthropic/claude-3-sonnet",
    temperature: float = 0.2,
    **kwargs
) -> BaseChatModel:
    """Create an OpenRouter LLM instance."""
    return LLMFactory.create(LLMProvider.OPENROUTER, model=model, temperature=temperature, **kwargs)
