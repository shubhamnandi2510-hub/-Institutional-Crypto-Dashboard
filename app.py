"""
Institutional Crypto Dashboard
Features:
- Binance OHLC Data
- Multi-timeframe Candlestick Chart
- EMA, Bollinger Bands
- RSI, MACD
- Volume
- Buy/Sell Signals (Confluence)
- Support & Resistance
- Pro UI Layout
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Institutional Crypto Dashboard", layout="wide", page_icon="🏦")

# Custom CSS for Pro Look
st.markdown("""
<style>
    .metric-container {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏦 Institutional Crypto Dashboard")

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    
    coins = {
        "Bitcoin": "BTCUSDT",
        "Ethereum": "ETHUSDT",
        "BNB": "BNBUSDT",
        "XRP": "XRPUSDT",
        "Solana": "SOLUSDT",
        "Cardano": "ADAUSDT",
        "Dogecoin": "DOGEUSDT"
    }

    timeframes = {
        "1 Minute": "1m",
        "5 Minutes": "5m",
        "15 Minutes": "15m",
        "1 Hour": "1h",
        "4 Hours": "4h",
        "1 Day": "1d"
    }

    selected_coin = st.selectbox("Select Asset", list(coins.keys()))
    selected_tf = st.selectbox("Select Timeframe", list(timeframes.keys()))
    
    symbol = coins[selected_coin]
    interval = timeframes[selected_tf]

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()

# ─── FETCH DATA ─────────────────────────────────────────
@st.cache_data(ttl=15)
def fetch_data(symbol, interval):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        st.error(f"API Error: Could not fetch data for {symbol}.")
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","quote_av","trades","tb_base_av","tb_quote_av","ignore"
    ])

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
    
    return df

with st.spinner("Fetching market data..."):
    df = fetch_data(symbol, interval)

if df.empty:
    st.warning("No data returned. Please try again later.")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
# EMA
df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

# Bollinger Bands
df["MA20"] = df["close"].rolling(window=20).mean()
df["STD"] = df["close"].rolling(window=20).std()
df["Upper"] = df["MA20"] + (2 * df["STD"])
df["Lower"] = df["MA20"] - (2 * df["STD"])

# RSI
delta = df["close"].diff()
gain = delta.where(delta > 0, 0.0)
loss = -delta.where(delta < 0, 0.0)
avg_gain = gain.rolling(window=14, min_periods=1).mean()
avg_loss = loss.rolling(window=14, min_periods=1).mean()
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI"] = df["RSI"].fillna(50) # default mid-value for NaN

# MACD
ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
df["MACD"] = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
df["MACD_Hist"] = df["MACD"] - df["Signal"]

# Support & Resistance
df["Support"] = df["low"].rolling(window=20, min_periods=1).min()
df["Resistance"] = df["high"].rolling(window=20, min_periods=1).max()

# ─── SIGNAL LOGIC (Vectorized for Performance) ──────────
df["Trade"] = "HOLD"
buy_condition = (df["RSI"] < 30) & (df["MACD"] > df["Signal"]) & (df["close"] > df["EMA20"])
sell_condition = (df["RSI"] > 70) & (df["MACD"] < df["Signal"]) & (df["close"] < df["EMA20"])

df.loc[buy_condition, "Trade"] = "BUY"
df.loc[sell_condition, "Trade"] = "SELL"

# ─── TOP METRICS ────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

price_change = latest['close'] - prev['close']
price_change_pct = (price_change / prev['close']) * 100

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("💰 Current Price", f"${latest['close']:,.2f}", f"{price_change:,.2f} ({price_change_pct:.2f}%)")
with col2:
    st.metric("📈 RSI (14)", f"{latest['RSI']:,.2f}", "Oversold" if latest['RSI'] < 30 else "Overbought" if latest['RSI'] > 70 else "Neutral", delta_color="off")
with col3:
    macd_delta = latest['MACD'] - latest['Signal']
    st.metric("📉 MACD", f"{latest['MACD']:,.2f}", f"{macd_delta:,.2f} Hist")
with col4:
    signal_color = "🟢" if latest["Trade"] == "BUY" else "🔴" if latest["Trade"] == "SELL" else "⚪"
    st.metric("🎯 Confluence Signal", f"{signal_color} {latest['Trade']}", "")

st.markdown("<br>", unsafe_allow_html=True)

# ─── ADVANCED CHARTING (Subplots) ───────────────────────
st.subheader("📊 Technical Analysis")

# Create a subplot figure with 3 rows (Price+Overlays, MACD, RSI)
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                    vertical_spacing=0.03, 
                    row_heights=[0.6, 0.2, 0.2])

# 1. Candlestick
fig.add_trace(go.Candlestick(
    x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
    name="Price", showlegend=False
), row=1, col=1)

# EMAs
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20", line=dict(color='blue', width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50", line=dict(color='orange', width=1)), row=1, col=1)

# Bollinger Bands
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], name="BB Upper", line=dict(color='gray', dash='dot', width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], name="BB Lower", line=dict(color='gray', dash='dot', width=1), fill='tonexty', fillcolor='rgba(128,128,128,0.1)'), row=1, col=1)

# Buy/Sell Signals
buy_signals = df[df["Trade"] == "BUY"]
sell_signals = df[df["Trade"] == "SELL"]

fig.add_trace(go.Scatter(
    x=buy_signals["time"], y=buy_signals["low"] * 0.99,
    mode="markers", marker=dict(symbol="triangle-up", size=12, color="green", line=dict(width=1, color="DarkSlateGrey")),
    name="BUY Signal"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=sell_signals["time"], y=sell_signals["high"] * 1.01,
    mode="markers", marker=dict(symbol="triangle-down", size=12, color="red", line=dict(width=1, color="DarkSlateGrey")),
    name="SELL Signal"
), row=1, col=1)

# 2. MACD
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], name="MACD", line=dict(color='blue', width=1)), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], name="Signal", line=dict(color='orange', width=1)), row=2, col=1)
# MACD Histogram colors
colors = ['green' if val >= 0 else 'red' for val in df['MACD_Hist']]
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], name="Histogram", marker_color=colors), row=2, col=1)

# 3. RSI
fig.add_trace(go.Scatter(x=df["time"], y=df["RSI"], name="RSI", line=dict(color='purple', width=1)), row=3, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

# Update layout
fig.update_layout(
    template="plotly_dark",
    height=800,
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

# Remove range slider from subplot x-axes
fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
fig.update_xaxes(rangeslider_visible=False, row=3, col=1)

st.plotly_chart(fig, use_container_width=True)

# ─── DATA TABLE ─────────────────────────────────────────
with st.expander("📁 View Raw Data & Trade Signals", expanded=False):
    st.dataframe(
        df[["time", "open", "high", "low", "close", "volume", "RSI", "MACD", "Trade"]].sort_values("time", ascending=False),
        use_container_width=True,
        hide_index=True
    )