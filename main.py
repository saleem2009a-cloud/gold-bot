import os
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Live"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# شغل Flask فوراً
threading.Thread(target=run_flask, daemon=True).start()

# هون كود التيليجرام
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

def get_candles():
    try:
        r = requests.get("https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=1h&limit=200", timeout=10).json()
        return [float(c[4]) for c in r]
    except:
        return []

def ema(p, n):
    k = 2/(n+1)
    e = sum(p[:n])/n
    for x in p[n:]:
        e = x*k + e*(1-k)
    return e

async def start(u,c):
    await u.message.reply_text("اهلا! /gold /tawsiya")

async def gold(u,c):
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        await u.message.reply_text(f"الذهب: ${r['price']}")
    except:
        await u.message.reply_text("خطأ جلب السعر")

async def tawsiya(u,c):
    await u.message.reply_text("⏳ احلل الذهب...")
    pr = get_candles()
    if len(pr)<60:
        await u.message.reply_text("جرب بعد دقيقة")
        return
    price = pr[-1]
    e50 = ema(pr,50)
    e200 = ema(pr,200)
    sig = "🟢 شراء BUY" if price>e50 else "🔴 بيع SELL"
    await u.message.reply_text(f"XAU {sig}\nالسعر {price:.2f}\nEMA50 {e50:.2f}\nEMA200 {e200:.2f}")

if __name__ == "__main__":
    # Flask شغال بالخلفية، هلا شغل البوت
    print("Starting bot...")
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("gold", gold))
    app_bot.add_handler(CommandHandler("tawsiya", tawsiya))
    app_bot.run_polling()
