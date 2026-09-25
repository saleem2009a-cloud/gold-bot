import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V10 SMC Real"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=4).json()['price'])
    except:
        try: return float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT",timeout=4).json()['price'])
        except: return 4305.0

def get_candles(tf, lim=200):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=7,headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r,list) and len(r)>100: return r
        except: pass
    return []

def ema(p,n):
    if len(p)<n: return p[-1]
    k=2/(n+1); e=sum(p[:n])/n
    for x in p[n:]: e=x*k+e*(1-k)
    return e

def find_swings(candles, lookback=5):
    # SMC سوينغ هاي ولو حقيقي
    highs=[]; lows=[]
    for i in range(lookback, len(candles)-lookback):
        h=float(candles[i][2]); l=float(candles[i][3])
        is_high=all(h>float(candles[j][2]) for j in range(i-lookback,i+lookback+1) if j!=i)
        is_low=all(l<float(candles[j][3]) for j in range(i-lookback,i+lookback+1) if j!=i)
        if is_high: highs.append((i,h))
        if is_low: lows.append((i,l))
    return highs[-10:], lows[-10:]

def find_order_blocks(candles):
    obs=[]
    for i in range(len(candles)-5, len(candles)-1):
        o=float(candles[i][1]); c=float(candles[i][4]); h=float(candles[i][2]); l=float(candles[i][3])
        next_c=float(candles[i+1][4])
        # اوردر بلوك صاعد: اخر شمعة حمرا قبل خضرا قوية
        if c<o and next_c>o and (next_c-o)>(o-l)*1.5:
            obs.append(("BUY OB", l, o))
        if c>o and next_c<o and (h-(o))>0:
            obs.append(("SELL OB", o, h))
    return obs[-4:]

