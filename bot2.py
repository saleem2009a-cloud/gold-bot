import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN2")
SYMBOL = "PAXGUSDT"

def get_klines():
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=15m&limit=100"
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

def calc_ema(prices, period):
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema

def get_signal():
    klines = get_klines()
    if len(klines) < 60:
        return "⏳ عم جمع بيانات..."

    closes = [float(k[4]) for k in klines]
    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    price = closes[-1]

    ema50 = calc_ema(closes, 50)

    # SWING
    swing_low = min(lows[-25:-5])
    swing_high = max(highs[-25:-5])

    # فيبو 50% - DISCOUNT
    fib50 = swing_low + (swing_high - swing_low) * 0.5

    # PULLBACK 3 حمرا
    three_red = closes[-2] < opens[-2] and closes[-3] < opens[-3] and closes[-4] < opens[-4]
    # تأكيد خضرا
    green_now = closes[-1] > opens[-1]

    uptrend = price > ema50
    discount = price < fib50 and price > swing_low

    # عرض الحالة دائما
    if uptrend and discount and three_red and green_now:
        sl = swing_low * 0.999
        tp1 = swing_high
        tp2 = swing_high + (swing_high - swing_low) * 0.5
        return f"🔥 LONG العيار الثقيل 100% 🔥\n{SYMBOL} ${price:.2f}\n\nدخول: ${price:.2f}\nستوب: ${sl:.2f}\nهدف1: ${tp1:.2f}\nهدف2: ${tp2:.2f}\n\n✅ فوق EMA50\n✅ تحت 50% فيبو (سعر مخفض)\n✅ 3 شمعات حمرا + خضرا تأكيد\n✅ SWING LOW: ${swing_low:.2f}"

    wd = datetime.now().weekday()
    return f"⏸️ مراقبة العيار الثقيل\nالسعر: ${price:.2f}\nEMA50: ${ema50:.2f} {'✅ فوق' if uptrend else '❌ تحت'}\nفيبو 50%: ${fib50:.2f} {'✅ مخفض' if discount else '❌ مو مخفض'}\n3 حمرا: {'✅' if three_red else '❌'}\nخضرا تأكيد: {'✅' if green_now else '❌'}\n\nلسا ما اكتملت - ناطرين نزول للخصم"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بوت العيار الثقيل جاهز 🧠 /tawsiya")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_signal())

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tawsiya", tawsiya))
    print("BOT RUNNING...")
    app.run_polling(drop_pending_updates=True)
