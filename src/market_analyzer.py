"""
Market Analyzer
===============
Tools for scanning and analyzing Kalshi markets to find opportunities.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Callable
from enum import Enum

from .kalshi_client import KalshiClient, Market


class OpportunityType(Enum):
    """Types of trading opportunities."""
    ARBITRAGE = "arbitrage"          # YES + NO != 100%
    WIDE_SPREAD = "wide_spread"      # Large bid-ask spread
    HIGH_VOLUME = "high_volume"      # Unusual volume spike
    MISPRICING = "mispricing"        # AI-detected mispricing
    CLOSING_SOON = "closing_soon"    # Market closing within timeframe


@dataclass
class Opportunity:
    """Represents a potential trading opportunity."""
    market: Market
    opportunity_type: OpportunityType
    score: float  # 0-100, higher = better
    details: str
    recommended_action: Optional[str] = None
    
    def __str__(self) -> str:
        return f"[{self.opportunity_type.value}] {self.market.title} - Score: {self.score:.1f}"


class MarketAnalyzer:
    """
    Analyzes Kalshi markets to identify trading opportunities.
    
    Usage:
        analyzer = MarketAnalyzer(client)
        
        # Find all opportunities
        opportunities = analyzer.scan_all()
        
        # Find specific opportunity types
        arb_opportunities = analyzer.find_arbitrage()
        
        # Filter by criteria
        hot_markets = analyzer.filter_markets(
            min_volume=1000,
            max_spread=0.10,
            closing_within_hours=24
        )
    """
    
    def __init__(self, client: KalshiClient):
        self.client = client
    
    def scan_all(
        self,
        min_score: float = 50.0,
        limit: int = 50
    ) -> List[Opportunity]:
        """
        Scans all open markets for various types of trading opportunities.

        This method acts as a comprehensive scanner by calling specialized
        detector methods for different opportunity types (e.g., arbitrage,
        wide spreads). It aggregates all identified opportunities, filters
        them by a minimum quality score, and returns the top results.

        Args:
            min_score: The minimum score (0-100) an opportunity must have to be
                included in the results. A higher score indicates a more
                compelling opportunity.
            limit: The maximum number of Opportunity objects to return.

        Returns:
            A list of the highest-scoring Opportunity objects found across all
            open markets, sorted by score in descending order.
        """
        markets = self.client.get_all_markets(status="open")
        opportunities = []
        
        for market in markets:
            # Check each opportunity type
            opps = [
                self._check_arbitrage(market),
                self._check_wide_spread(market),
                self._check_high_volume(market),
                self._check_closing_soon(market),
            ]
            
            for opp in opps:
                if opp and opp.score >= min_score:
                    opportunities.append(opp)
        
        # Sort by score and limit
        opportunities.sort(key=lambda x: x.score, reverse=True)
        return opportunities[:limit]
    
    def find_arbitrage(self, min_edge: float = 0.01) -> List[Opportunity]:
        """
        Finds risk-free arbitrage opportunities in the market.

        Arbitrage exists when market inefficiencies allow for guaranteed profit.
        This function scans for two common types:
        1.  YES ask + NO ask < $1.00: Buying one of each contract costs less
            than the guaranteed $1.00 payout, locking in a profit.
        2.  YES bid + NO bid > $1.00: Selling one of each contract yields more
            than the required $1.00 collateral, providing instant profit.

        Such opportunities are rare and usually short-lived.

        Args:
            min_edge: The minimum profit margin required to flag an opportunity.
                For example, 0.01 means the arbitrage must yield at least 1 cent
                per set of contracts.

        Returns:
            A list of all markets where an arbitrage condition is met, sorted
            by the size of the arbitrage edge.
        """
        markets = self.client.get_all_markets(status="open")
        opportunities = []
        
        for market in markets:
            opp = self._check_arbitrage(market, min_edge)
            if opp:
                opportunities.append(opp)
        
        return sorted(opportunities, key=lambda x: x.score, reverse=True)
    
    def find_wide_spreads(self, min_spread: float = 0.05) -> List[Opportunity]:
        """
        Finds markets with a large bid-ask spread, indicating potential for
        market-making strategies.

        A wide spread means there is a significant gap between the highest price
        a buyer is willing to pay (bid) and the lowest price a seller is willing
        to accept (ask).

        This presents an opportunity for a "market maker" to profit by
        simultaneously placing a buy order at the bid and a sell order at the
