import os, requests, threading, math
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V8 7-Directions ULTIMATE Live 🔥"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except:
        try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT",timeout=5).json()['price'])
        except: return 4290.0

def get_candles(tf, limit=100):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={limit}",timeout=6,headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r,list) and len(r)>80: return r
        except: pass
    return []

def get_macro():
    out={}
    # 1- DXY من EURUSD
    try:
        eur=float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=EURUSDT",timeout=4).json()['price'])
        out['dxy']= 1.08/eur*103.5
        out['dxy_trend']="صاعد 🔴 ضد الذهب" if eur<1.08 else "هابط 🟢 مع الذهب"
    except: out['dxy']=103; out['dxy_trend']="مجهول"
    # 2- عوائد 10 سنوات من Yahoo
    try:
        y=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval=1d&range=1d",timeout=5,headers={"User-Agent":"Mozilla/5.0"}).json()
        out['tnx']=y['chart']['result'][0]['meta']['regularMarketPrice']
        out['tnx_trend']="مرتفع 🔴" if out['tnx']>4.2 else "منخفض 🟢"
    except: out['tnx']=4.0; out['tnx_trend']="مجهول"
    # 3- خوف وطمع
    try:
        f=requests.get("https://api.alternative.me/fng/?limit=1",timeout=4).json()
        out['fng']=int(f['data'][0]['value']); out['fng_txt']=f['data'][0]['value_classification']
    except: out['fng']=50; out['fng_txt']="Neutral"
    # 4- اخبار ذهب
    try:
        n=requests.get("https://api.gold-api.com/news",timeout=4).json()
        out['news']=n[0]['title'][:110] if n else "لا اخبار قوية"
    except: out['news']="لا اخبار قوية - سوق فني"
    return out

def ema(p,per):
    if len(p)<per: return p[-1]
    k=2/(per+1); e=sum(p[:per])/per
    for x in p[per:]: e=x*k+e*(1-k)
    return e
def rsi(p,per=14):
    if len(p)<per+1: return 50
    d=[p[i]-p[i-1] for i in range(1,len(p))][-per:]
    g=sum([x for x in d if x>0])/per; l=sum([-x for x in d if x<0])/per
    return 100 if l==0 else 100-(100/(1+g/l))
def atr(cands,per=14):
    trs=[]
    for i in range(1,len(cands)):
        h=float(cands[i][2]); l=float(cands[i][3]); pc=float(cands[i-1][4])
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs[-per:])/per if trs else 5

async def start(update,context): await update.message.reply_text("🔥 V8 الوحش 7 اتجاهات\n/tawsiya\n/market\n/news\n/gold")

