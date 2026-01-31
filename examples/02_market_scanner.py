#!/usr/bin/env python3
"""
Example 2: Market Scanner (FIXED - UTF-8 Encoding)
==================================================
Scans Kalshi markets for trading opportunities.

Run: python examples/02_market_scanner.py
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from src.config import load_config
from src.kalshi_client import KalshiClient
from src.market_analyzer import MarketAnalyzer, OpportunityType


def main():
    print("=" * 60)
    print("KALSHI MARKET SCANNER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize
    config = load_config()
    client = KalshiClient(config)
    analyzer = MarketAnalyzer(client)
    
    # 1. Get top markets by volume
    print("\n TOP MARKETS BY VOLUME (24h)")
    print("-" * 40)
    top_markets = analyzer.get_top_by_volume(limit=10)
    
    for i, market in enumerate(top_markets, 1):
        # Clean the title for Windows console
        clean_title = market.title.encode('ascii', 'ignore').decode('ascii')[:45]
        print(f"{i:2}. {clean_title}")
        print(f"    YES: ${market.yes_ask:.2f} | NO: ${market.no_ask:.2f} | Vol: {market.volume_24h:,}")
    
    # 2. Find markets closing soon
    print("\n\n MARKETS CLOSING WITHIN 24 HOURS")
    print("-" * 40)
    closing_soon = analyzer.get_closing_soon(hours=24)
    
    if closing_soon:
        for market in closing_soon[:5]:
            hours_left = (market.close_time - datetime.now(timezone.utc)).total_seconds() / 3600
            clean_title = market.title.encode('ascii', 'ignore').decode('ascii')[:45]
            print(f"* {clean_title}")
            print(f"  Closes in {hours_left:.1f} hours | YES: ${market.yes_ask:.2f}")
    else:
        print("No markets closing within 24 hours.")
    
    # 3. Find wide spreads (market making opportunities)
    print("\n\n WIDE SPREAD OPPORTUNITIES (>5%)")
    print("-" * 40)
    wide_spreads = analyzer.find_wide_spreads(min_spread=0.05)
    
    if wide_spreads:
        for opp in wide_spreads[:5]:
            clean_title = opp.market.title.encode('ascii', 'ignore').decode('ascii')[:45]
            print(f"* {clean_title}")
            print(f"  {opp.details} | Midpoint: ${opp.market.midpoint:.2f}")
    else:
        print("No wide spread opportunities found.")
    
    # 4. Check for arbitrage
    print("\n\n ARBITRAGE OPPORTUNITIES")
    print("-" * 40)
    arb_opportunities = analyzer.find_arbitrage(min_edge=0.005)
    
    if arb_opportunities:
        for opp in arb_opportunities[:5]:
            clean_title = opp.market.title.encode('ascii', 'ignore').decode('ascii')[:45]
            print(f"* {clean_title}")
            print(f"  {opp.details}")
            print(f"  -> {opp.recommended_action}")
    else:
        print("No arbitrage opportunities found (markets are efficient).")
    
    # 5. Full opportunity scan
    print("\n\n FULL OPPORTUNITY SCAN (Score > 60)")
    print("-" * 40)
    all_opportunities = analyzer.scan_all(min_score=60, limit=10)
    
    if all_opportunities:
        by_type = {}
        for opp in all_opportunities:
            t = opp.opportunity_type.value
            if t not in by_type:
                by_type[t] = 0
            by_type[t] += 1
        
        print(f"Found {len(all_opportunities)} opportunities:")
        for t, count in by_type.items():
            print(f"  - {t}: {count}")
        
        print("\nTop 5:")
        for opp in all_opportunities[:5]:
            clean_title = opp.market.title.encode('ascii', 'ignore').decode('ascii')[:50]
            print(f"\n  [{opp.opportunity_type.value}] Score: {opp.score:.0f}")
            print(f"  {clean_title}")
            print(f"  {opp.details}")
    else:
        print("No high-scoring opportunities found.")
    
    # Generate report
    print("\n\n GENERATING FULL REPORT...")
    report = analyzer.generate_report(all_opportunities)
    
    # Save to file with UTF-8 encoding (FIXED)
    report_file = f"market_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Report saved to: {report_file}")
    
    print("\n" + "=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
