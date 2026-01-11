"""Configuration management for the agentic system."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration for the agentic system."""

    # LLM Provider Configuration
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()

    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Model Configuration
    MODEL = os.getenv("MODEL")  # Optional, will use provider defaults if not set

    # Base URL Configuration (for custom endpoints, proxies, etc.)
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")  # None = use default
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # None = use default
    GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL")  # Gemini doesn't support custom base_url

    # Agent Configuration
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))

    # Retry Configuration
    RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "5"))
    RETRY_INITIAL_DELAY = float(os.getenv("RETRY_INITIAL_DELAY", "1.0"))
    RETRY_MAX_DELAY = float(os.getenv("RETRY_MAX_DELAY", "60.0"))

    # Memory Management Configuration
    MEMORY_MAX_CONTEXT_TOKENS = int(os.getenv("MEMORY_MAX_CONTEXT_TOKENS", "100000"))
    MEMORY_TARGET_TOKENS = int(os.getenv("MEMORY_TARGET_TOKENS", "50000"))
    MEMORY_COMPRESSION_THRESHOLD = int(os.getenv("MEMORY_COMPRESSION_THRESHOLD", "40000"))
    MEMORY_SHORT_TERM_SIZE = int(os.getenv("MEMORY_SHORT_TERM_SIZE", "100"))
    MEMORY_COMPRESSION_RATIO = float(os.getenv("MEMORY_COMPRESSION_RATIO", "0.3"))

    # Logging Configuration
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "false").lower() == "true"

    # Provider configuration map
    PROVIDER_CONFIG = {
        "anthropic": {
            "api_key_attr": "ANTHROPIC_API_KEY",
            "default_model": "claude-3-5-sonnet-20241022",
            "base_url_attr": "ANTHROPIC_BASE_URL",
        },
        "openai": {
            "api_key_attr": "OPENAI_API_KEY",
            "default_model": "gpt-4o",
            "base_url_attr": "OPENAI_BASE_URL",
        },
        "gemini": {
            "api_key_attr": "GEMINI_API_KEY",
            "default_model": "gemini-1.5-pro",
            "base_url_attr": "GEMINI_BASE_URL",
        },
    }

    @classmethod
    def get_api_key(cls) -> str:
        """Get the appropriate API key based on the selected provider.

        Returns:
            API key for the selected provider

        Raises:
            ValueError: If API key is not set for the selected provider
        """
        provider_cfg = cls.PROVIDER_CONFIG.get(cls.LLM_PROVIDER)
        if not provider_cfg:
            raise ValueError(f"Unknown LLM provider: {cls.LLM_PROVIDER}")

        api_key = getattr(cls, provider_cfg["api_key_attr"], None)
        if not api_key:
            raise ValueError(f"{provider_cfg['api_key_attr']} not set")
        return api_key

    @classmethod
    def get_default_model(cls) -> str:
        """Get the default model for the selected provider.

        Returns:
            Default model identifier
        """
        if cls.MODEL:
            return cls.MODEL
        return cls.PROVIDER_CONFIG.get(cls.LLM_PROVIDER, {}).get("default_model", "")

    @classmethod
    def get_base_url(cls) -> str:
        """Get the base URL for the selected provider.

        Returns:
            Base URL string or None (use provider default)
        """
        provider_cfg = cls.PROVIDER_CONFIG.get(cls.LLM_PROVIDER, {})
        base_url_attr = provider_cfg.get("base_url_attr")
        return getattr(cls, base_url_attr, None) if base_url_attr else None

    @classmethod
    def get_retry_config(cls):
        """Get retry configuration.

        Returns:
            RetryConfig instance with settings from environment variables
        """
        from llm.retry import RetryConfig

        return RetryConfig(
            max_retries=cls.RETRY_MAX_ATTEMPTS,
            initial_delay=cls.RETRY_INITIAL_DELAY,
            max_delay=cls.RETRY_MAX_DELAY,
            exponential_base=2.0,
            jitter=True
        )

    @classmethod
    def get_memory_config(cls):
        """Get memory configuration.

        Returns:
            MemoryConfig instance with settings from environment variables
        """
        from memory import MemoryConfig

        return MemoryConfig(
            max_context_tokens=cls.MEMORY_MAX_CONTEXT_TOKENS,
            target_working_memory_tokens=cls.MEMORY_TARGET_TOKENS,
            compression_threshold=cls.MEMORY_COMPRESSION_THRESHOLD,
            short_term_message_count=cls.MEMORY_SHORT_TERM_SIZE,
            compression_ratio=cls.MEMORY_COMPRESSION_RATIO,
        )

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        try:
            cls.get_api_key()
        except ValueError as e:
            raise ValueError(
                f"{e}. Please set it in your .env file or environment variables."
            )
