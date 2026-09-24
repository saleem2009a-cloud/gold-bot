import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Smart Sideways Filter"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()['price'])
    except: return None

def get_candles(interval):
    for base in ["https://data-api.binance.vision", "https://api.binance.com"]:
        try:
            url = f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=100"
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r, list) and len(r)>50: return r
        except: continue
    return []

def ema(prices, p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices, period=7):
    g=l=0
    for i in range(1, period+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    if l==0: return 100
    return 100-(100/(1+g/l))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 بوت ذكي يكشف العرضي\n/saree3 - سريع مع كشف عرضي\n/tawsiya - طويل\n/gold - سعر")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot(); await update.message.reply_text(f"💰 {p:.2f}$" if p else "خطأ")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=get_candles("1h"); spot=get_spot()
    if len(data)<50 or not spot: await update.message.reply_text("جرب بعد دقيقة"); return
    c=[float(x[4]) for x in data]; e50=ema(c,50); e200=ema(c,200); r=rsi(c,14)
    atr=sum([float(x[2])-float(x[3]) for x in data[-14:]])/14
    sig="🟢 شراء" if c[-1]>e50 else "🔴 بيع"
    sl=spot-atr*1.5 if "شراء" in sig else spot+atr*1.5
    tp1=spot+atr*1.2 if "شراء" in sig else spot-atr*1.2
    await update.message.reply_text(f"{sig}\nدخول {spot:.2f}\nوقف {sl:.2f}\nهدف {tp1:.2f}")

async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡️ عم افحص اذا السوق عرضي...")
    d5=get_candles("5m"); d60=get_candles("1h"); spot=get_spot()
    if len(d5)<50 or not spot: await update.message.reply_text("جرب بعد دقيقة"); return
    c5=[float(x[4]) for x in d5]; c60=[float(x[4]) for x in d60]
    e9=ema(c5,9); e21=ema(c5,21); e50=ema(c60,50)
    r5=rsi(c5,7); r60=rsi(c60,14)
    atr=sum([float(x[2])-float(x[3]) for x in d5[-14:]])/14
    ema_distance = abs(e9-e21)
    is_sideways = ema_distance < atr*0.25
    if c5[-1]>e9 and e9>e21:
        sig="🟢 شراء سريع BUY"
        sl=spot-atr*0.8; tp=spot+atr*1.2
    elif c5[-1]<e9 and e9<e21:
        sig="🔴 بيع سريع SELL"
        sl=spot-atr*0.8; tp=spot-atr*1.2
    else:
        await update.message.reply_text(f"⏸️ انتظار تقاطع\nالسعر {spot:.2f}\nEMA9 {e9:.2f}\nEMA21 {e21:.2f}\nRSI {r5:.1f}")
        return
    if is_sideways:
        msg=f"⚠️ {sig} - انتبه سوق عرضي!\n\n💵 دخول: {spot:.2f}\n🛑 وقف: {sl:.2f}\n🎯 هدف: {tp:.2f}\n\n⚠️ تحذير عرضي:\nEMA قريبين {ema_distance:.2f}\nفعالية 50% - نص لوت فقط\nRSI: {r5:.1f}\n⏱️ 5 دقايق"
    else:
        msg=f"🔥 {sig} - ترند واضح!\n\n💵 دخول: {spot:.2f}\n🛑 وقف: {sl:.2f}\n🎯 هدف: {tp:.2f}\n\n✅ مو عرضي\n✅ EMA بعاد {ema_distance:.2f}\n✅ فعالية 70%\nRSI: {r5:.1f} | RSI 1h: {r60:.1f}\n⏱️ 10-15 دقيقة"
    await update.message.reply_text(msg)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("gold", gold))
    bot.add_handler(CommandHandler("tawsiya", tawsiya))
    bot.add_handler(CommandHandler("saree3", saree3))
    bot.run_polling()
