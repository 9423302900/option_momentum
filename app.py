# app.py
import streamlit as st
import pandas as pd
import time
import json
import os
from datetime import datetime, timezone
from typing import Dict

from indicators import compute_all
from telegram_alerts import send_telegram_message

import requests

# ---------- Config ----------
CONFIG_FILE = "config.json"
ALERTS_FILE = "alerts_sent.json"  # persists to avoid duplicate alerts

st.set_page_config(page_title="Option Momentum Alert", layout="wide")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        st.error(f"Create {CONFIG_FILE} with your Dhan/NSE and Telegram credentials. See README.")
        st.stop()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

cfg = load_config()

# ---------- Helpers ----------
def persist_alert(symbol, ts):
    data = {}
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            try:
                data = json.load(f)
            except:
                data = {}
    data[symbol] = ts
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f)

def was_alert_sent_recent(symbol, minutes=30):
    if not os.path.exists(ALERTS_FILE):
        return False
    with open(ALERTS_FILE, "r") as f:
        try:
            data = json.load(f)
        except:
            return False
    if symbol not in data:
        return False
    last_ts = datetime.fromisoformat(data[symbol])
    diff = datetime.now(timezone.utc) - last_ts.replace(tzinfo=timezone.utc)
    return diff.total_seconds() <= minutes * 60

# ---------- Data fetch (placeholder) ----------
def fetch_candles(symbol: str, interval="5m", limit=200) -> pd.DataFrame:
    """
    Fetch OHLCV candles for the option symbol.
    Replace with your real data provider code (Dhan / NSE API / broker feed).
    Return DataFrame with columns: ['open','high','low','close','volume'] sorted oldest -> newest.
    """
    # Example: Dhan historical candles (pseudocode) - replace below
    # endpoint = f"https://api.dhan.co/exchange/v1/ohlc?symbol={symbol}&interval={interval}&limit={limit}"
    # headers = {"Authorization": f"Bearer {cfg['dhan_token']}"}
    # r = requests.get(endpoint, headers=headers, timeout=10).json()
    # parse r into DataFrame...
    #
    # === For demo / if you don't have API, raise with helpful message ===
    if cfg.get("demo_mode", False):
        # demo: create synthetic data for UI testing
        idx = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="5T")
        import numpy as np
        price = 100 + np.cumsum(np.random.randn(limit).cumsum() * 0.1)
        df = pd.DataFrame({
            "open": price,
            "high": price + np.random.rand(limit) * 1.5,
            "low": price - np.random.rand(limit) * 1.5,
            "close": price + (np.random.rand(limit)-0.5),
            "volume": (np.random.rand(limit) * 50 + 10).astype(int)
        }, index=idx)
        return df
    raise RuntimeError("fetch_candles: You must implement the data fetch logic for your provider. Set demo_mode true in config.json to test UI.")

# ---------- Signal logic ----------
def detect_momentum_signal(df: pd.DataFrame) -> Dict:
    """
    Return a dict with signal info if last bar satisfies momentum breakout.
    """
    if df is None or len(df) < 30:
        return {}
    df = compute_all(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Conditions per our design
    ema_cross = last['ema9'] > last['ema21'] and prev['ema9'] <= prev['ema21']
    rsi_burst = last['rsi5'] > 55
    vol_spike = last['vol_spike'] == True
    atr_spike = last['atr_spike'] == True
    price_above_emas = last['close'] > last['ema9'] and last['close'] > last['ema21']

    # final boolean
    signal = (ema_cross or price_above_emas) and rsi_burst and vol_spike and atr_spike

    return {
        "signal": bool(signal),
        "ema_cross": bool(ema_cross),
        "rsi5": float(last['rsi5']),
        "vol_spike": bool(vol_spike),
        "atr_spike": bool(atr_spike),
        "close": float(last['close']),
        "time": str(last.name)
    }

# ---------- Streamlit UI ----------
st.title("Option Momentum Breakout Alerts")
st.markdown("Detects EMA9/21 breakout + RSI(5) + Volume + ATR spike and sends Telegram alerts.")

col1, col2 = st.columns([1, 3])

with col1:
    st.header("Settings")
    symbols_text = st.text_area("Symbols (one per line)", value="\n".join(cfg.get("watch_symbols", [])), height=200)
    run_button = st.button("Run Check Now")
    autorefresh = st.checkbox("Auto-check every 60s (uses rerun)", value=False)
    alert_minutes_lockout = st.number_input("Alert cooldown (minutes)", value=30, min_value=1, step=1)

with col2:
    st.header("Live Results")
    placeholder = st.empty()

symbols = [s.strip() for s in symbols_text.splitlines() if s.strip()]

def run_check():
    results = []
    for symbol in symbols:
        try:
            df = fetch_candles(symbol, interval="5m", limit=200)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})
            continue
        sig = detect_momentum_signal(df)
        sig["symbol"] = symbol
        results.append(sig)

        # send telegram if signal and not recently alerted
        if sig.get("signal", False):
            if not was_alert_sent_recent(symbol, minutes=alert_minutes_lockout):
                # compose message
                msg = (
                    f"🚀 <b>{symbol} Momentum Breakout</b>\n"
                    f"Price: ₹{sig['close']:.2f}\n"
                    f"Time: {sig['time']}\n"
                    f"RSI5: {sig['rsi5']:.1f} | EMA9>EMA21: {sig['ema_cross']}\n"
                    f"Vol Spike: {sig['vol_spike']} | ATR Spike: {sig['atr_spike']}\n"
                )
                sent = False
                try:
                    sent = send_telegram_message(cfg.get("telegram_bot_token"), cfg.get("telegram_chat_id"), msg)
                except Exception as e:
                    sent = False
                    st.error(f"Telegram send error for {symbol}: {e}")
                if sent:
                    persist_alert(symbol, datetime.now(timezone.utc).isoformat())
            else:
                # already alerted recently
                pass

    return results

if run_button:
    with st.spinner("Running checks..."):
        results = run_check()
        placeholder.dataframe(pd.DataFrame(results))
        st.success("Check completed.")

if autorefresh:
    st_autorefresh = st.experimental_get_query_params()  # just to use an experimental rerun
    # Streamlit's recommended simple autorefresh:
    count = st.experimental_get_query_params().get("count", [0])
    # Simpler — provide Run Now to quickly trigger; the user can refresh the page or deploy scheduled runner externally.

# show last alerts
if os.path.exists(ALERTS_FILE):
    with open(ALERTS_FILE, "r") as f:
        try:
            alerts = json.load(f)
            st.subheader("Recent Alerts (symbol -> timestamp)")
            st.json(alerts)
        except:
            st.write("No alerts recorded yet.")
else:
    st.write("No alerts recorded yet.")

st.markdown("---")
st.markdown("**Implementation notes:** Edit `config.json` with your tokens and set `demo_mode` to true to test UI without live data.")

