import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V10.1 SMC Fixed"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    for url in [
        "https://api.gold-api.com/price/XAU",
        "https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",
        "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
    ]:
        try:
            r=requests.get(url,timeout=4).json()
            p=float(r['price'] if 'price' in r else r.get('price',0))
            if p>2000: return p
        except: pass
    return None

def get_candles(tf, lim=200):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=6,headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r,list) and len(r)>100: return r
        except: pass
    return []

def find_swings_near(candles, lookback=2):
    highs=[]; lows=[]
    for i in range(lookback, len(candles)-lookback):
        h=float(candles[i][2]); l=float(candles[i][3])
        # اقرب سوينغ
        if h>=max(float(candles[j][2]) for j in range(i-lookback,i+lookback+1)):
            highs.append(h)
        if l<=min(float(candles[j][3]) for j in range(i-lookback,i+lookback+1)):
            lows.append(l)
    # شيل المكرر وقرب
    highs=list(dict.fromkeys([round(x,2) for x in highs]))[-15:]
    lows=list(dict.fromkeys([round(x,2) for x in lows]))[-15:]
    return highs, lows

async def tawsiya(update, context):
    await update.message.reply_text("🔍 V10.1 عم ادور دعوم قريبة...")
    try:
        price=get_price()
        if not price:
            await update.message.reply_text("❌ الذهب معلق جرب /test")
            return

        c5=get_candles("5m",200)
        c15=get_candles("15m",200)
        c60=get_candles("1h",200)

        if len(c5)<100: await update.message.reply_text(f"❌ شموع 5m {len(c5)}"); return

        h5,l5=find_swings_near(c5,2)
        h15,l15=find_swings_near(c15,2)
        h60,l60=find_swings_near(c60,3)

        # ادمج وقرب للسعر
        all_res=sorted(set(h5[-8:]+h15[-8:]+h60[-5:]))
        all_sup=sorted(set(l5[-8:]+l15[-8:]+l60[-5:]))

        # اقرب دعوم/مقاومات حقيقية (خلال 20$ فقط)
        near_res=[r for r in all_res if r>price and r-price<=25]
        near_sup=[s for s in all_sup if s<price and price-s<=25]

        # لو مافي قريب خد اقرب واحد حتى لو بعيد شوي
        if not near_res: near_res=[min([r for r in all_res if r>price], default=price+12)]
        if not near_sup: near_sup=[max([s for s in all_sup if s<price], default=price-12)]

        # اوردر بلوك من 15m
        def get_ob(cands):
            for i in range(len(cands)-10, len(cands)-1):
                try:
                    o=float(cands[i][1]); c=float(cands[i][4]); h=float(cands[i][2]); l=float(cands[i][3]); nc=float(cands[i+1][4])
                    if c<o and nc>o and (nc-c)>2: return f"شراء {l:.1f}-{o:.1f} قوي"
                    if c>o and nc<o and (c-nc)>2: return f"بيع {o:.1f}-{h:.1f} قوي"
                except: pass
            return "ما في OB واضح"
        ob5=get_ob(c5); ob15=get_ob(c15); ob60=get_ob(c60)

        # سيولة
        liq_up=len([r for r in all_res if 0 < r-price <= 8])
        liq_down=len([s for s in all_sup if 0 < price-s <= 8])

        # ترند
        closes5=[float(x[4]) for x in c5]
        e50_15=sum([float(x[4]) for x in c15[-50:]])/50
        trend="صاعد" if closes5[-1]>e50_15 else "هابط"

        # قرار
        sup1=max(near_sup) if near_sup else price-10
        res1=min(near_res) if near_res else price+10
        dist_sup=price-sup1; dist_res=res1-price

        if dist_sup < dist_res and dist_sup < 10:
            sig="🟢 شراء من دعم قريب"; sl=sup1-2.5; tp=res1; reason=f"ارتداد من {sup1:.2f} - اوردر بلوك {ob15}"
        elif dist_res < dist_sup and dist_res < 10:
            sig="🔴 بيع من مقاومة قريبة"; sl=res1+2.5; tp=sup1; reason=f"رفض من {res1:.2f} - اوردر بلوك {ob15}"
        elif liq_down>liq_up:
            sig="🔴 بيع - ضرب سيولة تحت"; sl=price+6; tp=sup1; reason=f"تحتنا سيولة كتير {liq_down} مستويات - الحيتان رح تنزل تضربها"
        else:
            sig="🟢 شراء - ضرب سيولة فوق"; sl=price-6; tp=res1; reason=f"فوقنا سيولة {liq_up} مستويات"

        txt=f"""{sig}
💰 السعر الحقيقي: {price:.2f}

📍 اقرب دعوم (خلال 25$):
{chr(10).join([f" • S: {s:.2f} ({price-s:.1f}$ تحت)" for s in sorted(near_sup, reverse=True)[:4]])}

📍 اقرب مقاومات (خلال 25$):
{chr(10).join([f" • R: {r:.2f} ({r-price:.1f}$ فوق)" for r in sorted(near_res)[:4]])}

💧 سيولة قريبة (0-8$):
 فوق: {liq_up} مستويات | تحت: {liq_down} مستويات
 {'⚠️ الحيتان رح يطلعوا يضربوا فوق اول' if liq_up>liq_down else '⚠️ الحيتان رح ينزلوا يضربوا تحت اول' if liq_down>0 else ''}

🏦 اوردر بلوكات الحيتان:
 5M: {ob5}
 15M: {ob15}
 1H: {ob60}

📊 كل الدعوم 15M: {l15[-5:]}
📊 كل المقاومات 15M: {h15[-5:]}

🎯 دخول {price:.2f} | وقف {sl:.2f} | هدف {tp:.2f}
💡 {reason}
"""
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def start(update,context): await update.message.reply_text("V10.1 مصلح\n/tawsiya")

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",tawsiya))
        b.add_handler(CommandHandler("tawsiyat",tawsiya))
        b.run_polling()