async def tawsiya(update,context):
    await update.message.reply_text("💣 عم فجّر 7 اتجاهات... 5 ثواني")
    try:
        price=get_price()
        macro=get_macro()
        tf_data={}
        for tf in ["5m","15m","1h","4h","1d"]:
            c=get_candles(tf,120)
            if len(c)>80:
                closes=[float(x[4]) for x in c]
                tf_data[tf]={"c":closes,"e50":ema(closes,50),"e200":ema(closes,200),"rsi":rsi(closes),"atr":atr(c),"cands":c}

        if "5m" not in tf_data: await update.message.reply_text("❌ بينانس معلق"); return

        score=50; reasons=[]; details=[]

        # 1- فني
        for tf,w in [("1d",25),("4h",20),("1h",20),("15m",10),("5m",15)]:
            if tf not in tf_data: continue
            d=tf_data[tf]
            if d["c"][-1]>d["e50"] and d["c"][-1]>d["e200"]: score+=w*0.45; reasons.append(f"✅ {tf} فوق 50+200")
            elif d["c"][-1]>d["e50"]: score+=w*0.15; reasons.append(f"⚠️ {tf} فوق 50")
            else: score-=w*0.4; reasons.append(f"🔴 {tf} تحت 50")
            details.append(f"{tf} RSI {d['rsi']:.0f}")

        # 2- DXY
        if macro['dxy']>104: score-=12; reasons.append(f"🔴 دولار قوي {macro['dxy']:.1f} {macro['dxy_trend']}")
        else: score+=8; reasons.append(f"🟢 دولار ضعيف {macro['dxy']:.1f} {macro['dxy_trend']}")

        # 3- عوائد
        if macro['tnx']>4.3: score-=10; reasons.append(f"🔴 عوائد 10س {macro['tnx']:.2f}% {macro['tnx_trend']} - ضغط ذهب")
        else: score+=8; reasons.append(f"🟢 عوائد {macro['tnx']:.2f}% {macro['tnx_trend']} - دعم ذهب")

        # 4- خوف وطمع
        if macro['fng']<25: score+=10; reasons.append(f"🟢 خوف شديد {macro['fng']} {macro['fng_txt']} = فرصة شراء ذهب")
        elif macro['fng']>75: score-=7; reasons.append(f"⚠️ طمع شديد {macro['fng']} {macro['fng_txt']}")

        # 5- SMC سيولة
        high_1h=max([float(x[2]) for x in tf_data["1h"]["cands"][-20:]]) if "1h" in tf_data else price+10
        low_1h=min([float(x[3]) for x in tf_data["1h"]["cands"][-20:]]) if "1h" in tf_data else price-10
        # 6- ATR
        atr5=tf_data["5m"]["atr"]

        r5=tf_data["5m"]["rsi"]; r60=tf_data.get("1h",tf_data["5m"])["rsi"]; r240=tf_data.get("4h",tf_data["5m"])["rsi"]

        # قرار
        if score>=78:
            txt=f"""🟢💎 **شراء خارق متفجر {score:.0f}/100** 🔥🔥🔥
💵 دخول {price:.2f}
🛑 وقف {price-atr5*1.2:.2f}
🎯 هدف1 {price+atr5*1.0:.2f}
🎯 هدف2 {price+atr5*2.5:.2f}
🎯 هدف3 {price+atr5*4:.2f}

📊 **7 اتجاهات:**
{chr(10).join(reasons[:7])}

💧 SMC: دعم {low_1h:.2f} مقاومة {high_1h:.2f}
📈 RSI: 5M {r5:.0f} 1H {r60:.0f} 4H {r240:.0f} | ATR {atr5:.1f}
🌍 DXY {macro['dxy']:.1f} | عوائد {macro['tnx']:.2f}% | خوف {macro['fng']} {macro['fng_txt']}
📰 {macro['news']}
"""
        elif score>=60:
            txt=f"""🟢 **شراء {score:.0f}/100**
دخول {price:.2f} وقف {price-atr5*1.0:.2f} هدف {price+atr5*1.8:.2f}
{chr(10).join(reasons[:6])}
RSI {r5:.0f}/{r60:.0f}/{r240:.0f} | DXY {macro['dxy']:.1f} | {macro['news'][:70]}
"""
        elif score<=22:
            txt=f"""🔴💎 **بيع خارق متفجر {score:.0f}/100** 🔥🔥🔥
💵 دخول {price:.2f}
🛑 وقف {price+atr5*1.2:.2f}
🎯 هدف1 {price-atr5*1.0:.2f}
🎯 هدف2 {price-atr5*2.5:.2f}
🎯 هدف3 {price-atr5*4:.2f}

📊 **7 اتجاهات:**
{chr(10).join(reasons[:7])}

💧 SMC: دعم {low_1h:.2f} مقاومة {high_1h:.2f}
📈 RSI: 5M {r5:.0f} 1H {r60:.0f} 4H {r240:.0f} | ATR {atr5:.1f}
🌍 DXY {macro['dxy']:.1f} | عوائد {macro['tnx']:.2f}% | خوف {macro['fng']}
📰 {macro['news']}
"""
        elif score<=40:
            txt=f"""🔴 **بيع {score:.0f}/100**
دخول {price:.2f} وقف {price+atr5*1.0:.2f} هدف {price-atr5*1.8:.2f}
{chr(10).join(reasons[:6])}
RSI {r5:.0f}/{r60:.0f}/{r240:.0f} | DXY {macro['dxy']:.1f}
"""
        else:
            txt=f"""⏸️ **حيادي {score:.0f}/100 - سوق ملخبط لا تدخل**

السعر {price:.2f} | SMC {low_1h:.0f}-{high_1h:.0f}
{chr(10).join(reasons[:6])}
RSI {r5:.1f}/{r60:.1f}/{r240:.1f} ATR {atr5:.1f}
🌍 DXY {macro['dxy']:.1f} {macro['dxy_trend']}
💵 عوائد {macro['tnx']:.2f}% {macro['tnx_trend']}
😨 خوف وطمع {macro['fng']} {macro['fng_txt']}
📰 {macro['news']}

💡 انتظر كسر {high_1h:.0f} او {low_1h:.0f}
"""
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ V8: {e}")

async def market(update,context):
    m=get_macro(); p=get_price()
    await update.message.reply_text(f"🌍 **سوق 7 اتجاهات:**\nذهب {p:.2f}\nDXY {m['dxy']:.1f} {m['dxy_trend']}\nعوائد 10س {m['tnx']:.2f}% {m['tnx_trend']}\nخوف {m['fng']} {m['fng_txt']}\n📰 {m['news']}")

if __name__=="__main__":
    if TOKEN:
        bot=Application.builder().token(TOKEN).build()
        bot.add_handler(CommandHandler("start",start))
        bot.add_handler(CommandHandler("tawsiya",tawsiya))
        bot.add_handler(CommandHandler("tawsiyat",tawsiya))
        bot.add_handler(CommandHandler("market",market))
        bot.run_polling()
