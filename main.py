import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Exact Entry Bot"

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

def rsi(prices, period=14):
    g=l=0
    for i in range(1, period+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    if l==0: return 100
    return 100-(100/(1+g/l))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/qawi - بيعطيك نقطة دخول بالضبط\nمثال: اذا وصل 4325.50 ادخل")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot(); await update.message.reply_text(f"💰 {p:.2f}$" if p else "خطأ")

async def qawi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 عم حدد نقطة دخول...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); spot=get_spot()
    if len(d5)<50 or not spot: await update.message.reply_text("جرب بعد دقيقة"); return
    
    c5=[float(x[4]) for x in d5]; h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]
    
    e9=ema(c5,9); e21=ema(c5,21); e50_5=ema(c5,50)
    e50_60=ema(c60,50); e200_60=ema(c60,200); e50_240=ema(c240,50)
    r5=rsi(c5,7); r60=rsi(c60,14); r240=rsi(c240,14)
    atr=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    
    # اقرب دعم ومقاومة
    recent_high=max(h5[-20:]); recent_low=min(l5[-20:])
    
    score=0
    if c240[-1]>e50_240: score+=30
    else: score-=20
    if c60[-1]>e50_60 and c60[-1]>e200_60: score+=30
    else: score-=10
    if c5[-1]>e9 and e9>e21: score+=20
    else: score-=10
    if 40<r5<68: score+=20
    else: score-=5
    
    if score>=50:
        # سيناريو شراء - نحدد نقطة دخول دقيقة
        if c5[-1] > e9 + atr*0.2:
            # السعر طاير فوق - ننتظر اعادة اختبار
            entry=round(e9 + atr*0.1, 2)
            entry_cond=f"اذا نزل السعر ولمس {entry}$ ادخل شراء فورا"
            order_type=f"BUY LIMIT {entry}$"
            trigger=f"🔔 حط تنبيه عند {entry}$"
            sl=round(entry - atr*1.0, 2)
            tp1=round(entry + atr*1.2, 2)
            tp2=round(entry + atr*2.5, 2)
        else:
            # قريب من EMA - دخول فوري
            entry=round(spot, 2)
            entry_cond=f"ادخل شراء هلا فورا على {entry}$"
            order_type=f"BUY MARKET {entry}$"
            trigger="🚀 دخول فوري - لا تنتظر"
            sl=round(spot - atr*1.0, 2)
            tp1=round(spot + atr*1.2, 2)
            tp2=round(spot + atr*2.5, 2)
        sig="🟢 شراء BUY"
        power="💎 قوي" if score>=70 else "⚠️ متوسط"
    elif score<=-30:
        if c5[-1] < e9 - atr*0.2:
            entry=round(e9 - atr*0.1, 2)
            entry_cond=f"اذا طلع السعر ولمس {entry}$ ادخل بيع فورا"
            order_type=f"SELL LIMIT {entry}$"
            trigger=f"🔔 حط تنبيه عند {entry}$"
            sl=round(entry + atr*1.0, 2)
            tp1=round(entry - atr*1.2, 2)
            tp2=round(entry - atr*2.5, 2)
        else:
            entry=round(spot, 2)
            entry_cond=f"ادخل بيع هلا فورا على {entry}$"
            order_type=f"SELL MARKET {entry}$"
            trigger="🚀 دخول فوري"
            sl=round(spot + atr*1.0, 2)
            tp1=round(spot - atr*1.2, 2)
            tp2=round(spot - atr*2.5, 2)
        sig="🔴 بيع SELL"
        power="💎 قوي" if score<=-50 else "⚠️ متوسط"
    else:
        sig="⏸️ لا تدخل"; entry=spot; entry_cond="انتظر"; order_type="-"; trigger="جرب بعد 15 دقيقة"
        sl=0; tp1=0; tp2=0; power=f"🔴 ضعيف نقاط {score}"
    
    msg=f"""{sig} {power}
نقاط: {score}/100

🎯 نقطة الدخول بالضبط:
{entry_cond}

📝 الامر:
{order_type}
وقف: {sl}$
هدف1: {tp1}$ 
هدف2: {tp2}$

{trigger}

📊 ليش هالنقطة؟
السعر الحالي: {spot:.2f}$
EMA9: {e9:.2f}$ (نقطة اعادة الاختبار)
EMA21: {e21:.2f}$
دعم 20 شمعة: {recent_low:.2f}$
مقاومة 20 شمعة: {recent_high:.2f}$
RSI 5m: {r5:.1f} | 1h: {r60:.1f} | 4h: {r240:.1f}
ATR: {atr:.2f}$

💡 اذا وصل السعر لـ {entry}$ ادخل واذا ما وصل لا تدخل - لا تلحق السوق!
"""
    await update.message.reply_text(msg)

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)
async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    for cmd, fn in [("start", start), ("gold", gold), ("qawi", qawi), ("tawsiya", tawsiya), ("saree3", saree3)]:
        bot.add_handler(CommandHandler(cmd, fn))
    bot.run_polling()
