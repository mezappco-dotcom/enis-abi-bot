from binance.client import Client
import pandas as pd
import numpy as np
import requests
import ta
import time
from datetime import datetime, timedelta
import os

# GitHub Secrets'tan verileri çekiyoruz
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Botun teknik ayarları
MAIN_INTERVAL = "15m"
HTF1 = "1h"
HTF2 = "4h"
COOLDOWN_MINUTES = 60

# Binance kısıtlamasını aşmak için alternatif uç nokta kullanıyoruz
client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY, tld='com')
client.API_URL = 'https://api1.binance.com/api' # Alternatif sunucu 1

last_signal_time = {}

# =========================
# DATA
# =========================

def get_df(symbol, interval, limit=300):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "_","_","_","_","_","_"
    ])
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df

# =========================
# INDICATORS
# =========================

def add_indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + rs))

    direction = np.where(df["close"].diff() > 0, 1, -1)
    df["obv"] = (df["volume"] * direction).cumsum()

    st = ta.trend.STIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=10,
        multiplier=3
    )
    df["supertrend"] = st.super_trend_direction()

    df["vol_ma20"] = df["volume"].rolling(20).mean()

    return df

# =========================
# FUNDING
# =========================

def get_funding(symbol):
    data = client.futures_funding_rate(symbol=symbol, limit=1)
    return float(data[0]["fundingRate"])

# =========================
# VOLUME SPIKE
# =========================

def volume_strength(df):
    current_vol = df["volume"].iloc[-1]
    avg_vol = df["vol_ma20"].iloc[-1]
    ratio = current_vol / avg_vol

    if ratio < 1.4:
        return False, ratio, "LOW"
    elif 1.4 <= ratio < 1.8:
        return True, ratio, "NORMAL"
    elif 1.8 <= ratio < 2.5:
        return True, ratio, "STRONG"
    else:
        return True, ratio, "EXTREME"

# =========================
# TELEGRAM
# =========================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

#
