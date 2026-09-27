import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL = "PAXGUSDT"
TOKEN = os.environ.get("BOT_TOKEN2")

def get_klines():
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=15m&limit=100"
        data = requests.get(url, timeout=10).json()
        return data
    except:
        return []

def calc_ema(prices, period):
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def get_signal():
    klines = get_klines()
    if len(klines) < 60:
        return "⏸️ عم جمع بيانات..."

    closes = [float(k[4]) for k in klines]
    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    price = closes[-1]

    ema50 = calc_ema(closes, 50)
    swing_low = min(lows[-20:-5])
    swing_high = max(highs[-20:-5])
    fib50 = swing_low + (swing_high - swing_low) * 0.5

    wd = datetime.now().weekday()
    days = ["الاثنين","الثلاثاء","الاربعاء","الخميس","الجمعة","السبت","الاحد"]
    today = days[wd]

    if wd >= 5:
        return f"🏦 {today} - السوق مسكر\nالسعر ${price:.2f}"

    above = price > ema50
    in_discount = price < fib50
    three_red = all(closes[-i] < opens[-i] for i in range(1, 4))
    green = closes[-1] > opens[-1]

    if above and in_discount and three_red and green:
        sl = swing_low * 0.998
        tp = swing_high
        return f"🔥 LONG خارق 🔥\n{SYMBOL} ${price:.2f}\n✅ فوق EMA50\n✅ تحت 50% فيبو {fib50:.1f}\n✅ 3 حمراء + شمعة خضراء\n\nدخول: ${price:.2f}\nستوب: ${sl:.2f}\nهدف: ${tp:.2f}\n\n{d} - {today}"

    return f"⏸️ {today} - عم فتش فرصة خارقة\n${price:.2f} | EMA50 {ema50:.1f} | فيبو50 {fib50:.1f}\nفوق EMA:{above} | تحت50%:{in_discount} | 3حمراء:{three_red} | تأكيد:{green}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"BOT2 {SYMBOL} الخارق جاهز 🧠\nاكتب /tawsiya")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_signal()
    await update.message.reply_text(msg)

if __name__ == "__main__":
    if TOKEN:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("tawsiya", tawsiya))
        print("BOT RUNNING...")
        app.run_polling(drop_pending_updates=True)
