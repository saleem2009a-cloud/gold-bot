import os
from flask import Flask
import threading
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold SUPER SMART Bot - Explosive"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()['price'])
    except: return None

def get_candles(interval, limit=100):
    for base in ["https://data-api.binance.vision", "https://api.binance.com"]:
        try:
            url = f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}"
            r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"}).json()
            if isinstance(r, list) and len(r)>50: return r
        except: continue
    return []

def ema(prices, p):
    k=2/(p+1); e=sum(prices[:p])/p
    for x in prices[p:]: e=x*k+e*(1-k)
    return e

def rsi(prices, period=14):
    g=l=0
    for i in range(1, period+1):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l-=d
    if l==0: return 100
    return 100-(100/(1+g/l))

def get_time_cycle():
    now = datetime.utcnow()
    hour = now.hour
    # الدورة الزمنية - افضل اوقات الذهب
    if 8 <= hour <= 11: session="🔥 لندن - اقوى سيولة"; bonus=15
    elif 13 <= hour <= 16: session="💥 نيويورك - انفجار"; bonus=20
    elif hour >= 22 or hour <= 2: session="🌙 آسيا - هادئ"; bonus=-10
    else: session="⚠️ فترة متوسطة"; bonus=0
    
    day = now.weekday()
    if day == 4: day_info="الجمعة - حذر اغلاق اسبوعي"; day_bonus=-5
    elif day == 0: day_info="الاثنين - بداية ترند جديد"; day_bonus=10
    elif day in [1,2]: day_info="ثلاثاء/اربعاء - افضل ايام التداول"; day_bonus=15
    else: day_info="خميس - جيد"; day_bonus=5
    
    return session, day_info, bonus+day_bonus

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💣 البوت الخارق الذكي 100%\n\n/qawi - توصية خارقة كاملة\nيحسب: 5m + 1h + 4h + 1D + الدورة الزمنية\nبيقلك ايمتى تفوت وايمتى تطلع وستوب")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot(); await update.message.reply_text(f"💰 الذهب: {p:.2f}$" if p else "خطأ")

