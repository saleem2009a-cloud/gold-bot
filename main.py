import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold No Trap"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=6).json()['price'])
    except:
        try: return float(requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",timeout=6).json()['price'])
        except: return None

def get_klines(interval, limit=100):
    try:
        d=requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=8).json()
        if isinstance(d,list) and len(d)>80: return d
    except: pass
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def analyze():
    spot=get_price()
    kl15=get_klines("15m",100); kl60=get_klines("1h",100); kl240=get_klines("4h",100); kl1440=get_klines("1d",100)
    if not spot: return None

    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60]; h60=[float(x[2]) for x in kl60]; l60=[float(x[3]) for x in kl60]
    c240=[float(x[4]) for x in kl240]
    c1440=[float(x[4]) for x in kl1440] if kl1440 else c240

    e50_15=ema(c15,50); e200_15=ema(c15,200)
    e50_1h=ema(c60,50); e200_1h=ema(c60,200)
    e50_4h=ema(c240,50); e200_4h=ema(c240,200)
    e50_d=ema(c1440,50)

    # === كشف الترند القوي - ممنوع عكسه ===
    up_4h = c240[-1] > e50_4h and e50_4h > e200_4h
    down_4h = c240[-1] < e50_4h and e50_4h < e200_4h
    up_1h = c60[-1] > e50_1h and e50_1h > e200_1h
    down_1h = c60[-1] < e50_1h and e50_1h < e200_1h

    # قوة الترند من 0-100
    if up_4h and up_1h and c15[-1] > e50_15:
        trend = "صاعد قوي جدا"; power_trend = 95; direction = "شراء فقط"
    elif down_4h and down_1h and c15[-1] < e50_15:
        trend = "هابط قوي جدا"; power_trend = 95; direction = "بيع فقط"
    elif up_1h:
        trend = "صاعد"; power_trend = 70; direction = "شراء"
    elif down_1h:
        trend = "هابط"; power_trend = 70; direction = "بيع"
    else:
        trend = "عرضي"; power_trend = 30; direction = "انتظار"

    sup = round(min(l15[-20:]),2)
    res = round(max(h15[-20:]),2)
    high_1h = max(h60[-12:]); low_1h = min(l60[-12:])

    hour=datetime.utcnow().hour
    if 8 <= hour <= 11: sess="🔥 لندن"; sess_power=95
    elif 13 <= hour <= 16: sess="💥 نيويورك"; sess_power=100
    else: sess="🌙 ضعيف"; sess_power=20

    # === قرار مستحيل يورطك ===
    if power_trend >= 70 and "شراء" in direction:
        # ترند صاعد - ممنوع البيع نهائيا
        if sess_power < 50:
            return {"spot":spot,"decision":"⏸️ انتظار","reason":f"ترند {trend} بس {sess} ضعيف - انتظر لندن او نيويورك","time_ok":False,"sup":sup,"res":res,"trend":trend,"power":power_trend,"sess":sess,"sess_power":sess_power}

        decision="🟢 شراء فقط - ممنوع البيع"
        entry_type=f"دخول مباشر هلا {spot:.2f} دولار"
        entry=spot
        sl=round(spot-5,2)
        tp1=round(spot+6,2)
        tp2=round(spot+13,2)
        tp3=round(spot+22,2)
        reason=f"الذهب طاير لفوق M15 و M30 و 1H كلهم خضر متل شارتك - اذا بعت بتتعلق - بس شراء"

    elif power_trend >=70 and "بيع" in direction:
        decision="🔴 بيع فقط - ممنوع الشراء"
        entry_type=f"دخول مباشر هلا {spot:.2f} دولار"
        entry=spot
        sl=round(spot+5,2)
        tp1=round(spot-6,2)
        tp2=round(spot-13,2)
        tp3=round(spot-22,2)
        reason=f"ترند {trend} قوي - اي صعود هو بيع"

    else:
        return {"spot":spot,"decision":"⏸️ انتظار - سوق عرضي","reason":f"ترند {trend} - السوق عرضي - لا تدخل","time_ok":False,"sup":sup,"res":res,"trend":trend,"power":power_trend,"sess":sess,"sess_power":sess_power}

    return {
        "spot":spot,"decision":decision,"entry":entry,"entry_type":entry_type,
        "sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"sup":sup,"res":res,
        "trend":trend,"power":power_trend,"sess":sess,"sess_power":sess_power,
        "reason":reason,"time_ok":True,"high_1h":high_1h,"low_1h":low_1h
    }

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت ما بيورط - بيمشي مع الترند\n/tawsiya")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل الترند القوي...")
    d=analyze()
    if not d:
        await update.message.reply_text("زحمة - جرب بعد 10 ثواني"); return
    now=datetime.utcnow().strftime("%H:%M توقيت عالمي")

    if not d['time_ok']:
        msg=f"""💰 {d['spot']:.2f} دولار | {now}

📈 الترند: {d['trend']} قوة {d['power']}%
⏰ الجلسة: {d['sess']} قوة {d['sess_power']}%

⏸️ {d['decision']}
{d['reason']}

الدعم {d['sup']}$ المقاومة {d['res']}$

💡 متل حالتك اليوم - كنت بايع بترند صاعد - هاد البوت الجديد ما بيعطيك بيع ابدا اذا الترند صاعد قوي
"""
    else:
        msg=f"""💰 {d['spot']:.2f} دولار | {now}

📈 الترند: {d['trend']} قوة {d['power']}% - {d['sess']} قوة {d['sess_power']}%

{d['decision']}

🎯 {d['entry_type']}
السعر هلا {d['spot']:.2f} دولار

🛑 وقف الخسارة: {d['sl']} دولار
💰 هدف أول: {d['tp1']} دولار
💰 هدف ثاني: {d['tp2']} دولار
💰 هدف ثالث: {d['tp3']} دولار

📊 السبب:
{d['reason']}

الدعم {d['sup']}$ المقاومة {d['res']}$
قمة الساعة {d['high_1h']:.2f}$ قاع الساعة {d['low_1h']:.2f}$

✅ هاد البوت اذا شاف شارتك يلي بالصورة - كل الشموع خضرا طالعة - مستحيل يقلك بيع
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.run_polling()
