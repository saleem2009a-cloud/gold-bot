import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V11 SMC + Tawsiya"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    for url in ["https://api.gold-api.com/price/XAU","https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT","https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"]:
        try:
            r=requests.get(url,timeout=4).json()
            p=float(r['price'])
            if p>2000: return p
        except: pass
    return 4290.0

def get_candles(tf, lim=150):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=6).json()
            if isinstance(r,list) and len(r)>80: return r
        except: pass
    return []

def get_levels(candles):
    # دعوم ومقاومات قريبة من اخر 50 شمعة بس
    highs=[float(x[2]) for x in candles[-50:]]
    lows=[float(x[3]) for x in candles[-50:]]
    # اقرب قمة وقاع
    return max(highs), min(lows), highs, lows

async def tawsiya(update, context):
    await update.message.reply_text("🔍 عم حلل SMC + توصية...")
    try:
        price=get_price()
        c5=get_candles("5m",150)
        c15=get_candles("15m",150)
        c60=get_candles("1h",150)

        if len(c5)<50:
            await update.message.reply_text(f"❌ شموع فاضية - السعر {price}")
            return

        c5_close=[float(x[4]) for x in c5]
        c15_close=[float(x[4]) for x in c15]
        c60_close=[float(x[4]) for x in c60]

        # مستويات قريبة
        r5,s5,_,_=get_levels(c5)
        r15,s15,_,_=get_levels(c15)
        r60,s60,_,_=get_levels(c60)

        # سوينغات حقيقية قريبة (اخر 20 شمعة)
        sups=sorted(set([min([float(c5[i][3]) for i in range(len(c5)-20,len(c5))])] + [s5,s15,s60]))
        ress=sorted(set([max([float(c5[i][2]) for i in range(len(c5)-20,len(c5))])] + [r5,r15,r60]))

        near_sup=[s for s in sups if s<price][-3:]
        near_res=[r for r in ress if r>price][:3]

        # مؤشرات
        def ema(p,n):
            if len(p)<n: return p[-1]
            k=2/(n+1); e=sum(p[:n])/n
            for x in p[n:]: e=x*k+e*(1-k)
            return e

        e9=ema(c5_close,9); e21=ema(c5_close,21)
        e50_15=ema(c15_close,50); e50_60=ema(c60_close,50); e200_60=ema(c60_close,200)

        # سكور
        score=50
        if c5_close[-1]>e9: score+=10
        if e9>e21: score+=10
        if c15_close[-1]>e50_15: score+=15
        if c60_close[-1]>e50_60: score+=10
        if c60_close[-1]>e200_60: score+=15
        else: score-=15

        # توصية اجبارية
        atr=abs(c5_close[-1]-c5_close[-2])*2.5
        if atr<4: atr=5

        # دعم ومقاومة قريبة للوقف
        sup = near_sup[-1] if near_sup else price-8
        res = near_res[0] if near_res else price+8

        if score>=58:
            sig="🟢 شراء BUY"; sl=sup-1.5; tp1=price+atr; tp2=res; exp=f"فوق EMA + دعم {sup:.1f} + ترند صاعد"
        elif score<=42:
            sig="🔴 بيع SELL"; sl=res+1.5; tp1=price-atr; tp2=sup; exp=f"تحت EMA + مقاومة {res:.1f} + ترند هابط"
        else:
            # حتى بالحيادي بيعطيك سكالب
            if price-sup < res-price:
                sig="🟢 شراء سكالب"; sl=sup-1; tp1=price+5; tp2=res; exp=f"ارتداد من دعم قريب {sup:.1f}"
            else:
                sig="🔴 بيع سكالب"; sl=res+1; tp1=price-5; tp2=sup; exp=f"رفض من مقاومة قريبة {res:.1f}"

        txt=f"""{sig} | قوة {score}/100
💰 دخول: {price:.2f}
🛑 وقف: {sl:.2f} ({abs(price-sl):.1f}$)
🎯 هدف1: {tp1:.2f}
🎯 هدف2: {tp2:.2f}
📝 السبب: {exp}

━━━━━━━━━━━━━━━
🧱 دعم ومقاومة قريبة (15M-1H):
دعوم:
{chr(10).join([f" • {s:.2f} ({price-s:.1f}$ تحت)" for s in sorted(near_sup,reverse=True)])}

مقاومات:
{chr(10).join([f" • {r:.2f} ({r-price:.1f}$ فوق)" for r in sorted(near_res)])}

رينج 1H: {s60:.1f} - {r60:.1f}
رينج 15M: {s15:.1f} - {r15:.1f}

💧 سيولة:
اقرب تجمع فوق: {res:.2f}
اقرب تجمع تحت: {sup:.2f}
الحيتان: رح يضربوا {'فوق' if res-price < price-sup else 'تحت'} اول

🏦 OB: 15M دعم {s15:.1f} مقاومة {r15:.1f}
"""
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e} - جرب /test")

async def start(update,context):
    await update.message.reply_text("V11\n/tawsiya توصية + SMC")

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",tawsiya))
        b.add_handler(CommandHandler("tawsiyat",tawsiya))
        b.add_handler(CommandHandler("qawi",tawsiya))
        b.run_polling()
