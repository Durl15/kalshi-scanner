"""
AI Decider
==========
Claude-powered AI analysis for Kalshi market predictions.
Uses a multi-agent approach: Forecaster, Critic, and Trader.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .kalshi_client import Market
from .config import Config


class Decision(Enum):
    """Trading decision types."""
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    SELL_YES = "sell_yes"
    SELL_NO = "sell_no"
    SKIP = "skip"
    HOLD = "hold"


@dataclass
class AIAnalysis:
    """Results of AI analysis on a market."""
    market_ticker: str
    market_title: str
    
    # Forecaster output
    predicted_probability: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    reasoning: str
    key_factors: List[str]
    
    # Critic output
    risks: List[str]
    blind_spots: List[str]
    alternative_view: str
    
    # Trader output
    decision: Decision
    recommended_price: Optional[float]
    position_size_pct: float  # % of max position
    edge: float  # expected edge over market
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "market_ticker": self.market_ticker,
            "market_title": self.market_title,
            "predicted_probability": self.predicted_probability,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "risks": self.risks,
            "blind_spots": self.blind_spots,
            "alternative_view": self.alternative_view,
            "decision": self.decision.value,
            "recommended_price": self.recommended_price,
            "position_size_pct": self.position_size_pct,
            "edge": self.edge,
        }


class AIDecider:
    """
    AI-powered decision engine for Kalshi trading.
    
    Uses a three-agent approach:
    1. Forecaster: Estimates true probability
    2. Critic: Identifies risks and blind spots
    3. Trader: Makes final trading decision
    
    Usage:
        decider = AIDecider(config)
        analysis = decider.analyze_market(market)
        
        if analysis.decision == Decision.BUY_YES:
            # Execute trade
            pass
    """
    
    def __init__(self, config: Config):
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        
        if not config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required for AI analysis")
        
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"
    
    def analyze_market(
        self,
        market: Market,
        additional_context: Optional[str] = None,
    ) -> AIAnalysis:
        """
        Performs a deep, multi-agent AI analysis on a single market.

        This function orchestrates a sequence of AI agents to produce a comprehensive
        trading recommendation:
        1.  **Forecaster**: Estimates the true probability of the event, ignoring
            the current market price.
        2.  **Critic**: Challenges the forecast, identifying potential risks,
            biases, and blind spots.
        3.  **Trader**: Synthesizes the forecast, critique, and live market data
            to make a final, actionable trading decision (e.g., BUY_YES, SKIP).

        Args:
            market: The Kalshi Market object to be analyzed.
            additional_context: Optional string containing external information
                (e.g., news articles, statistical data) to provide to the AI
                for a more informed analysis.

        Returns:
            An AIAnalysis data object containing the combined outputs of all
            three agents, including the final trading decision and rationale.
        """
        # Step 1: Forecaster
        forecast = self._run_forecaster(market, additional_context)
        
        # Step 2: Critic
        critique = self._run_critic(market, forecast)
        
        # Step 3: Trader
        decision = self._run_trader(market, forecast, critique)
        
        return AIAnalysis(
            market_ticker=market.ticker,
            market_title=market.title,
            predicted_probability=forecast["probability"],
            confidence=forecast["confidence"],
            reasoning=forecast["reasoning"],
            key_factors=forecast["key_factors"],
            risks=critique["risks"],
            blind_spots=critique["blind_spots"],
            alternative_view=critique["alternative_view"],
            decision=Decision(decision["action"]),
            recommended_price=decision.get("price"),
            position_size_pct=decision["position_size_pct"],
            edge=decision["edge"],
        )
    
    def batch_analyze(
        self,
        markets: List[Market],
        min_confidence: float = 0.6,
    ) -> List[AIAnalysis]:
        """
        Analyzes a list of markets and filters for high-quality opportunities.

        This method iterates through a list of markets, performs a full
        `analyze_market` deep dive on each, and then filters the results to
        return only those analyses where the AI's confidence level meets a
        minimum threshold.

        The final list is sorted by a combination of a trade's "edge" (the
        difference between predicted probability and market price) and the AI's
        confidence in its prediction, highlighting the most promising trades.

        Args:
            markets: A list of Market objects to analyze.
            min_confidence: The minimum AI confidence score (0.0 to 1.0) required
                for an analysis to be included in the results.

        Returns:
            A list of AIAnalysis objects for markets that meet the confidence
            threshold, sorted from most to least promising.
        """
        results = []
        for market in markets:
            try:
                analysis = self.analyze_market(market)
                if analysis.confidence >= min_confidence:
                    results.append(analysis)
            except Exception as e:
                print(f"Error analyzing {market.ticker}: {e}")
        
        # Sort by edge * confidence
        results.sort(key=lambda a: a.edge * a.confidence, reverse=True)
        return results
    
    def _run_forecaster(
        self,
        market: Market,
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the Forecaster agent to estimate probability."""
        
        prompt = f"""You are an expert forecaster analyzing prediction markets. Your job is to estimate the TRUE probability of an event, independent of market prices.

MARKET INFORMATION:
- Title: {market.title}
- Subtitle: {market.subtitle}
- Current YES price: ${market.yes_ask:.2f} (implies {market.yes_ask*100:.0f}% probability)
- Current NO price: ${market.no_ask:.2f}
- 24h Volume: {market.volume_24h:,} contracts
- Closes: {market.close_time}

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

Analyze this market and provide your forecast. Think step by step about:
1. What is this event actually asking?
2. What are the key factors that will determine the outcome?
3. What does historical data/base rates suggest?
4. What recent developments might affect the outcome?

Respond in JSON format:
{{
    "probability": 0.XX,  // Your estimated true probability (0.0-1.0)
    "confidence": 0.XX,   // How confident are you in this estimate (0.0-1.0)
    "reasoning": "Your detailed reasoning...",
    "key_factors": ["factor 1", "factor 2", "factor 3"]
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON from response
        content = response.content[0].text
        return self._parse_json(content)
    
    def _run_critic(
        self,
        market: Market,
        forecast: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run the Critic agent to identify risks and blind spots."""
        
        prompt = f"""You are a critical analyst reviewing a market forecast. Your job is to find flaws, risks, and blind spots.

MARKET: {market.title}

FORECASTER'S ANALYSIS:
- Predicted probability: {forecast['probability']*100:.0f}%
- Confidence: {forecast['confidence']*100:.0f}%
- Reasoning: {forecast['reasoning']}
- Key factors: {', '.join(forecast['key_factors'])}

Now critically analyze this forecast:
1. What could the forecaster be missing?
2. What risks could invalidate this prediction?
3. What's the strongest argument for the opposite view?

Respond in JSON format:
{{
    "risks": ["risk 1", "risk 2", "risk 3"],
    "blind_spots": ["blind spot 1", "blind spot 2"],
    "alternative_view": "The strongest case against this forecast is..."
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._parse_json(response.content[0].text)
    
    def _run_trader(
        self,
        market: Market,
        forecast: Dict[str, Any],
        critique: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run the Trader agent to make final decision."""
        
        prompt = f"""You are a disciplined trader making a final decision. Consider the forecast, critique, and market prices.

MARKET: {market.title}
- Current YES price: ${market.yes_ask:.2f}
- Current NO price: ${market.no_ask:.2f}
- Spread: ${market.spread:.2f}

FORECAST:
- Predicted probability: {forecast['probability']*100:.0f}%
- Confidence: {forecast['confidence']*100:.0f}%

CRITIQUE:
- Risks: {', '.join(critique['risks'])}
- Blind spots: {', '.join(critique['blind_spots'])}

TRADING RULES:
- Only trade if edge > 5% AND confidence > 60%
- Position size based on Kelly Criterion (fractional)
- Account for trading fees (~1-2%)

Calculate the edge and make a decision:
Edge = |predicted_probability - market_price| - fees

Respond in JSON format:
{{
    "action": "buy_yes" | "buy_no" | "skip",
    "edge": 0.XX,  // Expected edge after fees
    "price": 0.XX,  // Recommended limit price (or null for skip)
    "position_size_pct": 0.XX,  // % of max position (0.0-1.0)
    "rationale": "Why this decision..."
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._parse_json(response.content[0].text)
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response text."""
        # Find JSON in response
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start == -1 or end == 0:
            raise ValueError(f"No JSON found in response: {text}")
        
        json_str = text[start:end]
        return json.loads(json_str)
    
    def quick_screen(
        self,
        markets: List[Market],
        batch_size: int = 10,
    ) -> List[Market]:
        """
        Performs a fast, high-level AI screen of markets to find candidates
        for deeper analysis.

        This method is a cost-effective way to pre-filter a large number of
        markets. It sends batches of markets to the AI and asks for a simple
        rating (1-5) based on perceived mispricing or potential. Only markets
        that receive a high score are returned.

        This helps focus the more expensive `analyze_market` calls on only the
        most promising opportunities.

        Args:
            markets: A list of Market objects to screen.
            batch_size: The number of markets to include in each API call to the AI.

        Returns:
            A filtered list of Market objects that the AI has identified as
            having high potential and being worthy of a full analysis.
        """
        promising = []
        
        for i in range(0, len(markets), batch_size):
            batch = markets[i:i+batch_size]
            
            market_list = "\n".join([
                f"{j+1}. {m.title} - YES: ${m.yes_ask:.2f}, Volume: {m.volume_24h:,}"
                for j, m in enumerate(batch)
            ])
            
            prompt = f"""Quickly screen these prediction markets for trading opportunities.
For each, give a 1-5 score (5 = high potential, 1 = skip).
Only select markets where you see clear mispricing potential.

MARKETS:
{market_list}

Respond with just the market numbers worth analyzing (score 4-5):
Format: [1, 3, 7] or [] if none are promising"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse indices
            text = response.content[0].text
            try:
                start = text.find("[")
                end = text.find("]") + 1
                if start != -1 and end != 0:
                    indices = json.loads(text[start:end])
                    for idx in indices:
                        if 1 <= idx <= len(batch):
                            promising.append(batch[idx-1])
            except:
                pass
        
        return promising
