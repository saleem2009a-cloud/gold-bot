import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Full Analysis Bot"

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
    await update.message.reply_text("🔥 بوت التحليل الكامل\n/qawi - يقلك قوي ولا ضعيف + كل التحاليل\n/saree3 - سريع\n/tawsiya - طويل\n/gold - سعر")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot(); await update.message.reply_text(f"💰 {p:.2f}$" if p else "خطأ")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await qawi(update, context)

async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await qawi(update, context)

async def qawi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 عم حلل كل الفريمات...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); spot=get_spot()
    if len(d5)<50 or len(d60)<50 or not spot:
        await update.message.reply_text("API مشغول جرب بعد دقيقة"); return
    
    c5=[float(x[4]) for x in d5]; c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]
    h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    
    e9_5=ema(c5,9); e21_5=ema(c5,21); e50_5=ema(c5,50)
    e50_60=ema(c60,50); e200_60=ema(c60,200)
    e50_240=ema(c240,50); e200_240=ema(c240,200)
    
    r5=rsi(c5,7); r14_5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14)
    atr5=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    atr60=sum([float(x[2])-float(x[3]) for x in d60[-14:]])/14
    
    # حساب القوة
    score=0; reasons=[]
    # 1- ترند 4h
    if c240[-1]>e50_240 and c240[-1]>e200_240: score+=25; reasons.append("✅ 4H ترند صاعد قوي (+25)")
    elif c240[-1]>e50_240: score+=15; reasons.append("✅ 4H صاعد (+15)")
    else: score-=15; reasons.append("🔴 4H هابط (-15)")
    
    # 2- ترند 1h
    if c60[-1]>e50_60 and c60[-1]>e200_60: score+=25; reasons.append("✅ 1H فوق 50 و 200 (+25)")
    elif c60[-1]>e50_60: score+=10; reasons.append("⚠️ 1H فوق 50 بس (+10)")
    else: score-=10; reasons.append("🔴 1H تحت 50 (-10)")
    
    # 3- 5m
    if c5[-1]>e9_5 and e9_5>e21_5 and e21_5>e50_5: score+=20; reasons.append("✅ 5M ترتيب EMA مثالي (+20)")
    elif c5[-1]>e9_5 and e9_5>e21_5: score+=10; reasons.append("✅ 5M تقاطع صاعد (+10)")
    else: score-=10; reasons.append("🔴 5M هابط (-10)")
    
    # 4- RSI
    if 50<r5<68 and 50<r60<70: score+=15; reasons.append("✅ RSI متوازن (+15)")
    elif r5>70 or r5<30: score-=15; reasons.append(f"⚠️ RSI متشبع {r5:.0f} (-15)")
    else: score+=5; reasons.append(f"⚠️ RSI {r5:.0f} (+5)")
    
    # 5- بعد عن EMA
    dist=abs(c5[-1]-e21_5)
    if dist>atr5*0.4: score+=15; reasons.append(f"✅ بعيد عن EMA {dist:.2f} (+15)")
    else: score-=10; reasons.append(f"⚠️ قريب من EMA - عرضي (-10)")
    
    # تحديد القوة
    if score>=70: power="💎💎💎 قوي جدا 85%+"; action="ادخل بثقة - فول لوت"
    elif score>=50: power="💎💎 قوي 70%"; action="ادخل - لوت عادي"
    elif score>=30: power="⚠️ متوسط 55%"; action="نص لوت فقط - هدف قريب"
    elif score>=0: power="⚠️ ضعيف 40%"; action="لا تدخل او سكالبينغ سريع جدا"
    else: power="🔴 ضعيف جدا 25% - لا تدخل"; action="انتظر فرصة احسن"
    
    # اتجاه
    if score>20: sig="🟢 شراء BUY"; sl=spot-atr5*1.0; tp1=spot+atr5*1.0; tp2=spot+atr5*2.2
    elif score<-20: sig="🔴 بيع SELL"; sl=spot+atr5*1.0; tp1=spot-atr5*1.0; tp2=spot-atr5*2.2
    else: sig="⏸️ حيادي - سوق عرضي"; sl=spot; tp1=spot; tp2=spot
    
    msg=f"""{sig}
{power}
نقاط القوة: {score}/100

💵 السعر: {spot:.2f}$
🛑 وقف: {sl:.2f}$
🎯 هدف1: {tp1:.2f}$
🎯 هدف2: {tp2:.2f}$

📊 التحليل الكامل:
{chr(10).join(reasons)}

📈 تفاصيل فنية:
• 5M: EMA9 {e9_5:.2f} | EMA21 {e21_5:.2f} | EMA50 {e50_5:.2f}
• RSI 5M: {r5:.1f} (سريع) | {r14_5:.1f} (بطيء)
• 1H: EMA50 {e50_60:.2f} | EMA200 {e200_60:.2f} | RSI {r60:.1f}
• 4H: EMA50 {e50_240:.2f} | EMA200 {e200_240:.2f} | RSI {r240:.1f}
• ATR 5M: {atr5:.2f}$ | ATR 1H: {atr60:.2f}$
• مسافة عن EMA21: {dist:.2f}$

💡 القرار: {action}
⏱️ { '10-30 دقيقة' if abs(score)<40 else '30-120 دقيقة' }
"""
    await update.message.reply_text(msg)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("gold", gold))
    bot.add_handler(CommandHandler("tawsiya", tawsiya))
    bot.add_handler(CommandHandler("saree3", saree3))
    bot.add_handler(CommandHandler("qawi", qawi))
    bot.run_polling()
