"""LLM-based configuration extractor with multi-provider support."""

import json
from typing import Dict

import structlog

from .config import ExtractorConfig
from .llm_provider import create_provider, LLMProvider
from .utils import extract_json_from_text

logger = structlog.get_logger()


class LLMExtractor:
    """Extracts MCP configurations using configurable LLM provider."""

    def __init__(self, config: ExtractorConfig):
        """
        Initialize LLM provider.

        Args:
            config: Extractor configuration
        """
        self.config = config
        self.provider: LLMProvider = create_provider(config)

        logger.info(
            "llm_extractor_initialized",
            provider=self.provider.get_provider_name(),
            model=config.active_model
        )

    async def extract_config(self, prompt: str) -> Dict:
        """
        Extract config from prompt using configured LLM provider.

        Args:
            prompt: Complete extraction prompt

        Returns:
            Extracted configuration dict (or error dict if failed)
        """
        try:
            # Call provider
            response = await self.provider.create_completion(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                model=self.config.active_model
            )

            # Extract and clean JSON
            json_text = extract_json_from_text(response.content)

            # Parse JSON
            config = json.loads(json_text)

            # Add metadata (now includes provider name)
            config["_llm_metadata"] = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "model": response.model,
                "provider": self.provider.get_provider_name()
            }

            logger.info(
                "extraction_success",
                provider=self.provider.get_provider_name(),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens
            )

            return config

        except json.JSONDecodeError as e:
            logger.error(
                "json_parse_error",
                error=str(e),
                snippet=json_text[:200] if 'json_text' in locals() else "N/A"
            )

            return {
                "error": f"Invalid JSON from LLM: {str(e)}",
                "requires_manual_review": True,
                "raw_response": json_text[:500] if 'json_text' in locals() else "N/A"
            }

        except Exception as e:
            # Catch all provider exceptions (already logged by provider)
            logger.error("extraction_failed", error=str(e), exc_info=True)

            return {
                "error": f"Extraction failed: {str(e)}",
                "requires_manual_review": True
            }

