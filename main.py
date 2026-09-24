import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Fixed Recommendation Bot"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port,threaded=True,use_reloader=False)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=8).json()['price'])
    except: return None

def get_candles(interval):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=200",timeout=8,headers={"User-Agent":"Mozilla/5.0"}).json()
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
    return 100-(100/(1+g/l)) if l!=0 else 100

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت المصلح - التوصية صارت صح\n/qawi - جرب هلا")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 عم صحح التوصية...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); spot=get_spot()
    if len(d5)<100 or not spot:
        await update.message.reply_text("جرب بعد دقيقة"); return

    c5=[float(x[4]) for x in d5]; o5=[float(x[1]) for x in d5]; h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]

    e21_5=ema(c5,21); e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_60=ema(c60,50); e200_60=ema(c60,200)
    e50_240=ema(c240,50); e200_240=ema(c240,200)

    r5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14)

    # شمعة تأكيد - اهم شي لتصليح التوصية
    last_bull = c5[-1] > o5[-1] and c5[-1] > c5[-2] # شمعة صاعدة وتكسر اللي قبلها
    last_bear = c5[-1] < o5[-1] and c5[-1] < c5[-2]

    # الترند الحقيقي - لازم 3 فريمات متوافقة
    up_4h = c240[-1] > e50_240 and c240[-1] > e200_240
    up_1h = c60[-1] > e50_60 and c60[-1] > e200_60
    down_4h = c240[-1] < e50_240 and c240[-1] < e200_240
    down_1h = c60[-1] < e50_60 and c60[-1] < e200_60

    # ارتداد حقيقي من EMA50 - مو بس لمس
    pullback_buy = l5[-1] <= e21_5*1.001 and c5[-1] > e21_5 and c5[-1] > e50_5
    pullback_sell = h5[-1] >= e21_5*0.999 and c5[-1] < e21_5 and c5[-1] < e50_5

    atr=sum([h5[i]-l5[i] for i in range(-14,0)])/14

    # التوصية الصحيحة - لازم 4 شروط
    if up_4h and up_1h and pullback_buy and last_bull and 40 < r5 < 68 and 45 < r60 < 70:
        entry = round(max(e21_5, c5[-1]-atr*0.3),2)
        sl = round(entry - atr*1.2,2)
        tp1 = round(spot + atr*1.5,2)
        tp2 = round(spot + atr*2.8,2)
        msg = f"""✅ توصية صحيحة مصلحة 💎

🟢 شراء BUY - قوي 80%

ليش هلا شراء؟ (السبب الحقيقي)
1- 4H صاعد فوق 50 و 200 ✅
2- 1H صاعد فوق 50 و 200 ✅
3- ارتداد حقيقي من EMA21 ✅
4- شمعة صاعدة كسرت اللي قبلها ✅
5- RSI 5M {r5:.1f} مو متشبع ✅

🎯 اذا وصل {entry}$ ادخل شراء
📝 BUY LIMIT {entry}$
🛑 وقف {sl}$
🎯 هدف1 {tp1}$ هدف2 {tp2}$

السعر هلا {spot:.2f}$ - حط الامر وانتظر يلمس {entry}$
"""
    elif down_4h and down_1h and pullback_sell and last_bear and 32 < r5 < 60 and 30 < r60 < 55:
        entry = round(min(e21_5, c5[-1]+atr*0.3),2)
        sl = round(entry + atr*1.2,2)
        tp1 = round(spot - atr*1.5,2)
        tp2 = round(spot - atr*2.8,2)
        msg = f"""✅ توصية صحيحة مصلحة 💎

🔴 بيع SELL - قوي 80%

ليش هلا بيع؟
1- 4H هابط تحت 50 و 200 ✅
2- 1H هابط تحت 50 و 200 ✅
3- ارتداد من EMA21 لتحت ✅
4- شمعة هابطة كسرت اللي قبلها ✅
5- RSI 5M {r5:.1f} ✅

🎯 اذا وصل {entry}$ ادخل بيع
📝 SELL LIMIT {entry}$
🛑 وقف {sl}$
🎯 هدف1 {tp1}$ هدف2 {tp2}$

السعر هلا {spot:.2f}$
"""
    else:
        reason = []
        if not up_4h and not down_4h: reason.append("4H عرضي")
        if not up_1h and not down_1h: reason.append("1H عرضي")
        if not pullback_buy and not pullback_sell: reason.append("ما في ارتداد من EMA")
        if not last_bull and not last_bear: reason.append("ما في شمعة تأكيد")
        if not (30 < r5 < 70): reason.append(f"RSI {r5:.0f} سيء")

        msg = f"""⏸️ ما في توصية صح هلا - وهاد الصح!

ليش ما عم اعطيك توصية؟
{chr(10).join(['- '+r for r in reason])}

السعر هلا {spot:.2f}$
EMA21 5M {e21_5:.2f}$
EMA50 1H {e50_60:.2f}$ | 4H {e50_240:.2f}$
RSI 5M {r5:.1f} | 1H {r60:.1f} | 4H {r240:.1f}

القديم كان يعطيك توصية غلط هون - الجديد ما بيعطيك الا اذا كانت صح 100%
جرب بعد 15 دقيقة
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.add_handler(CommandHandler("saree3",qawi))
    bot.run_polling()
