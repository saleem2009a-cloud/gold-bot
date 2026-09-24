import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Strong TP"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()['price'])
    except: return None

def get_klines(interval):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            d=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=150",timeout=10).json()
            if isinstance(d,list) and len(d)>50: return d
        except: continue
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("شغال ✅\n/qawi - جني ارباح قوي")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ثواني عم احسب هدف قوي...")
    spot=get_price()
    kl5=get_klines("5m"); kl60=get_klines("1h"); kl240=get_klines("4h")
    if not spot or len(kl5)<50:
        await update.message.reply_text("جرب بعد دقيقة"); return

    c5=[float(x[4]) for x in kl5]
    h5=[float(x[2]) for x in kl5]
    l5=[float(x[3]) for x in kl5]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c5

    e21=ema(c5,21); e50=ema(c5,50); e50_1h=ema(c60,50); e50_4h=ema(c240,50)

    # ATR محسن - ناخد اكبر قيمة بين 5m و 1h
    atr5=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    atr_min = 1.5 # اقل هدف 1.5 دولار - ما عاد يعطيك 0.01
    if atr5 < atr_min: atr5 = atr_min

    # نقاط دخول مستقبلية
    buy_entry = round(e21,2)
    if buy_entry > spot: buy_entry = round(spot - 2.0,2) # على الاقل 2$ تحت

    # جني ارباح قوي - 3 مراحل
    tp1 = round(buy_entry + 3.0,2) # 3$
    tp2 = round(buy_entry + 6.0,2) # 6$
    tp3 = round(buy_entry + 10.0,2) # 10$ - قوي
    sl = round(buy_entry - 4.0,2) # ستوب 4$

    # اذا ترند قوي على 4 ساعات نكبر الهدف
    strong_trend = c240[-1] > e50_4h if len(c240)>50 else True
    if strong_trend:
        tp3 = round(buy_entry + 15.0,2)

    msg=f"""💰 السعر هلا: {spot:.2f}$

🎯 اذا وصل {buy_entry}$ ادخل شراء
BUY LIMIT {buy_entry}

🛑 وقف خسارة: {sl}$ (4$)

💎 جني ارباح قوي - مو 0.01:
🎯 هدف1: {tp1}$ (+3$) سكر 40% هون
🎯 هدف2: {tp2}$ (+6$) سكر 30% هون
🎯 هدف3: {tp3}$ (+{tp3-buy_entry:.0f}$) سكر 30% - هاد القوي

⏰ ايمتى يوصل؟
- هدف1: 10-30 دقيقة
- هدف2: 1-2 ساعة
- هدف3: اليوم اذا الترند قوي

📊 EMA21 {e21:.2f} | EMA50 {e50:.2f} | EMA50 1H {e50_1h:.2f}
ATR {atr5:.2f}$ | ترند 4H {'صاعد قوي ✅' if strong_trend else 'ضعيف'}

💡 حط الامر هلا و بس يوصل {buy_entry}$ بيدخل لحالو و بياخد {tp3-buy_entry:.0f}$ مو 0.1$
"""
    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",bot))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.add_handler(CommandHandler("saree3",qawi))
    bot.run_polling()
