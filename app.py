import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Market Based Crypto Dashboard", layout="wide", page_icon="📊")
st.title("📊 Market Based Crypto Dashboard")

# ─── FETCH TOP COINS (CoinGecko) ────────────────────────
@st.cache_data(ttl=60)
def fetch_data():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
    
    try:
        res = requests.get(url, timeout=10)
        data = res.json()

        df = pd.DataFrame([{
            "name": c["name"],
            "symbol": c["symbol"].upper(),
            "price": c["current_price"],
            "change": c["price_change_percentage_24h"],
            "market_cap": c["market_cap"],
            "id": c["id"]
        } for c in data])

        return df

    except:
        return pd.DataFrame()

# ─── FETCH HISTORICAL DATA ─────────────────────────────
@st.cache_data(ttl=60)
def fetch_history(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
    res = requests.get(url, timeout=10)
    data = res.json()

    df = pd.DataFrame(data["prices"], columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)

    return df

# ─── RESAMPLE FOR TIMEFRAME ─────────────────────────────
def resample_df(df, timeframe):
    ohlc = df["price"].resample(timeframe).ohlc()
    ohlc["volume"] = 0
    ohlc.dropna(inplace=True)
    return ohlc.reset_index()

# ─── LOAD DATA ─────────────────────────────────────────
coins_df = fetch_data()

if coins_df.empty:
    st.error("❌ Failed to fetch data from CoinGecko")
    st.stop()

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    selected_coin = st.selectbox("Select Coin", coins_df["name"])
    timeframe = st.selectbox("Timeframe", ["5T", "15T", "1H", "4H", "1D"])

    if st.button("🔄 Refresh"):
        st.cache_data.clear()

coin = coins_df[coins_df["name"] == selected_coin].iloc[0]

# ─── FETCH PRICE HISTORY ───────────────────────────────
df_raw = fetch_history(coin["id"])
df = resample_df(df_raw, timeframe)

if len(df) < 20:
    st.warning("Not enough data")
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
c1, c2, c3, c4 = st.columns(4)

c1.metric("💰 Price", f"${coin['price']:.2f}")
c2.metric("📈 24h Change", f"{coin['change']:.2f}%")
c3.metric("🏦 Market Cap", f"${coin['market_cap']:.0f}")
c4.metric("🎯 Signal", df.iloc[-1]["Trade"])

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
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="cyan")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange")), row=1, col=1)

# Bollinger
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(color="gray", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty', line=dict(color="gray", dash="dot")), row=1, col=1)

# Buy/Sell markers
buy = df[df["Trade"] == "BUY"]
sell = df[df["Trade"] == "SELL"]

fig.add_trace(go.Scatter(x=buy["time"], y=buy["low"], mode="markers",
                         marker=dict(color="green", size=10), name="BUY"), row=1, col=1)

fig.add_trace(go.Scatter(x=sell["time"], y=sell["high"], mode="markers",
                         marker=dict(color="red", size=10), name="SELL"), row=1, col=1)

# MACD
colors = np.where(df["MACD_Hist"] >= 0, "green", "red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue")), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange")), row=2, col=1)

fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False)

st.plotly_chart(fig, use_container_width=True)

# ─── RAW DATA ─────────────────────────────────────────
with st.expander("📁 View Raw Data & Trade Signals"):
    st.dataframe(df.sort_values("time", ascending=False), use_container_width=True)