-       ask, capturing the spread as profit if both orders are filled.

        Args:
            min_spread: The minimum bid-ask spread (in dollars) to identify as
                an opportunity. E.g., 0.05 for a 5-cent spread.

        Returns:
            A list of opportunities where the market spread exceeds the minimum,
            sorted by the size of the spread.
        """
        markets = self.client.get_all_markets(status="open")
        opportunities = []
        
        for market in markets:
            if market.spread >= min_spread:
                score = min(100, market.spread * 500)  # Higher spread = higher score
                opp = Opportunity(
                    market=market,
                    opportunity_type=OpportunityType.WIDE_SPREAD,
                    score=score,
                    details=f"Spread: {market.spread:.2f} ({market.spread*100:.1f}%)",
                    recommended_action=f"Consider market making at {market.midpoint:.2f}"
                )
                opportunities.append(opp)
        
        return sorted(opportunities, key=lambda x: x.score, reverse=True)
    
    def filter_markets(
        self,
        min_volume: Optional[int] = None,
        max_spread: Optional[float] = None,
        closing_within_hours: Optional[int] = None,
        event_ticker: Optional[str] = None,
        custom_filter: Optional[Callable[[Market], bool]] = None,
    ) -> List[Market]:
        """
        Filter markets by various criteria.
        
        Args:
            min_volume: Minimum 24h volume
            max_spread: Maximum bid-ask spread
            closing_within_hours: Markets closing within N hours
            event_ticker: Filter by event
            custom_filter: Custom filter function
            
        Returns:
            List of markets matching criteria
        """
        markets = self.client.get_all_markets(
            status="open",
            event_ticker=event_ticker
        )
        
        filtered = []
        now = datetime.now(timezone.utc)
        
        for market in markets:
            # Volume filter
            if min_volume and market.volume_24h < min_volume:
                continue
            
            # Spread filter
            if max_spread and market.spread > max_spread:
                continue
            
            # Closing time filter
            if closing_within_hours and market.close_time:
                hours_until_close = (market.close_time - now).total_seconds() / 3600
                if hours_until_close > closing_within_hours:
                    continue
            
            # Custom filter
            if custom_filter and not custom_filter(market):
                continue
            
            filtered.append(market)
        
        return filtered
    
    def get_top_by_volume(self, limit: int = 20) -> List[Market]:
        """Get the most active markets by 24h volume."""
        markets = self.client.get_all_markets(status="open")
        return sorted(markets, key=lambda m: m.volume_24h, reverse=True)[:limit]
    
    def get_closing_soon(self, hours: int = 24) -> List[Market]:
        """Get markets closing within the specified hours."""
        return self.filter_markets(closing_within_hours=hours)
    
    # ========== Private Helper Methods ==========
    
    def _check_arbitrage(
        self, 
        market: Market, 
        min_edge: float = 0.01
    ) -> Optional[Opportunity]:
        """Check for arbitrage opportunity on a market."""
        # Check if YES ask + NO ask < 100 (free money)
        total_ask = market.yes_ask + market.no_ask
        if total_ask < 1.0 - min_edge:
            edge = 1.0 - total_ask
            score = min(100, edge * 1000)  # 10% edge = 100 score
            return Opportunity(
                market=market,
                opportunity_type=OpportunityType.ARBITRAGE,
                score=score,
                details=f"YES ask ({market.yes_ask:.2f}) + NO ask ({market.no_ask:.2f}) = {total_ask:.2f}",
                recommended_action=f"Buy both YES and NO for guaranteed {edge*100:.1f}% profit"
            )
        
        # Check if YES bid + NO bid > 100 (sell both)
        total_bid = market.yes_bid + market.no_bid
        if total_bid > 1.0 + min_edge:
            edge = total_bid - 1.0
            score = min(100, edge * 1000)
            return Opportunity(
                market=market,
                opportunity_type=OpportunityType.ARBITRAGE,
                score=score,
                details=f"YES bid ({market.yes_bid:.2f}) + NO bid ({market.no_bid:.2f}) = {total_bid:.2f}",
                recommended_action=f"Sell both YES and NO for guaranteed {edge*100:.1f}% profit"
            )
        
        return None
    
    def _check_wide_spread(self, market: Market) -> Optional[Opportunity]:
        """Check if market has unusually wide spread."""
        if market.spread >= 0.10:  # 10 cent spread
            score = min(100, market.spread * 300)
            return Opportunity(
                market=market,
                opportunity_type=OpportunityType.WIDE_SPREAD,
                score=score,
                details=f"Spread: {market.spread:.2f}",
            )
        return None
    
    def _check_high_volume(self, market: Market) -> Optional[Opportunity]:
        """Check for unusual volume activity."""
        # This would ideally compare to historical average
        if market.volume_24h > 10000:
            score = min(100, market.volume_24h / 500)
            return Opportunity(
                market=market,
                opportunity_type=OpportunityType.HIGH_VOLUME,
                score=score,
                details=f"24h Volume: {market.volume_24h:,}",
            )
        return None
    
    def _check_closing_soon(self, market: Market) -> Optional[Opportunity]:
        """Check if market is closing soon (final price convergence)."""
        if not market.close_time:
            return None
        
        now = datetime.now(timezone.utc)
        hours_until_close = (market.close_time - now).total_seconds() / 3600
        
        if 0 < hours_until_close <= 6:
            score = min(100, (6 - hours_until_close) * 16)
            return Opportunity(
                market=market,
                opportunity_type=OpportunityType.CLOSING_SOON,
                score=score,
                details=f"Closes in {hours_until_close:.1f} hours",
            )
        return None
    
    def generate_report(self, opportunities: List[Opportunity]) -> str:
        """Generate a formatted report of opportunities."""
        lines = [
            "=" * 60,
            "KALSHI MARKET OPPORTUNITIES REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
        ]
        
        if not opportunities:
            lines.append("No opportunities found matching criteria.")
            return "\n".join(lines)
        
        # Group by type
        by_type = {}
        for opp in opportunities:
            key = opp.opportunity_type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(opp)
        
        for opp_type, opps in by_type.items():
            lines.append(f"\n--- {opp_type.upper()} ({len(opps)}) ---")
            for opp in opps[:5]:  # Top 5 per type
                lines.append(f"\n  {opp.market.title}")
                lines.append(f"    Ticker: {opp.market.ticker}")
                lines.append(f"    Score: {opp.score:.1f}")
                lines.append(f"    {opp.details}")
                if opp.recommended_action:
                    lines.append(f"    Action: {opp.recommended_action}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
