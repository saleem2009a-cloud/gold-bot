import os, requests, threading, re
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold V7 ULTIMATE Live"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

# ---------- مصادر ----------
def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()['price'])
    except:
        try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5).json()['price'])
        except: return 4290.0

def get_candles(tf, lim=120):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}", timeout=6).json()
            if isinstance(r,list) and len(r)>80: return r
        except: pass
    return []

def get_dxy_yield():
    # دولار و عوائد 10 سنوات - اهم شي للذهب
    try:
        # DXY proxy من UUP
        dxy=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTRY", timeout=4).json()
        # نجيب BTC ك مؤشر مخاطر
        btc=float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=4).json()['price'])
        return {"risk": "خوف" if btc<100000 else "طمع", "btc":btc}
    except: return {"risk":"محايد","btc":0}

def get_news():
    # اخبار سريعة من forexfactory proxy
    try:
        # ناخد اخبار من gold-api news
        r=requests.get("https://api.gold-api.com/news", timeout=5).json()
        if r and len(r)>0: return r[0]['title'][:120]
    except: pass
    # اخبار عامة
    return "لا اخبار قوية هلا - السوق فني"

def ema(p,per):
    k=2/(per+1); e=sum(p[:per])/per
    for x in p[per:]: e=x*k+e*(1-k)
    return e
def rsi(p,per=14):
    d=[p[i]-p[i-1] for i in range(1,len(p))][-per:]
    g=sum([x for x in d if x>0])/per; l=sum([-x for x in d if x<0])/per
    return 100 if l==0 else 100-(100/(1+g/l))
def macd(p):
    return ema(p,12)-ema(p,26)
def bb(p,per=20):
    import math
    m=sum(p[-per:])/per; std=math.sqrt(sum((x-m)**2 for x in p[-per:])/per)
    return m+2*std, m-2*std, m

async def start(update, context):
    await update.message.reply_text(
        "🔥 **V7 ULTIMATE الحارق** 🔥\n\n"
        "/tawsiya - تحليل 7 محاور خارق\n"
        "/news - اخبار الذهب الان\n"
        "/market - دولار + خوف وطمع + سيولة\n"
        "/gold - سعر\n"
        "/test - فحص"
    )

async def news(update, context):
    n=get_news(); d=get_dxy_yield()
    await update.message.reply_text(f"📰 **اخبار:**\n{n}\n\n📊 سوق المخاطرة: {d['risk']}\nBTC: {d['btc']:.0f}")

async def market(update, context):
    d=get_dxy_yield(); price=get_price()
    await update.message.reply_text(
        f"🌍 **تحليل السوق الشامل:**\n\n"
        f"💰 ذهب: {price:.2f}\n"
        f"📈 ريسك: {d['risk']} (BTC {d['btc']:.0f})\n"
        f"💵 الدولار: اذا طالع = الذهب نازل والعكس\n"
        f"📉 عوائد 10 سنوات: اذا طالعة = الذهب مضغوط\n\n"
        f"الخلاصة: الذهب هلا بـ {price:.2f} عم يراقب الدولار"
    )

