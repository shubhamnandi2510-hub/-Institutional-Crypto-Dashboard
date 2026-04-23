import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Market Based Crypto Dashboard", layout="wide", page_icon="📊")
st.title("📊 Market Based Crypto Dashboard")

# 👉 ADD YOUR CoinMarketCap API Key here
CMC_API_KEY = "YOUR_API_KEY"

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    coins = {
        "Bitcoin": ("BTC", "bitcoin"),
        "Ethereum": ("ETH", "ethereum"),
        "BNB": ("BNB", "binancecoin"),
        "Solana": ("SOL", "solana")
    }

    timeframes = {
        "5 Min": "5T",
        "15 Min": "15T",
        "1 Hour": "1H",
        "4 Hour": "4H",
        "1 Day": "1D"
    }

    selected_coin = st.selectbox("Select Asset", list(coins.keys()))
    selected_tf = st.selectbox("Select Timeframe", list(timeframes.keys()))

    symbol, coingecko_id = coins[selected_coin]
    tf = timeframes[selected_tf]

    if st.button("🔄 Refresh"):
        st.cache_data.clear()

# ─── FETCH CoinMarketCap DATA ───────────────────────────
@st.cache_data(ttl=60)
def fetch_cmc_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()["data"]

        df = pd.DataFrame([{
            "symbol": c["symbol"],
            "price": c["quote"]["USD"]["price"],
            "change": c["quote"]["USD"]["percent_change_24h"],
            "market_cap": c["quote"]["USD"]["market_cap"]
        } for c in data])

        return df

    except:
        return pd.DataFrame()

# ─── FETCH CoinGecko OHLC ───────────────────────────────
@st.cache_data(ttl=60)
def fetch_ohlc(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
    res = requests.get(url, timeout=10)
    data = res.json()

    df = pd.DataFrame(data["prices"], columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)

    return df

def resample_ohlc(df, timeframe):
    ohlc = df["price"].resample(timeframe).ohlc()
    ohlc["volume"] = 0
    ohlc.dropna(inplace=True)
    return ohlc.reset_index()

# ─── LOAD DATA ─────────────────────────────────────────
cmc_df = fetch_cmc_data()
if cmc_df.empty:
    st.error("❌ CoinMarketCap API failed. Check API key.")
    st.stop()

coin_data = cmc_df[cmc_df["symbol"] == symbol].iloc[0]

df_raw = fetch_ohlc(coingecko_id)
df = resample_ohlc(df_raw, tf)

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

c1.metric("💰 Price", f"${coin_data['price']:.2f}")
c2.metric("📈 24h Change", f"{coin_data['change']:.2f}%")
c3.metric("🏦 Market Cap", f"${coin_data['market_cap']:.0f}")
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
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="cyan"), name="EMA20"), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange"), name="EMA50"), row=1, col=1)

# Bollinger
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(color="gray", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty', line=dict(color="gray", dash="dot")), row=1, col=1)

# BUY / SELL markers
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
