"""LLM provider adapters for multi-provider support."""

from abc import ABC, abstractmethod
from typing import Protocol

import structlog

from .retry_utils import api_retry_no_reraise

logger = structlog.get_logger()


from dataclasses import dataclass


@dataclass
class StandardLLMResponse:
    """Standard response from any LLM provider."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str

    @classmethod
    def from_anthropic(cls, response, model: str):
        """Create from Anthropic response."""
        return cls(
            content=response.content[0].text.strip(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model
        )

    @classmethod
    def from_openrouter(cls, response, model: str):
        """Create from OpenRouter response."""
        return cls(
            content=response.choices[0].message.content.strip(),
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model=model
        )


class LLMResponse(Protocol):
    """Standard response format from any LLM provider."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def create_completion(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: str
    ) -> LLMResponse:
        """Create a completion using the provider's API."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name for logging."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider adapter."""

    def __init__(self, api_key: str, timeout_seconds: int):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            timeout_seconds: Request timeout in seconds
        """
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.timeout = timeout_seconds
        self.anthropic = anthropic

        logger.info("anthropic_provider_initialized")

    @api_retry_no_reraise()
    async def create_completion(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: str
    ) -> LLMResponse:
        """
        Create completion using Anthropic API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model name

        Returns:
            LLMResponse with standardized fields
        """
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            # Convert to standard format
            return StandardLLMResponse.from_anthropic(response, model)

        except self.anthropic.APITimeoutError as e:
            logger.error("anthropic_timeout", error=str(e))
            raise
        except self.anthropic.RateLimitError as e:
            logger.error("anthropic_rate_limit", error=str(e))
            raise
        except self.anthropic.APIError as e:
            logger.error("anthropic_api_error", error=str(e))
            raise

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "anthropic"


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider adapter using OpenAI client."""

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int,
        site_url: str | None = None,
        app_name: str | None = None
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            timeout_seconds: Request timeout in seconds
            site_url: Optional site URL for HTTP-Referer header
            app_name: Optional app name for X-Title header
        """
        from openai import AsyncOpenAI

        # Build extra headers for OpenRouter
        extra_headers = {}
        if site_url:
            extra_headers["HTTP-Referer"] = site_url
        if app_name:
            extra_headers["X-Title"] = app_name

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=timeout_seconds,
            default_headers=extra_headers
        )

        logger.info(
            "openrouter_provider_initialized",
            has_site_url=bool(site_url),
            has_app_name=bool(app_name)
        )

    @api_retry_no_reraise()
    async def create_completion(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: str
    ) -> LLMResponse:
        """
        Create completion using OpenRouter API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model name

        Returns:
            LLMResponse with standardized fields
        """
        from openai import APITimeoutError, RateLimitError, APIError

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Convert to standard format
            return StandardLLMResponse.from_openrouter(response, model)

        except APITimeoutError as e:
            logger.error("openrouter_timeout", error=str(e))
            raise
        except RateLimitError as e:
            logger.error("openrouter_rate_limit", error=str(e))
            raise
        except APIError as e:
            logger.error("openrouter_api_error", error=str(e))
            raise

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "openrouter"


def create_provider(config) -> LLMProvider:
    """
    Factory function to create the appropriate provider.

    Args:
        config: ExtractorConfig instance

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If unsupported provider specified
    """
    from .config import ExtractorConfig

    if config.llm_provider == "anthropic":
        return AnthropicProvider(
            api_key=config.active_api_key,
            timeout_seconds=config.timeout_seconds
        )
    elif config.llm_provider == "openrouter":
        return OpenRouterProvider(
            api_key=config.active_api_key,
            timeout_seconds=config.timeout_seconds,
            site_url=config.openrouter_site_url,
            app_name=config.openrouter_app_name
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")
