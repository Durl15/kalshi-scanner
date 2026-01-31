"""
Configuration management for Kalshi Starter Kit.
Loads settings from environment variables and .env file.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment."""
    
    # Kalshi API
    api_key_id: str
    private_key_path: str
    environment: str  # "production" or "demo"
    
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
        key_path = Path(self.private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(
                f"Private key not found at {self.private_key_path}. "
                "Download from Kalshi Settings → API"
            )
        return key_path.read_text()
    
    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "Config":
        """
        Load configuration from environment variables.
        
        Args:
            env_path: Optional path to .env file
            
        Returns:
            Config instance with loaded settings
        """
        # Load .env file if it exists
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()
        
        # Required settings
        api_key_id = os.getenv("KALSHI_API_KEY_ID")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        
        if not api_key_id or not private_key_path:
            raise ValueError(
                "Missing required environment variables: "
                "KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH"
            )
        
        return cls(
            api_key_id=api_key_id,
            private_key_path=private_key_path,
            environment=os.getenv("KALSHI_ENVIRONMENT", "demo"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            max_position_size_usd=float(os.getenv("MAX_POSITION_SIZE_USD", "100")),
            max_daily_loss_usd=float(os.getenv("MAX_DAILY_LOSS_USD", "50")),
            min_confidence_threshold=float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.65")),
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
