import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Live"

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
                return [float(c[4]) for c in r]
        except:
            continue
    return []

def ema(prices, period):
    k = 2 / (period + 1)
    e = sum(prices[:period]) / period
    for price in prices[period:]:
        e = price * k + e * (1 - k)
    return e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً سليم! 👋\nأرسل /gold لمعرفة سعر الذهب الحالي 💰\nأرسل /tawsiya للتحليل")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        price = float(r['price'])
        gram24 = price / 31.1035
        await update.message.reply_text(f"💰 سعر أونصة الذهب الآن:\n${price:.2f}\n\nسعر الغرام عيار 24: ${gram24:.2f}")
    except Exception as e:
        await update.message.reply_text("خطأ جلب السعر، جرب بعد ثانية")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ احلل الذهب...")
    prices = get_candles()
    if len(prices) < 60:
        await update.message.reply_text("جرب بعد دقيقة، السيرفر مشغول")
        return
    price = prices[-1]
    e50 = ema(prices, 50)
    e200 = ema(prices, 200)

    if price > e50 and e50 > e200:
        signal = "🟢 شراء قوي BUY"
    elif price > e50:
        signal = "🟢 شراء BUY"
    elif price < e50 and e50 < e200:
        signal = "🔴 بيع قوي SELL"
    else:
        signal = "🔴 بيع SELL"

    await update.message.reply_text(f"تحليل الذهب XAU/USD:\n{signal}\n\nالسعر الحالي: {price:.2f}\nEMA50: {e50:.2f}\nEMA200: {e200:.2f}\n\nالفريم: 1 ساعة")

if __name__ == "__main__":
    print("Starting bot...")
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("gold", gold))
    app_bot.add_handler(CommandHandler("tawsiya", tawsiya))
    app_bot.run_polling()
