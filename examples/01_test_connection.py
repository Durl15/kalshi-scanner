#!/usr/bin/env python3
"""
Example 1: Test Connection to Kalshi API
========================================
Verifies your API credentials are working correctly.

Run: python examples/01_test_connection.py
"""

import sys
sys.path.insert(0, '.')

from src.config import load_config
from src.kalshi_client import KalshiClient, KalshiError


def main():
    print("=" * 50)
    print("KALSHI API CONNECTION TEST")
    print("=" * 50)
    
    # Load configuration
    print("\n1. Loading configuration...")
    try:
        config = load_config()
        print(f"   ✓ Environment: {config.environment}")
        print(f"   ✓ API Key ID: {config.api_key_id[:8]}...")
        print(f"   ✓ Base URL: {config.api_base_url}")
    except Exception as e:
        print(f"   ✗ Configuration error: {e}")
        return False
    
    # Initialize client
    print("\n2. Initializing client...")
    try:
        client = KalshiClient(config)
        print("   ✓ Client initialized")
    except Exception as e:
        print(f"   ✗ Client error: {e}")
        return False
    
    # Test exchange status
    print("\n3. Checking exchange status...")
    try:
        status = client.get_exchange_status()
        print(f"   ✓ Exchange active: {status.get('exchange_active', 'unknown')}")
        print(f"   ✓ Trading active: {status.get('trading_active', 'unknown')}")
    except KalshiError as e:
        print(f"   ✗ API error: {e}")
        return False
    
    # Test market data
    print("\n4. Fetching sample markets...")
    try:
        response = client.get_markets(status="open", limit=5)
        markets = response.get("markets", [])
        print(f"   ✓ Retrieved {len(markets)} markets")
        
        if markets:
            print("\n   Sample markets:")
            for m in markets[:3]:
                print(f"   - {m.get('title', 'Unknown')[:50]}")
    except KalshiError as e:
        print(f"   ✗ API error: {e}")
        return False
    
    # Test account (if production)
    if config.environment == "production":
        print("\n5. Checking account balance...")
        try:
            balance = client.get_balance()
            bal_cents = balance.get("balance", 0)
            print(f"   ✓ Balance: ${bal_cents/100:.2f}")
        except KalshiError as e:
            print(f"   ⚠ Could not fetch balance: {e}")
    else:
        print("\n5. Skipping balance check (demo environment)")
    
    print("\n" + "=" * 50)
    print("CONNECTION TEST PASSED ✓")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
