"""
Kalshi Starter Kit
==================
A modular framework for Kalshi prediction market integration.

DJ AI Business Consultant
"""

from .config import Config
from .kalshi_client import KalshiClient
from .market_analyzer import MarketAnalyzer
from .ai_decider import AIDecider

__version__ = "1.0.0"
__author__ = "DJ AI Business Consultant"

__all__ = [
    "Config",
    "KalshiClient", 
    "MarketAnalyzer",
    "AIDecider",
]
