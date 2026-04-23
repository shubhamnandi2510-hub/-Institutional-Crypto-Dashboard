"""
Market Based Crypto Dashboard (CoinGecko Only)

Features:
- Candlestick-style chart (approximated from price data)
- EMA (20, 50)
- Bollinger Bands
- RSI, MACD
- Buy/Sell Signals
- Liquidity-style Heatmap (simulated)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Crypto Dashboard", layout="wide", page_icon="📊")
st.title("📊 Market Based Crypto Dashboard")

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    coins = {
        "Bitcoin": "bitcoin",
        "Ethereum": "ethereum",
        "BNB": "binancecoin",
        "Solana": "solana"
    }

    selected_coin = st.selectbox("Select Asset", list(coins.keys()))
    coin_id = coins[selected_coin]

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH DATA FROM COINGECKO ─────────────────────────
@st.cache_data(ttl=60)
def fetch_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
    res = requests.get(url, timeout=10)
    data = res.json()

    prices = data["prices"]

    df = pd.DataFrame(prices, columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")

    # Simulate OHLC
    df["open"] = df["price"]
    df["high"] = df["price"]
    df["low"] = df["price"]
    df["close"] = df["price"]
    df["volume"] = 0

    return df

df = fetch_data(coin_id)

if df.empty:
    st.error("No data available")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

df["MA20"] = df["close"].rolling(20).mean()
df["STD"] = df["close"].rolling(20).std()
df["Upper"] = df["MA20"] + 2 * df["STD"]
df["Lower"] = df["MA20"] - 2 * df["STD"]

# RSI
delta = df["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
rs = gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI"].fillna(50, inplace=True)

# MACD
ema12 = df["close"].ewm(span=12).mean()
ema26 = df["close"].ewm(span=26).mean()
df["MACD"] = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9).mean()
df["MACD_Hist"] = df["MACD"] - df["Signal"]

# Signals
df["Trade"] = "HOLD"
df.loc[(df["RSI"] < 30) & (df["MACD"] > df["Signal"]), "Trade"] = "BUY"
df.loc[(df["RSI"] > 70) & (df["MACD"] < df["Signal"]), "Trade"] = "SELL"

# ─── METRICS ───────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

change = latest["close"] - prev["close"]
pct = (change / prev["close"]) * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Price", f"${latest['close']:.2f}", f"{pct:.2f}%")
c2.metric("📈 RSI", f"{latest['RSI']:.2f}")
c3.metric("📉 MACD", f"{latest['MACD']:.2f}")
c4.metric("🎯 Signal", latest["Trade"])

# ─── CHART ─────────────────────────────────────────────
st.subheader("📊 Technical Analysis")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])

# Candlestick (simulated)
fig.add_trace(go.Candlestick(
    x=df["time"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    increasing_line_color="#00e676",
    decreasing_line_color="#ff5252"
), row=1, col=1)

# EMA
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20", line=dict(color="cyan")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50", line=dict(color="orange")), row=1, col=1)

# Bollinger Bands
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(color="gray", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty', line=dict(color="gray", dash="dot")), row=1, col=1)

# MACD
colors = np.where(df["MACD_Hist"] >= 0, "green", "red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue")), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange")), row=2, col=1)

fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ─── SIMULATED HEATMAP ────────────────────────────────
st.subheader("🔥 Liquidity Heatmap (Simulated)")

heat_df = df.copy()
heat_df["intensity"] = np.random.rand(len(heat_df))

heatmap = go.Figure()
heatmap.add_trace(go.Scatter(
    x=heat_df["time"],
    y=heat_df["close"],
    mode="markers",
    marker=dict(
        size=heat_df["intensity"] * 20,
        color=heat_df["intensity"],
        colorscale="Turbo",
        showscale=True
    )
))

heatmap.update_layout(template="plotly_dark", height=400)
st.plotly_chart(heatmap, use_container_width=True)
