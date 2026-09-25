import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold V6 Fixed"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    # 3 مصادر
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
    # نجرب 3 سيرفرات بينانس
    bases = ["https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com"]
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
    if p:
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
    atr5=atr(d5); atr60=atr(d60) if len(d60)>14 else atr5*3

    # حساب دقيق
    score=50
    reasons=[]

    # 4H
    if c240[-1] > e50_240: score+=15; reasons.append(f"✅ 4H صاعد {c240[-1]:.1f}>{e50_240:.1f}")
    else: score-=15; reasons.append(f"🔴 4H هابط {c240[-1]:.1f}<{e50_240:.1f}")

    # 1H
    if c60[-1] > e50_60 and c60[-1] > e200_60: score+=20; reasons.append("✅ 1H فوق 50+200")
    elif c60[-1] > e50_60: score+=8; reasons.append("⚠️ 1H فوق 50")
    else: score-=12; reasons
