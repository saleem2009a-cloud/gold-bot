import os, requests, threading, time, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime

app = Flask(__name__)
@app.route('/')
def home(): return "V20 OB + Fibonacci 0.382 Confirmation"

def keep_alive():
    while True:
        try:
            url=os.environ.get("RENDER_EXTERNAL_URL")
            if url: requests.get(url, timeout=10)
        except: pass
        time.sleep(240)

threading.Thread(target=keep_alive, daemon=True).start()
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN=os.environ.get("BOT_TOKEN")
ALERT_CHATS=set()
LAST_ALERT={}

def get_price():
    for u in ["https://api.gold-api.com/price/XAU","https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT"]:
        try:
            p=float(requests.get(u,timeout=5).json()['price'])
            if p>2000: return p
        except: pass
    return 4286.2

def get_candles(tf,lim=200):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=6).json()
            if isinstance(r,list) and len(r)>100: return r
        except: pass
    return []

def get_market_data():
    data={}
    try:
        r=requests.get("https://api.binance.vision/api/v3/ticker/24hr?symbol=BTCUSDT",timeout=5).json()
        data['btc_change']=float(r['priceChangePercent'])
    except: data['btc_change']=0
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()
        data['gold_change']=r.get('ch',0)
    except: data['gold_change']=0
    news=[]
    try:
        r=requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",timeout=6).json()
        for ev in r[-30:]:
            if ev.get('impact')=='High' and 'USD' in ev.get('country',''):
                news.append(ev.get('title','')[:40])
    except: pass
    if not news: news=["لا اخبار قوية - حركة فنية"]
    data['news']=news[:3]
    return data

def find_zones(candles):
    zones=[]
    for i in range(20,len(candles)-3):
        try:
            c0=float(candles[i][4]); o0=float(candles[i][1]); h0=float(candles[i][2]); l0=float(candles[i][3])
            c1=float(candles[i+1][4]); o1=float(candles[i+1][1])
            if c0<o0 and c1>o1 and (c1-o1)>abs(c0-o0)*1.1:
                zones.append({"type":"DEMAND","from":l0,"to":h0,"score":2,"i":i})
            if c0>o0 and c1<o1 and (o1-c1)>abs(c0-o0)*1.1:
                zones.append({"type":"SUPPLY","from":l0,"to":h0,"score":2,"i":i})
        except: continue
    return zones[-20:]

def calc_fibonacci(candles):
    # مثل الفيديو: حدد القاع والقمة
    if len(candles)<50: return None
    highs=[float(c[2]) for c in candles[-50:]]
    lows=[float(c[3]) for c in candles[-50:]]
    swing_high=max(highs)
    swing_low=min(lows)
    # وين كانو
    high_idx=highs.index(swing_high)
    low_idx=lows.index(swing_low)

    diff=swing_high-swing_low
    # مستويات فيبو التصحيحي
    levels={
        "0%": swing_high if high_idx>low_idx else swing_low,
        "23.6%": swing_high - diff*0.236 if high_idx>low_idx else swing_low + diff*0.236,
        "38.2%": swing_high - diff*0.382 if high_idx>low_idx else swing_low + diff*0.382, # الاهم مثل الفيديو
        "50%": swing_high - diff*0.5 if high_idx>low_idx else swing_low + diff*0.5,
        "61.8%": swing_high - diff*0.618 if high_idx>low_idx else swing_low + diff*0.618,
        "78.6%": swing_high - diff*0.786 if high_idx>low_idx else swing_low + diff*0.786,
        "100%": swing_low if high_idx>low_idx else swing_high,
    }
    return {"high":swing_high,"low":swing_low,"levels":levels,"uptrend": low_idx < high_idx, "high_idx": high_idx, "low_idx": low_idx}

