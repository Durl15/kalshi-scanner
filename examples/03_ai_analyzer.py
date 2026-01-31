#!/usr/bin/env python3
"""
Example 3: AI-Powered Market Analyzer
=====================================
Uses Claude to analyze markets and generate trading recommendations.

Run: python examples/03_ai_analyzer.py
"""

import sys
sys.path.insert(0, '.')

import json
from datetime import datetime
from src.config import load_config
from src.kalshi_client import KalshiClient
from src.market_analyzer import MarketAnalyzer
from src.ai_decider import AIDecider, Decision


def main():
    print("=" * 60)
    print("AI-POWERED KALSHI MARKET ANALYZER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize
    config = load_config()
    
    if not config.anthropic_api_key:
        print("\n⚠️  ANTHROPIC_API_KEY not set in .env")
        print("AI analysis requires an Anthropic API key.")
        print("Get one at: https://console.anthropic.com/")
        return
    
    client = KalshiClient(config)
    analyzer = MarketAnalyzer(client)
    ai = AIDecider(config)
    
    # Step 1: Get top markets
    print("\n1️⃣  Fetching top markets by volume...")
    top_markets = analyzer.get_top_by_volume(limit=20)
    print(f"   Found {len(top_markets)} active markets")
    
    # Step 2: Quick AI screening
    print("\n2️⃣  AI Quick Screen (identifying promising markets)...")
    promising = ai.quick_screen(top_markets, batch_size=10)
    print(f"   AI selected {len(promising)} markets for deep analysis")
    
    if not promising:
        print("\n   No promising markets found. Selecting top 3 by volume instead.")
        promising = top_markets[:3]
    
    # Step 3: Deep analysis on each
    print("\n3️⃣  Running Deep Analysis...")
    analyses = []
    
    for i, market in enumerate(promising[:5], 1):  # Limit to 5 for demo
        print(f"\n   Analyzing ({i}/{min(5, len(promising))}): {market.title[:50]}...")
        
        try:
            analysis = ai.analyze_market(market)
            analyses.append(analysis)
            
            # Print summary
            action_emoji = {
                Decision.BUY_YES: "🟢 BUY YES",
                Decision.BUY_NO: "🔴 BUY NO", 
                Decision.SKIP: "⏭️  SKIP",
                Decision.HOLD: "⏸️  HOLD",
            }
            
            print(f"   {action_emoji.get(analysis.decision, '❓')}")
            print(f"   Predicted: {analysis.predicted_probability*100:.0f}% | Market: {market.yes_ask*100:.0f}%")
            print(f"   Confidence: {analysis.confidence*100:.0f}% | Edge: {analysis.edge*100:.1f}%")
            
        except Exception as e:
            print(f"   ⚠️ Error analyzing market: {e}")
    
    # Step 4: Summary report
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 60)
    
    actionable = [a for a in analyses if a.decision not in (Decision.SKIP, Decision.HOLD)]
    
    if actionable:
        print(f"\n🎯 ACTIONABLE TRADES ({len(actionable)}):\n")
        
        # Sort by edge * confidence
        actionable.sort(key=lambda a: a.edge * a.confidence, reverse=True)
        
        for analysis in actionable:
            market = next(m for m in promising if m.ticker == analysis.market_ticker)
            
            print(f"{'='*50}")
            print(f"Market: {analysis.market_title}")
            print(f"Ticker: {analysis.market_ticker}")
            print(f"{'='*50}")
            
            print(f"\n📈 FORECAST:")
            print(f"   AI Probability: {analysis.predicted_probability*100:.0f}%")
            print(f"   Market Price:   {market.yes_ask*100:.0f}%")
            print(f"   Edge:           {analysis.edge*100:+.1f}%")
            print(f"   Confidence:     {analysis.confidence*100:.0f}%")
            
            print(f"\n💭 REASONING:")
            print(f"   {analysis.reasoning[:200]}...")
            
            print(f"\n📌 KEY FACTORS:")
            for factor in analysis.key_factors[:3]:
                print(f"   • {factor}")
            
            print(f"\n⚠️  RISKS:")
            for risk in analysis.risks[:3]:
                print(f"   • {risk}")
            
            print(f"\n✅ RECOMMENDATION:")
            print(f"   Action: {analysis.decision.value.upper()}")
            if analysis.recommended_price:
                print(f"   Target Price: ${analysis.recommended_price:.2f}")
            print(f"   Position Size: {analysis.position_size_pct*100:.0f}% of max")
            
            print()
    else:
        print("\nNo actionable trades found in current market conditions.")
        print("This is normal - good opportunities are rare!")
    
    # Save full analysis
    output_file = f"ai_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, 'w') as f:
        json.dump([a.to_dict() for a in analyses], f, indent=2)
    print(f"\n📁 Full analysis saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    
    print("\n⚠️  DISCLAIMER: This is for educational purposes only.")
    print("   Trading involves significant risk. Never trade more than you can afford to lose.")


if __name__ == "__main__":
    main()
