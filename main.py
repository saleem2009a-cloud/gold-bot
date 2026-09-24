import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)
@app.route('/')
def home(): return "Gold 3 in 1 - Final"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=6).json()['price'])
    except:
        try:
            d=requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",timeout=6).json()
            return float(d['price'])
        except: return None

def get_klines(interval, limit=100):
    try:
        d=requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=8).json()
        if isinstance(d,list) and len(d)>60: return d
    except: pass
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def analyze():
    spot=get_price()
    kl1=get_klines("1m",100); kl5=get_klines("5m",100); kl15=get_klines("15m",100); kl60=get_klines("1h",100); kl240=get_klines("4h",100)
    if not spot or len(kl1)<60: return None, spot

    c1=[float(x[4]) for x in kl1]; h1=[float(x[2]) for x in kl1]; l1=[float(x[3]) for x in kl1]; o1=[float(x[1]) for x in kl1]
    c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c5
    c240=[float(x[4]) for x in kl240] if kl240 else c5

    e9_1=ema(c1,9); e21_1=ema(c1,21)
    e21_5=ema(c5,21); e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_1h=ema(c60,50); e50_4h=ema(c240,50)

    recent_high=max(h15[-15:-1]); recent_low=min(l15[-15:-1])
    sup1=round(min(l15[-30:]),2); res1=round(max(h15[-30:]),2)

    # سكالبينج
    last_body=c1[-1]-o1[-1]
    if c1[-1] > e9_1 and e9_1 > e21_1 and last_body>0:
        scalp={"side":"🟢 BUY NOW","sl":round(spot-1.8,2),"tp1":round(spot+1.2,2),"tp2":round(spot+2.5,2),"reason":"شمعة 1د خضرا فوق EMA9"}
    elif c1[-1] < e9_1 and e9_1 < e21_1 and last_body<0:
        scalp={"side":"🔴 SELL NOW","sl":round(spot+1.8,2),"tp1":round(spot-1.2,2),"tp2":round(spot-2.5,2),"reason":"شمعة 1د حمرا تحت EMA9"}
    else:
        is_buy = c1[-1]>e21_1
        scalp={"side":"🟢 BUY قريب" if is_buy else "🔴 SELL قريب","sl":round(spot-1.8,2) if is_buy else round(spot+1.8,2),"tp1":round(spot+1.2,2) if is_buy else round(spot-1.2,2),"tp2":round(spot+2.5,2) if is_buy else round(spot-2.5,2),"reason":"فوق EMA21" if is_buy else "تحت EMA21"}

    # كبير
    if h15[-1] > recent_high and c15[-1] < recent_high:
        liq=f"💧 سحب سيولة فوق {recent_high:.2f}$ - ضرب ستوبات البيع = بيع قوي"
        b_side="🔴 بيع من المقاومة"; b_entry=round(res1-1.5,2)
    elif l15[-1] < recent_low and c15[-1] > recent_low:
        liq=f"💧 سحب سيولة تحت {recent_low:.2f}$ - ضرب ستوبات الشراء = شراء قوي"
        b_side="🟢 شراء من الدعم"; b_entry=round(sup1+1.5,2)
    else:
        liq=f"💧 ما في سحب هلا - القمة {recent_high:.2f}$ القاع {recent_low:.2f}$"
        b_side="🟢 شراء من الدعم" if c15[-1]>e50_1h else "🔴 بيع من المقاومة"
        b_entry=round(sup1+1.5,2) if "شراء" in b_side else round(res1-1.5,2)

    if "شراء" in b_side and b_entry>spot: b_entry=round(spot-2.5,2)
    if "بيع" in b_side and b_entry<spot: b_entry=round(spot+2.5,2)

    big={"side":b_side,"entry":b_entry,"sl":round(b_entry-5,2) if "شراء" in b_side else round(b_entry+5,2),"tp1":round(b_entry+3,2) if "شراء" in b_side else round(b_entry-3,2),"tp2":round(b_entry+6.5,2) if "شراء" in b_side else round(b_entry-6.5,2),"tp3":round(b_entry+12,2) if "شراء" in b_side else round(b_entry-12,2),"sup":sup1,"res":res1,"liq":liq,"rh":recent_high,"rl":recent_low,"e9":e9_1,"e21_1":e21_1,"e21_5":e21_5,"e50_5":e50_5,"e50_1h":e50_1h,"e50_4h":e50_4h}

    return {"spot":spot,"scalp":scalp,"big":big}, spot

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت 3 في 1 جاهز\n\n/tawsiya - بيعطيك التلاتة سوا\n\nوتقدر تحكي معي:\n- وين الدعم؟\n- وين السيولة؟\n- شو الدورة؟\n- حلل الذهب")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم اجيب التلاتة...")
    data, spot = analyze()
    if not data:
        await update.message.reply_text("زحمة - جرب بعد 20 ثانية"); return

    hour=datetime.utcnow().hour
    if 8 <= hour <= 11: sess="🔥 لندن هلا - اقوى وقت"; when="30-90 دقيقة"
    elif 13 <= hour <= 16: sess="💥 نيويورك هلا"; when="1-2 ساعة"
    elif 0 <= hour <= 6: sess="🌙 آسيا - سوق نايم"; when="بعد 4-7 ساعات بلندن"
    else: sess="🌆 مسائي"; when="1-3 ساعات"

    s=data["scalp"]; b=data["big"]

    msg=f"""💰 السعر: {data['spot']:.2f}$

━━━━━━━━━━━━━━━
⚡ 1- سكالبينج سريع 3 دقايق
━━━━━━━━━━━━━━━
{s['side']}
دخول MARKET {data['spot']:.2f}$
ستوب {s['sl']}$ (1.8$)
هدف1 {s['tp1']}$ (1.2$) سكر 70%
هدف2 {s['tp2']}$ (2.5$) سكر 30%
ليش؟ {s['reason']}
⏱️ 2-4 دقايق بس

━━━━━━━━━━━━━━━
📊 2- توصية كبيرة كاملة
━━━━━━━━━━━━━━━
{b['side']} LIMIT {b['entry']}$
ستوب {b['sl']}$ (5$)
هدف1 {b['tp1']}$ (+3$) 40%
هدف2 {b['tp2']}$ (+6.5$) 30%
هدف3 {b['tp3']}$ (+12$) 30%

📈 الدعم والمقاومة M15:
دعم: {b['sup']}$ | مقاومة: {b['res']}$
قمة اخيرة: {b['rh']:.2f}$ قاع اخير: {b['rl']:.2f}$

{b['liq']}

⏰ الدورة الزمنية:
{sess} | يوصل بعد {when}
UTC {hour}:00

📊 EMA:
1M: 9={b['e9']:.2f}$ 21={b['e21_1']:.2f}$
5M: 21={b['e21_5']:.2f}$ 50={b['e50_5']:.2f}$
1H: 50={b['e50_1h']:.2f}$ 4H: {b['e50_4h']:.2f}$

━━━━━━━━━━━━━━━
💬 3- تحاورني
اكتب: وين الدعم؟ / وين السيولة؟ / شو الدورة؟
"""

    await update.message.reply_text(msg)

