"""
Market Based Crypto Dashboard (Stable Version)

Features:
- Multi-timeframe (5m, 15m, 1h, 4h, 1d)
- Candlestick Chart
- EMA, Bollinger Bands
- RSI, MACD
- Buy/Sell Signals
- Raw Data Table
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Crypto Dashboard", layout="wide")
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

    timeframes = {
        "5 Minutes": "5min",
        "15 Minutes": "15min",
        "1 Hour": "1H",
        "4 Hours": "4H",
        "1 Day": "1D"
    }

    selected_coin = st.selectbox("Select Asset", list(coins.keys()))
    selected_tf = st.selectbox("Select Timeframe", list(timeframes.keys()))

    coin_id = coins[selected_coin]
    tf = timeframes[selected_tf]

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH DATA ─────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_data(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        if "prices" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(data["prices"], columns=["time", "price"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df.sort_values("time")
        df.set_index("time", inplace=True)

        return df

    except Exception:
        return pd.DataFrame()

# ─── RESAMPLE (FIXED) ─────────────────────────────────
def resample_df(df, timeframe):
    try:
        ohlc = df["price"].resample(timeframe).ohlc()
        ohlc.dropna(inplace=True)
        return ohlc.reset_index()
    except Exception:
        return pd.DataFrame()

# ─── LOAD DATA ─────────────────────────────────────────
df_raw = fetch_data(coin_id)

if df_raw.empty:
    st.error("❌ Failed to load data. Try again.")
    st.stop()

df = resample_df(df_raw, tf)

if df.empty or len(df) < 2:
    st.warning("⚠️ Not enough data for selected timeframe")
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
df["RSI"] = df["RSI"].fillna(50)

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

# Candlestick
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
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20"), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50"), row=1, col=1)

# Bollinger Bands
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty'), row=1, col=1)

# MACD
colors = np.where(df["MACD_Hist"] >= 0, "green", "red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"]), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"]), row=2, col=1)

fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False)

st.plotly_chart(fig, use_container_width=True)

# ─── RAW DATA ─────────────────────────────────────────
with st.expander("📁 View Raw Data & Trade Signals"):
    st.dataframe(
        df.sort_values("time", ascending=False),
        use_container_width=True,
        hide_index=True
    )