def draw_chart(candles,zones,fib,price,path="/tmp/gold.png"):
    plt.figure(figsize=(12,7),facecolor='#0e0e12')
    ax=plt.gca(); ax.set_facecolor('#0e0e12')
    data=candles[-80:]
    for idx,c in enumerate(data):
        o=float(c[1]); h=float(c[2]); l=float(c[3]); cl=float(c[4])
        col='#00ff88' if cl>=o else '#ff3355'
        ax.plot([idx,idx],[l,h],color=col,linewidth=1)
        ax.plot([idx,idx],[o,cl],color=col,linewidth=4,solid_capstyle='round')
    # رسم مناطق OB القديمة
    for z in zones:
        x0=z['i']-len(candles)+len(data)
        if x0<0: continue
        col='#00ff88' if z['type']=="DEMAND" else '#ff3355'
        rect=patches.Rectangle((x0,z['from']),80-x0,z['to']-z['from'],facecolor=col,alpha=0.25,linewidth=0)
        ax.add_patch(rect)
    # رسم فيبوناتشي الجديد - مثل الفيديو
    if fib:
        colors={"23.6%":"#888888","38.2%":"#ffaa00","50%":"#ffffff","61.8%":"#00ff88","78.6%":"#0088ff"}
        for k,v in fib['levels'].items():
            if k in colors:
                ax.axhline(v, color=colors[k], linestyle='--', alpha=0.7, linewidth=1 if k!="38.2%" else 2)
                ax.text(0, v, f" {k} {v:.1f}", color=colors[k], fontsize=7, va='bottom', bbox=dict(facecolor='#0e0e12', alpha=0.7, edgecolor='none'))
        # تظليل 0.382 الاهم
        if "38.2%" in fib['levels']:
            ax.axhspan(fib['levels']["38.2%"]-2, fib['levels']["38.2%"]+2, color='#ffaa00', alpha=0.1)

    if price:
        ax.axhline(price,color='white',linestyle='-',alpha=0.9, linewidth=1.5)
        ax.text(79,price,f" {price:.2f} ",color='black',fontsize=8,ha='right',bbox=dict(facecolor='white'))
    ax.set_xlim(-2,82)
    try:
        lows=[float(c[3]) for c in data]; highs=[float(c[2]) for c in data]
        ax.set_ylim(min(lows)*0.996,max(highs)*1.004)
    except: pass
    ax.tick_params(colors='gray')
    plt.title(f"XAUUSD OB + Fibonacci 0.382 | {price}", color='white', fontsize=10)
    plt.tight_layout(); plt.savefig(path,dpi=150,facecolor='#0e0e12'); plt.close()
    return path

