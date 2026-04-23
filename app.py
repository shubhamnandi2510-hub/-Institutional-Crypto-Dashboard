"""
Market Based Crypto Dashboard (Final Version)
Features:
- Multi-timeframe Candlestick Chart
- EMA (20, 50)
- Bollinger Bands
- MACD + Histogram
- RSI
- Buy/Sell Signals
- Order Book Heatmap
- Silent API fallback (no errors shown)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Market Based Crypto Dashboard", layout="wide", page_icon="📊")

st.title("📊 Market Based Crypto Dashboard")

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    coins = {
        "Bitcoin": "BTCUSDT",
        "Ethereum": "ETHUSDT",
        "BNB": "BNBUSDT",
        "Solana": "SOLUSDT"
    }

    timeframes = {
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

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH DATA (BINANCE + FALLBACK) ────────────────────
@st.cache_data(ttl=60)
def fetch_data(symbol, interval):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code == 451:
            raise Exception("Blocked")

        data = res.json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_av","trades","tb_base_av","tb_quote_av","ignore"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)

        return df

    except:
        # Fallback → CoinGecko
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=10"
        res = requests.get(url, headers=headers)
        data = res.json()

        prices = data["prices"]
        df = pd.DataFrame(prices, columns=["time", "price"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")

        df["open"] = df["price"]
        df["high"] = df["price"]
        df["low"] = df["price"]
        df["close"] = df["price"]
        df["volume"] = 0

        return df

# ─── ORDER BOOK ─────────────────────────────────────────
def fetch_order_book(symbol):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()

        bids = pd.DataFrame(data["bids"], columns=["price", "volume"], dtype=float)
        asks = pd.DataFrame(data["asks"], columns=["price", "volume"], dtype=float)

        return bids, asks
    except:
        return pd.DataFrame(), pd.DataFrame()

# ─── LOAD DATA ─────────────────────────────────────────
df = fetch_data(symbol, interval)

if df.empty:
    st.error("No data available")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

# Bollinger Bands
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

# ─── ADVANCED CHART ─────────────────────────────────────
st.subheader("📊 Technical Analysis")

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3]
)

# Candlestick
fig.add_trace(go.Candlestick(
    x=df["time"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    increasing_line_color="#00c853",
    decreasing_line_color="#ff1744"
), row=1, col=1)

# EMA
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="blue"), name="EMA20"), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange"), name="EMA50"), row=1, col=1)

# Bollinger Bands
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(dash="dot", color="gray"), name="BB Upper"), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], line=dict(dash="dot", color="gray"), fill='tonexty'), row=1, col=1)

# MACD Histogram
colors = np.where(df["MACD_Hist"] >= 0, "green", "red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)

# MACD lines
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue"), name="MACD"), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange"), name="Signal"), row=2, col=1)

fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ─── ORDER BOOK HEATMAP ────────────────────────────────
st.subheader("📊 Order Book Heatmap")

bids, asks = fetch_order_book(symbol)

if not bids.empty:
    ob = pd.concat([bids, asks])
    ob["intensity"] = ob["volume"] / ob["volume"].max()

    heatmap = go.Figure()
    heatmap.add_trace(go.Scatter(
        x=ob["price"],
        y=ob["volume"],
        mode="markers",
        marker=dict(size=8, color=ob["intensity"], colorscale="Turbo")
    ))

    heatmap.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(heatmap, use_container_width=True)
else:
    st.warning("Order book unavailable")
