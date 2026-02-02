"""
Kalshi Market Dashboard - Professional Edition
==============================================
DJ AI Business Consultant | Syracuse, NY

Features:
- Real-time market scanning
- AI-powered analysis (Claude)
- Wide spread opportunities
- Closing soon alerts
- Custom branding

Run: streamlit run dashboard.py
"""

import sys
import os
sys.path.insert(0, '.')

# Fix invalid SSL_CERT_FILE that prevents httpx/anthropic from initializing
_ssl_cert = os.environ.get("SSL_CERT_FILE")
if _ssl_cert and not os.path.exists(_ssl_cert):
    del os.environ["SSL_CERT_FILE"]

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from src.config import load_config
from src.kalshi_client import KalshiClient, KalshiError

# Try to import AI decider
try:
    from src.ai_decider import AIDecider, Decision
    HAS_AI = True
except ImportError:
    HAS_AI = False

# Page config
st.set_page_config(
    page_title="Kalshi Market Scanner | DJ AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with branding
st.markdown("""
<style>
    /* Brand Colors */
    :root {
        --primary: #1E3A5F;
        --secondary: #3498db;
        --accent: #27ae60;
        --warning: #f39c12;
        --danger: #e74c3c;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2C5282 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    
    /* Metric cards */
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid var(--secondary);
    }
    
    /* Opportunity cards */
    .opportunity-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid var(--accent);
    }
    
    /* AI recommendation styling */
    .ai-buy {
        background: #d4edda;
        border-left-color: #28a745;
    }
    
    .ai-skip {
        background: #fff3cd;
        border-left-color: #ffc107;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem;
        color: #666;
        border-top: 1px solid #eee;
        margin-top: 2rem;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_client():
    """Initialize Kalshi client (cached)."""
    config = load_config()
    client = KalshiClient(config)
    return client, config


@st.cache_resource
def get_ai_decider():
    """Initialize AI decider if available."""
    if not HAS_AI:
        return None
    try:
        config = load_config()
        if config.anthropic_api_key:
            return AIDecider(config)
    except Exception as e:
        st.warning(f"AI features unavailable: {e}")
    return None


@st.cache_resource(ttl=120)
def fetch_markets(_client, max_pages=3):
    """Fetch markets with caching."""
    return _client.get_all_markets(status="open", max_pages=max_pages)


def render_header():
    """Render branded header."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Kalshi Market Scanner</h1>
        <p>AI-Powered Prediction Market Analysis | DJ AI Business Consultant</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar(config):
    """Render sidebar with controls and branding."""
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60/1E3A5F/FFFFFF?text=DJ+AI", width=200)
        st.markdown("---")
        
        st.header("⚙️ Settings")
        
        max_pages = st.slider("Data depth", 1, 5, 3, 
                              help="More pages = more markets")
        
        min_volume = st.number_input("Min 24h Volume", 0, 100000, 100)
        
        min_spread = st.slider("Min Spread ($)", 0.0, 0.20, 0.05)
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Connection status
        env_badge = "🟢 Production" if config.environment == "production" else "🟡 Demo"
        st.success(f"Connected: {env_badge}")
        
        # AI status
        ai = get_ai_decider()
        if ai:
            st.success("🤖 AI Analysis: Enabled")
        else:
            st.warning("🤖 AI Analysis: Disabled")
            st.caption("Add ANTHROPIC_API_KEY to enable")
        
        st.markdown("---")
        
        # Branding
        st.markdown("""
        **DJ AI Business Consultant**  
        Syracuse, NY  
        
        🔗 [Contact Us](mailto:contact@example.com)
        """)
        
        return max_pages, min_volume, min_spread


def render_metrics(markets):
    """Render summary metrics."""
    col1, col2, col3, col4 = st.columns(4)
    
    total_volume = sum(m.volume_24h for m in markets)
    avg_spread = sum(m.spread for m in markets) / len(markets) if markets else 0
    
    now = datetime.now(timezone.utc)
    closing_24h = len([m for m in markets if m.close_time and 
                       (m.close_time - now).total_seconds() < 86400 and
                       (m.close_time - now).total_seconds() > 0])
    
    high_volume = len([m for m in markets if m.volume_24h > 1000])
    
    col1.metric("📈 Total Markets", f"{len(markets):,}")
    col2.metric("📊 24h Volume", f"{total_volume:,}")
    col3.metric("⏰ Closing <24h", closing_24h)
    col4.metric("🔥 High Volume", high_volume)


def render_ai_analysis_tab(markets):
    """Render AI-powered analysis tab."""
    st.subheader("🤖 AI-Powered Market Analysis")
    
    ai = get_ai_decider()
    
    if not ai:
        st.warning("""
        **AI Analysis Requires Anthropic API Key**
        
        Add `ANTHROPIC_API_KEY` to your secrets to enable Claude-powered market analysis.
        
        Features when enabled:
        - Probability forecasting
        - Risk assessment
        - Buy/Skip recommendations
        - Confidence scoring
        """)
        return
    
    # Select markets to analyze
    st.markdown("Select markets for AI analysis:")
    
    # Show top markets by volume
    top_markets = sorted(markets, key=lambda m: m.volume_24h, reverse=True)[:10]
    
    market_options = {f"{m.title[:50]} (Vol: {m.volume_24h:,})": m for m in top_markets}
    
    selected_names = st.multiselect(
        "Choose markets (max 3 for demo):",
        options=list(market_options.keys()),
        max_selections=3
    )
    
    if selected_names and st.button("🧠 Run AI Analysis", type="primary"):
        for name in selected_names:
            market = market_options[name]
            
            with st.spinner(f"Analyzing: {market.title[:40]}..."):
                try:
                    analysis = ai.analyze_market(market)
                    
                    # Display results
                    st.markdown("---")
                    
                    # Decision badge
                    if analysis.decision in [Decision.BUY_YES, Decision.BUY_NO]:
                        badge_class = "ai-buy"
                        badge_text = f"🟢 {analysis.decision.value.upper()}"
                    else:
                        badge_class = "ai-skip"
                        badge_text = f"⏭️ {analysis.decision.value.upper()}"
                    
                    st.markdown(f"""
                    <div class="opportunity-card {badge_class}">
                        <h4>{market.title[:60]}</h4>
                        <p><strong>AI Recommendation: {badge_text}</strong></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Analysis details
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("AI Probability", f"{analysis.predicted_probability*100:.0f}%")
                        st.metric("Market Price", f"{market.yes_ask*100:.0f}%")
                    
                    with col2:
                        st.metric("Edge", f"{analysis.edge*100:+.1f}%")
                        st.metric("Confidence", f"{analysis.confidence*100:.0f}%")
                    
                    with col3:
                        st.metric("Position Size", f"{analysis.position_size_pct*100:.0f}%")
                        if analysis.recommended_price:
                            st.metric("Target Price", f"${analysis.recommended_price:.2f}")
                    
                    # Reasoning
                    with st.expander("📝 AI Reasoning"):
                        st.write(analysis.reasoning)
                        
                        st.markdown("**Key Factors:**")
                        for factor in analysis.key_factors[:3]:
                            st.write(f"• {factor}")
                        
                        st.markdown("**Risks:**")
                        for risk in analysis.risks[:3]:
                            st.write(f"⚠️ {risk}")
                    
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
    
    elif not selected_names:
        st.info("Select 1-3 markets above to analyze with AI")


def render_opportunities_tab(markets, min_spread):
    """Render trading opportunities tab."""
    st.subheader("💰 Trading Opportunities")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Wide Spreads")
        st.caption("Potential market-making opportunities")
        
        wide_spread = [m for m in markets if m.spread >= min_spread]
        wide_spread = sorted(wide_spread, key=lambda m: m.spread, reverse=True)[:10]
        
        if wide_spread:
            for m in wide_spread:
                spread_pct = (m.spread / m.yes_ask * 100) if m.yes_ask > 0 else 0
                st.markdown(f"""
                **{m.title[:45]}**  
                Spread: ${m.spread:.2f} ({spread_pct:.1f}%) | Mid: ${m.midpoint:.2f}
                """)
                st.progress(min(m.spread / 0.20, 1.0))
        else:
            st.info(f"No markets with spread > ${min_spread:.2f}")
    
    with col2:
        st.markdown("### Arbitrage Check")
        st.caption("YES + NO should equal $1.00")
        
        arb_opportunities = []
        for m in markets:
            total = m.yes_ask + m.no_ask
            if total < 0.98:  # Potential arb
                arb_opportunities.append((m, 1.0 - total))
        
        arb_opportunities.sort(key=lambda x: x[1], reverse=True)
        
        if arb_opportunities:
            for m, edge in arb_opportunities[:5]:
                st.markdown(f"""
                **{m.title[:45]}**  
                Edge: {edge*100:.2f}% | YES: ${m.yes_ask:.2f} + NO: ${m.no_ask:.2f}
                """)
        else:
            st.success("No arbitrage opportunities (markets are efficient)")


def render_closing_soon_tab(markets):
    """Render markets closing soon."""
    st.subheader("⏰ Markets Closing Soon")
    
    now = datetime.now(timezone.utc)
    
    # Filter and sort by close time
    closing = []
    for m in markets:
        if m.close_time:
            hours_left = (m.close_time - now).total_seconds() / 3600
            if 0 < hours_left < 48:
                closing.append((m, hours_left))
    
    closing.sort(key=lambda x: x[1])
    
    if closing:
        # Time buckets
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 🔴 < 6 Hours")
            urgent = [(m, h) for m, h in closing if h < 6]
            for m, h in urgent[:5]:
                st.markdown(f"**{m.title[:40]}**")
                st.caption(f"{h:.1f}h left | YES: ${m.yes_ask:.2f}")
        
        with col2:
            st.markdown("### 🟡 6-24 Hours")
            soon = [(m, h) for m, h in closing if 6 <= h < 24]
            for m, h in soon[:5]:
                st.markdown(f"**{m.title[:40]}**")
                st.caption(f"{h:.1f}h left | YES: ${m.yes_ask:.2f}")
        
        with col3:
            st.markdown("### 🟢 24-48 Hours")
            later = [(m, h) for m, h in closing if 24 <= h < 48]
            for m, h in later[:5]:
                st.markdown(f"**{m.title[:40]}**")
                st.caption(f"{h:.1f}h left | YES: ${m.yes_ask:.2f}")
    else:
        st.info("No markets closing in the next 48 hours")


def render_all_markets_tab(markets, min_volume):
    """Render searchable market list."""
    st.subheader("📋 All Markets")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search = st.text_input("🔍 Search", placeholder="Bitcoin, weather, sports...")
    
    with col2:
        sort_by = st.selectbox("Sort by", [
            "Volume (High → Low)",
            "Volume (Low → High)",
            "Spread (High → Low)",
            "YES Price (High → Low)",
            "YES Price (Low → High)"
        ])
    
    with col3:
        show_count = st.selectbox("Show", [25, 50, 100, 200], index=1)
    
    # Filter
    filtered = markets
    if search:
        search_lower = search.lower()
        filtered = [m for m in filtered if search_lower in m.title.lower()]
    
    if min_volume > 0:
        filtered = [m for m in filtered if m.volume_24h >= min_volume]
    
    # Sort
    if "Volume (High" in sort_by:
        filtered = sorted(filtered, key=lambda m: m.volume_24h, reverse=True)
    elif "Volume (Low" in sort_by:
        filtered = sorted(filtered, key=lambda m: m.volume_24h)
    elif "Spread" in sort_by:
        filtered = sorted(filtered, key=lambda m: m.spread, reverse=True)
    elif "High → Low" in sort_by:
        filtered = sorted(filtered, key=lambda m: m.yes_ask, reverse=True)
    else:
        filtered = sorted(filtered, key=lambda m: m.yes_ask)
    
    st.caption(f"Showing {min(show_count, len(filtered))} of {len(filtered)} markets")
    
    # Display as dataframe
    if filtered:
        df = pd.DataFrame([{
            "Market": m.title[:60],
            "Ticker": m.ticker,
            "YES": f"${m.yes_ask:.2f}",
            "NO": f"${m.no_ask:.2f}",
            "Spread": f"${m.spread:.2f}",
            "24h Vol": m.volume_24h,
            "Interest": m.open_interest
        } for m in filtered[:show_count]])
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No markets match your filters")


def render_footer():
    """Render footer with branding."""
    st.markdown("""
    <div class="footer">
        <p><strong>DJ AI Business Consultant</strong> | Syracuse, NY</p>
        <p>AI-Powered Solutions for Healthcare, Construction & Small Business</p>
        <p>⚠️ For informational purposes only. Trading involves significant risk.</p>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main application."""
    # Header
    render_header()
    
    # Initialize client
    try:
        client, config = get_client()
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        st.info("Check your secrets configuration")
        return
    
    # Sidebar
    max_pages, min_volume, min_spread = render_sidebar(config)
    
    # Fetch data
    with st.spinner("Fetching markets..."):
        try:
            markets = fetch_markets(client, max_pages)
        except KalshiError as e:
            st.error(f"API Error: {e}")
            st.info("Try again in a minute (rate limits)")
            return
    
    # Metrics
    render_metrics(markets)
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🤖 AI Analysis",
        "💰 Opportunities", 
        "⏰ Closing Soon",
        "📋 All Markets"
    ])
    
    with tab1:
        render_ai_analysis_tab(markets)
    
    with tab2:
        render_opportunities_tab(markets, min_spread)
    
    with tab3:
        render_closing_soon_tab(markets)
    
    with tab4:
        render_all_markets_tab(markets, min_volume)
    
    # Footer
    render_footer()


if __name__ == "__main__":
    main()
