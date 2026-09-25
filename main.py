import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Arabic Only"
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
        if isinstance(d,list) and len(d)>70: return d
    except: pass
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices, p=14):
    gains=losses=0
    for i in range(1,p+1):
        diff=prices[-i]-prices[-i-1]
        if diff>0: gains+=diff
        else: losses+=-diff
    if losses==0: return 70
    return 100-(100/(1+gains/losses if losses!=0 else 1))

def analyze():
    spot=get_price()
    kl5=get_klines("5m",100); kl15=get_klines("15m",100); kl60=get_klines("1h",100); kl240=get_klines("4h",100)
    if not spot: return None

    c5=[float(x[4]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c60

    e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50)
    rsi15=rsi(c15)

    score=0
    if c15[-1] > e50_5: score+=1
    if e50_5 > e200_5: score+=1
    if c60[-1] > e50_1h: score+=1
    if c240[-1] > e50_4h: score+=1
    if rsi15 > 52: score+=1

    sup1=round(min(l15[-30:]),2); res1=round(max(h15[-30:]),2)
    hour=datetime.utcnow().hour

    if 8 <= hour <= 11: session="🔥 لندن - قوة 95%"; power=95; time_ok=True
    elif 13 <= hour <= 16: session="💥 نيويورك - قوة 100%"; power=100; time_ok=True
    else: session="🌙 سوق ضعيف"; power=30; time_ok=False

    if not time_ok:
        return {"spot":spot,"decision":"⏸️ انتظار","reason":f"{session} - انتظر وقت قوي","time_ok":False,"sup":sup1,"res":res1,"score":score,"rsi":rsi15,"session":session,"power":power}

    if score >= 3:
        distance_to_sup = spot - sup1
        if distance_to_sup > 8:
            entry = spot
            entry_type = f"دخول مباشر هلا {spot:.2f}$"
            sl = round(spot-4,2)
            tp1 = round(spot+4,2)
            tp2 = round(spot+9,2)
            tp3 = round(spot+16,2)
        else:
            entry = round(spot-1.5,2)
            entry_type = f"أمر معلق عند {entry:.2f}$ (تصحيح صغير)"
            sl = round(entry-4,2)
            tp1 = round(entry+5,2)
            tp2 = round(entry+10,2)
            tp3 = round(entry+17,2)

        decision="🟢 شراء"
        reason=f"ترند صاعد {score}/5 + {session} - ممنوع البيع"

    else:
        distance_to_res = res1 - spot
        if distance_to_res > 8:
            entry = spot
            entry_type = f"دخول مباشر هلا {spot:.2f}$"
            sl = round(spot+4,2)
            tp1 = round(spot-4,2)
            tp2 = round(spot-9,2)
            tp3 = round(spot-16,2)
        else:
            entry = round(spot+1.5,2)
            entry_type = f"أمر معلق عند {entry:.2f}$ (تصحيح صغير)"
            sl = round(entry+4,2)
            tp1 = round(entry-5,2)
            tp2 = round(entry-10,2)
            tp3 = round(entry-17,2)

        decision="🔴 بيع"
        reason=f"ترند هابط {score}/5 + {session}"

    return {
        "spot":spot,"decision":decision,"entry":entry,"entry_type":entry_type,
        "sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"sup":sup1,"res":res1,"score":score,
        "rsi":rsi15,"session":session,"power":power,"reason":reason,"time_ok":True
    }

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت عربي كامل\n/tawsiya")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل...")
    d=analyze()
    if not d:
        await update.message.reply_text("زحمة - جرب بعد 10 ثواني"); return

    now=datetime.utcnow().strftime("%H:%M توقيت عالمي")

    if not d['time_ok']:
        msg=f"""💰 السعر هلا: {d['spot']:.2f} دولار

⏰ الدورة: {d['session']}
القوة: {d['power']}%

⏸️ انتظار
{d['reason']}

الدعم {d['sup']}$ | المقاومة {d['res']}$
"""
    else:
        msg=f"""💰 السعر هلا: {d['spot']:.2f} دولار | {now}

⏰ الدورة: {d['session']}
القوة: {d['power']}%

━━━━━━━━━━━━━━━
{d['decision']} - واضح
━━━━━━━━━━━━━━━
🎯 {d['entry_type']}
السعر الحالي {d['spot']:.2f} دولار

🛑 وقف الخسارة: {d['sl']} دولار
💰 الهدف الأول: {d['tp1']} دولار - سكر 50%
💰 الهدف الثاني: {d['tp2']} دولار - سكر 30%
💰 الهدف الثالث: {d['tp3']} دولار - سكر 20%

📊 السبب:
{d['reason']}
التقييم {d['score']}/5 | مؤشر القوة {d['rsi']:.0f}
الدعم {d['sup']} دولار | المقاومة {d['res']} دولار

⏱️ مدة الوصول: {'نص ساعة لساعة' if d['power']>80 else 'ساعة ل 3 ساعات'}
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.run_polling()