async def chat(update:Update, context:ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.lower()
    data, spot = analyze()
    if not data:
        await update.message.reply_text("ثواني..."); return

    b=data["big"]; s=data["scalp"]
    hour=datetime.utcnow().hour

    if "دعم" in txt or "مقاومة" in txt:
        await update.message.reply_text(f"💰 السعر {spot:.2f}$\n\n📈 الدعم: {b['sup']}$ (قاع 30 شمعة M15)\n📉 المقاومة: {b['res']}$ (قمة 30 شمعة)\n\nقمة اخيرة {b['rh']:.2f}$ قاع اخير {b['rl']:.2f}$\n\nاذا كسر المقاومة رح يطير 8$ واذا كسر الدعم رح ينزل 8$")
        return
    if "سيولة" in txt or "سحب" in txt or "ستوب" in txt:
        await update.message.reply_text(f"{b['liq']}\n\nالسعر هلا {spot:.2f}$\nاذا شفت سحب سيولة فوق = بيع، تحت = شراء")
        return
    if "دورة" in txt or "زمنية" in txt or "جلسة" in txt or "لندن" in txt or "نيويورك" in txt:
        sess = "🔥 لندن اقوى وقت ادخل هلا" if 8<=hour<=11 else "💥 نيويورك انفجار" if 13<=hour<=16 else "🌙 آسيا نايم لا تدخل الكبير، بس سكالبينج" if 0<=hour<=6 else "🌆 مسائي هادئ"
        await update.message.reply_text(f"⏰ {sess}\nالساعة UTC {hour}:00\nالسعر {spot:.2f}$")
        return
    if "حلل" in txt or "ذهب" in txt or "شو اعمل" in txt:
        await update.message.reply_text(f"💰 {spot:.2f}$\n\nسكالبينج: {s['side']} دخول {spot:.2f}$ هدف {s['tp1']}$\n\nكبير: {b['side']} {b['entry']}$ ستوب {b['sl']}$\n\n{b['liq']}\nدعم {b['sup']}$ مقاومة {b['res']}$")
        return

    await update.message.reply_text(f"السعر هلا {spot:.2f}$\n\nاكتب /tawsiya بيعطيك التلاتة سوا\n\nاو اسألني:\n- وين الدعم؟\n- وين السيولة؟\n- شو الدورة؟")

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.add_handler(CommandHandler("qawi",tawsiya))
    bot.add_handler(CommandHandler("saree3",tawsiya))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    bot.run_polling()
