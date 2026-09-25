import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Time Cycle Fixed"
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
    rs=gains/losses
    return 100-(100/(1+rs))

def get_time_cycle():
    now = datetime.utcnow()
    hour = now.hour
    weekday = now.weekday() # 0=الاثنين

    cycle = {}
    # الجلسات
    if 0 <= hour < 6:
        cycle['session'] = "🌙 آسيا - السوق ميت"
        cycle['power'] = 20
        cycle['advice'] = "لا تدخل توصية كبيرة - بس سكالبينج 1$ اذا بدك"
        cycle['next_power'] = "لندن بتفتح بعد "+str(8-hour)+" ساعات"
        cycle['best_trade'] = "انتظار"
    elif 6 <= hour < 8:
        cycle['session'] = "⚠️ قبل لندن - تجميع"
        cycle['power'] = 50
        cycle['advice'] = "عم يجمعو سيولة - رح ينفجر بعد شوي"
        cycle['next_power'] = "لندن بتفتح الساعة 8:00 UTC"
        cycle['best_trade'] = "جهز حالك"
    elif 8 <= hour < 11:
        cycle['session'] = "🔥 لندن KILLZONE - اقوى وقت"
        cycle['power'] = 95
        cycle['advice'] = "ادخل هلا - هاد اقوى وقت للذهب 30$ حركة"
        cycle['next_power'] = "هلا الذروة"
        cycle['best_trade'] = "ادخل هلا MARKET"
    elif 11 <= hour < 13:
        cycle['session'] = "📉 بين لندن ونيويورك - هدوء"
        cycle['power'] = 40
        cycle['advice'] = "السوق بهدي - لا تدخل جديد - استنى نيويورك"
        cycle['next_power'] = "نيويورك بتفتح 13:00 UTC"
        cycle['best_trade'] = "انتظار"
    elif 13 <= hour < 16:
        cycle['session'] = "💥 نيويورك KILLZONE - انفجار"
        cycle['power'] = 100
        cycle['advice'] = "اقوى انفجار - ادخل هلا اذا فاتتك لندن"
        cycle['next_power'] = "هلا الذروة"
        cycle['best_trade'] = "ادخل هلا MARKET"
    elif 16 <= hour < 19:
        cycle['session'] = "📉 بعد نيويورك - ترند بطيء"
        cycle['power'] = 45
        cycle['advice'] = "الحركة خلصت - سكر وانتظر بكرا"
        cycle['next_power'] = "بكرا لندن 8:00 UTC"
        cycle['best_trade'] = "سكر"
    else:
        cycle['session'] = "🌙 مسائي ميت - لا تدخل"
        cycle['power'] = 10
        cycle['advice'] = "لا تدخل - السوق نايم"
        cycle['next_power'] = "بكرا آسيا"
        cycle['best_trade'] = "لا تدخل"

    # يوم الاسبوع
    if weekday == 0:
        cycle['day'] = "الاثنين - بداية اسبوع - حذر"
        cycle['day_power'] = 60
    elif weekday == 4:
        cycle['day'] = "الجمعة - يوم خطير - سكر قبل 16:00 UTC"
        cycle['day_power'] = 50
    elif weekday == 2 or weekday == 3:
        cycle['day'] = "ثلاثاء/اربعاء - اقوى ايام الذهب"
        cycle['day_power'] = 95
    else:
        cycle['day'] = "منتصف الاسبوع - جيد"
        cycle['day_power'] = 80

    # الدورة الشهرية
    day_month = now.day
    if 1 <= day_month <= 3:
        cycle['month'] = "بداية شهر - NFP قريب - حذر"
    elif 28 <= day_month <= 31:
        cycle['month'] = "نهاية شهر - جني ارباح"
    else:
        cycle['month'] = "منتصف شهر - عادي"

    return cycle

