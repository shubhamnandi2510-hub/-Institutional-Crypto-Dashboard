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

    currency = st.selectbox("Select Currency", ["usd", "eur", "inr"])

    timeframe_map = {
        "15 Minutes": "15T",
        "1 Hour": "1H",
        "4 Hours": "4H",
        "1 Day": "1D"
    }

    selected_tf_label = st.selectbox("Select Timeframe", list(timeframe_map.keys()))
    selected_tf = timeframe_map[selected_tf_label]

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH TOP COINS ─────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_top_coins(currency):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency={currency}&order=market_cap_desc&per_page=10&page=1"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        df = pd.DataFrame([{
            "name": c.get("name"),
            "symbol": c.get("symbol", "").upper(),
            "price": c.get("current_price"),
            "change": c.get("price_change_percentage_24h"),
            "market_cap": c.get("market_cap"),
            "id": c.get("id")
        } for c in data])

        return df

    except Exception as e:
        st.error(f"API Error: {e}")
        return pd.DataFrame()

# ─── FETCH PRICE HISTORY ─────────────────────────────────
@st.cache_data(ttl=60)
def fetch_price_history(coin_id, currency):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency={currency}&days=10"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        df = pd.DataFrame(data["prices"], columns=["time", "price"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)

        return df

    except Exception as e:
        st.error(f"Price fetch error: {e}")
        return pd.DataFrame()

# ─── LOAD DATA ──────────────────────────────────────────
df_top = fetch_top_coins(currency)

if df_top.empty:
    st.error("⚠️ Unable to fetch crypto data")
    st.stop()

# ─── TOP TABLE ──────────────────────────────────────────
st.subheader("🏆 Top 10 Cryptocurrencies")

df_display = df_top.copy()
df_display["price"] = df_display["price"].map(lambda x: f"{x:,.2f}")
df_display["change"] = df_display["change"].map(lambda x: f"{x:+.2f}%")

st.dataframe(df_display, use_container_width=True, hide_index=True)

# ─── SELECT COIN ────────────────────────────────────────
selected_coin = st.selectbox("Select Coin", df_top["name"])
coin_id = df_top[df_top["name"] == selected_coin]["id"].values[0]

# ─── FETCH HISTORY ──────────────────────────────────────
df_price = fetch_price_history(coin_id, currency)

if df_price.empty:
    st.error("Price data unavailable")
    st.stop()

# ─── RESAMPLE ───────────────────────────────────────────
ohlc = df_price["price"].resample(selected_tf).ohlc().dropna()
df = ohlc.reset_index()

if len(df) < 2:
    st.warning("Not enough data")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

# RSI (fixed)
delta = df["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / (avg_loss + 1e-10)
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
c1.metric("💰 Price", f"{latest['close']:.2f}", f"{pct:.2f}%")
c2.metric("📈 RSI", f"{latest['RSI']:.2f}")
c3.metric("📉 MACD", f"{latest['MACD']:.2f}")
c4.metric("🎯 Signal", latest["Trade"])

# ─── CHART ─────────────────────────────────────────────
st.subheader(f"📊 Candlestick Chart ({selected_tf_label})")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])

fig.add_trace(go.Candlestick(
    x=df["time"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    increasing_line_color="#00e676",
    decreasing_line_color="#ff5252"
), row=1, col=1)

fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="cyan")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange")), row=1, col=1)

colors = np.where(df["MACD_Hist"] >= 0, "green", "red")
fig.add_trace(go.Bar(x=df["time"], y=df["MACD_Hist"], marker_color=colors), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue")), row=2, col=1)
fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange")), row=2, col=1)

fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ─── HEATMAP ───────────────────────────────────────────
st.subheader("🔥 Market Heatmap")

heatmap_data = df_top[["name", "change"]].fillna(0)

fig_heat = go.Figure(data=go.Heatmap(
    z=[heatmap_data["change"]],
    x=heatmap_data["name"],
    y=["24h % Change"],
    colorscale="RdYlGn"
))

fig_heat.update_layout(template="plotly_dark", height=250)
st.plotly_chart(fig_heat, use_container_width=True)

# ─── RAW DATA ──────────────────────────────────────────
with st.expander("📁 View Raw Data & Trade Signals"):
    st.dataframe(df.sort_values("time", ascending=False), use_container_width=True)