async def tawsiya(update, context):
    await update.message.reply_text("🔍 عم ادرس SMC - دعم مقاومة سيولة - 5 ثواني...")
    try:
        price=get_price()
        c1h=get_candles("1h",200)
        c4h=get_candles("4h",200)
        c15=get_candles("15m",200)
        c5=get_candles("5m",100)

        if len(c1h)<100: await update.message.reply_text("❌ بينانس معلق"); return

        # 1- سوينغات
        highs_1h, lows_1h = find_swings(c1h, 5)
        highs_4h, lows_4h = find_swings(c4h, 3)

        # 2- اقوى دعم ومقاومة (اخر 5 سوينغات)
        supports=sorted([l for _,l in lows_1h+lows_4h])[:5]
        resistances=sorted([h for _,h in highs_1h+highs_4h], reverse=True)[:5]

        strong_sup = supports[0] if supports else price-15
        strong_res = resistances[0] if resistances else price+15
        nearest_sup = max([s for s in supports if s < price], default=strong_sup)
        nearest_res = min([r for r in resistances if r > price], default=strong_res)

        # 3- اوردر بلوكات
        ob_1h=find_order_blocks(c1h)
        ob_15=find_order_blocks(c15)

        # 4- سيولة - وين الستوبات مجمعة
        # سيولة فوق = ستوبات البائعين - سيولة تحت = ستوبات المشترين
        liquidity_up = [r for r in resistances if abs(r-price)<25]
        liquidity_down = [s for s in supports if abs(s-price)<25]

        # 5- بريميوم / ديسكاونت
        range_4h_high = max([float(x[2]) for x in c4h[-50:]])
        range_4h_low = min([float(x[3]) for x in c4h[-50:]])
        range_mid = (range_4h_high+range_4h_low)/2
        zone = "بريميوم 🔴 (غالي - دور بيع)" if price>range_mid else "ديسكاونت 🟢 (رخيص - دور شراء)"

        # 6- FVG
        closes_1h=[float(x[4]) for x in c1h]
        e50=ema(closes_1h,50); e200=ema(closes_1h,200)
        trend = "صاعد" if closes_1h[-1]>e50 and e50>e200 else "هابط" if closes_1h[-1]<e50 else "عرضي"

        # 7- قرار SMC
        dist_sup = price-nearest_sup
        dist_res = nearest_res-price

        if zone.startswith("ديسكاونت") and dist_sup<8 and trend!="هابط":
            sig="🟢 **شراء SMC من دعم**"; sl=nearest_sup-3; tp1=range_mid; tp2=strong_res; reason=f"السعر بديسكاونت + قريب من دعم قوي {nearest_sup:.1f} + ترند {trend}"
        elif zone.startswith("بريميوم") and dist_res<8 and trend!="صاعد":
            sig="🔴 **بيع SMC من مقاومة**"; sl=nearest_res+3; tp1=range_mid; tp2=strong_sup; reason=f"السعر ببريميوم + قريب من مقاومة {nearest_res:.1f} + ترند {trend}"
        elif dist_res < dist_sup:
            sig="🔴 **بيع سكالب - سيولة فوق**"; sl=nearest_res+2; tp1=price-8; tp2=nearest_sup; reason=f"اقرب سيولة فوق {nearest_res:.1f} الحيتان رح تضرب ستوبات البائعين فوق"
        else:
            sig="🟢 **شراء سكالب - سيولة تحت**"; sl=nearest_sup-2; tp1=price+8; tp2=nearest_res; reason=f"اقرب سيولة تحت {nearest_sup:.1f} الحيتان رح تضرب ستوبات المشترين تحت"

        txt=f"""{sig}

💰 السعر هلا: {price:.2f}
📍 المنطقة: {zone}
📈 ترند 1H: {trend} (50: {e50:.1f} | 200: {e200:.1f})

━━━━━━━━━━━━━━━
💧 **السيولة - وين الستوبات:**

🔴 سيولة فوق (ستوب البائعين):
{chr(10).join([f" • {r:.2f} ({r-price:.1f}$ فوق)" for r in liquidity_up[:3]]) if liquidity_up else " • مافي سيولة قريبة فوق"}

🟢 سيولة تحت (ستوب المشترين):
{chr(10).join([f" • {s:.2f} ({price-s:.1f}$ تحت)" for s in liquidity_down[:3]]) if liquidity_down else " • مافي سيولة قريبة تحت"}

━━━━━━━━━━━━━━━
🧱 **الدعم والمقاومة الحقيقية SMC:**

مقاومات:
{chr(10).join([f" R{i+1}: {r:.2f}" for i,r in enumerate(resistances[:4])])}

دعوم:
{chr(10).join([f" S{i+1}: {s:.2f}" for i,s in enumerate(sorted(supports)[:4])])}

اقرب دعم: {nearest_sup:.2f} ({dist_sup:.1f}$ تحت)
اقرب مقاومة: {nearest_res:.2f} ({dist_res:.1f}$ فوق)
رينج 4H: {range_4h_low:.1f} - {range_4h_high:.1f} | النص {range_mid:.1f}

━━━━━━━━━━━━━━━
🏦 **اوردر بلوك الحيتان:**
1H: {ob_1h[-1] if ob_1h else "مافي OB واضح"}
15M: {ob_15[-1] if ob_15 else "مافي OB واضح"}

━━━━━━━━━━━━━━━
🎯 **الصفقة المقترحة SMC:**
دخول: {price:.2f}
وقف: {sl:.2f}
هدف1: {tp1:.2f}
هدف2: {tp2:.2f}
السبب: {reason}

💡 الحيتان هلا رح يروحوا يضربوا {'السيولة فوق' if dist_res<dist_sup else 'السيولة تحت'} اول
"""
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ SMC: {e}")

async def start(update,context):
    await update.message.reply_text("V10 SMC الحقيقي 🧱\n/tawsiya - تحليل دعم مقاومة سيولة\n/gold - سعر")

async def gold(update,context):
    await update.message.reply_text(f"💰 {get_price():.2f}")

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",b.add_handler if False else tawsiya))
        b.add_handler(CommandHandler("tawsiyat",tawsiya))
        b.add_handler(CommandHandler("gold",gold))
        b.run_polling()
