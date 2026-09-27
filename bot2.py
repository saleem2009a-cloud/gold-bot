import os
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN2")
CHAT_ID = os.environ.get("CHAT_ID") # حط ايديك بالتليجرام هون بال Render
SYMBOL = "PAXGUSDT"

def get_klines():
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=15m&limit=100"
    try:
        return requests.get(url, timeout=10).json()
    except:
        return []

def calc_ema(prices, period):
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema

def get_analysis():
    klines = get_klines()
    if len(klines) < 60:
        return None, "⏳ عم جمع بيانات..."

    closes = [float(k[4]) for k in klines]
    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    price = closes[-1]

    # 1. EMA 50
    ema50 = calc_ema(closes, 50)

    # 2. SWING HIGH & LOW - اخر 20 شمعة بدون اخر 5
    swing_low = min(lows[-25:-5])
    swing_high = max(highs[-25:-5])
    low_idx = lows.index(swing_low)
    high_idx = highs.index(swing_high)

    # 3. فيبوناتشي 50% - منطقة السعر المخفض
    fib50 = swing_low + (swing_high - swing_low) * 0.5

    # 4. PULLBACK - 3 شمعات حمرا متتالية
    three_red = all(closes[-i] < opens[-i] for i in range(2,5)) # 3 حمرا قبل شمعة التأكيد
    # 5. شمعة تأكيد خضرا
    green_confirm = closes[-1] > opens[-1] and closes[-2] < opens[-2]

    # 6. ننظر لليسار - هل في دعم؟
    left_support = any(abs(l - swing_low) < (swing_high-swing_low)*0.02 for l in lows[-60:-25])

    is_uptrend = price > ema50
    in_discount = price < fib50 and price > swing_low

    # الشروط كلها متل الفيديو
    if is_uptrend and in_discount and three_red and green_confirm and left_support:
        sl = swing_low - (swing_high - swing_low) * 0.05
        tp1 = swing_high
        tp2 = swing_high + (swing_high - swing_low) * 0.5
        risk = price - sl
        reward = tp1 - price
        rr = reward / risk if risk > 0 else 0

        msg = f"""🔥 توصية خارقة 100% - استراتيجية العيار الثقيل 🔥

💎 {SYMBOL} LONG

📍 دخول: ${price:.2f}
🛑 ستوب: ${sl:.2f} (تحت الدعم)
🎯 هدف 1: ${tp1:.2f}
🎯 هدف 2: ${tp2:.2f}
📊 مخاطرة/ربح: 1/{rr:.1f}

✅ الشروط كلها محققة:
• فوق EMA50: {ema50:.2f} ✅
• تحت 50% فيبو (سعر مخفض): {fib50:.2f} ✅
• 3 شمعات حمرا تصحيح ✅
• شمعة خضرا تأكيد ✅
• دعم على اليسار ✅

⚠️ ادارة راس مال 1% فقط"""
        return True, msg

    # اذا مافي اشارة
    status = f"""⏸️ مراقبة - استراتيجية العيار الثقيل

السعر: ${price:.2f}
EMA50: ${ema50:.2f} - {'فوق ✅' if is_uptrend else 'تحت ❌'}
فيبو 50%: ${fib50:.2f} - {'تحت ✅ مخفض' if in_discount else 'فوق ❌ مو مخفض'}
3 شمعات حمرا: {'✅' if three_red else '❌'}
شمعة تأكيد خضرا: {'✅' if green_confirm else '❌'}
دعم يسار: {'✅' if left_support else '❌'}

لسا ما اكتملت الشروط - ناطرين السعر ينزل لمنطقة الخصم"""
    return False, status

# فحص تلقائي كل 15 دقيقة ويبعت لحالو
async def auto_check(context: ContextTypes.DEFAULT_TYPE):
    is_signal, msg = get_analysis()
    if is_signal and CHAT_ID:
        await context.bot.send_message(chat_id=CHAT_ID, text=msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بوت العيار الثقيل جاهز 🧠\nرح ابعتلك التوصية لحالو بس تتحقق الشروط\nجرب /tawsiya")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, msg = get_analysis()
    await update.message.reply_text(msg)

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tawsiya", tawsiya))

    # يفحص كل 15 دقيقة تلقائيا
    if CHAT_ID:
        app.job_queue.run_repeating(auto_check, interval=900, first=10)

    print("BOT HEAVY RUNNING...")
    app.run_polling(drop_pending_updates=True)
