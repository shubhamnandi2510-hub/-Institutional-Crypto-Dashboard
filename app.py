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
        "Bitcoin": ("BTCUSDT", "bitcoin"),
        "Ethereum": ("ETHUSDT", "ethereum"),
        "BNB": ("BNBUSDT", "binancecoin"),
        "Solana": ("SOLUSDT", "solana")
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

    symbol, cg_id = coins[selected_coin]
    interval = timeframes[selected_tf]

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH MARKET DATA ─────────────────────────────────
@st.cache_data(ttl=60)
def fetch_data(symbol, interval, cg_id):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            raise Exception("API Error")

        data = res.json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_av","trades","tb_base_av","tb_quote_av","ignore"
        ])

        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
        return df

    except Exception as e:
        # Fallback to CoinGecko
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days=10"
            res = requests.get(url, headers=headers)
            data = res.json()
            prices = data["prices"]
            df = pd.DataFrame(prices, columns=["time", "price"])
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            
            # Mimic OHLC for fallback
            df["open"] = df["price"]
            df["high"] = df["price"]
            df["low"] = df["price"]
            df["close"] = df["price"]
            df["volume"] = 0.0
            return df
        except:
            return pd.DataFrame()

# ─── ORDER BOOK ─────────────────────────────────────────
def fetch_order_book(symbol):
    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
        data = requests.get(url, timeout=5).json()
        bids = pd.DataFrame(data["bids"], columns=["price", "volume"], dtype=float)
        asks = pd.DataFrame(data["asks"], columns=["price", "volume"], dtype=float)
        return bids, asks
    except:
        return pd.DataFrame(), pd.DataFrame()

# ─── LOAD DATA ─────────────────────────────────────────
df = fetch_data(symbol, interval, cg_id)

if df.empty or len(df) < 2:
    st.error("Unable to load data. Please check your internet connection or try again later.")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
# Technical indicators logic
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()
df["MA20"] = df["close"].rolling(20).mean()
df["STD"] = df["close"].rolling(20).std()
df["Upper"] = df["MA20"] + (2 * df["STD"])
df["Lower"] = df["MA20"] - (2 * df["STD"])

# RSI
delta = df["close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss.replace(0, np.nan)
df["RSI"] = 100 - (100 / (1 + rs))
df["RSI"] = df["RSI"].fillna(50)

# MACD
ema12 = df["close"].ewm(span=12, adjust=False).mean()
ema26 = df["close"].ewm(span=26, adjust=False).mean()
df["MACD"] = ema12 - ema26
df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
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

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 Price", f"${latest['close']:,.2f}", f"{pct:.2f}%")
m2.metric("📈 RSI (14)", f"{latest['RSI']:.2f}")
m3.metric("📉 MACD", f"{latest['MACD']:.4f}")
m4.metric("🎯 Signal", latest["Trade"])

# ─── MAIN CHART ────────────────────────────────────────
st.subheader(f"📊 {selected_coin} Technical Analysis ({selected_tf})")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                   vertical_spacing=0.05, row_heights=[0.7, 0.3])

# Candlestick
fig.add_trace(go.Candlestick(
    x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
    name="Price", increasing_line_color="#00e676", decreasing_line_color="#ff5252"
), row=1, col=1)

# Overlay EMA and Bollinger
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA 20", line=dict(color="cyan", width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA 50", line=dict(color="orange", width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], name="BB Upper", line=dict(color="rgba(173, 216, 230, 0.4)", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], name="BB Lower", line=dict(color="rgba(173, 216, 230, 0.4)", dash="dot"), fill='tonexty'), row=1, col=1)

# MACD Subplot
colors = ["#00e676" if x >= 0 else "#ff5252" for x in df["MACD_Hist"]]
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], name="Histogram", marker_color=colors), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], name="MACD", line=dict(color="white", width=1.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], name="Signal", line=dict(color="yellow", width=1)), row=2, col=1)

fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

# ─── ORDER BOOK HEATMAP ────────────────────────────────
st.subheader("🔥 Order Book Depth Heatmap")

bids, asks = fetch_order_book(symbol)

if not bids.empty and not asks.empty:
    bids["side"] = "Bids (Support)"
    asks["side"] = "Asks (Resistance)"
    ob = pd.concat([bids, asks])
    
    # Normalize volume for marker size
    max_vol = ob["volume"].max() if ob["volume"].max() > 0 else 1
    ob["intensity"] = ob["volume"] / max_vol

    heatmap = go.Figure()
    heatmap.add_trace(go.Scatter(
        x=ob["price"],
        y=ob["side"],
        mode="markers",
        marker=dict(
            size=ob["intensity"] * 50,
            color=ob["volume"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Volume")
        ),
        text=ob["volume"],
        hovertemplate="Price: %{x}<br>Volume: %{text}<extra></extra>"
    ))

    heatmap.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(heatmap, use_container_width=True)
else:
    st.warning("Order book data could not be retrieved. This may be due to Binance API regional restrictions.")
