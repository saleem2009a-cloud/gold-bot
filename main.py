import os, requests, threading
from flask import Flask
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Future Entry Bot"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port,threaded=True,use_reloader=False)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=8).json()['price'])
    except: return None

def get_candles(interval, limit=150):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=8,headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r,list) and len(r)>100: return r
        except: continue
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices,period=14):
    g=l=0
    for i in range(1,period+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    return 100-(100/(1+g/l)) if l!=0 else 100)

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 بوت التوصية المستقبلية\n/qawi - بيعطيك دخول حتى لو ما في توصية هلا")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 عم احسب الدورة الزمنية ونقطة الدخول الجاي...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); d1d=get_candles("1d"); spot=get_spot()
    if len(d5)<100 or not spot:
        await update.message.reply_text("API مشغول جرب بعد دقيقة"); return

    c5=[float(x[4]) for x in d5]; h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]; c1d=[float(x[4]) for x in d1d]

    e9_5=ema(c5,9); e21_5=ema(c5,21); e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_60=ema(c60,50); e200_60=ema(c60,200); e50_240=ema(c240,50); e200_240=ema(c240,200); e50_1d=ema(c1d,50)
    r5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14); r1d=rsi(c1d,14)
    atr5=sum([h5[i]-l5[i] for i in range(-14,0)])/14

    now=datetime.utcnow()
    hour=now.hour

    # الدورة الزمنية لقدام
    if 6 <= hour < 8: next_session="لندن بتفتح بعد"; next_in="30-90 دقيقة"; time_strength="قوي - جهز حالك"; bonus=20
    elif 8 <= hour <= 11: next_session="لندن شغالة هلا"; next_in="هلا - افضل وقت"; time_strength="خارق"; bonus=20
    elif 12 <= hour < 13: next_session="هدوء قبل نيويورك"; next_in="1-2 ساعة"; time_strength="متوسط"; bonus=0
    elif 13 <= hour <= 16: next_session="نيويورك شغالة هلا"; next_in="هلا - انفجار"; time_strength="خارق"; bonus=20
    elif 17 <= hour <= 21: next_session="نيويورك بتسكر - ترند مسائي"; next_in="30 دقيقة"; time_strength="جيد"; bonus=5
    else: next_session="آسيا - سوق هادئ رح يتحرك بلندن"; next_in="4-7 ساعات للندن"; time_strength="ضعيف هلا بس قوي بعدين"; bonus=-10

    # حساب الترند العام
    up_day = c1d[-1] > e50_1d
    up_4h = c240[-1] > e50_240
    up_1h = c60[-1] > e50_60

    # نقاط الدخول المستقبلية - دايما موجودة
    # دعم ومقاومة حقيقية
    support1 = round(min(l5[-20:]),2)
    support2 = round(e50_5,2)
    support3 = round(e50_60,2)
    resist1 = round(max(h5[-20:]),2)
    resist2 = round(e21_5 + atr5,2)

    # اختيار النقطة الاقرب والمنطقية
    if up_day and up_4h: # ترند صاعد عام
        # نعطي 2 دخول شراء مستقبلي
        buy1 = round(e21_5,2)
        buy2 = round(e50_5,2)
        if buy1 > spot: buy1 = round(spot - atr5*0.5,2)
        if buy2 > spot: buy2 = round(spot - atr5*1.2,2)

        sl1 = round(buy1 - atr5*1.0,2)
        sl2 = round(buy2 - atr5*1.0,2)
        tp1_1 = round(buy1 + atr5*1.5,2)
        tp1_2 = round(buy1 + atr5*3,2)
        tp2_1 = round(buy2 + atr5*1.5,2)

        msg=f"""💎 توصية مستقبلية - ترند صاعد عام 💎

السعر هلا: {spot:.2f}$
الترند: يومي {'صاعد' if up_day else 'هابط'} | 4H {'صاعد' if up_4h else 'هابط'} | 1H {'صاعد' if up_1h else 'هابط'}

⏰ الدورة الزمنية:
{next_session}
ايمتا: {next_in}
القوة: {time_strength}

🎯 نقطة الدخول القادمة رقم 1 (القريبة):
اذا وصل {buy1}$ ادخل شراء فورا
📝 BUY LIMIT {buy1}$
🛑 وقف {sl1}$
🎯 هدف1 {tp1_1}$ هدف2 {tp1_2}$
⏱️ متوقع يوصلها: {next_in}

🎯 نقطة الدخول القادمة رقم 2 (الاقوى):
اذا وصل {buy2}$ ادخل شراء قوي جدا
📝 BUY LIMIT {buy2}$
🛑 وقف {sl2}$
🎯 هدف1 {tp2_1}$
⏱️ هاي نقطة EMA50 - اذا وصلها ارتداد قوي 90%

📊 ليش هدول النقاط؟
- {buy1}$ = EMA21 على 5 دقايق (اعادة اختبار)
- {buy2}$ = EMA50 على 5 دقايق / EMA50 على ساعة = دعم قوي
- RSI 5M {r5:.1f} | 1H {r60:.1f} | 4H {r240:.1f} | يومي {r1d:.1f}
- دعم اخير {support1}$ | مقاومة {resist1}$

💡 حط الامرين هلا وانتظر - اول واحد بيلمس بيدخل لحالو!
"""

    elif not up_day and not up_4h: # ترند هابط
        sell1 = round(e21_5,2)
        sell2 = round(e50_5,2)
        if sell1 < spot: sell1 = round(spot + atr5*0.5,2)
        if sell2 < spot: sell2 = round(spot + atr5*1.2,2)
        sl1 = round(sell1 + atr5*1.0,2)
        tp1 = round(sell1 - atr5*1.5,2)
        msg=f"""💎 توصية مستقبلية - ترند هابط عام 💎
السعر هلا: {spot:.2f}$

⏰ {next_session} - {next_in}

🎯 اذا وصل {sell1}$ ادخل بيع
SELL LIMIT {sell1}$ وقف {sl1}$ هدف {tp1}$

🎯 اذا وصل {sell2}$ ادخل بيع قوي
SELL LIMIT {sell2}$

RSI {r5:.1f} | {r60:.1f} | {r240:.1f}
"""
    else: # عرضي
        buy_level = round(support1,2)
        sell_level = round(resist1,2)
        msg=f"""💎 سوق عرضي - توصية حدودية 💎

السعر هلا: {spot:.2f}$ - سوق عرضي بين {support1}$ و {resist1}$

⏰ {next_session} - {next_in}

🎯 اذا نزل لـ {buy_level}$ ادخل شراء
BUY LIMIT {buy_level}$ وقف {round(buy_level-atr5,2)}$ هدف {round(buy_level+atr5*1.2,2)}$

🎯 اذا طلع لـ {sell_level}$ ادخل بيع
SELL LIMIT {sell_level}$ وقف {round(sell_level+atr5,2)}$ هدف {round(sell_level-atr5*1.2,2)}$

💡 هاي استراتيجية العرضي - بيع فوق وشراء تحت
⏰ رح ينفجر بـ {next_session}
RSI 5M {r5:.1f} - عرضي
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.add_handler(CommandHandler("saree3",qawi))
    bot.run_polling()
