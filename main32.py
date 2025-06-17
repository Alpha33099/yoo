import time
import requests
import datetime
import traceback
from statistics import mean
from collections import defaultdict
from flask import Flask
import threading

# === Replit Keep-Alive Server ===
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run).start()

# === Bot Config ===
SCAN_INTERVAL = 60  # seconds
COOLDOWN_SECONDS = 7200  # 2 hours
WEBHOOK_URL = "https://discord.com/api/webhooks/1384346378075111495/RtiEoVfRbnhqMuFYMFHe0Ln61EcYDEVgI1OlghGrFgKNxVx67Zhw4oytnaDgvUeasN8p"

# === Coins to Scan ===
COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "SHIBUSDT", "TRXUSDT",
    "LTCUSDT", "LINKUSDT", "BCHUSDT", "UNIUSDT", "XLMUSDT", "FILUSDT"
]

QUOTES = [
    "🌟 Keep going, your setup is just around the corner!",
    "🚀 Every candle brings a new opportunity.",
    "⏳ Patience makes the best traders.",
    "🔍 No signal yet, but momentum is building!",
    "💡 Stay sharp. Good setups reward discipline.",
]

cooldowns = {}
active_signals = defaultdict(dict)

# === Fetch Candles from Binance Only ===
def fetch_candles(symbol, interval='5m', limit=50):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        data = requests.get(url, timeout=10).json()
        closes = [float(d[4]) for d in data]
        volumes = [float(d[5]) for d in data]
        return closes, volumes
    except:
        print(f"[ERROR] Could not fetch candles for {symbol}")
        return None, None

def ema(data, period):
    return [mean(data[i - period + 1:i + 1]) if i >= period else None for i in range(len(data))]

def now():
    return datetime.datetime.now()

def send_discord(msg):
    try:
        requests.post(WEBHOOK_URL, json={"content": msg})
        print("📤 Discord message sent.")
    except Exception as e:
        print(f"[DISCORD ERROR] {e}")

def analyze(symbol):
    closes, volumes = fetch_candles(symbol)
    if not closes or not volumes:
        return None

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    avg_vol = mean(volumes[:-3])
    current_vol = volumes[-1]

    if not ema9[-2] or not ema21[-2]:
        return None

    signal_type = None
    if ema9[-2] < ema21[-2] and ema9[-1] > ema21[-1] and current_vol > avg_vol * 1.1:
        signal_type = "LONG"
    elif ema9[-2] > ema21[-2] and ema9[-1] < ema21[-1] and current_vol > avg_vol * 1.1:
        signal_type = "SHORT"

    if not signal_type:
        return None

    price = closes[-1]
    tp = round(price * (1.02 if signal_type == "LONG" else 0.98), 4)
    sl = round(price * (0.98 if signal_type == "LONG" else 1.02), 4)

    return {
        "symbol": symbol,
        "type": signal_type,
        "price": price,
        "volume": int(current_vol),
        "tp": tp,
        "sl": sl
    }

# === Bot Loop ===
print("🤖 EMA 5-Min Binance Bot Running with Discord alerts...")
while True:
    try:
        found_signal = False
        for coin in COINS:
            if coin in cooldowns and (now() - cooldowns[coin]).total_seconds() < COOLDOWN_SECONDS:
                continue

            signal = analyze(coin)
            if signal:
                cooldowns[coin] = now()
                active_signals[coin] = signal
                found_signal = True

                emoji = "📈" if signal["type"] == "LONG" else "📉"
                msg = f"""
{emoji} **{signal['type']} SIGNAL — {signal['symbol']}**

💰 Price: `${signal['price']}`
📊 Volume: `{signal['volume']}`

🎯 TP: `${signal['tp']}`
❌ SL: `${signal['sl']}`

📌 Trade according to your risk management plan.
                """.strip()
                send_discord(msg)

            elif coin in active_signals:
                closes, _ = fetch_candles(coin)
                if not closes:
                    continue
                price = closes[-1]
                sig = active_signals[coin]

                if sig["type"] == "LONG":
                    if price >= sig["tp"]:
                        send_discord(f"🎯 **TP HIT** — {coin} Take Profit hit at ${price:.4f}")
                        del active_signals[coin]
                    elif price <= sig["sl"]:
                        send_discord(f"❌ **SL HIT** — {coin} Stop Loss hit at ${price:.4f}")
                        del active_signals[coin]
                elif sig["type"] == "SHORT":
                    if price <= sig["tp"]:
                        send_discord(f"🎯 **TP HIT** — {coin} Take Profit hit at ${price:.4f}")
                        del active_signals[coin]
                    elif price >= sig["sl"]:
                        send_discord(f"❌ **SL HIT** — {coin} Stop Loss hit at ${price:.4f}")
                        del active_signals[coin]

        if not found_signal:
            quote = QUOTES[int(time.time()) % len(QUOTES)]
            msg = f"📭 **No Signal this round.**\n{quote}"
            send_discord(msg)

        time.sleep(SCAN_INTERVAL)

    except Exception as e:
        print(f"[ERROR] {e}\n{traceback.format_exc()}")
        time.sleep(SCAN_INTERVAL)
