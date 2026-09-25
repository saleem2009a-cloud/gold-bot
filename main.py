import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Bot Live ✅"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        return float(r['price'])
    except:
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5).json()
            return float(r['price'])
        except:
            return None

def get_candles(tf, limit=100):
    bases = ["https://data-api.binance.vision","https://api.binance.com"]
    for base in bases:
        try:
            url = f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={limit}"
            r = requests.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r, list) and len(r) >= 80:
                return r
        except:
            continue
    return []

def ema(prices, per):
    if len(prices) < per: return prices[-1]
    k = 2/(per+1)
    e = sum(prices[:per])/per
    for p in prices[per:]:
        e = p*k + e*(1-k)
    return e

def rsi(prices, per=14):
    if len(prices) < per+1: return 50
    deltas = [prices[i]-prices[i-1] for i in range(1,len(prices))][-per:]
    gains = sum([d for d in deltas if d>0])/per
    losses = sum([-d for d in deltas if d<0])/per
    if losses == 0: return 100
    return 100 - (100/(1+gains/losses))

async def start(update, context):
    await update.message.reply_text("✅ شغال\n/tawsiya - توصية\n/gold - سعر\n/test - فحص")

async def test(update, context):
    p = get_price()
    d5 = get_candles("5m", 100)
    await update.message.reply_text(f"فحص:\nسعر: {p} {'✅' if p else '❌'}\n5m: {len(d5)} شمعة {'✅' if len(d5)>80 else '❌'}")

async def gold(update, context):
    p = get_price()
    if p: await update.message.reply_text(f"💰 {p:.2f}$")
    else: await update.message.reply_text("❌ معلق")

async def tawsiya(update, context):
    try:
        await update.message.reply_text("⏳ عم حلل... 3 ثواني")
        price = get_price()
        d5 = get_candles("5m", 100)
        d60 = get_candles("1h", 100)
        d240 = get_candles("4h", 100)

        if not price or len(d5) < 80:
            await update.message.reply_text(f"❌ معلق\nسعر: {price}\nشموع: {len(d5)}")
            return

        c5 = [float(x[4]) for x in d5]
        c60 = [float(x[4]) for x in d60] if len(d60)>50 else c5
        c240 = [float(x[4]) for x in d240] if len(d240)>50 else c5

        e9 = ema(c5,9); e21 = ema(c5,21); e50 = ema(c5,50)
        e50_60 = ema(c60,50); e200_60 = ema(c60,200); e50_240 = ema(c240,50)
        r5 = rsi(c5); r60 = rsi(c60); r240 = rsi(c240)

        score = 50; reasons = []
        if c240[-1] > e50_240: score+=15; reasons.append("✅ 4H صاعد")
        else: score-=15; reasons.append("🔴 4H هابط")

        if c60[-1] > e50_60 and c60[-1] > e200_60: score+=20; reasons.append("✅ 1H قوي فوق 50+200")
        elif c60[-1] > e50_60: score+=8; reasons.append("⚠️ 1H فوق 50")
        else: score-=15; reasons.append("🔴 1H هابط")

        if c5[-1] > e9 and e9 > e21: score+=15; reasons.append("✅ 5M صاعد")
        else: score-=10; reasons.append("🔴 5M هابط")

        if r5 > 75: score-=10; reasons.append(f"⚠️ تشبع شراء RSI {r5:.0f}")
        elif r5 < 25: score+=10; reasons.append(f"⚠️ تشبع بيع RSI {r5:.0f}")

        if score >= 65:
            txt = f"🟢 **شراء BUY {score}/100**\n\n💵 دخول: {price:.2f}\n🛑 وقف: {price-5:.2f}\n🎯 هدف: {price+8:.2f}\n\n{chr(10).join(reasons)}\nRSI {r5:.0f}/{r60:.0f}/{r240:.0f}"
        elif score <= 35:
            txt = f"🔴 **بيع SELL {score}/100**\n\n💵 دخول: {price:.2f}\n🛑 وقف: {price+5:.2f}\n🎯 هدف: {price-8:.2f}\n\n{chr(10).join(reasons)}\nRSI {r5:.0f}/{r60:.0f}/{r240:.0f}"
        else:
            txt = f"⏸️ **حيادي {score}/100 لا تدخل**\n\nالسعر {price:.2f}\n\n{chr(10).join(reasons)}\nRSI {r5:.1f} {r60:.1f} {r240:.1f}\nانتظر 15د"

        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

if __name__ == "__main__":
    if TOKEN:
        bot = Application.builder().token(TOKEN).build()
        bot.add_handler(CommandHandler("start", start))
        bot.add_handler(CommandHandler("gold", gold))
        bot.add_handler(CommandHandler("test", test))
        bot.add_handler(CommandHandler("tawsiya", tawsiya))
        bot.add_handler(CommandHandler("tawsiyat", tawsiya))
        bot.add_handler(CommandHandler("qawi", tawsiya))
        bot.add_handler(CommandHandler("saree3", tawsiya))
        bot.run_polling()
