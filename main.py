import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold High Winrate Bot"

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
            if isinstance(r, list) and len(r) > 50: return r
        except: continue
    return []

def ema(prices, p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices, period=14):
    g=l=0
    for i in range(1, period+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    if l==0: return 100
    return 100-(100/(1+g/l))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 بوت الفعالية العالية\n/tawsiya - طويلة\n/saree3 - سريعة بفلترة قوية\n/gold - السعر")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot()
    await update.message.reply_text(f"💰 {p:.2f}$" if p else "خطأ")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=get_candles("1h"); spot=get_spot()
    if len(data)<50 or not spot: await update.message.reply_text("جرب بعد دقيقة"); return
    c=[float(x[4]) for x in data]; e50=ema(c,50); e200=ema(c,200); r=rsi(c)
    atr=sum([float(x[2])-float(x[3]) for x in data[-14:]])/14
    sig="🟢 شراء قوي" if c[-1]>e50 and c[-1]>e200 else "🔴 بيع قوي"
    sl=spot-atr*1.5 if "شراء" in sig else spot+atr*1.5
    tp1=spot+atr*1.2 if "شراء" in sig else spot-atr*1.2
    tp2=spot+atr*2.5 if "شراء" in sig else spot-atr*2.5
    await update.message.reply_text(f"{sig}\nدخول {spot:.2f}\nوقف {sl:.2f}\nهدف1 {tp1:.2f}\nهدف2 {tp2:.2f}\nRSI {r:.1f}")

async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡️ عم افحص 4 فلاتر للفعالية...")
    d5=get_candles("5m"); d60=get_candles("1h"); spot=get_spot()
    if len(d5)<50 or len(d60)<50 or not spot: await update.message.reply_text("API مشغول جرب بعد دقيقة"); return
    c5=[float(x[4]) for x in d5]; c60=[float(x[4]) for x in d60]
    e9_5=ema(c5,9); e21_5=ema(c5,21); r5=rsi(c5,7)
    e50_60=ema(c60,50); r60=rsi(c60,14)
    atr=sum([float(x[2])-float(x[3]) for x in d5[-14:]])/14
    buy_trend = c60[-1]>e50_60 and r60>50
    sell_trend = c60[-1]<e50_60 and r60<50
    buy_scalp = c5[-1]>e9_5 and e9_5>e21_5 and 50<r5<70 and abs(c5[-1]-e21_5)>atr*0.3
    sell_scalp = c5[-1]<e9_5 and e9_5<e21_5 and 30<r5<50 and abs(c5[-1]-e21_5)>atr*0.3
    if buy_trend and buy_scalp:
        sl=spot-atr*0.9; tp1=spot+atr*0.9; tp2=spot+atr*1.8
        msg=f"⚡️ صفقة سريعة فعالية عالية 75%+\n🟢 شراء سريع BUY SCALP\n\n💵 دخول: {spot:.2f}\n🛑 وقف: {sl:.2f}\n🎯 هدف1: {tp1:.2f} (سكر هون 50%)\n🎯 هدف2: {tp2:.2f}\n\n📊 تأكيدات:\n✅ ترند ساعة صاعد\n✅ تقاطع EMA9 فوق 21\n✅ RSI 5m: {r5:.1f}\n✅ RSI 1h: {r60:.1f}\n⏱️ 10-25 دقيقة"
        await update.message.reply_text(msg)
    elif sell_trend and sell_scalp:
        sl=spot+atr*0.9; tp1=spot-atr*0.9; tp2=spot-atr*1.8
        msg=f"⚡️ صفقة سريعة فعالية عالية 75%+\n🔴 بيع سريع SELL SCALP\n\n💵 دخول: {spot:.2f}\n🛑 وقف: {sl:.2f}\n🎯 هدف1: {tp1:.2f}\n🎯 هدف2: {tp2:.2f}\n\n📊 تأكيدات:\n✅ ترند ساعة هابط\n✅ تقاطع EMA9 تحت 21\n✅ RSI 5m: {r5:.1f}\n✅ RSI 1h: {r60:.1f}\n⏱️ 10-25 دقيقة"
        await update.message.reply_text(msg)
    else:
        reason=[]
        if not (buy_trend or sell_trend): reason.append("ترند الساعة مو واضح")
        if r5>70 or r5<30: reason.append(f"RSI متشبع {r5:.1f}")
        if abs(c5[-1]-e21_5)<atr*0.3: reason.append("السعر قريب من EMA")
        await update.message.reply_text(f"⏸️ ما في صفقة بفعالية عالية هلا\nالسعر: {spot:.2f}\nالسبب:\n- " + "\n- ".join(reason))

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("gold", gold))
    bot.add_handler(CommandHandler("tawsiya", tawsiya))
    bot.add_handler(CommandHandler("saree3", saree3))
    bot.run_polling()
