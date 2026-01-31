"""
Kalshi Market Dashboard
=======================
Web-based dashboard for viewing and analyzing Kalshi prediction markets.

Run: streamlit run dashboard.py
"""

import sys
sys.path.insert(0, '.')

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from src.config import load_config
from src.kalshi_client import KalshiClient, KalshiError
from src.market_analyzer import MarketAnalyzer

# Page config
st.set_page_config(
    page_title="Kalshi Market Scanner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .big-number {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .stMetric > div {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_client():
    """Initialize Kalshi client (cached)."""
    config = load_config()
    return KalshiClient(config), MarketAnalyzer(KalshiClient(config))


@st.cache_data(ttl=120)  # Cache for 2 minutes
def fetch_markets(_client, max_pages=3):
    """Fetch markets with caching."""
    return _client.get_all_markets(status="open", max_pages=max_pages)


def main():
    # Header
    st.title("📊 Kalshi Market Scanner")
    st.markdown("*Real-time prediction market analysis*")
    st.markdown("---")
    
    # Initialize client
    try:
        client, analyzer = get_client()
        config = load_config()
        env_badge = "🟢 Production" if config.environment == "production" else "🟡 Demo"
        st.sidebar.success(f"Connected: {env_badge}")
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        st.info("Check your .env file configuration")
        return
    
    # Sidebar controls
    st.sidebar.header("Settings")
    
    max_pages = st.sidebar.slider("Data depth (pages)", 1, 5, 3, 
                                   help="More pages = more markets but slower")
    
    min_volume = st.sidebar.number_input("Min 24h Volume", 0, 100000, 100,
                                          help="Filter markets by minimum volume")
    
    min_spread = st.sidebar.slider("Min Spread ($)", 0.0, 0.20, 0.05,
                                    help="For spread opportunities")
    
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**DJ AI Business Consultant**")
    st.sidebar.markdown("Syracuse, NY")
    
    # Fetch data
    with st.spinner("Fetching markets..."):
        try:
            markets = fetch_markets(client, max_pages)
        except KalshiError as e:
            st.error(f"API Error: {e}")
            st.info("Try again in a minute (rate limits)")
            return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_volume = sum(m.volume_24h for m in markets)
    avg_spread = sum(m.spread for m in markets) / len(markets) if markets else 0
    closing_24h = len([m for m in markets if m.close_time and 
                       (m.close_time - datetime.now(timezone.utc)).total_seconds() < 86400])
    
    col1.metric("Total Markets", f"{len(markets):,}")
    col2.metric("24h Volume", f"{total_volume:,}")
    col3.metric("Avg Spread", f"${avg_spread:.3f}")
    col4.metric("Closing <24h", closing_24h)
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔥 Top by Volume", 
        "📈 Wide Spreads", 
        "⏰ Closing Soon",
        "🎯 All Markets"
    ])
    
    # Tab 1: Top by Volume
    with tab1:
        st.subheader("Top Markets by 24h Volume")
        
        top_markets = sorted(markets, key=lambda m: m.volume_24h, reverse=True)[:20]
        
        if top_markets:
            df = pd.DataFrame([{
                "Market": m.title[:60],
                "Ticker": m.ticker,
                "YES Price": f"${m.yes_ask:.2f}",
                "NO Price": f"${m.no_ask:.2f}",
                "Spread": f"${m.spread:.2f}",
                "24h Vol": f"{m.volume_24h:,}",
                "Open Interest": f"{m.open_interest:,}"
            } for m in top_markets])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No markets found")
    
    # Tab 2: Wide Spreads
    with tab2:
        st.subheader(f"Wide Spread Opportunities (>{min_spread*100:.0f}%)")
        
        wide_spread_markets = [m for m in markets if m.spread >= min_spread]
        wide_spread_markets = sorted(wide_spread_markets, key=lambda m: m.spread, reverse=True)[:20]
        
        if wide_spread_markets:
            df = pd.DataFrame([{
                "Market": m.title[:60],
                "Ticker": m.ticker,
                "YES Bid": f"${m.yes_bid:.2f}",
                "YES Ask": f"${m.yes_ask:.2f}",
                "Spread": f"${m.spread:.2f}",
                "Spread %": f"{(m.spread/m.yes_ask*100) if m.yes_ask > 0 else 0:.1f}%",
                "Midpoint": f"${m.midpoint:.2f}",
                "24h Vol": f"{m.volume_24h:,}"
            } for m in wide_spread_markets])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.info(f"💡 **Market Making Opportunity**: Wide spreads mean you could potentially profit by placing orders on both sides.")
        else:
            st.info(f"No markets with spread > ${min_spread:.2f}")
    
    # Tab 3: Closing Soon
    with tab3:
        st.subheader("Markets Closing Within 24 Hours")
        
        now = datetime.now(timezone.utc)
        closing_soon = [m for m in markets if m.close_time and 
                        0 < (m.close_time - now).total_seconds() < 86400]
        closing_soon = sorted(closing_soon, key=lambda m: m.close_time)[:20]
        
        if closing_soon:
            df = pd.DataFrame([{
                "Market": m.title[:60],
                "Ticker": m.ticker,
                "YES Price": f"${m.yes_ask:.2f}",
                "Hours Left": f"{(m.close_time - now).total_seconds() / 3600:.1f}h",
                "Closes": m.close_time.strftime("%Y-%m-%d %H:%M UTC"),
                "24h Vol": f"{m.volume_24h:,}"
            } for m in closing_soon])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.info("💡 **Closing Soon**: Prices often converge to true probability as markets near resolution.")
        else:
            st.info("No markets closing within 24 hours")
    
    # Tab 4: All Markets
    with tab4:
        st.subheader("All Markets")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("Search markets", placeholder="e.g., Bitcoin, Trump, weather")
        with col2:
            sort_by = st.selectbox("Sort by", ["Volume (High)", "Volume (Low)", "Spread (High)", "Price (High)", "Price (Low)"])
        
        # Filter
        filtered = markets
        if search:
            search_lower = search.lower()
            filtered = [m for m in filtered if search_lower in m.title.lower()]
        
        if min_volume > 0:
            filtered = [m for m in filtered if m.volume_24h >= min_volume]
        
        # Sort
        if sort_by == "Volume (High)":
            filtered = sorted(filtered, key=lambda m: m.volume_24h, reverse=True)
        elif sort_by == "Volume (Low)":
            filtered = sorted(filtered, key=lambda m: m.volume_24h)
        elif sort_by == "Spread (High)":
            filtered = sorted(filtered, key=lambda m: m.spread, reverse=True)
        elif sort_by == "Price (High)":
            filtered = sorted(filtered, key=lambda m: m.yes_ask, reverse=True)
        elif sort_by == "Price (Low)":
            filtered = sorted(filtered, key=lambda m: m.yes_ask)
        
        # Display
        st.write(f"Showing {len(filtered)} markets")
        
        if filtered:
            df = pd.DataFrame([{
                "Market": m.title[:70],
                "Ticker": m.ticker,
                "YES": f"${m.yes_ask:.2f}",
                "NO": f"${m.no_ask:.2f}",
                "Spread": f"${m.spread:.2f}",
                "Volume": f"{m.volume_24h:,}",
                "Event": m.event_ticker[:20] if m.event_ticker else ""
            } for m in filtered[:100]])
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            if len(filtered) > 100:
                st.caption(f"Showing first 100 of {len(filtered)} markets")
        else:
            st.info("No markets match your filters")
    
    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data cached for 2 minutes")
    st.caption("⚠️ For informational purposes only. Trading involves risk.")


if __name__ == "__main__":
    main()
