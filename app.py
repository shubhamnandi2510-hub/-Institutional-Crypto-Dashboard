"""
Institutional Crypto Dashboard (Final Fixed Version)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Institutional Crypto Dashboard", layout="wide", page_icon="🏦")
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

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH DATA (FIXED) ─────────────────────────────────
@st.cache_data(ttl=60)
def fetch_data(symbol, interval):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
    
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        # 🔥 Handle Binance error response
        if isinstance(data, dict) and "code" in data:
            return None, data.get("msg", "Unknown API error")

    except Exception as e:
        return None, str(e)

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","quote_av","trades","tb_base_av","tb_quote_av","ignore"
    ])

    if df.empty:
        return None, "Empty response from API"

    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)

    return df, None


with st.spinner("Fetching market data..."):
    df, error = fetch_data(symbol, interval)

if error:
    st.error(f"API Error: {error}")
    st.warning("Try switching timeframe or refresh after a few seconds.")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────

# EMA
df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

# Bollinger Bands
df["MA20"] = df["close"].rolling(20).mean()
df["STD"] = df["close"].rolling(20).std()
df["Upper"] = df["MA20"] + 2 * df["STD"]
df["Lower"] = df["MA20"] - 2 * df["STD"]

# RSI (FIXED)
delta = df["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss.replace(0, np.nan)
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI"].fillna(50, inplace=True)

# MACD
ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
df["MACD"] = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
df["MACD_Hist"] = df["MACD"] - df["Signal"]

# Support & Resistance
df["Support"] = df["low"].rolling(20).min()
df["Resistance"] = df["high"].rolling(20).max()

# ─── SIGNALS ────────────────────────────────────────────
df["Trade"] = "HOLD"

df.loc[
    (df["RSI"] < 30) & (df["MACD"] > df["Signal"]) & (df["close"] > df["EMA20"]),
    "Trade"
] = "BUY"

df.loc[
    (df["RSI"] > 70) & (df["MACD"] < df["Signal"]) & (df["close"] < df["EMA20"]),
    "Trade"
] = "SELL"

# ─── METRICS ────────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

price_change = latest["close"] - prev["close"]
price_pct = (price_change / prev["close"]) * 100

c1, c2, c3, c4 = st.columns(4)

c1.metric("💰 Price", f"${latest['close']:.2f}", f"{price_change:.2f} ({price_pct:.2f}%)")
c2.metric("📈 RSI", f"{latest['RSI']:.2f}")
c3.metric("📉 MACD", f"{latest['MACD']:.2f}")
c4.metric("🎯 Signal", latest["Trade"])

# ─── CHART ──────────────────────────────────────────────
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    row_heights=[0.6, 0.2, 0.2])

# Candlestick
fig.add_trace(go.Candlestick(
    x=df["time"], open=df["open"], high=df["high"],
    low=df["low"], close=df["close"]
), row=1, col=1)

# EMA
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20"), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50"), row=1, col=1)

# MACD
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], name="MACD"), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], name="Signal"), row=2, col=1)

# RSI
fig.add_trace(go.Scatter(x=df["time"], y=df["RSI"], name="RSI"), row=3, col=1)
fig.add_hline(y=70, row=3, col=1)
fig.add_hline(y=30, row=3, col=1)

fig.update_layout(template="plotly_dark", height=800)
st.plotly_chart(fig, use_container_width=True)

# ─── TABLE ──────────────────────────────────────────────
with st.expander("📁 Data"):
    st.dataframe(df.tail(50), use_container_width=True)
