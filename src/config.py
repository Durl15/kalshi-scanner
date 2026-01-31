"""
Configuration management for Kalshi Starter Kit.
Loads settings from environment variables, .env file, or Streamlit secrets.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Try to load dotenv
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Try to load Streamlit secrets
try:
    import streamlit as st
    HAS_STREAMLIT = hasattr(st, 'secrets')
except ImportError:
    HAS_STREAMLIT = False


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first
    if HAS_STREAMLIT:
        try:
            return st.secrets.get(key, None)
        except:
            pass
    
    # Fall back to environment variables
    return os.getenv(key, default)


@dataclass
class Config:
    """Application configuration loaded from environment."""
    
    # Kalshi API
    api_key_id: str
    environment: str  # "production" or "demo"
    
    # Private key - either path or content
    private_key_path: Optional[str] = None
    private_key_content: Optional[str] = None
    
    # AI Integration
    anthropic_api_key: Optional[str] = None
    
    # Telegram Alerts
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Trading Limits
    max_position_size_usd: float = 100.0
    max_daily_loss_usd: float = 50.0
    min_confidence_threshold: float = 0.65
    
    @property
    def api_base_url(self) -> str:
        """Return the appropriate API URL based on environment."""
        if self.environment == "demo":
            return "https://demo-api.kalshi.co/trade-api/v2"
        return "https://api.elections.kalshi.com/trade-api/v2"
    
    @property
    def private_key(self) -> str:
        """Load and return the private key content."""
        # If we have direct content, use it
        if self.private_key_content:
            return self.private_key_content
        
        # Otherwise, load from file
        if self.private_key_path:
            key_path = Path(self.private_key_path)
            if key_path.exists():
                return key_path.read_text()
            else:
                raise FileNotFoundError(
                    f"Private key not found at {self.private_key_path}. "
                    "Download from Kalshi Settings → API"
                )
        
        raise ValueError("No private key configured. Set KALSHI_PRIVATE_KEY or KALSHI_PRIVATE_KEY_PATH")
    
    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "Config":
        """
        Load configuration from environment variables or Streamlit secrets.
        
        Args:
            env_path: Optional path to .env file
            
        Returns:
            Config instance with loaded settings
        """
        # Load .env file if available
        if HAS_DOTENV:
            if env_path:
                load_dotenv(env_path)
            else:
                load_dotenv()
        
        # Required settings
        api_key_id = get_secret("KALSHI_API_KEY_ID")
        
        if not api_key_id:
            raise ValueError(
                "Missing required: KALSHI_API_KEY_ID. "
                "Set in .env file or Streamlit secrets."
            )
        
        # Private key - try content first, then path
        private_key_content = get_secret("KALSHI_PRIVATE_KEY")
        private_key_path = get_secret("KALSHI_PRIVATE_KEY_PATH")
        
        if not private_key_content and not private_key_path:
            raise ValueError(
                "Missing private key. Set KALSHI_PRIVATE_KEY (content) or "
                "KALSHI_PRIVATE_KEY_PATH (file path)."
            )
        
        return cls(
            api_key_id=api_key_id,
            environment=get_secret("KALSHI_ENVIRONMENT", "demo"),
            private_key_path=private_key_path,
            private_key_content=private_key_content,
            anthropic_api_key=get_secret("ANTHROPIC_API_KEY"),
            telegram_bot_token=get_secret("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=get_secret("TELEGRAM_CHAT_ID"),
            max_position_size_usd=float(get_secret("MAX_POSITION_SIZE_USD", "100")),
            max_daily_loss_usd=float(get_secret("MAX_DAILY_LOSS_USD", "50")),
            min_confidence_threshold=float(get_secret("MIN_CONFIDENCE_THRESHOLD", "0.65")),
        )
    
    def validate(self) -> bool:
        """Validate configuration settings."""
        errors = []
        
        if self.environment not in ("production", "demo"):
            errors.append(f"Invalid environment: {self.environment}")
        
        if self.max_position_size_usd <= 0:
            errors.append("max_position_size_usd must be positive")
            
        if self.min_confidence_threshold < 0 or self.min_confidence_threshold > 1:
            errors.append("min_confidence_threshold must be between 0 and 1")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True


# Convenience function
def load_config(env_path: Optional[str] = None) -> Config:
    """Load and validate configuration."""
    config = Config.from_env(env_path)
    config.validate()
    return config
