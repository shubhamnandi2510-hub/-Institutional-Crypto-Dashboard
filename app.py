import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Crypto Candlestick Dashboard", layout="wide", page_icon="📊")
st.title("📊 Crypto Candlestick Dashboard")

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    currency = st.selectbox("Select Currency", ["usd", "eur", "inr"])

    timeframe_map = {
        "1 Minute": "1min",
        "15 Minutes": "15min",
        "1 Hour": "hourly",
        "4 Hours": "hourly",
        "1 Day": "daily"
    }

    selected_tf = st.selectbox("Select Timeframe", list(timeframe_map.keys()))

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

# ─── FETCH TOP COINS ─────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_top_coins(currency):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency={currency}&order=market_cap_desc&per_page=10&page=1"
    
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

# ─── FETCH PRICE DATA ───────────────────────────────────
@st.cache_data(ttl=60)
def fetch_price_history(coin_id, currency):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency={currency}&days=10"
    
    res = requests.get(url, timeout=10)
    data = res.json()

    df = pd.DataFrame(data["prices"], columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)

    return df

# ─── RESAMPLE (FIXED FOR ALL TIMEFRAMES) ────────────────
def resample_df(df, tf):
    tf_map = {
        "1 Minute": "1T",
        "15 Minutes": "15T",
        "1 Hour": "1H",
        "4 Hours": "4H",
        "1 Day": "1D"
    }

    freq = tf_map[tf]

    ohlc = df["price"].resample(freq).ohlc().dropna()
    return ohlc.reset_index()

# ─── LOAD DATA ──────────────────────────────────────────
df_top = fetch_top_coins(currency)

if df_top.empty:
    st.error("⚠️ Failed to fetch data. Try again.")
    st.stop()

# ─── TOP 10 TABLE ───────────────────────────────────────
st.subheader("🏆 Top 10 Cryptocurrencies")
st.dataframe(df_top, use_container_width=True, hide_index=True)

# ─── SELECT COIN ────────────────────────────────────────
coin = st.selectbox("Select Coin", df_top["name"])
coin_id = df_top[df_top["name"] == coin]["id"].values[0]

# ─── FETCH + RESAMPLE ───────────────────────────────────
df_price = fetch_price_history(coin_id, currency)
df = resample_df(df_price, selected_tf)

if df.empty:
    st.error("No data available for selected timeframe.")
    st.stop()

# ─── METRICS ────────────────────────────────────────────
latest = df.iloc[-1]
prev = df.iloc[-2]

change = latest["close"] - prev["close"]
pct = (change / prev["close"]) * 100

c1, c2 = st.columns(2)
c1.metric("💰 Price", f"{latest['close']:.2f}", f"{pct:.2f}%")
c2.metric("📊 Timeframe", selected_tf)

# ─── CANDLESTICK CHART ─────────────────────────────────
st.subheader("📊 Candlestick Chart")

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["time"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"],
    increasing_line_color="#00e676",
    decreasing_line_color="#ff5252"
))

fig.update_layout(
    template="plotly_dark",
    height=700,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)

# ─── RAW DATA ──────────────────────────────────────────
with st.expander("📁 View Raw Data"):
    st.dataframe(df.sort_values("time", ascending=False), use_container_width=True, hide_index=True)
