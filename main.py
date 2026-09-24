import os, requests, threading, re
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)
@app.route('/')
def home(): return "Gold AI Chat Bot"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()['price'])
    except: return None

def get_klines(interval, limit=150):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            d=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=10).json()
            if isinstance(d,list) and len(d)>80: return d
        except: continue
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def find_levels(highs, lows, closes):
    # دعم ومقاومة حقيقي - pivots
    supports=[]; resists=[]
    for i in range(2, len(closes)-2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            supports.append(lows[i])
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resists.append(highs[i])

    # اقرب 3 دعوم ومقاومات
    if supports: supports=sorted(set([round(x,2) for x in supports]))[-3:]
    if resists: resists=sorted(set([round(x,2) for x in resists]))[:3]
    return supports, resists

def check_liquidity(highs, lows, closes):
    # سحب سيولة = كسر كاذب ورجوع
    last_high=max(highs[-20:-1])
    last_low=min(lows[-20:-1])
    swept_high = highs[-1] > last_high and closes[-1] < last_high
    swept_low = lows[-1] < last_low and closes[-1] > last_low
    if swept_high:
        return f"💧 سحب سيولة فوق {last_high:.2f}$ - ضرب ستوبات البيع ورجع نزل - اشارة بيع قوية!"
    if swept_low:
        return f"💧 سحب سيولة تحت {last_low:.2f}$ - ضرب ستوبات الشراء ورجع طلع - اشارة شراء قوية!"
    return f"ما في سحب سيولة هلا - القمة {last_high:.2f}$ القاع {last_low:.2f}$"

async def qawi_logic():
    spot=get_price()
    kl5=get_klines("5m"); kl60=get_klines("1h"); kl240=get_klines("4h"); kl1d=get_klines("1d")
    if not spot or len(kl5)<80: return "النت ضعيف جرب بعد دقيقة"

    c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c5

    e21=ema(c5,21); e50=ema(c5,50); e200=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50)

    supports, resists = find_levels(h5,l5,c5)
    liq = check_liquidity(h5,l5,c5)

    now=datetime.utcnow()
    hour=now.hour
    if 8 <= hour <= 11: session="🔥 لندن - اقوى سيولة وحركة"; next_move="الحركة رح تكون قوية هلا"
    elif 13 <= hour <= 16: session="💥 نيويورك - انفجار سيولة"; next_move="انتبه انفجار هلا"
    elif 6 <= hour < 8: session="⏳ قبل لندن ب شوي - تجميع"; next_move="رح ينفجر بعد شوي بلندن"
    elif 17 <= hour <= 21: session="🌆 بعد نيويورك - ترند مسائي"; next_move="حركة بطيئة بس ترند"
    else: session="🌙 آسيا - هادئ تجميع سيولة"; next_move="ما تدخل هلا - انتظر لندن بعد 4-7 ساعات"

    atr=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    if atr<1.5: atr=1.5

    # توصية
    if c5[-1]>e50 and c60[-1]>e50_1h:
        trend="صاعد"; entry=round(e21,2)
        if entry>spot: entry=round(spot-2.0,2)
        return f"""💰 السعر: {spot:.2f}$

📊 الترند: {trend} قوي
EMA21: {e21:.2f}$ | EMA50: {e50:.2f}$ | EMA50 1H: {e50_1h:.2f}$ | 4H: {e50_4h:.2f}$

🎯 الدعم والمقاومة:
دعم: {', '.join([str(s)+'$' for s in supports]) if supports else 'عم يحسب'}
مقاومة: {', '.join([str(r)+'$' for r in resists]) if resists else 'عم يحسب'}

{liq}

⏰ الدورة الزمنية:
{session}
{next_move}
الساعة هلا UTC {hour}:00

🎯 اذا وصل {entry}$ ادخل شراء
BUY LIMIT {entry}$
وقف: {round(entry-4,2)}$
هدف1: {round(entry+3,2)}$ (+3$)
هدف2: {round(entry+6,2)}$ (+6$)
هدف3: {round(entry+12,2)}$ (+12$)
"""
    else:
        entry=round(e21,2)
        if entry<spot: entry=round(spot+2.0,2)
        return f"""💰 السعر: {spot:.2f}$
📊 الترند: هابط
دعم: {supports}
مقاومة: {resists}
{liq}
⏰ {session}

🎯 اذا وصل {entry}$ ادخل بيع
SELL LIMIT {entry}$
"""

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اهلا! انا بوت ذكي 🤖\n\n/qawi - توصية كاملة\n\nواذا بدك تحاورني اكتبلي متل:\n- وين الدعم؟\n- وين سحب السيولة؟\n- شو الدورة الزمنية؟\n- حلللي الذهب\n\nاكتب اي شي وبرد عليك!")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ثواني عم احلل دعم ومقاومة وسحب سيولة...")
    txt=await qawi_logic()
    await update.message.reply_text(txt)

# هون الحوار - اهم شي
async def chat(update:Update, context:ContextTypes.DEFAULT_TYPE):
    text=update.message.text.lower()
    spot=get_price()

    if "دعم" in text or "مقاومة" in text:
        kl5=get_klines("5m")
        if kl5:
            c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
            sup, res = find_levels(h5,l5,c5)
            await update.message.reply_text(f"السعر هلا {spot:.2f}$\n\nدعم قوي: {sup}\nمقاومة قوية: {res}\n\nاذا كسر الدعم رح ينزل 5-10$ واذا كسر المقاومة رح يطير")
        else:
            await update.message.reply_text("ثواني...")
        return

    if "سيولة" in text or "سحب" in text or "ستوب" in text:
        kl5=get_klines("5m")
        if kl5:
            h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]; c5=[float(x[4]) for x in kl5]
            liq=check_liquidity(h5,l5,c5)
            await update.message.reply_text(f"{liq}\nالسعر هلا {spot:.2f}$")
        return

    if "دورة" in text or "زمنية" in text or "جلسة" in text or "لندن" in text or "نيويورك" in text:
        now=datetime.utcnow(); hour=now.hour
        if 8 <= hour <= 11: msg="هلا جلسة لندن - اقوى وقت تداول الذهب حركة 10-20$"
        elif 13 <= hour <= 16: msg="هلا نيويورك - انفجار ثاني اقوى وقت"
        elif 6 <= hour < 8: msg="قبل لندن بشوي - السوق عم يجمع سيولة رح ينفجر بعد شوي"
        else: msg="هلا آسيا - سوق نايم لا تدخل انتظر لندن الساعة 8 UTC"
        await update.message.reply_text(f"⏰ {msg}\nالساعة هلا UTC {hour}:00\nالسعر {spot:.2f}$")
        return

    if "حلل" in text or "ذهب" in text or "توصية" in text or "شو اعمل" in text:
        txt=await qawi_logic()
        await update.message.reply_text(txt)
        return

    # رد عام ذكي
    await update.message.reply_text(f"فهمتك: {update.message.text}\n\nالسعر هلا {spot:.2f}$\n\nاكتبلي:\n/qawi - توصية كاملة\n'وين الدعم' - بعطيك الدعم والمقاومة\n'وين سحب السيولة' - بعطيك السيولة\n'شو الدورة الزمنية' - بعطيك الجلسة\n\nاو اسألني اي شي عن الذهب!")

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.add_handler(CommandHandler("saree3",qawi))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    bot.run_polling()
