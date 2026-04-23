import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Crypto Dashboard Pro", layout="wide", page_icon="📊")
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
        "1 Minute": "1min",
        "5 Minutes": "5min",
        "15 Minutes": "15min",
        "1 Hour": "1H",
        "4 Hours": "4H",
        "1 Day": "1D"
    }

    selected_coin = st.selectbox("Select Main Asset", list(coins.keys()))
    compare_coins = st.multiselect(
        "Compare With",
        list(coins.keys()),
        default=["Ethereum"]
    )

    selected_tf = st.selectbox("Timeframe", list(timeframes.keys()))

    coin_id = coins[selected_coin]
    tf = timeframes[selected_tf]

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH DATA ─────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
    res = requests.get(url, timeout=10)

    if res.status_code != 200:
        return pd.DataFrame()

    data = res.json()
    df = pd.DataFrame(data["prices"], columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)
    return df

# ─── RESAMPLE ──────────────────────────────────────────
def resample_df(df, timeframe):
    ohlc = df["price"].resample(timeframe).ohlc()
    ohlc["volume"] = 0
    return ohlc.dropna().reset_index()

# ─── MAIN DATA ─────────────────────────────────────────
df_raw = fetch_data(coin_id)

if df_raw.empty:
    st.error("Failed to fetch data")
    st.stop()

df = resample_df(df_raw, tf)

# ─── INDICATORS ─────────────────────────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

df["MA20"] = df["close"].rolling(20).mean()
df["STD"] = df["close"].rolling(20).std()
df["Upper"] = df["MA20"] + 2 * df["STD"]
df["Lower"] = df["MA20"] - 2 * df["STD"]

# ─── METRICS ───────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

pct = ((latest["close"] - prev["close"]) / prev["close"]) * 100

c1, c2 = st.columns(2)
c1.metric("💰 Price", f"${latest['close']:.2f}", f"{pct:.2f}%")
c2.metric("📊 Trend", "Bullish" if latest["close"] > latest["EMA20"] else "Bearish")

# ─── CANDLESTICK CHART ─────────────────────────────────
st.subheader("📈 Candlestick Chart")

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["time"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    increasing_line_color="#00ff9f",
    decreasing_line_color="#ff4d4d"
))

# EMA
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20", line=dict(color="cyan")))
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50", line=dict(color="orange")))

# Bollinger
fig.add_trace(go.Scatter(x=df["time"], y=df["Upper"], line=dict(color="gray", dash="dot")))
fig.add_trace(go.Scatter(x=df["time"], y=df["Lower"], fill='tonexty', line=dict(color="gray", dash="dot")))

fig.update_layout(
    template="plotly_dark",
    height=600,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)

# ─── COMPARISON CHART ──────────────────────────────────
st.subheader("📊 Asset Comparison")

comp_fig = go.Figure()

# Add main coin
main_prices = df_raw["price"] / df_raw["price"].iloc[0] * 100
comp_fig.add_trace(go.Scatter(
    x=df_raw.index,
    y=main_prices,
    name=selected_coin,
    line=dict(width=3)
))

# Add comparison coins
for coin in compare_coins:
    coin_df = fetch_data(coins[coin])
    if not coin_df.empty:
        norm_price = coin_df["price"] / coin_df["price"].iloc[0] * 100
        comp_fig.add_trace(go.Scatter(
            x=coin_df.index,
            y=norm_price,
            name=coin
        ))

comp_fig.update_layout(
    template="plotly_dark",
    height=400,
    yaxis_title="Normalized Performance (%)"
)

st.plotly_chart(comp_fig, use_container_width=True)

# ─── HEATMAP AT BOTTOM ─────────────────────────────────
st.subheader("🔥 Market Heatmap")

price_levels = np.linspace(df["low"].min(), df["high"].max(), 50)
intensity = np.random.rand(50)

heatmap = go.Figure(data=go.Heatmap(
    z=intensity.reshape(-1, 1),
    y=price_levels,
    colorscale="Turbo"
))

heatmap.update_layout(
    template="plotly_dark",
    height=300,
    xaxis_showticklabels=False
)

st.plotly_chart(heatmap, use_container_width=True)

# ─── RAW DATA ──────────────────────────────────────────
with st.expander("📁 View Raw Data"):
    st.dataframe(df.sort_values("time", ascending=False), use_container_width=True)
