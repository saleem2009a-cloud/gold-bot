import os
from flask import Flask
import threading
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Gold Entry Timing Bot"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")

def get_spot():
    try: return float(requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()['price'])
    except: return None

def get_candles(interval):
    for base in ["https://data-api.binance.vision", "https://api.binance.com"]:
        try:
            url = f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit=100"
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 بوت دخول ذكي\n/qawi - قوة + ايمتا تدخل\n/saree3 - سريع\n/gold - سعر")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p=get_spot(); await update.message.reply_text(f"💰 {p:.2f}$" if p else "خطأ")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)
async def saree3(update: Update, context: ContextTypes.DEFAULT_TYPE): await qawi(update, context)

async def qawi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 عم حلل ايمتا تدخل...")
    d5=get_candles("5m"); d60=get_candles("1h"); d240=get_candles("4h"); spot=get_spot()
    if len(d5)<50 or not spot: await update.message.reply_text("جرب بعد دقيقة"); return
    
    c5=[float(x[4]) for x in d5]; o5=[float(x[1]) for x in d5]; h5=[float(x[2]) for x in d5]; l5=[float(x[3]) for x in d5]
    c60=[float(x[4]) for x in d60]; c240=[float(x[4]) for x in d240]
    
    e9_5=ema(c5,9); e21_5=ema(c5,21); e50_5=ema(c5,50)
    e50_60=ema(c60,50); e200_60=ema(c60,200)
    e50_240=ema(c240,50)
    
    r5=rsi(c5,7); r60=rsi(c60,14); r240=rsi(c240,14)
    atr5=sum([h5[i]-l5[i] for i in range(-14,0)])/14
    
    score=0; reasons=[]
    if c240[-1]>e50_240: score+=25; reasons.append("✅ 4H صاعد")
    else: score-=15; reasons.append("🔴 4H هابط")
    if c60[-1]>e50_60 and c60[-1]>e200_60: score+=25; reasons.append("✅ 1H قوي")
    elif c60[-1]>e50_60: score+=10; reasons.append("⚠️ 1H متوسط")
    else: score-=10; reasons.append("🔴 1H ضعيف")
    if c5[-1]>e9_5 and e9_5>e21_5: score+=20; reasons.append("✅ 5M تقاطع")
    else: score-=10; reasons.append("🔴 5M هابط")
    if 45<r5<68: score+=15; reasons.append(f"✅ RSI {r5:.0f} ممتاز")
    elif r5>72: score-=10; reasons.append(f"⚠️ RSI {r5:.0f} متشبع")
    
    dist=abs(c5[-1]-e21_5); last_candle_body=abs(c5[-1]-o5[-1])
    
    # تحديد ايمتا تدخل
    if score>=60 and dist>atr5*0.3 and r5<65:
        entry_type="🚀 دخول فوري ماركت NOW"
        entry_price=spot
        entry_time="هلأ فورا - لا تنتظر"
        why_entry="السعر بعيد عن EMA و RSI مو متشبع - دخول فوري قبل ما يطير"
    elif score>=60 and dist<atr5*0.3:
        entry_type="⏳ انتظار اعادة اختبار"
        entry_price=e9_5 if c5[-1]>e9_5 else e21_5
        entry_time=f"حط امر معلق BUY LIMIT عند {entry_price:.2f}$"
        why_entry=f"السعر قريب كتير من EMA - انتظر يرجع لـ EMA9 عند {entry_price:.2f} وادخل، احسن سعر"
    elif score>=60 and r5>68:
        entry_type="⏳ انتظار تصحيح صغير"
        entry_price=spot-atr5*0.5
        entry_time=f"لا تدخل هلا RSI عالي - حط BUY LIMIT {entry_price:.2f}$"
        why_entry="RSI متشبع 68+، السوق رح يصحح 2-3$ وبعدين يطلع - ادخل من تحت"
    elif score>=30:
        entry_type="⚡️ سكالبينغ سريع"
        entry_price=spot
        entry_time="ادخل هلا بس اطلع بسرعة 5 دقايق"
        why_entry="قوة متوسطة - صالحة سكالبينغ فقط"
    elif score>=0:
        entry_type="⏸️ لا تدخل هلا"
        entry_price=spot
        entry_time="انتظر 15 دقيقة وجرب /qawi مرة تانية"
        why_entry="السوق عرضي وضعيف"
    else:
        entry_type="🔴 لا تدخل ابدا"
        entry_price=0
        entry_time="سوق هابط قوي"
        why_entry="كل الفريمات هابطة"
    
    if score>20: sig="🟢 شراء BUY"; sl=spot-atr5*1.0; tp1=spot+atr5*1.2; tp2=spot+atr5*2.5
    elif score<-20: sig="🔴 بيع SELL"; sl=spot+atr5*1.0; tp1=spot-atr5*1.2; tp2=spot-atr5*2.5; 
    else: sig="⏸️ حيادي"; sl=spot; tp1=spot; tp2=spot
    
    if score>=70: power="💎💎💎 قوي جدا 85%+"
    elif score>=50: power="💎💎 قوي 70%"
    elif score>=30: power="⚠️ متوسط 55%"
    else: power="🔴 ضعيف"
    
    msg=f"""{sig} - {power}
نقاط: {score}/100

{entry_type}
💵 سعر الدخول: {entry_price:.2f}$
🛑 وقف: {sl:.2f}$
🎯 هدف1: {tp1:.2f}$ | هدف2: {tp2:.2f}$

⏰ ايمتا تدخل؟
{entry_time}

❓ ليش؟
{why_entry}

📊 التحليل:
{chr(10).join(reasons)}
RSI 5M {r5:.1f} | 1H {r60:.1f} | 4H {r240:.1f}
EMA9 {e9_5:.2f} | EMA21 {e21_5:.2f} | ATR {atr5:.2f}$
جسم الشمعة الاخيرة: {last_candle_body:.2f}$

💡 مثال امر:
اذا قال LIMIT حط:
BUY LIMIT {entry_price:.2f}
SL {sl:.2f}
TP {tp1:.2f}
"""
    await update.message.reply_text(msg)

if __name__ == "__main__":
    bot = Application.builder().token(TOKEN).build()
    for cmd, fn in [("start", start), ("gold", gold), ("tawsiya", tawsiya), ("saree3", saree3), ("qawi", qawi)]:
        bot.add_handler(CommandHandler(cmd, fn))
    bot.run_polling()