async def qawi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 البوت الذكي عم يحسب 4 فريمات + الدورة الزمنية...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); d1d=get_candles("1d"); spot=get_spot()
    if len(d5)<50 or len(d240)<50 or not spot:
        await update.message.reply_text("API مشغول ثواني وجرب"); return
    
    c5=[float(x[4]) for x in d5]; h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    c60=[float(x[4]) for x in d60]; h60=[float(x[2]) for x in d60]; l60=[float(x[3]) for x in d60]
    c240=[float(x[4]) for x in d240]; c1d=[float(x[4]) for x in d1d]
    
    # كل المؤشرات
    e9_5=ema(c5,9); e21_5=ema(c5,21); e50_5=ema(c5,50); e200_5=ema(c5,200)
    e50_60=ema(c60,50); e200_60=ema(c60,200)
    e50_240=ema(c240,50); e200_240=ema(c240,200)
    e50_1d=ema(c1d,50); e200_1d=ema(c1d,200)
    
    r5=rsi(c5,7); r14_5=rsi(c5,14); r60=rsi(c60,14); r240=rsi(c240,14); r1d=rsi(c1d,14)
    atr5=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    atr60=sum([h60[i]-l60[i] for i in range(-14,0)])/14
    
    session, day_info, time_bonus = get_time_cycle()
    recent_high=max(h5[-30:]); recent_low=min(l5[-30:])
    
    # حساب ذكي خارق 100 نقطة
    score=0; analysis=[]
    
    # 1- اليومي 30 نقطة - اهم شي
    if c1d[-1]>e50_1d and c1d[-1]>e200_1d and r1d>55:
        score+=30; analysis.append("✅ يومي صاعد قوي فوق 50 و 200 (+30)")
    elif c1d[-1]>e50_1d:
        score+=15; analysis.append("✅ يومي صاعد (+15)")
    else:
        score-=20; analysis.append("🔴 يومي هابط (-20)")
    
    # 2- 4 ساعات 25 نقطة
    if c240[-1]>e50_240 and c240[-1]>e200_240 and r240>55:
        score+=25; analysis.append("✅ 4H ترند صاعد مثالي (+25)")
    elif c240[-1]>e50_240:
        score+=12; analysis.append("✅ 4H صاعد (+12)")
    else:
        score-=15; analysis.append("🔴 4H هابط (-15)")
    
    # 3- ساعة 20 نقطة
    if c60[-1]>e50_60 and c60[-1]>e200_60 and r60>50:
        score+=20; analysis.append("✅ 1H صاعد قوي (+20)")
    elif c60[-1]>e50_60:
        score+=8; analysis.append("⚠️ 1H فوق 50 (+8)")
    else:
        score-=10; analysis.append("🔴 1H هابط (-10)")
    
    # 4- 5 دقايق 15 نقطة
    if c5[-1]>e9_5 and e9_5>e21_5 and e21_5>e50_5 and e50_5>e200_5:
        score+=15; analysis.append("✅ 5M ترتيب EMA خارق (+15)")
    elif c5[-1]>e9_5 and e9_5>e21_5:
        score+=8; analysis.append("✅ 5M تقاطع صاعد (+8)")
    else:
        score-=8; analysis.append("🔴 5M هابط (-8)")
    
    # 5- RSI توافقي
    if 50<r5<65 and 50<r60<68 and 50<r240<70:
        score+=10; analysis.append(f"✅ RSI توافقي ممتاز 5M {r5:.0f} 1H {r60:.0f} 4H {r240:.0f} (+10)")
    elif r5>75 or r5<25:
        score-=10; analysis.append(f"🔴 RSI متشبع {r5:.0f} (-10)")
    
    # 6- الدورة الزمنية
    score+=time_bonus
    analysis.append(f"⏰ {session} {day_info} ({'+' if time_bonus>=0 else ''}{time_bonus})")
    
    # تحديد الدخول والخروج الذكي
    if score>=75:
        sig="💣💣💣 شراء خارق 90%+ BUY EXPLOSIVE"
        power="💎💎💎 خارق جدا"
        entry_now=spot
        entry_limit=round(e9_5,2)
        sl=round(entry_limit - atr5*1.2,2)
        tp1=round(spot + atr5*1.5,2)
        tp2=round(spot + atr5*3.0,2)
        tp3=round(spot + atr60*2.0,2)
        entry_msg=f"🚀 ادخل هلا ماركت {entry_now:.2f}$ واذا نزل لـ {entry_limit:.2f}$ زود\nاذا وصل {entry_limit:.2f}$ ادخل بقوة"
        exit_msg=f"هدف1 {tp1}$ سكر 50%\nهدف2 {tp2}$ سكر 30%\nهدف3 {tp3}$ سكر 20% واترك الباقي"
        lot="فول لوت 100%"
    elif score>=55:
        sig="🟢 شراء قوي BUY STRONG"
        power="💎💎 قوي 75%"
        entry_now=spot
        entry_limit=round(e9_5,2)
        sl=round(entry_limit - atr5*1.0,2)
        tp1=round(spot + atr5*1.2,2)
        tp2=round(spot + atr5*2.2,2)
        tp3=0
        entry_msg=f"ادخل هلا {entry_now:.2f}$ او حط LIMIT {entry_limit:.2f}$\nاذا لمس {entry_limit:.2f}$ ادخل"
        exit_msg=f"هدف1 {tp1}$ سكر نص\nهدف2 {tp2}$ سكر الباقي"
        lot="لوت عادي 70%"
    elif score>=30:
        sig="⚠️ شراء ضعيف سكالبينغ"
        power="⚠️ متوسط 55%"
        entry_now=spot
        sl=round(spot - atr5*0.8,2)
        tp1=round(spot + atr5*0.8,2)
        tp2=0; tp3=0
        entry_msg=f"سكالبينغ سريع ادخل هلا {entry_now:.2f}$ واطلع بسرعة"
        exit_msg=f"هدف وحيد {tp1}$ اطلع بسرعة 5-10 دقايق"
        lot="نص لوت 50% فقط"
    elif score<=-50:
        sig="🔴 بيع خارق SELL EXPLOSIVE"
        power="💎💎💎 خارق"
        entry_now=spot; entry_limit=round(e9_5,2)
        sl=round(entry_limit + atr5*1.2,2)
        tp1=round(spot - atr5*1.5,2); tp2=round(spot - atr5*3.0,2); tp3=round(spot - atr60*2.0,2)
        entry_msg=f"بيع هلا {entry_now:.2f}$ او LIMIT {entry_limit:.2f}$"
        exit_msg=f"هدف1 {tp1}$ هدف2 {tp2}$ هدف3 {tp3}$"
        lot="فول لوت"
    else:
        sig="⏸️ لا تدخل - انتظار"
        power=f"🔴 ضعيف {score}/100"
        entry_now=spot; entry_limit=0; sl=0; tp1=0; tp2=0; tp3=0
        entry_msg="لا تدخل هلا - السوق عرضي\nانتظر /qawi بعد 20 دقيقة"
        exit_msg="-"
        lot="لا تدخل"
    
    msg=f"""{sig}
{power} - نقاط: {score}/100

💰 السعر الحالي: {spot:.2f}$

🎯 ايمتى تفوت؟
{entry_msg}

🛑 ستوب لوز:
{sl}$

💵 ايمتى تطلع؟
{exit_msg}

📦 حجم الصفقة: {lot}

⏰ الدورة الزمنية:
{session}
{day_info}

📊 التحليل الخارق الكامل:
{chr(10).join(analysis)}

📈 كل الفريمات:
• يومي: {c1d[-1]:.2f} | EMA50 {e50_1d:.2f} | EMA200 {e200_1d:.2f} | RSI {r1d:.1f}
• 4H: {c240[-1]:.2f} | EMA50 {e50_240:.2f} | EMA200 {e200_240:.2f} | RSI {r240:.1f}
• 1H: {c60[-1]:.2f} | EMA50 {e50_60:.2f} | EMA200 {e200_60:.2f} | RSI {r60:.1f}
• 5M: EMA9 {e9_5:.2f} | EMA21 {e21_5:.2f} | EMA50 {e50_5:.2f} | EMA200 {e200_5:.2f} | RSI {r5:.1f}/{r14_5:.1f}
• ATR 5M {atr5:.2f}$ | ATR 1H {atr60:.2f}$
• دعم {recent_low:.2f}$ | مقاومة {recent_high:.2f}$

🔔 تنبيه:
اذا وصل {entry_limit:.2f}$ ادخل فورا
وقفك {sl}$
"""
    await update.message.reply_text(msg)

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)
async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    for cmd, fn in [("start", start), ("gold", gold), ("qawi", qawi), ("tawsiya", tawsiya), ("saree3", saree3)]:
        bot.add_handler(CommandHandler(cmd, fn))
    bot.run_polling()