async def tawsiya(update,context):
    await update.message.reply_text("🔍 عم حلل: OB + فيبوناتشي 0.382 + اخبار...")
    price=get_price()
    c1h=get_candles("1h",200)
    if len(c1h)<50:
        await update.message.reply_text(f"السوق مسكر - {price}")
        return
    mkt=get_market_data()
    zones=find_zones(c1h)
    fib=calc_fibonacci(c1h) # جديد
    c4h=get_candles("4h",200)
    zones4=find_zones(c4h)
    all_zones=zones+zones4

    highs=[float(c[2]) for c in c1h[-50:]]; lows=[float(c[3]) for c in c1h[-50:]]
    high_50=max(highs); low_50=min(lows)
    closes=[float(c[4]) for c in c1h[-20:]]
    trend_up=closes[-1]>sum(closes)/len(closes)

    demands=[z for z in all_zones if z['type']=="DEMAND"]
    supplies=[z for z in all_zones if z['type']=="SUPPLY"]
    nearest_sup=sorted(supplies, key=lambda x: abs(x['from']-price))[0] if supplies else None
    nearest_dem=sorted(demands, key=lambda x: abs(price-x['to']))[0] if demands else None

    # تأكيد فيبوناتشي 0.382 مع OB
    fib_confirm=""
    fib_382=fib['levels']["38.2%"] if fib else 0
    fib_50=fib['levels']["50%"] if fib else 0
    fib_618=fib['levels']["61.8%"] if fib else 0

    ob_aligned_fib=False
    if nearest_sup and fib and abs(nearest_sup['from']-fib_382)<8:
        fib_confirm=f"✅ تأكيد قوي: عرض {nearest_sup['from']:.1f} متوافق مع فيبو 38.2% {fib_382:.1f} - اكثر مستوى ينعكس منو السعر (مثل الفيديو)"
        ob_aligned_fib=True
    elif nearest_dem and fib and abs(nearest_dem['to']-fib_382)<8:
        fib_confirm=f"✅ تأكيد قوي: طلب {nearest_dem['to']:.1f} متوافق مع فيبو 38.2% {fib_382:.1f} - نقطة شراء ممتازة"
        ob_aligned_fib=True
    elif fib and abs(price-fib_382)<5:
        fib_confirm=f"⚠️ السعر حاليا عند 38.2% {fib_382:.1f} - المستوى الذهبي للانعكاس حسب الفيديو - انتظر اشارة تأكيد"
    else:
        fib_confirm=f"فيبو 38.2% عند {fib_382:.1f} | 50% عند {fib_50:.1f} | 61.8% عند {fib_618:.1f} - انتظر السعر يرجع لاحد المستويات"

    if not trend_up and nearest_sup:
        entry=nearest_sup['from']+0.5; sl=nearest_sup['to']+3.8; tp1=entry-8; tp2=low_50
        type_trade="🔴 بيع SELL"
        reason=f"ترند هابط + عرض {nearest_sup['from']:.1f}"
    elif trend_up and nearest_dem:
        entry=nearest_dem['to']-0.5; sl=nearest_dem['from']-3.8; tp1=entry+8; tp2=high_50
        type_trade="🟢 شراء BUY"
        reason=f"ترند صاعد + طلب {nearest_dem['from']:.1f}"
    else:
        entry=price; sl=price-5; tp1=price-8 if not trend_up else price+8; tp2=low_50 if not trend_up else high_50
        type_trade="🔴 بيع SELL" if not trend_up else "🟢 شراء BUY"
        reason="انتظار"

    chart=draw_chart(c1h,zones,fib,price)
    news_txt="\n".join([f"• {n}" for n in mkt['news']])

    conf_emoji="🔥🔥 تأكيد مزدوج OB+فيبو" if ob_aligned_fib else "⏳ بانتظار توافق فيبو"

    txt=f"""{type_trade} | {'صاعد 🟢' if trend_up else 'هابط 🔴'} {conf_emoji}
━━━━━━━━━━━━━━━
💰 السعر: {price:.2f}

🎯 التوصية:
دخول: {entry:.2f}
وقف: {sl:.2f} ({abs(entry-sl):.1f}$)
هدف1: {tp1:.2f} ({abs(tp1-entry):.1f}$)
هدف2: {tp2:.2f}
نسبة: 1:{abs(tp1-entry)/max(1,abs(entry-sl)):.1f}

📍 الفني القديم:
{reason}
دعم: {nearest_dem['from']:.1f} طلب | {len(demands)} مناطق
مقاومة: {nearest_sup['from']:.1f} عرض | {len(supplies)} مناطق
قمة 50: {high_50:.1f} | قاع 50: {low_50:.1f}

📐 فيبوناتشي الجديد (من الفيديو):
Swing Low: {fib['low']:.1f} | Swing High: {fib['high']:.1f}
• 38.2% الذهبي: {fib_382:.1f} ← اكثر مستوى ينعكس
• 50%: {fib_50:.1f}
• 61.8%: {fib_618:.1f}
{fib_confirm}

🌍 اساسي:
BTC: {mkt.get('btc_change',0):+.1f}% | الذهب اليوم: {mkt.get('gold_change',0):+.2f}%
📰 اخبار:
{news_txt}

💡 طريقة الدخول (مثل الفيديو):
1. حدد القاع والقمة ✅ عملها البوت
2. انتظر السعر يرجع لـ 38.2% ← {fib_382:.1f}
3. ادمج مع OB + اشارة تأكيد ثانية = نقطة دخول ممتازة

✅ كلشي القديم موجود + فيبو تأكيد
"""
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(chart,'rb'), caption=txt)

async def alert_on(update,context):
    ALERT_CHATS.add(update.effective_chat.id)
    await update.message.reply_text("✅ التنبيه شغال مع فيبو 38.2% 🔔")

async def alert_off(update,context):
    ALERT_CHATS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ وقفنا")

async def start(update,context):
    await update.message.reply_text("V20 OB + Fibonacci 0.382\n/tawsiya توصية مؤكدة بفيبو\n/alert_on")

async def check_alerts(context):
    if not ALERT_CHATS: return
    price=get_price()
    c1h=get_candles("1h",200)
    fib=calc_fibonacci(c1h)
    zones=find_zones(c1h)
    for z in zones:
        if z['from']-3 <= price <= z['to']+3:
            # تأكيد اضافي مع فيبو
            extra=""
            if fib and abs(z['from']-fib['levels']["38.2%"])<8:
                extra=" + توافق فيبو 38.2% 🔥"
            key=f"{z['type']}_{z['from']:.0f}"
            if LAST_ALERT.get(key) and abs(price-LAST_ALERT[key])<4: continue
            LAST_ALERT[key]=price
            for chat_id in list(ALERT_CHATS):
                try:
                    await context.bot.send_message(chat_id,f"🚨 {z['type']} {z['from']:.1f}{extra}\n/tawsiya للشارت مع فيبو")
                except: pass

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",tawsiya))
        b.add_handler(CommandHandler("alert_on",alert_on))
        b.add_handler(CommandHandler("alert_off",alert_off))
        b.job_queue.run_repeating(check_alerts, interval=120, first=10)
        b.run_polling()
