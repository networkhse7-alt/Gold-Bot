import time
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime, timedelta

# ================== TELEGRAM ==================
TOKEN = "8182359938:AAGX1i_MkGtRnfaCgvEeswSzD13Ydde-nLA"
CHAT_ID = "926218869"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=payload)

# ================== SETTINGS ==================
SYMBOL = "XAUUSD=X"       # الذهب
INTERVAL = "5m"            # فريم 5 دقائق
LOOKBACK = "2d"            # آخر يومين
COOLDOWN_MINUTES = 10
SPREAD_ESTIMATE = 0.4      # تقدير السبريد بالدولار
last_signal_time = {"BUY": None, "SELL": None}
last_activity_alert = datetime.now() - timedelta(minutes=60)

# ================== DATA ==================
def get_data():
    """جلب البيانات من Yahoo Finance"""
    df = yf.download(SYMBOL, interval=INTERVAL, period=LOOKBACK)
    df.dropna(inplace=True)
    return df

# ================== STRATEGY ==================
def analyze():
    global last_signal_time, last_activity_alert

    df = get_data()

    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["RSI"] = ta.rsi(df["Close"], 14)
    df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], 14)
    df["ADX"] = ta.adx(df["High"], df["Low"], df["Close"], 14)["ADX_14"]

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # ===== Market Filter =====
    if last["ADX"] < 18 or last["ATR"] < df["ATR"].rolling(20).mean().iloc[-1]:
        return False

    price = last["Close"]

    # ===== Direction Bias =====
    direction = None
    if price > last["EMA50"]:
        direction = "BUY"
    elif price < last["EMA50"]:
        direction = "SELL"
    else:
        return False

    # ===== Cooldown =====
    now = datetime.now()
    if last_signal_time[direction]:
        if now - last_signal_time[direction] < timedelta(minutes=COOLDOWN_MINUTES):
            return False

    # ===== AI Confidence Score =====
    confidence = 0
    if direction == "BUY":
        if price > last["EMA20"]: confidence += 30
        if 40 <= last["RSI"] <= 60: confidence += 25
        if last["Close"] > prev["Close"]: confidence += 20
        if last["ADX"] > 25: confidence += 15
        if last["ATR"] > df["ATR"].rolling(20).mean().iloc[-1]: confidence += 10
    if direction == "SELL":
        if price < last["EMA20"]: confidence += 30
        if 40 <= last["RSI"] <= 60: confidence += 25
        if last["Close"] < prev["Close"]: confidence += 20
        if last["ADX"] > 25: confidence += 15
        if last["ATR"] > df["ATR"].rolling(20).mean().iloc[-1]: confidence += 10

    if confidence < 60:
        return False

    # ===== Signal Type =====
    if confidence >= 80:
        signal_type = "Aggressive 🚀"
        tp_multiplier = 2.2
    else:
        signal_type = "Conservative 🛡️"
        tp_multiplier = 1.8

    # ===== TP / SL Dynamic + Spread =====
    atr = last["ATR"]
    sl = price - atr if direction=="BUY" else price + atr
    tp = price + tp_multiplier*atr if direction=="BUY" else price - tp_multiplier*atr

    # خصم/إضافة تقدير السبريد
    if direction == "BUY":
        tp -= SPREAD_ESTIMATE
    else:
        tp += SPREAD_ESTIMATE

    # ===== Trailing TP =====
    trailing_active = True
    trailing_pct = 0.5
    if trailing_active:
        if direction == "BUY" and last["Close"] - price > trailing_pct*atr:
            tp += (last["Close"] - price)*0.5
        elif direction == "SELL" and price - last["Close"] > trailing_pct*atr:
            tp -= (price - last["Close"])*0.5

    last_signal_time[direction] = now

    # ===== Telegram Message =====
    msg = f"""
💰 GOLD SCALPING SIGNAL 💰
Symbol: XAUUSD
Type: {direction} ({signal_type})
Entry: {price:.2f}
TP: {tp:.2f} {'(Trailing Active)' if trailing_active else ''}
SL: {sl:.2f}
Confidence: {confidence}%
Score Threshold: 60
Spread Estimate: {SPREAD_ESTIMATE}
Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
"""
    send_telegram(msg)
    return True

# ================== LOOP ==================
while True:
    try:
        sent_signal = analyze()

        # ===== Hourly activity alert =====
        now = datetime.now()
        if not sent_signal and (now - last_activity_alert).seconds >= 3600:
            send_telegram("⏱ Bot Status: Active but no valid signals in the last hour. Scanning market...")
            last_activity_alert = now

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(60)
