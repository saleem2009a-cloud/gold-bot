import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Live - Gold Bot"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_spot_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r['price'])
    except:
        return None

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
    await update.message.reply_text("أهلاً سليم! 👋\n/gold - سعر الذهب\n/tawsiya - توصية بهدفين")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_spot_price()
    if price:
        await update.message.reply_text(f"💰 الذهب: ${price:.2f}")
    else:
        await update.message.reply_text("خطأ")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ احلل...")
    data = get_candles()
    spot = get_spot_price()
    if len(data) < 60 or not spot:
        await update.message.reply_text("جرب بعد دقيقة")
        return
    closes = [float(c[4]) for c in data]
    e50 = ema(closes, 50)
    e200 = ema(closes, 200)
    last_14 = data[-14:]
    atr = sum([float(x[2])-float(x[3]) for x in last_14]) / 14
    if closes[-1] > e50:
        signal = "🟢 شراء BUY"
        sl = spot - atr*1.5
        tp1 = spot + atr*1.0
        tp2 = spot + atr*2.0
    else:
        signal = "🔴 بيع SELL"
        sl = spot + atr*1.5
        tp1 = spot - atr*1.0
        tp2 = spot - atr*2.0
    msg = f"🔥 الذهب XAU/USD\n{signal}\n\n💵 الدخول: {spot:.2f}\n🛑 وقف الخسارة: {sl:.2f}\n🎯 هدف أول: {tp1:.2f}\n🎯 هدف تاني: {tp2:.2f}\n\nEMA50: {e50:.2f}\nEMA200: {e200:.2f}"
    await update.message.reply_text(msg)

if __name__ == "__main__":
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("gold", gold))
    app_bot.add_handler(CommandHandler("tawsiya", tawsiya))
    app_bot.run_polling()
