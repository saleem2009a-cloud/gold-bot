import os, requests, threading
from flask import Flask
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)
@app.route('/')
def home(): return "Gold 4 in 1 with News"
def run_flask():
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)
threading.Thread(target=run_flask,daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=6).json()['price'])
    except:
        try: return float(requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",timeout=6).json()['price'])
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

def get_gold_news():
    news_text = ""
    try:
        # 1- اخبار اقتصادية امريكية عالية التأثير (هي اللي بتحرك الذهب)
        cal = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=8).json()
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        important = []
        keywords = ["CPI","FOMC","Fed","NFP","Non-Farm","Inflation","PPI","GDP","Unemployment","Interest Rate","Powell","FED"]

        for ev in cal:
            try:
                ev_date = datetime.strptime(ev['date'][:10], "%Y-%m-%d").date()
                if ev_date not in [today, tomorrow]: continue
                if ev.get('impact')!= 'High': continue
                if ev.get('country')!= 'USD': continue
                title = ev.get('title','')
                time = ev.get('date','')[11:16] if len(ev.get('date',''))>11 else ""
                # فلترة بس اخبار بتأثر على الذهب
                if any(k.lower() in title.lower() for k in keywords):
                    important.append(f"🔴 {time} UTC - {title} - USD HIGH")
            except: continue

        if important:
            news_text += "⚠️ اخبار قوية اليوم/بكرا بتحرك الذهب 20$+ :\n" + "\n".join(important[:5]) + "\n"
            news_text += "💡 نصيحة: لا تدخل الكبير قبل الخبر ب 30 دقيقة - بس سكالبينج\n\n"
        else:
            news_text += "✅ ما في اخبار قوية HIGH اليوم على الدولار - السوق هادئ للسكالبينج\n\n"

        # 2- اذا في اخبار FOMC/CPI قريب
        for ev in cal:
            if "FOMC" in ev.get('title','') or "Fed Interest" in ev.get('title',''):
                ev_date = ev.get('date','')[:10]
                news_text += f"🏦 تذكير: الفيدرالي FOMC بتاريخ {ev_date} - الذهب رح ينفجر\n\n"
                break

    except Exception as e:
        news_text = "📊 الاخبار: ما قدرت جيب التقويم هلا - شيك ForexFactory\n\n"

    # تحذير عام حسب الوقت
    hour = datetime.utcnow().hour
    if 12 <= hour <= 14: # وقت اخبار امريكا عادة
        news_text += "⏰ هلا وقت اخبار امريكا (12-15 UTC) - انتبه من الحركة القوية\n"

    return news_text

def analyze():
    spot=get_price()
    kl1=get_klines("1m",100); kl5=get_klines("5m",100); kl15=get_klines("15m",100); kl60=get_klines("1h",100)
    if not spot or len(kl1)<60: return None, spot, ""

    c1=[float(x[4]) for x in kl1]; o1=[float(x[1]) for x in kl1]
    c5=[float(x[4]) for x in kl5]
    c15=[float(x[4]) for x in kl15]; h15=[float(x[2]) for x in kl15]; l15=[float(x[3]) for x in kl15]
    c60=[float(x[4]) for x in kl60] if kl60 else c5

    e9_1=ema(c1,9); e21_1=ema(c1,21)
    e50_5=ema(c5,50)
    e50_1h=ema(c60,50)

    recent_high=max(h15[-15:-1]); recent_low=min(l15[-15:-1])
    sup1=round(min(l15[-30:]),2); res1=round(max(h15[-30:]),2)

    # سكالبينج
    last_body=c1[-1]-o1[-1]
    if c1[-1] > e9_1 and last_body>0:
        scalp={"side":"🟢 BUY NOW","sl":round(spot-1.8,2),"tp1":round(spot+1.2,2),"tp2":round(spot+2.5,2)}
    else:
        scalp={"side":"🔴 SELL NOW","sl":round(spot+1.8,2),"tp1":round(spot-1.2,2),"tp2":round(spot-2.5,2)}
        if c1[-1]>e21_1:
            scalp={"side":"🟢 BUY قريب","sl":round(spot-1.8,2),"tp1":round(spot+1.2,2),"tp2":round(spot+2.5,2)}

    # كبير
    if h15[-1] > recent_high and c15[-1] < recent_high:
        liq=f"💧 سحب سيولة فوق {recent_high:.2f}$ = بيع قوي"
        b_side="🔴 بيع"; b_entry=round(res1-1.5,2)
    elif l15[-1] < recent_low and c15[-1] > recent_low:
        liq=f"💧 سحب سيولة تحت {recent_low:.2f}$ = شراء قوي"
        b_side="🟢 شراء"; b_entry=round(sup1+1.5,2)
    else:
        liq=f"💧 قمة {recent_high:.2f}$ قاع {recent_low:.2f}$"
        b_side="🟢 شراء" if c15[-1]>e50_1h else "🔴 بيع"
        b_entry=round(sup1+1.5,2) if "شراء" in b_side else round(res1-1.5,2)

    if "شراء" in b_side and b_entry>spot: b_entry=round(spot-2.5,2)
    if "بيع" in b_side and b_entry<spot: b_entry=round(spot+2.5,2)

    big={"side":b_side,"entry":b_entry,"sl":round(b_entry-5,2) if "شراء" in b_side else round(b_entry+5,2),"tp1":round(b_entry+3,2) if "شراء" in b_side else round(b_entry-3,2),"tp2":round(b_entry+6.5,2) if "شراء" in b_side else round(b_entry-6.5,2),"tp3":round(b_entry+12,2) if "شراء" in b_side else round(b_entry-12,2),"sup":sup1,"res":res1,"liq":liq}

    news = get_gold_news()
    return {"spot":spot,"scalp":scalp,"big":big}, spot, news

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ بوت 4 في 1 جاهز\n\n/tawsiya - بيعطيك:\n1- سكالبينج 3 دقايق\n2- توصية كبيرة\n3- اخبار الذهب\n\nواسألني: وين الدعم؟ شو الاخبار؟")