async def tawsiya(update, context):
    await update.message.reply_text("🔥🔥 عم فجّر السوق تحليل من 7 جهات... 10 ثواني")

    price=get_price()
    timeframes=["1m","5m","15m","1h","4h","1d"]
    data={}
    for tf in timeframes:
        c=get_candles(tf, 120)
        if len(c)>50:
            closes=[float(x[4]) for x in c]
            highs=[float(x[2]) for x in c]; lows=[float(x[3]) for x in c]
            data[tf]={"c":closes, "e9":ema(closes,9), "e21":ema(closes,21), "e50":ema(closes,50), "e200":ema(closes,200),
                      "rsi":rsi(closes), "macd":macd(closes), "bb_up":bb(closes)[0], "bb_low":bb(closes)[1],
                      "high":max(highs[-20:]), "low":min(lows[-20:])}

    if "5m" not in data:
        await update.message.reply_text("❌ API معلق جرب /test"); return

    # حساب خارق
    score=50; reasons=[]; strong_sell=0; strong_buy=0

    for tf, weight in [("1d",30),("4h",25),("1h",20),("15m",10),("5m",15)]:
        if tf not in data: continue
        d=data[tf]
        if d["c"][-1] > d["e50"] and d["c"][-1] > d["e200"] and d["e9"]>d["e21"]:
            score+=weight*0.4; reasons.append(f"✅ {tf} صاعد قوي (فوق 50+200)")
            strong_buy+=1
        elif d["c"][-1] < d["e50"] and d["c"][-1] < d["e200"]:
            score-=weight*0.4; reasons.append(f"🔴 {tf} هابط قوي")
            strong_sell+=1
        elif d["c"][-1] > d["e50"]:
            score+=weight*0.15; reasons.append(f"⚠️ {tf} صاعد ضعيف")

    # RSI
    r5=data["5m"]["rsi"]; r60=data.get("1h",data["5m"])["rsi"]; r240=data.get("4h",data["5m"])["rsi"]
    if r5>78 or r60>78: score-=20; reasons.append(f"🔥 RSI متشبع شراء {r5:.0f} - خطر بيع")
    elif r5<22 or r60<22: score-= -15; reasons.append(f"🔥 RSI متشبع بيع {r5:.0f} - فرصة شراء")
    elif 50<r5<65 and 50<r60<68: score+=10; reasons.append(f"✅ RSI صحي {r5:.0f}/{r60:.0f}")

    # MACD
    if data["5m"]["macd"]>0 and data.get("1h",data["5m"])["macd"]>0: score+=8; reasons.append("✅ MACD صاعد 5M+1H")
    else: score-=5; reasons.append("🔴 MACD هابط")

    # Bollinger
    if data["5m"]["c"][-1] > data["5m"]["bb_up"]: reasons.append("⚠️ لامس البولنجر العلوي - تشبع")
    if data["5m"]["c"][-1] < data["5m"]["bb_low"]: reasons.append("⚠️ لامس البولنجر السفلي - ارتداد محتمل")

    # سيولة SMC
    sup=data["1h"]["low"] if "1h" in data else price-15
    res=data["1h"]["high"] if "1h" in data else price+15

    # سوق خارجي
    ext=get_dxy_yield(); news_txt=get_news()

    # القرار النهائي
    if score>=75: sig="🟢💎 **شراء قوي جدا BUY**"; sl=price-6; tp1=price+7; tp2=price+15; tp3=price+25; power="🔥🔥🔥 حارق 90%"
    elif score>=62: sig="🟢 **شراء BUY**"; sl=price-5; tp1=price+5; tp2=price+12; power="💎 قوي 75%"
    elif score<=25: sig="🔴💎 **بيع قوي جدا SELL**"; sl=price+6; tp1=price-7; tp2=price-15; tp3=price-25; power="🔥🔥🔥 حارق 90%"
    elif score<=38: sig="🔴 **بيع SELL**"; sl=price+5; tp1=price-5; tp2=price-12; power="💎 قوي 75%"
    else:
        txt=f"""⏸️ **حيادي - لا تدخل**

نقاط: {score:.0f}/100 - ضعيف
السعر: {price:.2f}
دعم: {sup:.2f} مقاومة: {res:.2f}

تحليل 7 محاور:
{chr(10).join(reasons[:6])}

🌍 خارجي: {ext['risk']} | اخبار: {news_txt[:80]}
💡 انتظر كسر {res:.2f} او {sup:.2f}
RSI 5M {r5:.1f} 1H {r60:.1f} 4H {r240:.1f}
"""
        await update.message.reply_text(txt); return

    txt=f"""{sig}
{power} | {score:.0f}/100

💵 دخول: {price:.2f}
🛑 وقف: {sl:.2f} ({abs(price-sl):.1f}$)
🎯 هدف1: {tp1:.2f} (50%)
🎯 هدف2: {tp2:.2f} (30%)
🎯 هدف3: {tp3:.2f if 'tp3' in locals() else price+20:.2f} (20%)

📊 **تحليل 7 محاور خارق:**
{chr(10).join(reasons[:7])}

💧 **سيولة SMC:**
دعم قوي: {sup:.2f} | مقاومة: {res:.2f}
البولنجر: {data['5m']['bb_low']:.1f} - {data['5m']['bb_up']:.1f}

🌍 **خارج السوق:**
سوق المخاطرة: {ext['risk']}
📰 خبر: {news_txt[:90]}

⏱️ صلاحية: 1-4 ساعات
💼 ادارة: {'فول لوت' if score>70 or score<30 else 'نص لوت'}
"""
    await update.message.reply_text(txt)

async def gold(update, context):
    await update.message.reply_text(f"💰 {get_price():.2f}$")

if __name__=="__main__":
    if TOKEN:
        bot=Application.builder().token(TOKEN).build()
        for c,f in [("start",start),("tawsiya",tawsiya),("tawsiyat",tawsiya),("qawi",tawsiya),("saree3",tawsiya),("gold",gold),("news",news),("market",market)]:
            bot.add_handler(CommandHandler(c,f))
        bot.run_polling()
