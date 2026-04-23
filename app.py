import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Market Based Crypto Dashboard", layout="wide", page_icon="📊")
st.title("📊 Market Based Crypto Dashboard")

# ─── SIDEBAR ─────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    coins = {
        "Bitcoin": "BTCUSDT",
        "Ethereum": "ETHUSDT",
        "BNB": "BNBUSDT",
        "Solana": "SOLUSDT"
    }

    timeframes = {
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d"
    }

    selected_coin = st.selectbox("Asset", list(coins.keys()))
    selected_tf = st.selectbox("Timeframe", list(timeframes.keys()))

    symbol = coins[selected_coin]
    interval = timeframes[selected_tf]

    if st.button("🔄 Refresh"):
        st.cache_data.clear()

# ─── FETCH DATA ──────────────────────
@st.cache_data(ttl=60)
def fetch_data(symbol, interval):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "ct","qav","trades","tb","tq","ignore"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)

        return df

    except:
        return pd.DataFrame()

# ─── ORDER BOOK ──────────────────────
def fetch_orderbook(symbol):
    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
        r = requests.get(url, timeout=10)
        data = r.json()

        bids = pd.DataFrame(data["bids"], columns=["price","volume"], dtype=float)
        asks = pd.DataFrame(data["asks"], columns=["price","volume"], dtype=float)

        return bids, asks
    except:
        return pd.DataFrame(), pd.DataFrame()

df = fetch_data(symbol, interval)

if df.empty:
    st.warning("Data unavailable")
    st.stop()

# ─── INDICATORS ──────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

df["MA20"] = df["close"].rolling(20).mean()
df["STD"] = df["close"].rolling(20).std()
df["Upper"] = df["MA20"] + 2 * df["STD"]
df["Lower"] = df["MA20"] - 2 * df["STD"]

delta = df["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

rs = gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI"].fillna(50, inplace=True)

ema12 = df["close"].ewm(span=12).mean()
ema26 = df["close"].ewm(span=26).mean()
df["MACD"] = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9).mean()
df["MACD_Hist"] = df["MACD"] - df["Signal"]

# ─── SIGNALS ─────────────────────────
df["Trade"] = "HOLD"
df.loc[(df["RSI"] < 30) & (df["MACD"] > df["Signal"]), "Trade"] = "BUY"
df.loc[(df["RSI"] > 70) & (df["MACD"] < df["Signal"]), "Trade"] = "SELL"

# ─── METRICS ─────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

change = latest["close"] - prev["close"]
pct = (change / prev["close"]) * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Price", f"${latest['close']:.2f}", f"{pct:.2f}%")
c2.metric("RSI", f"{latest['RSI']:.2f}")
c3.metric("MACD", f"{latest['MACD']:.2f}")
c4.metric("Signal", latest["Trade"])

# ─── CHART ───────────────────────────
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7,0.3])

fig.add_trace(go.Candlestick(
    x=df["time"], open=df["open"], high=df["high"],
    low=df["low"], close=df["close"],
    increasing_line_color="#00e676",
    decreasing_line_color="#ff5252"
), row=1, col=1)

fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20", line=dict(color="cyan")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50", line=dict(color="orange")), row=1, col=1)

fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(color="gray", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty'), row=1, col=1)

colors = np.where(df["MACD_Hist"]>=0, "green","red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)

fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue")), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange")), row=2, col=1)

fig.update_layout(template="plotly_dark", height=700)
st.plotly_chart(fig, use_container_width=True)

# ─── ORDER BOOK HEATMAP ──────────────
st.subheader("🔥 Order Book Heatmap")

bids, asks = fetch_orderbook(symbol)

if not bids.empty:
    bids["side"] = "Bids"
    asks["side"] = "Asks"

    ob = pd.concat([bids, asks])

    # Normalize
    ob["volume_norm"] = ob["volume"] / ob["volume"].max()

    heatmap = go.Figure()

    heatmap.add_trace(go.Scatter(
        x=ob["price"],
        y=ob["side"],
        mode="markers",
        marker=dict(
            size=ob["volume_norm"] * 20,
            color=ob["volume_norm"],
            colorscale="Turbo",
            showscale=True
        )
    ))

    heatmap.update_layout(
        template="plotly_dark",
        height=400,
        title="Liquidity Heatmap (Order Book)"
    )

    st.plotly_chart(heatmap, use_container_width=True)

else:
    st.info("Order book unavailable")