def analyze():
    spot=get_price()
    kl1=get_klines("1m",100); kl5=get_klines("5m",100); kl15=get_klines("15m",100); kl60=get_klines("1h",100); kl240=get_klines("4h",100)
    if not spot or len(kl1)<60: return None

    c1=[float(x[4]) for x in kl1]; h1=[float(x[2]) for x in kl1]
    c5=[float(x[4]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c60

    e9_1=ema(c1,9); e21_1=ema(c1,21)
    e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50)

    rsi1=rsi(c1); rsi5=rsi(c5); rsi15=rsi(c15)

    bullish_score=0
    if c15[-1] > e50_5: bullish_score+=1
    if e50_5 > e200_5: bullish_score+=1
    if c60[-1] > e50_1h: bullish_score+=1
    if c240[-1] > e50_4h: bullish_score+=1
    if rsi15 > 50: bullish_score+=1

    sup1=round(min(l15[-30:]),2); res1=round(max(h15[-30:]),2)
    recent_high=max(h15[-20:-1]); recent_low=min(l15[-20:-1])

    cycle = get_time_cycle()
    power = cycle['power']

    # === المنطق مع الدورة الزمنية ===
    if power < 30:
        # سوق ميت - لا توصية كبيرة
        scalp_side = "⏸️ سوق ميت - لا تدخل"
        scalp_entry = spot
        scalp_sl = 0; scalp_tp1 = 0; scalp_tp2 = 0
        scalp_reason = f"{cycle['session']} - قوة {power}% - انتظر {cycle['next_power']}"

        big_side = "⏸️ انتظار - سوق ميت"
        big_entry = 0
        big_sl = 0; big_tp1 = 0; big_tp2 = 0
        big_reason = f"الساعة UTC {datetime.utcnow().hour}:00 سوق ميت - لا تدخل توصية كبيرة"

    elif bullish_score >= 4:
        scalp_side = "🟢 شراء مع الترند + دورة قوية"
        scalp_entry = spot
        scalp_sl = round(spot-1.5,2)
        scalp_tp1 = round(spot+ (2.5 if power>80 else 1.2),2) # هدف اكبر وقت لندن/نيويورك
        scalp_tp2 = round(spot+ (5 if power>80 else 2.5),2)
        scalp_reason = f"ترند صاعد {bullish_score}/5 + {cycle['session']} قوة {power}% = ادخل MARKET هلا"

        big_side = "🟢 شراء مع الترند"
        big_entry = round(sup1+1,2) if sup1 < spot else round(spot-2,2)
        big_sl = round(big_entry-4.5,2)
        big_tp1 = round(big_entry+ (6 if power>80 else 3),2)
        big_tp2 = round(big_entry+ (12 if power>80 else 6),2)
        big_reason = f"ترند صاعد + {cycle['session']} = اي هبوط شراء"

    elif bullish_score <= 1:
        scalp_side = "🔴 بيع مع الترند + دورة قوية"
        scalp_entry = spot
        scalp_sl = round(spot+1.5,2)
        scalp_tp1 = round(spot- (2.5 if power>80 else 1.2),2)
        scalp_tp2 = round(spot- (5 if power>80 else 2.5),2)
        scalp_reason = f"ترند هابط {bullish_score}/5 + {cycle['session']} قوة {power}% = ادخل MARKET هلا"

        big_side = "🔴 بيع مع الترند"
        big_entry = round(res1-1,2) if res1 > spot else round(spot+2,2)
        big_sl = round(big_entry+4.5,2)
        big_tp1 = round(big_entry- (6 if power>80 else 3),2)
        big_tp2 = round(big_entry- (12 if power>80 else 6),2)
        big_reason = f"ترند هابط + {cycle['session']} = اي صعود بيع"

    else:
        scalp_side = "🟡 عرضي - سكالبينج خفيف"
        scalp_entry = spot
        scalp_sl = round(spot-1.5,2) if spot-sup1 < res1-spot else round(spot+1.5,2)
        scalp_tp1 = round(spot+1.2,2) if spot-sup1 < res1-spot else round(spot-1.2,2)
        scalp_tp2 = round(spot+2.5,2) if spot-sup1 < res1-spot else round(spot-2.5,2)
        scalp_reason = f"عرضي + {cycle['session']} قوة {power}%"

        big_side = "🟡 انتظار كسر"
        big_entry = round(sup1+0.8,2)
        big_sl = round(big_entry-4,2)
        big_tp1 = round(big_entry+3,2)
        big_tp2 = round(big_entry+6,2)
        big_reason = f"سوق عرضي - استنى كسر {res1}$ او {sup1}$ مع {cycle['session']}"

    big_tp3 = round(big_tp2+5,2) if "شراء" in big_side else round(big_tp2-5,2) if big_tp2!=0 else 0

    return {
        "spot":spot,"sup":sup1,"res":res1,"rh":recent_high,"rl":recent_low,
        "score":bullish_score,"rsi1":rsi1,"rsi5":rsi5,"rsi15":rsi15,
        "cycle":cycle,
        "scalp_side":scalp_side,"scalp_entry":scalp_entry,"scalp_sl":scalp_sl,"scalp_tp1":scalp_tp1,"scalp_tp2":scalp_tp2,"scalp_reason":scalp_reason,
        "big_side":big_side,"big_entry":big_entry,"big_sl":big_sl,"big_tp1":big_tp1,"big_tp2":big_tp2,"big_tp3":big_tp3,"big_reason":big_reason,
    }

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت مع دورة زمنية حقيقية\n/tawsiya")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل الترند + الدورة الزمنية...")
    d=analyze()
    if not d:
        await update.message.reply_text("زحمة - جرب بعد 10 ثواني"); return

    c = d['cycle']
    now = datetime.utcnow()

    if d['scalp_sl']==0:
        msg=f"""💰 {d['spot']:.2f}$ | {now.strftime('%H:%M')} UTC

⏰ الدورة الزمنية:
{c['session']}
قوة السوق: {c['power']}%
اليوم: {c['day']}
{ c['month']}

{c['advice']}
{ c['next_power']}

📊 الترند: Score {d['score']}/5
دعم {d['sup']}$ مقاومة {d['res']}$

⏸️ {d['scalp_side']}
لا تدخل هلا - انتظر {c['next_power']}
"""
    else:
        msg=f"""💰 {d['spot']:.2f}$ | {now.strftime('%H:%M')} UTC

⏰ الدورة الزمنية - هاد الجديد:
{c['session']} - قوة {c['power']}%
{c['day']} - قوة {c['day_power']}%
{ c['month']}
{c['advice']}
➡️ {c['next_power']}
قرار الدورة: {c['best_trade']}

📊 الترند: Score {d['score']}/5 | RSI 15m {d['rsi15']:.0f}
دعم {d['sup']}$ | مقاومة {d['res']}$
قمة {d['rh']:.2f}$ قاع {d['rl']:.2f}$

━━━━━━━━━━━━━━━
⚡ سكالبينج مع الدورة
━━━━━━━━━━━━━━━
{d['scalp_side']}
دخول {d['scalp_entry']:.2f}$ MARKET
ستوب {d['scalp_sl']}$ هدف {d['scalp_tp1']}$ / {d['scalp_tp2']}$
ليش؟ {d['scalp_reason']}

━━━━━━━━━━━━━━━
📊 توصية كبيرة مع الدورة
━━━━━━━━━━━━━━━
{d['big_side']} {d['big_entry']:.2f}$
ستوب {d['big_sl']}$ هدف {d['big_tp1']}$ / {d['big_tp2']}$
ليش؟ {d['big_reason']}

💡 وقت لندن ونيويورك الهدف ضعف - وقت آسيا لا تدخل
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.add_handler(CommandHandler("saree3",tawsiya))
    bot.run_polling()
