import os
import requests
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot OK"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r['price'])
    except:
        return None

def get_klines(interval):
    urls = [
        f"https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=100",
        f"https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=100"
    ]
    for url in urls:
        try:
            data = requests.get(url, timeout=10).json()
            if isinstance(data, list) and len(data) > 50:
                return data
        except:
            continue
    return []

def ema(prices, period):
    k = 2 / (period + 1)
    e = sum(prices[:period]) / period
    for p in prices[period:]:
        e = p * k + e * (1 - k)
    return e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("شغال ✅\n/qawi - نقطة دخول مستقبلية")

async def qawi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ثواني...")
    spot = get_price()
    kl5 = get_klines("5m")
    kl60 = get_klines("1h")

    if not spot or len(kl5) < 50:
        await update.message.reply_text("النت ضعيف جرب بعد دقيقة")
        return

    c5 = [float(x[4]) for x in kl5]
    h5 = [float(x[2]) for x in kl5]
    l5 = [float(x[3]) for x in kl5]
    c60 = [float(x[4]) for x in kl60] if kl60 else c5

    e9 = ema(c5, 9)
    e21 = ema(c5, 21)
    e50 = ema(c5, 50)
    e50_1h = ema(c60, 50) if len(c60) > 50 else e50

    atr = sum([h5[i]-l5[i] for i in range(-14,0)]) / 14

    sup = min(l5[-20:])
    res = max(h5[-20:])

    # نقاط دخول مستقبلية - دايما يعطي
    buy1 = round(e21, 2)
    buy2 = round(e50, 2)
    if buy1 > spot:
        buy1 = round(spot - atr*0.5, 2)
    if buy2 > spot:
        buy2 = round(spot - atr*1.2, 2)

    sl1 = round(buy1 - atr, 2)
    tp1 = round(buy1 + atr*1.5, 2)

    sl2 = round(buy2 - atr, 2)
    tp2 = round(buy2 + atr*1.5, 2)

    msg = f"""السعر هلا: {spot:.2f}$

🎯 اذا وصل {buy1}$ ادخل شراء
BUY LIMIT {buy1}
وقف {sl1}
هدف {tp1}

🎯 اذا وصل {buy2}$ ادخل شراء قوي
BUY LIMIT {buy2}
وقف {sl2}
هدف {tp2}

EMA9 {e9:.2f} | EMA21 {e21:.2f} | EMA50 {e50:.2f}
دعم {sup:.2f} | مقاومة {res:.2f}
ATR {atr:.2f}

حط الامرين وانتظر اللمس
"""
    await update.message.reply_text(msg)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("qawi", qawi))
    bot.add_handler(CommandHandler("tawsiya", qawi))
    bot.add_handler(CommandHandler("saree3", qawi))
    bot.run_polling()
