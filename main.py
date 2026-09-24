import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Live - Gold Bot Working"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_candles():
    urls = [
        "https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval=1h&limit=200",
        "https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=1h&limit=200"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r, list) and len(r) > 50:
                return r
        except:
            continue
    return []

def ema(prices, period):
    k = 2 / (period + 1)
    e = sum(prices[:period]) / period
    for p in prices[period:]:
        e = p*k + e*(1-k)
    return e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً سليم! 👋\n\n/gold - سعر الذهب\n/tawsiya - توصية كاملة بهدف وستوب")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        price = float(r['price'])
        gram24 = price / 31.1035
        await update.message.reply_text(f"💰 أونصة الذهب: ${price:.2f}\nغرام 24: ${gram24:.2f}")
    except:
        await update.message.reply_text("خطأ جلب السعر")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري تحليل الذهب...")
    data = get_candles()
    if len(data) < 60:
        await update.message.reply_text("السوق بطيء جرب بعد دقيقة")
        return

    closes = [float(c[4]) for c in data]
    price = closes[-1]
    e50 = ema(closes, 50)
    e200 = ema(closes, 200)

    last_14 = data[-14:]
    atr = sum([float(x[2])-float(x[3]) for x in last_14]) / 14

    if price > e50:
        signal = "🟢 شراء قوي BUY"
        sl = price - atr*1.5
        tp1 = price + atr*1.0
        tp2 = price + atr*2.0
    else:
        signal = "🔴 بيع قوي SELL"
        sl = price + atr*1.5
        tp1 = price - atr*1.0
        tp2 = price - atr*2.0

    msg = f"""🔥 توصية الذهب XAU/USD
{signal}

💵 الدخول: {price:.2f}
🛑 وقف الخسارة: {sl:.2f}
🎯 هدف 1: {tp1:.2f}
🎯 هدف 2: {tp2:.2f}

📊 السعر: {price:.2f}
EMA50: {e50:.2f}
EMA200: {e200:.2f}
الفريم: 1 ساعة
"""
    await update.message.reply_text(msg)

if __name__ == "__main__":
    print("Starting bot...")
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("gold", gold))
    app_bot.add_handler(CommandHandler("tawsiya", tawsiya))
    app_bot.run_polling()
