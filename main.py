import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

@app.route('/')
def home():
    return "Gold V6 Fixed - Live ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# شغل فلاسك بخيط منفصل
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    urls = [
        "https://api.gold-api.com/price/XAU",
        "https://data-asg.goldprice.org/dbXRates/XAU",
        "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=6).json()
            if "price" in r: return float(r["price"])
            if "items" in r: return float(r["items"][0]["xauPrice"])
            if "symbol" in r: return float(r["price"])
        except: continue
    return None

def get_candles(tf="5m", limit=100):
    bases = ["https://data-api.binance.vision","https://api.binance.com"]
    for base in bases:
        try:
            url = f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={limit}"
            r = requests.get(url, timeout=7, headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r, list) and len(r)>=80:
                return r
        except: continue
    return []

def ema(prices, period):
    if len(prices)<period: return prices[-1]
    k=2/(period+1)
    e=sum(prices[:period])/period
    for p in prices[period:]:
        e = p*k + e*(1-k)
    return e

def rsi(prices, period=14):
    if len(prices)<period+1: return 50
    deltas = [prices[i]-prices[i-1] for i in range(1,len(prices))]
    gains = [d if d>0 else 0 for d in deltas[-period:]]
    losses = [-d if d<0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period
    if avg_loss==0: return 100
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def atr(data, period=14):
    if len(data)<period: return 2.0
    tr = [float(c[2])-float(c[3]) for c in data[-period:]]
    return sum(tr)/period

async def start(update, context):
    await update.message.reply_text(
        "🔥 V6 مصلح\n"
        "/tawsiya - توصية دقيقة\n"
        "/tawsiyat - 3 توصيات\n"
        "/gold - سعر\n"
        "/test - فحص الـ API\n"
        "/qawi - نفس التوصية"
    )

async def test(update, context):
    msg="🔍 فحص:\n"
    p=get_price()
    msg+=f"السعر: {p} {'✅' if p else '❌'}\n"
    for tf in ["5m","1h","4h"]:
        d=get_candles(tf)
        msg+=f"{tf}: {len(d)} شمعة {'✅' if len(d)>80 else '❌'}\n"
    if p and len(get_candles("5m"))>10:
        d5=get_candles("5m")
        c5=[float(x[4]) for x in d5]
        msg+=f"\nRSI 5M: {rsi(c5):.1f}\nEMA9 {ema(c5,9):.2f} EMA21 {ema(c5,21):.2f}"
    await update.message.reply_text(msg)

async def gold(update, context):
    p=get_price()
    if p: await update.message.reply_text(f"💰 الذهب: {p:.2f}$")
    else: await update.message.reply_text("❌ السعر معلق - جرب /test")

async def tawsiya(update, context):
    await update.message.reply_text("⏳ عم حلل... ثانية")
    price=get_price()
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h")

    if not price or len(d5)<80:
        await update.message.reply_text(f"❌ API معلق\nالسعر: {price}\n5m: {len(d5)} شمعة\nجرب /test بعد دقيقة")
        return

    c5=[float(x[4]) for x in d5]
    c60=[float(x[4]) for x in d60] if len(d60)>50 else c5
    c240=[float(x[4]) for x in d240] if len(d240)>50 else c5

    e9=ema(c5,9); e21=ema(c5,21); e50_5=ema(c5,50)
    e50_60=ema(c60,50); e200_60=ema(c60,200)
    e50_240=ema(c240,50)

    r5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14)
    atr5=atr(d5)

    score=50
    reasons=[]

    if c240[-1] > e50_240: score+=15; reasons.append(f"✅ 4H صاعد")
    else: score-=15; reasons.append(f"🔴 4H هابط")

    if c60[-1] > e50_60 and c60[-1] > e200_60: score+=20; reasons.append("✅ 1H فوق 50+200")
    elif c60[-1] > e50_60: score+=8; reasons.append("⚠️ 1H فوق 50")
    else: score-=12; reasons.append("🔴 1H هابط")

    if c5[-1] > e9 and e9 > e21: score+=20; reasons.append(f"✅ 5M صاعد")
    else: score-=10; reasons.append(f"🔴 5M هابط")

    if abs(e9-e21) < atr5*0.2:
        await update.message.reply_text(f"⏸️ **توصية: انتظار - عرضي**\nالسعر {price:.2f}\nEMA9 {e9:.2f} = EMA21 {e21:.2f}")
        return

    if score>=70: power="💎💎💎 قوي جدا 85-90%"
    elif score>=60: power="💎💎 قوي 75%"
    elif score>=45: power="⚠️ متوسط 55%"
    else: power=f"🔴 ضعيف {score}%"

    if score>52:
        sig="🟢 **توصية: شراء BUY**"; sl=price-atr5*1.2; tp1=price+atr5*1.0; tp2=price+atr5*2.2
    elif score<42:
        sig="🔴 **توصية: بيع SELL**"; sl=price+atr5*1.2; tp1=price-atr5*1.0; tp2=price-atr5*2.2
    else:
        sig="⏸️ **حيادي**"; sl=tp1=tp2=price

    txt=f"""{sig}
{power} | {score}/100

💵 دخول: {price:.2f}
🛑 وقف: {sl:.2f}
🎯 هدف1: {tp1:.2f}
🎯 هدف2: {tp2:.2f}

📊 ليش؟
{chr(10).join(reasons)}

RSI: 5M {r5:.1f} 1H {r60:.1f} 4H {r240:.1f}
ATR 5M {atr5:.2f}
"""
    await update.message.reply_text(txt)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ BOT_TOKEN missing! Add it in Render Environment")
    else:
        print(f"✅ Bot starting with token {TOKEN[:10]}...")
        bot = Application.builder().token(TOKEN).build()
        bot.add_handler(CommandHandler("start", start))
        bot.add_handler(CommandHandler("gold", gold))
        bot.add_handler(CommandHandler("test", test))
        bot.add_handler(CommandHandler("tawsiya", tawsiya))
        bot.add_handler(CommandHandler("tawsiyat", tawsiya))
        bot.add_handler(CommandHandler("qawi", tawsiya))
        bot.add_handler(CommandHandler("saree3", tawsiya))
        bot.run_polling()
