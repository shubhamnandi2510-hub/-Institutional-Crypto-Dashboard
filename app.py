import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── PAGE CONFIG ───────────────────────────────────────
st.set_page_config(layout="wide", page_title="Pro Crypto Terminal", page_icon="📈")

# ─── DARK THEME CSS ────────────────────────────────────
st.markdown("""
<style>
body {background-color: #0e1117;}
.block-container {padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)

st.title("📈 Crypto Trading Terminal")

# ─── FETCH DATA (CoinGecko) ────────────────────────────
@st.cache_data(ttl=60)
def fetch_data():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
    res = requests.get(url, timeout=10)
    data = res.json()

    return pd.DataFrame([{
        "name": c["name"],
        "symbol": c["symbol"].upper(),
        "price": c["current_price"],
        "change": c["price_change_percentage_24h"],
        "market_cap": c["market_cap"],
        "id": c["id"]
    } for c in data])

@st.cache_data(ttl=60)
def fetch_history(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
    res = requests.get(url, timeout=10)
    data = res.json()

    df = pd.DataFrame(data["prices"], columns=["time", "price"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)
    return df

def resample_df(df, tf):
    ohlc = df["price"].resample(tf).ohlc()
    ohlc.dropna(inplace=True)
    return ohlc.reset_index()

# ─── LOAD DATA ─────────────────────────────────────────
coins = fetch_data()
selected = st.sidebar.selectbox("Select Coin", coins["name"])
tf = st.sidebar.selectbox("Timeframe", ["5T","15T","1H","4H","1D"])

coin = coins[coins["name"] == selected].iloc[0]
df_raw = fetch_history(coin["id"])
df = resample_df(df_raw, tf)

# ─── INDICATORS ─────────────────────────────────────────
df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()

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
df["Hist"] = df["MACD"] - df["Signal"]

# ─── LAYOUT (TRADINGVIEW STYLE) ────────────────────────
left, right = st.columns([3,1])

# ─── MAIN CHART ────────────────────────────────────────
with left:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6,0.2,0.2])

    # Candles
    fig.add_trace(go.Candlestick(
        x=df["time"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color="#00ff9c",
        decreasing_line_color="#ff4d4d"
    ), row=1, col=1)

    # EMA
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="cyan")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange")), row=1, col=1)

    # MACD
    colors = np.where(df["Hist"] >= 0, "green", "red")
    fig.add_trace(go.Bar(x=df["time"], y=df["Hist"], marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["time"], y=df["MACD"], line=dict(color="blue")), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["time"], y=df["Signal"], line=dict(color="orange")), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df["time"], y=df["RSI"], line=dict(color="purple")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(template="plotly_dark", height=800, margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

# ─── SIDE PANEL (LIKE TRADINGVIEW WATCHLIST) ───────────
with right:
    st.subheader("📊 Watchlist")

    for _, row in coins.iterrows():
        color = "green" if row["change"] > 0 else "red"
        st.markdown(
            f"""
            **{row['symbol']}**  
            ${row['price']:.2f}  
            <span style='color:{color}'>{row['change']:.2f}%</span>
            """,
            unsafe_allow_html=True
        )

# ─── BOTTOM DATA TABLE ─────────────────────────────────
st.markdown("---")
st.subheader("📁 Market Data")
st.dataframe(coins, use_container_width=True)
