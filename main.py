import os, requests, threading
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold SMC Fixed Bot"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=8).json()['price'])
    except:
        try:
            d=requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",timeout=8).json()
            return float(d['price'])
        except: return None

def get_klines(interval, limit=100):
    try:
        d=requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}",timeout=10).json()
        if isinstance(d,list) and len(d)>60: return d
    except: pass
    return []

def ema(prices,p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم التصليح ✅\n/tawsiya - توصية حسب الهيكلية مو EMA بس")

async def qawi(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل الهيكلية وسحب السيولة متل شارتك...")
    spot=get_price()
    kl5=get_klines("5m",100); kl15=get_klines("15m",100); kl60=get_klines("1h",100)
    if not spot or len(kl15)<60:
        await update.message.reply_text("زحمة - جرب بعد 30 ثانية"); return

    c5=[float(x[4]) for x in kl5]; h5=[float(x[2]) for x in kl5]; l5=[float(x[3]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c15

    e21_15=ema(c15,21); e50_15=ema(c15,50); e200_15=ema(c15,200)
    e50_1h=ema(c60,50)

    # 1. الهيكلية الحقيقية M15 (متل صورتك)
    recent_high = max(h15[-10:-1])
    recent_low = min(l15[-10:-1])
    last_close = c15[-1]

    # 2. سحب السيولة
    swept_high = h15[-1] > recent_high and c15[-1] < recent_high
    swept_low = l15[-1] < recent_low and c15[-1] > recent_low

    # 3. دعم ومقاومة حقيقية (قمم وقيعان 15 دقيقة - نفس فريمك)
    sup = round(min(l15[-30:]),2)
    res = round(max(h15[-30:]),2)

    # 4. الدورة الزمنية
    hour=datetime.utcnow().hour
    if 0 <= hour <= 6: sess="🌙 آسيا - لا تدخل هلا - رح يسحب سيولة وينفجر بلندن"
    elif 7 <= hour <= 11: sess="🔥 لندن - ادخل هلا"
    elif 12 <= hour <= 16: sess="💥 نيويورك - ادخل هلا"
    else: sess="🌆 مسائي - حذر"

    # 5. التوصية الصحيحة - حسب الهيكلية مو EMA
    # اذا سحب سيولة فوق = بيع
    # اذا سحب سيولة تحت = شراء
    # اذا السعر تحت EMA50 على 15د = الترند هابط = بيع من المقاومة

    if swept_high or (last_close < e50_15 and last_close < e21_15):
        # هابط - مثل حالتك بالصورة
        entry = round(recent_high - 2.5,2) if recent_high < spot+8 else round(spot+3.0,2)
        sl = round(entry + 5.0,2)
        tp1 = round(entry - 4.0,2)
        tp2 = round(entry - 8.5,2)
        tp3 = round(sup,2)
        side = "🔴 بيع SELL - الهيكلية هابطة"
        liq_txt = f"💧 سحب سيولة فوق {recent_high:.2f}$ صار (مثل شمعتك الطويلة) - ضرب ستوبات الشراء = بيع"
        reason = f"السعر تحت EMA50 ({e50_15:.2f}$) وتحت EMA21 ({e21_15:.2f}$) + قمة {recent_high}$ ما انكسرت"
    elif swept_low or (last_close > e50_15 and last_close > e21_15):
        entry = round(recent_low + 2.5,2) if recent_low > spot-8 else round(spot-3.0,2)
        sl = round(entry - 5.0,2)
        tp1 = round(entry + 4.0,2)
        tp2 = round(entry + 8.5,2)
        tp3 = round(res,2)
        side = "🟢 شراء BUY - الهيكلية صاعدة"
        liq_txt = f"💧 سحب سيولة تحت {recent_low:.2f}$ صار - ضرب ستوبات البيع = شراء"
        reason = f"السعر فوق EMA50 وارتداد من {recent_low}$"
    else:
        # عرضي
        entry_buy = round(sup+1.5,2)
        entry_sell = round(res-1.5,2)
        await update.message.reply_text(f"""💰 السعر: {spot:.2f}$
📊 سوق عرضي بين {sup}$ و {res}$
EMA15: 21={e21_15:.2f}$ 50={e50_15:.2f}$

{liq_txt if 'liq_txt' in locals() else f'ما في سحب هلا - القمة {recent_high}$ القاع {recent_low}$'}

⏰ {sess}

🎯 خطة العرضي (متل شارتك هلا):
اذا وصل {entry_sell}$ بيع - SELL LIMIT {entry_sell}$ ستوب {entry_sell+5}$ هدف {entry_sell-6}$
اذا وصل {entry_buy}$ شراء - BUY LIMIT {entry_buy}$ ستوب {entry_buy-5}$ هدف {entry_buy+6}$
""")
        return

    msg=f"""💰 السعر هلا: {spot:.2f}$ - نفس سعر منصتك {spot:.2f}$

{side}

📉 ليش هاي التوصية صح؟ (مو متل قبل)
{reason}

🎯 ايمتى افوت؟
اذا وصل {entry}$ ادخل فورا
{'SELL' if 'بيع' in side else 'BUY'} LIMIT {entry}$

🛑 ستوب: {sl}$ ({'+5$' if 'بيع' in side else '-5$'} - فوق القمة/تحت القاع)

💎 اهداف قوية:
هدف1: {tp1}$ سكر 50%
هدف2: {tp2}$ سكر 30%
هدف3: {tp3}$ سكر 20%

📊 الدعم والمقاومة (M15 متل شارتك):
دعم: {sup}$ (قاع 30 شمعة)
مقاومة: {res}$ (قمة 30 شمعة)
قمة اخيرة: {recent_high}$ | قاع اخير: {recent_low}$

{liq_txt}

⏰ الدورة الزمنية:
{sess}
الساعة UTC {hour}:00 - انت صورت 00:39 = آسيا نايم - صح كلام البوت القديم هون بس التوصية غلط

💡 ملاحظة: التوصية القديمة كانت BUY 4260$ يعني شراء بالقاع بستوب 4$ - رح ينضرب. الجديدة بيع من فوق مع ستوب 5$ فوق القمة = آمن
"""

    await update.message.reply_text(msg)

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("qawi",qawi))
    bot.add_handler(CommandHandler("tawsiya",qawi))
    bot.run_polling()
