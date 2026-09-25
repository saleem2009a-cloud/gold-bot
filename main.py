import os, requests, threading, asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold V5 Tawsiyat"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU", timeout=8).json()['price'])
    except: return None

def candles(tf, lim=100):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r = requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}", timeout=8).json()
            if isinstance(r,list) and len(r)>60: return r
        except: continue
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices, per=14):
    g=l=0
    for i in range(1,per+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    if l==0: return 100
    return 100-(100/(1+g/l))

def atr_calc(data, per=14):
    return sum([float(x[2])-float(x[3]) for x in data[-per:]])/per

def analyze():
    d5=candles("5m"); d60=candles("1h"); d240=candles("4h"); p=spot()
    if len(d5)<60 or not p: return None
    c5=[float(x[4]) for x in d5]; c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]
    e9=ema(c5,9); e21=ema(c5,21); e50_5=ema(c5,50); e50_60=ema(c60,50); e200_60=ema(c60,200); e50_240=ema(c240,50)
    r5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14)
    atr5=atr_calc(d5); atr60=atr_calc(d60)

    score=0
    if c240[-1]>e50_240: score+=30
    else: score-=15
    if c60[-1]>e50_60 and c60[-1]>e200_60: score+=30
    elif c60[-1]>e50_60: score+=10
    else: score-=15
    if c5[-1]>e9 and e9>e21: score+=25
    else: score-=10
    if 40<r5<68: score+=15

    is_range = abs(e9-e21) < atr5*0.25
    return {
        "price":p, "score":score, "r5":r5, "r60":r60, "r240":r240,
        "e9":e9, "e21":e21, "e50_5":e50_5, "e50_60":e50_60, "e200_60":e200_60, "e50_240":e50_240,
        "atr5":atr5, "atr60":atr60, "is_range":is_range,
        "c5":c5[-1], "c60":c60[-1], "c240":c240[-1]
    }

async def start(update, context):
    await update.message.reply_text(
        "🔥 بوت التوصيات V5\n\n"
        "💎 /tawsiya - توصية مفصلة + قوة %\n"
        "📋 /tawsiyat - 3 توصيات (سريع + متوسط + قوي)\n"
        "⚡️ /saree3 - سكالبينغ 5 دقايق\n"
        "💰 /gold - سعر الذهب\n"
        "🔔 /auto - تشغيل التنبيهات كل ساعة"
    )

async def gold(update, context):
    p=spot()
    await update.message.reply_text(f"💰 الذهب: {p:.2f}$" if p else "جرب بعد ثانية")

async def tawsiya(update, context):
    await update.message.reply_text("🔍 عم جهزلك توصية قوية...")
    a=analyze()
    if not a: await update.message.reply_text("API مشغول جرب بعد 30ث"); return
    if a["is_range"]:
        await update.message.reply_text(f"⏸️ **توصية: انتظار**\n\nالسوق عرضي هلا\nالسعر: {a['price']:.2f}$\nEMA9 {a['e9']:.2f} ~ EMA21 {a['e21']:.2f}\n\n💡 لا تدخل - انتظر /saree3")
        return

    if a["score"]>=70: power="💎💎💎 قوي جدا 90%"; lot="فول لوت"; time="1-3 ساعات"
    elif a["score"]>=55: power="💎💎 قوي 75%"; lot="لوت عادي"; time="30-90 دقيقة"
    elif a["score"]>=35: power="⚠️ متوسط 55%"; lot="نص لوت"; time="15-30 دقيقة"
    else: power=f"🔴 ضعيف {a['score']}%"; lot="لا تدخل"; time="انتظر"

    if a["score"]>30:
        sig="🟢 **توصية: شراء BUY**"; sl=a["price"]-a["atr5"]*1.2; tp1=a["price"]+a["atr5"]*1.2; tp2=a["price"]+a["atr5"]*2.5; tp3=a["price"]+a["atr60"]
    elif a["score"]<-20:
        sig="🔴 **توصية: بيع SELL**"; sl=a["price"]+a["atr5"]*1.2; tp1=a["price"]-a["atr5"]*1.2; tp2=a["price"]-a["atr5"]*2.5; tp3=a["price"]-a["atr60"]
    else:
        sig="⏸️ **توصية: حيادي**"; sl=tp1=tp2=tp3=a["price"]

    msg=f"""{sig}
{power} | النقاط {a['score']}/100

💵 دخول: {a['price']:.2f}$
🛑 وقف خسارة: {sl:.2f}$ ({abs(a['price']-sl):.1f}$ خسارة)
🎯 هدف1: {tp1:.2f}$ (سكر 50%)
🎯 هدف2: {tp2:.2f}$ (سكر 30%)
🎯 هدف3: {tp3:.2f}$ (سكر 20% - سوينغ)

📊 التحليل:
• 4H: {'صاعد' if a['c240']>a['e50_240'] else 'هابط'} | RSI {a['r240']:.0f}
• 1H: {'صاعد' if a['c60']>a['e50_60'] else 'هابط'} فوق 200: {'نعم' if a['c60']>a['e200_60'] else 'لا'} | RSI {a['r60']:.0f}
• 5M: EMA9 {a['e9']:.2f} > EMA21 {a['e21']:.2f} {'✅' if a['e9']>a['e21'] else '❌'} | RSI {a['r5']:.0f}

💼 إدارة رأس مال: {lot}
⏱️ صلاحية: {time}
⚠️ ATR: {a['atr5']:.2f}$ - تذبذب {'عالي' if a['atr5']>3 else 'طبيعي'}
"""
    await update.message.reply_text(msg)

async def tawsiyat(update, context):
    a=analyze()
    if not a: return
    p=a['price']; atr5=a['atr5']
    msg=f"""📋 **3 توصيات جاهزة - {p:.2f}$**

**1- ⚡️ سكالبينغ (5-10 دق):**
{'🟢 BUY' if a['e9']>a['e21'] else '🔴 SELL'} دخول {p:.2f}
SL {p-atr5*0.7:.2f} / TP {p+atr5*0.8:.2f}
قوة: {'65%' if abs(a['e9']-a['e21'])>atr5*0.3 else '45% عرضي'}

**2- 📈 انتراداي (30-60 دق):**
{'🟢 BUY' if a['c60']>a['e50_60'] else '🔴 SELL'} دخول {p:.2f}
SL {p-atr5*1.2:.2f} / TP {p+atr5*2.0:.2f}
قوة: {a['score']}%

**3- 💎 سوينغ قوي (2-6 ساعات):**
"""
    if a['score']>=55:
        msg+=f"{'🟢 BUY قوي' if a['score']>0 else '🔴 SELL قوي'} {p:.2f}\nSL {p-atr5*1.5:.2f} / TP {p+atr5*3:.2f} + TP2 {p+atr5*5:.2f}\nقوة {a['score']}%"
    else:
        msg+=f"⏸️ لا يوجد - السوق مو جاهز (نقاط {a['score']})\nانتظر /tawsiya"

    msg+=f"\n\n💡 انصحك بـ رقم 2 هلا"
    await update.message.reply_text(msg)

async def saree3(update, context):
    await tawsiya(update, context)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    for cmd, fn in [("start",start),("gold",gold),("tawsiya",tawsiya),("tawsiyat",tawsiyat),("saree3",tawsiya),("qawi",tawsiya)]:
        bot.add_handler(CommandHandler(cmd, fn))
    bot.run_polling()
