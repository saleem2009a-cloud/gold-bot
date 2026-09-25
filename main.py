import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Fixed Buy Sell"
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

    c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c60

    e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50); e200_1h=ema(c60,200)
    rsi15=rsi(c15)

    # ترند واضح
    score=0
    if c15[-1] > e50_5: score+=1
    if e50_5 > e200_5: score+=1
    if c60[-1] > e50_1h: score+=1
    if c240[-1] > e50_4h: score+=1
    if rsi15 > 52: score+=1

    sup1=round(min(l15[-30:]),2); res1=round(max(h15[-30:]),2)
    hour=datetime.utcnow().hour

    # دورة زمنية
    if 8 <= hour <= 11:
        session="🔥 لندن - قوة 95%"; power=95; time_ok=True
    elif 13 <= hour <= 16:
        session="💥 نيويورك - قوة 100%"; power=100; time_ok=True
    elif 6 <= hour <= 7:
        session="⚠️ قبل لندن - قوة 50%"; power=50; time_ok=False
    elif 11 <= hour <= 12:
        session="📉 بين الجلستين - قوة 40%"; power=40; time_ok=False
    else:
        session="🌙 آسيا/مسائي - قوة 20% - ميت"; power=20; time_ok=False

    # === قرار واضح شراء ولا بيع ===
    if not time_ok:
        decision = "⏸️ انتظار"
        side = "لا تدخل هلا"
        entry = 0
        reason = f"{session} - السوق ضعيف - انتظر لندن 8:00 او نيويورك 13:00 UTC"
    elif score >= 3: # صاعد
        decision = "🟢 شراء"
        side = "BUY"
        # دخول واضح
        if spot - sup1 < 4: # قريب من الدعم
            entry = spot
            entry_type = "MARKET هلا"
        else:
            entry = round(sup1+1.2,2)
            entry_type = f"LIMIT {entry}$ عند الدعم"
        reason = f"ترند صاعد Score {score}/5 + {session} = ممنوع البيع - بس شراء"
    else: # هابط
        decision = "🔴 بيع"
        side = "SELL"
        if res1 - spot < 4:
            entry = spot
            entry_type = "MARKET هلا"
        else:
            entry = round(res1-1.2,2)
            entry_type = f"LIMIT {entry}$ عند المقاومة"
        reason = f"ترند هابط Score {score}/5 + {session} = ممنوع الشراء - بس بيع"

    if decision == "⏸️ انتظار":
        return {
            "spot":spot,"decision":decision,"side":side,"entry":0,"session":session,"power":power,
            "sup":sup1,"res":res1,"score":score,"rsi":rsi15,"reason":reason,"time_ok":False,
            "sl":0,"tp1":0,"tp2":0,"entry_type":""
        }

    # ستوب واهداف حسب الدورة
    if decision == "🟢 شراء":
        sl = round(entry-4.5,2) if entry!=spot else round(spot-2,2)
        tp1 = round(entry+ (6 if power>80 else 3),2)
        tp2 = round(entry+ (12 if power>80 else 6),2)
        tp3 = round(entry+ (20 if power>80 else 10),2)
    else:
        sl = round(entry+4.5,2) if entry!=spot else round(spot+2,2)
        tp1 = round(entry- (6 if power>80 else 3),2)
        tp2 = round(entry- (12 if power>80 else 6),2)
        tp3 = round(entry- (20 if power>80 else 10),2)

    return {
        "spot":spot,"decision":decision,"side":side,"entry":entry,"entry_type":entry_type,
        "session":session,"power":power,"sup":sup1,"res":res1,"score":score,"rsi":rsi15,
        "reason":reason,"time_ok":True,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3
    }

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت مصلح - بيحدد شراء ولا بيع بوضوح\n/tawsiya")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل...")
    d=analyze()
    if not d:
        await update.message.reply_text("زحمة - جرب بعد 10 ثواني"); return

    now=datetime.utcnow().strftime("%H:%M UTC")

    if not d['time_ok']:
        msg=f"""💰 {d['spot']:.2f}$ | {now}

⏰ الدورة: {d['session']}
قوة: {d['power']}%

{d['decision']} - {d['side']}
❌ {d['reason']}

دعم {d['sup']}$ مقاومة {d['res']}$
Score {d['score']}/5 RSI {d['rsi']:.0f}

💡 لا تدخل هلا - انتظر وقت قوي
"""
    else:
        msg=f"""💰 {d['spot']:.2f}$ | {now}

⏰ الدورة: {d['session']}
قوة: {d['power']}%

━━━━━━━━━━━━━━━
{d['decision']} - {d['side']} - واضح
━━━━━━━━━━━━━━━
🎯 دخول: {d['entry_type']}
السعر هلا {d['spot']:.2f}$

🛑 ستوب: {d['sl']}$
💰 هدف1: {d['tp1']}$ سكر 50%
💰 هدف2: {d['tp2']}$ سكر 30%
💰 هدف3: {d['tp3']}$ سكر 20%

📊 ليش {d['decision']}؟
{d['reason']}
Score {d['score']}/5 | RSI 15m {d['rsi']:.0f}
دعم {d['sup']}$ | مقاومة {d['res']}$

⏱️ ايمتى يوصل؟
قوة {d['power']}% = {'30-60 دقيقة' if d['power']>80 else '1-3 ساعات'}
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.add_handler(CommandHandler("qawi",tawsiya))
    bot.run_polling()
