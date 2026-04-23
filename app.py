import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Crypto Dashboard (Excel)", layout="wide", page_icon="📊")
st.title("📊 Market Based Crypto Dashboard (Excel Data)")

# ─── LOAD EXCEL ─────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_excel("your_file.xlsx", header=None)

    # Extract main table starting point
    table = df.iloc[54:].reset_index(drop=True)

    # Rename columns
    table.columns = [
        "ignore", "Rank", "Coin", "Action", "Price",
        "1h", "24h", "7d", "Volume", "Market Cap", "Chart"
    ]

    # Drop empty rows
    table = table.dropna(subset=["Rank"])

    # Clean data
    table["Coin"] = table["Coin"].fillna(method="ffill")
    table["Price"] = table["Price"].replace('[\$,]', '', regex=True).astype(float)
    table["Volume"] = table["Volume"].replace('[\$,]', '', regex=True).astype(float)
    table["Market Cap"] = table["Market Cap"].replace('[\$,]', '', regex=True).astype(float)

    return table[["Rank", "Coin", "Price", "24h", "Volume", "Market Cap"]]

df = load_data()

# ─── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    coin_list = df["Coin"].unique()
    selected_coin = st.selectbox("Select Coin", coin_list)

# ─── FILTER DATA ───────────────────────────────────────
coin_df = df[df["Coin"] == selected_coin]

# ─── METRICS ───────────────────────────────────────────
latest = coin_df.iloc[0]

c1, c2, c3 = st.columns(3)

c1.metric("💰 Price", f"${latest['Price']:,.2f}")
c2.metric("📈 24h Change", f"{latest['24h']}")
c3.metric("🏦 Market Cap", f"${latest['Market Cap']:,.0f}")

# ─── FAKE TIME SERIES (since Excel has no history) ──────
st.subheader("📊 Price Chart")

dates = pd.date_range(end=pd.Timestamp.now(), periods=50)

prices = np.random.normal(latest["Price"], latest["Price"] * 0.01, size=50)

ohlc = pd.DataFrame({
    "time": dates,
    "open": prices,
    "high": prices * 1.01,
    "low": prices * 0.99,
    "close": prices
})

# ─── CHART ─────────────────────────────────────────────
fig = make_subplots(rows=1, cols=1)

fig.add_trace(go.Candlestick(
    x=ohlc["time"],
    open=ohlc["open"],
    high=ohlc["high"],
    low=ohlc["low"],
    close=ohlc["close"],
    increasing_line_color="#00e676",
    decreasing_line_color="#ff5252"
))

fig.update_layout(template="plotly_dark", height=600)

st.plotly_chart(fig, use_container_width=True)

# ─── TABLE ─────────────────────────────────────────────
st.subheader("📊 Top Coins")
st.dataframe(df, use_container_width=True)
