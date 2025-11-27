"""Configuration for GitHub crawler and LLM extractor using Pydantic."""

from pydantic_settings import BaseSettings


class CrawlerConfig(BaseSettings):
    """Configuration for MCP GitHub crawler."""

    # GitHub API
    github_token: str
    github_rate_limit_buffer: int = 500  # Safety margin under 5000/hour

    # Crawling settings
    test_mode: bool = True  # True = test with limited servers, False = all
    test_limit: int = 10    # Number of servers to process in test mode

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 2

    # File paths
    input_file: str = "data/input/top_200_mcp_servers.json"
    output_file: str = "data/output/github_crawled_data.json"

    class Config:
        env_file = ".env"
        env_prefix = "CRAWLER_"
        case_sensitive = False
        extra = "ignore"


class ExtractorConfig(BaseSettings):
    """Configuration for LLM extraction."""

    # Provider selection
    llm_provider: str = "anthropic"  # "anthropic" or "openrouter"

    # Anthropic API
    anthropic_api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"

    # OpenRouter API
    openrouter_api_key: str | None = None
    openrouter_model: str = "deepseek/deepseek-v3.2-exp"
    openrouter_site_url: str | None = None  # Optional HTTP-Referer
    openrouter_app_name: str | None = None  # Optional X-Title

    # Common settings
    max_tokens: int = 4000
    temperature: float = 0.0
    timeout_seconds: int = 30

    # Processing (asyncio with configurable batch)
    test_mode: bool = True
    test_limit: int = 10
    batch_size: int = 5  # Configurable: 1=sequential, 5-10=parallel

    # Validation thresholds
    auto_approve_threshold: float = 0.9
    needs_review_threshold: float = 0.7

    # File paths
    input_file: str = "data/output/github_crawled_data.json"
    output_file: str = "data/output/extracted_configs.json"
    prompt_template_file: str = "config/extraction_prompt.txt"
    validation_prompt_file: str = "config/validation_prompt.txt"
    prompts_dir: str = "prompts"

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 2

    @property
    def active_api_key(self) -> str:
        """Get API key for selected provider."""
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError("EXTRACTOR_ANTHROPIC_API_KEY required for Anthropic")
            return self.anthropic_api_key
        elif self.llm_provider == "openrouter":
            if not self.openrouter_api_key:
                raise ValueError("EXTRACTOR_OPENROUTER_API_KEY required for OpenRouter")
            return self.openrouter_api_key
        else:
            raise ValueError(f"Unknown provider: {self.llm_provider}")

    @property
    def active_model(self) -> str:
        """Get model for selected provider."""
        if self.llm_provider == "openrouter":
            return self.openrouter_model
        return self.model

    class Config:
        env_file = ".env"
        env_prefix = "EXTRACTOR_"
        case_sensitive = False
        extra = "ignore"