async def tawsiya(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم اجيب السعر + الاخبار...")
    data, spot, news = analyze()
    if not data:
        await update.message.reply_text("زحمة - جرب بعد 20 ثانية"); return

    hour=datetime.utcnow().hour
    sess="🔥 لندن" if 8<=hour<=11 else "💥 نيويورك" if 13<=hour<=16 else "🌙 آسيا" if 0<=hour<=6 else "🌆 مسائي"

    s=data["scalp"]; b=data["big"]

    msg=f"""💰 السعر: {data['spot']:.2f}$ | {sess} UTC {hour}:00

━━━━━━━━━━━━━━━
⚡ 1- سكالبينج 3 دقايق
━━━━━━━━━━━━━━━
{s['side']}
دخول {data['spot']:.2f}$ MARKET
ستوب {s['sl']}$ | هدف {s['tp1']}$ / {s['tp2']}$

━━━━━━━━━━━━━━━
📊 2- توصية كبيرة
━━━━━━━━━━━━━━━
{b['side']} LIMIT {b['entry']}$
ستوب {b['sl']}$ | هدف {b['tp1']}$ / {b['tp2']}$ / {b['tp3']}$
دعم {b['sup']}$ | مقاومة {b['res']}$
{b['liq']}

━━━━━━━━━━━━━━━
📰 3- اخبار بتأثر على الذهب
━━━━━━━━━━━━━━━
{news}
💡 كيف تستفيد؟
- اذا الخبر HIGH على USD = الذهب رح يتحرك 15-30$
- اذا الخبر ايجابي للدولار = الذهب بينزل
- اذا الخبر سلبي للدولار = الذهب بيطلع
- قبل الخبر ب 30 دقيقة لا تدخل الكبير، بس سكالبينج 1$

اكتب: شو الاخبار؟ / وين الدعم؟
"""

    await update.message.reply_text(msg)

async def chat(update:Update, context:ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.lower()
    data, spot, news = analyze()
    if not data:
        await update.message.reply_text("ثواني..."); return
    b=data["big"]

    if "خبر" in txt or "اخبار" in txt or "news" in txt:
        await update.message.reply_text(f"📰 اخبار الذهب هلا:\n\n{news}\nالسعر {spot:.2f}$")
        return
    if "دعم" in txt or "مقاومة" in txt:
        await update.message.reply_text(f"دعم {b['sup']}$ مقاومة {b['res']}$\nالسعر {spot:.2f}$\n{b['liq']}")
        return
    if "سيولة" in txt:
        await update.message.reply_text(f"{b['liq']}\nالسعر {spot:.2f}$")
        return

    await update.message.reply_text(f"السعر {spot:.2f}$\n\n/tawsiya بيعطيك كلشي مع الاخبار\n\nاو اكتب: شو الاخبار؟")

if __name__=="__main__":
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start",start))
    bot.add_handler(CommandHandler("tawsiya",tawsiya))
    bot.add_handler(CommandHandler("qawi",tawsiya))
    bot.add_handler(CommandHandler("saree3",tawsiya))
    bot.add_handler(CommandHandler("akhbar",tawsiya))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    bot.run_polling()
