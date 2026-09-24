import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "OK"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=8).json()['price'])
    except:
        try:
            d=requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",timeout=8).json()
            return float(d['price'])
        except: return None

def get_klines(interval, limit=100):
    try:
        d=requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=10).json()
        if isinstance(d,list) and len(d)>50: return d
    except: pass
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ جاهز\n/qawi - توصية كاملة مع كلشي")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم اجيب السعر والدعم والسيولة...")
    spot=get_price()
    kl5=get_klines("5m",100); kl60=get_klines("1h",100); kl240=get_klines("4h",100)
    if not spot or len(kl5)<50:
        await update.message.reply_text("السيرفر مزحوم - جرب بعد 30 ثانية"); return

    c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c5

    e21=ema(c5,21); e50=ema(c5,50); e200=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50)

    # دعم ومقاومة حقيقي
    sup1=round(min(l5[-30:]),2)
    sup2=round(e50,2)
    res1=round(max(h5[-30:]),2)
    res2=round(e21+2,2)

    # سحب سيولة
    last_high=max(h5[-20:-1]); last_low=min(l5[-20:-1])
    if h5[-1] > last_high and c5[-1] < last_high:
        liq=f"💧 سحب سيولة فوق {last_high:.2f}$ - ضرب ستوبات البيع ورجع نزل = إشارة بيع قوية"
    elif l5[-1] < last_low and c5[-1] > last_low:
        liq=f"💧 سحب سيولة تحت {last_low:.2f}$ - ضرب ستوبات الشراء ورجع طلع = إشارة شراء قوية"
    else:
        liq=f"💧 ما في سحب هلا - القمة {last_high:.2f}$ القاع {last_low:.2f}$ - اذا كسرهم بيصير سحب"

    # دورة زمنية
    hour=datetime.utcnow().hour
    if 8 <= hour <= 11: sess="🔥 لندن هلا - اقوى وقت - ادخل هلا"; when="هلا"
    elif 13 <= hour <= 16: sess="💥 نيويورك هلا - انفجار - ادخل هلا"; when="هلا"
    elif 6 <= hour < 8: sess="⏳ قبل لندن - تجميع سيولة"; when="بعد 30-90 دقيقة"
    elif 17 <= hour <= 21: sess="🌆 مسائي - ترند هادئ"; when="هلا بس هدف صغير"
    else: sess="🌙 آسيا - سوق نايم - لا تدخل"; when="بعد 4-7 ساعات بلندن"

    atr=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    if atr<1.5: atr=1.5

    # توصية مع دخول - دايما
    if c5[-1] > e50 and c60[-1] > e50_1h: # صاعد
        entry=round(e21,2)
        if entry > spot-0.8: entry=round(spot-2.2,2)
        sl=round(entry-4.0,2)
        tp1=round(entry+3.0,2); tp2=round(entry+6.5,2); tp3=round(entry+12.0,2)
        side="🟢 شراء BUY"; order=f"BUY LIMIT {entry}$"
    else: # هابط او عرضي نعطي شراء من الدعم لانو الذهب ترنده صاعد عام
        entry=round(sup1,2) if sup1 < spot else round(e50,2)
        if entry > spot: entry=round(spot-2.5,2)
        sl=round(entry-4.0,2)
        tp1=round(entry+3.0,2); tp2=round(entry+6.5,2); tp3=round(entry+12.0,2)
        side="🟢 شراء من الدعم BUY"; order=f"BUY LIMIT {entry}$"

    msg=f"""💰 السعر هلا: {spot:.2f}$

{side} - مع كل التفاصيل

🎯 ايمتى افوت؟
{order}
اذا وصل {entry}$ ادخل فورا

🛑 ستوب: {sl}$ (-4$)

💎 اهداف قوية مو 0.1$:
هدف1: {tp1}$ (+3$) سكر 40%
هدف2: {tp2}$ (+6.5$) سكر 30%
هدف3: {tp3}$ (+12$) سكر 30%

📊 الدعم والمقاومة:
دعم1: {sup1}$ (قاع 30 شمعة)
دعم2: {sup2}$ (EMA50)
مقاومة1: {res1}$ (قمة 30 شمعة)
مقاومة2: {res2}$

{liq}

⏰ الدورة الزمنية:
{sess}
ايمتى يوصل الهدف؟ {when}

📈 EMA:
5M: 21={e21:.2f}$ 50={e50:.2f}$ 200={e200:.2f}$
1H: 50={e50_1h:.2f}$ | 4H: 50={e50_4h:.2f}$

حط الامر هلا وانتظر اللمس
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.run_polling()
