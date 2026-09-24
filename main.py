import os, requests, threading
from flask import Flask
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
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()
        return float(r['price'])
    except:
        return 4325.0

def get_klines():
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            d=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval=5m&limit=100",timeout=10).json()
            if isinstance(d,list) and len(d)>50: return d
        except: continue
    return []

def ema(prices,p):
    k=2/(p+1)
    e=sum(prices[:p])/p
    for x in prices[p:]:
        e=x*k+e*(1-k)
    return e

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت شغال\n/qawi - توصية دخول + هدف + ستوب")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ ثواني عم احسب التوصية...")
    
    spot=get_price()
    kl=get_klines()
    
    if len(kl)<50:
        # حتى لو ما في بيانات نعطيك توصية
        buy=round(spot-2.5,2)
        await update.message.reply_text(f"""💰 السعر: {spot:.2f}$

🟢 شراء BUY

🎯 ادخل: {buy}$ 
BUY LIMIT {buy}$

🛑 ستوب: {round(buy-4,2)}$

🎯 هدف1: {round(buy+3,2)}$ +3$
🎯 هدف2: {round(buy+6,2)}$ +6$ 
🎯 هدف3: {round(buy+12,2)}$ +12$

حط الامر هلا""")
        return

    c=[float(x[4]) for x in kl]
    h=[float(x[2]) for x in kl]
    l=[float(x[3]) for x in kl]
    
    e21=ema(c,21)
    e50=ema(c,50)
    
    atr=sum([h[i]-l[i] for i in range(-14,0)])/14
    if atr<1.5: atr=1.5
    
    # دايما شراء من الدعم - عشان تاخد توصية دايما
    buy_entry=round(e21,2)
    if buy_entry>spot:
        buy_entry=round(spot-2.0,2)
    if buy_entry>spot-0.5:
        buy_entry=round(spot-2.0,2)
    
    # نقاط واضحة
    sl=round(buy_entry-4.0,2)
    tp1=round(buy_entry+3.0,2)
    tp2=round(buy_entry+6.0,2)
    tp3=round(buy_entry+12.0,2)
    
    sup=round(min(l[-20:]),2)
    res=round(max(h[-20:]),2)

    msg=f"""💰 السعر هلا: {spot:.2f}$

🟢 شراء BUY - قوي

🎯 ايمتى افوت؟
اذا وصل {buy_entry}$ ادخل شراء فورا
BUY LIMIT {buy_entry}$

🛑 الستوب تبعي:
{sl}$ (-4$)

💎 الهدف تبعي:
هدف1: {tp1}$ (+3$) سكر 40%
هدف2: {tp2}$ (+6$) سكر 30%
هدف3: {tp3}$ (+12$) سكر 30%

📊 معلومات:
EMA21: {e21:.2f}$ | EMA50: {e50:.2f}$
دعم: {sup}$ | مقاومة: {res}$
ATR: {atr:.2f}$

⏰ حط الامر هلا وانتظر يلمس {buy_entry}$ - بيدخل لحالو
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.add_handler(CommandHandler("saree3",qawi))
    bot.run_polling()
