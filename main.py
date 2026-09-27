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
def home(): return "V21 OB+Fibo+Liquidity Sweep"

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
    data['news']=["لا اخبار قوية - حركة فنية"]
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
    if len(candles)<50: return None
    highs=[float(c[2]) for c in candles[-50:]]
    lows=[float(c[3]) for c in candles[-50:]]
    swing_high=max(highs); swing_low=min(lows)
    diff=swing_high-swing_low
    levels={
        "23.6%": swing_high - diff*0.236,
        "38.2%": swing_high - diff*0.382,
        "50%": swing_high - diff*0.5,
        "61.8%": swing_high - diff*0.618,
        "78.6%": swing_high - diff*0.786,
    }
    return {"high":swing_high,"low":swing_low,"levels":levels}

# === جديد: كشف اصطياد السيولة ===
def detect_liquidity_sweep(candles):
    if len(candles)<60: return None
    # حدد اقوى دعم ومقاومة بآخر 50 شمعة
    recent=candles[-50:]
    lows=[float(c[3]) for c in recent]
    highs=[float(c[2]) for c in recent]
    closes=[float(c[4]) for c in recent]

    support=min(lows)
    resistance=max(highs)

    # افحص آخر 5 شموع هل صار سويب
    last5=candles[-5:]
    sweep=None

    # حالة 1: سويب تحت الدعم (شراء)
    for c in last5:
        low=float(c[3]); close=float(c[4]); open_=float(c[1])
        # ذيل طويل تحت الدعم + اغلاق داخل المنطقة
        if low < support - 1.5 and close > support:
            # فرق بين الاختراق الوهمي والحقيقي: ذيل طويل + اغلاق داخل
            wick_size = support - low
            body = abs(close-open_)
            if wick_size > 1.5 and body < wick_size*2: # ذيل اكبر من الجسم
                sweep={
                    "type":"BUY_SWEEP",
                    "level":support,
                    "sweep_low":low,
                    "msg":f"✅ اصطياد سيولة شرائي: السعر نزل تحت الدعم {support:.1f} ل {low:.1f} (اخذ ستوبات) ورجع اغلق فوق - دخول مؤسسات",
                    "entry":support+1,
                    "is_valid": True
                }
                break

    # حالة 2: سويب فوق المقاومة (بيع)
    if not sweep:
        for c in last5:
            high=float(c[2]); close=float(c[4]); open_=float(c[1])
            if high > resistance + 1.5 and close < resistance:
                wick_size = high - resistance
                body = abs(close-open_)
                if wick_size > 1.5 and body < wick_size*2:
                    sweep={
                        "type":"SELL_SWEEP",
                        "level":resistance,
                        "sweep_high":high,
                        "msg":f"✅ اصطياد سيولة بيعي: السعر طلع فوق المقاومة {resistance:.1f} ل {high:.1f} (اخذ ستوبات) ورجع اغلق تحت - دخول مؤسسات",
                        "entry":resistance-1,
                        "is_valid": True
                    }
                    break

    # حالة 3: كسر حقيقي - لا نتداول
    if not sweep:
        # اذا اغلاق شمعة كبيرة برا المستوى = كسر حقيقي
        last_close=closes[-1]
        last_open=float(recent[-1][1])
        body_size=abs(last_close-last_open)
        if last_close < support - 3 and body_size > 4:
            sweep={"type":"REAL_BREAKDOWN","msg":f"❌ كسر حقيقي تحت {support:.1f} بشمعة كبيرة {body_size:.1f}$ - لا تتداول عكس الكسر","is_valid": False}
        elif last_close > resistance + 3 and body_size > 4:
            sweep={"type":"REAL_BREAKOUT","msg":f"❌ اختراق حقيقي فوق {resistance:.1f} بشمعة كبيرة - لا تتداول عكس الاختراق","is_valid": False}

    return sweep

def draw_chart(candles,zones,fib,sweep,price,path="/tmp/gold.png"):
    plt.figure(figsize=(13,7),facecolor='#0e0e12')
    ax=plt.gca(); ax.set_facecolor('#0e0e12')
    data=candles[-80:]
    for idx,c in enumerate(data):
        o=float(c[1]); h=float(c[2]); l=float(c[3]); cl=float(c[4])
        col='#00ff88' if cl>=o else '#ff3355'
        ax.plot([idx,idx],[l,h],color=col,linewidth=1)
        ax.plot([idx,idx],[o,cl],color=col,linewidth=4,solid_capstyle='round')
    for z in zones:
        x0=z['i']-len(candles)+len(data)
        if x0<0: continue
        col='#00ff88' if z['type']=="DEMAND" else '#ff3355'
        rect=patches.Rectangle((x0,z['from']),80-x0,z['to']-z['from'],facecolor=col,alpha=0.2,linewidth=0)
        ax.add_patch(rect)
    if fib:
        colors={"38.2%":"#ffaa00","50%":"#ffffff","61.8%":"#00ff88"}
        for k,v in fib['levels'].items():
            if k in colors:
                ax.axhline(v, color=colors[k], linestyle='--', alpha=0.6, linewidth=2 if k=="38.2%" else 1)
                ax.text(0,v,f" {k}", color=colors[k], fontsize=7, va='bottom')
    # رسم السيولة
    if sweep and "level" in sweep:
        ax.axhline(sweep["level"], color='#ff00ff', linestyle='-', alpha=0.8, linewidth=1.5)
        ax.text(40,sweep["level"], f" LIQUIDITY {sweep['level']:.1f}", color='#ff00ff', fontsize=8, fontweight='bold', bbox=dict(facecolor='#ff00ff', alpha=0.2))
        if "sweep_low" in sweep:
            ax.plot([75,75],[sweep["level"],sweep["sweep_low"]], color='#ff00ff', linewidth=3, marker='o')
        if "sweep_high" in sweep:
            ax.plot([75,75],[sweep["level"],sweep["sweep_high"]], color='#ff00ff', linewidth=3, marker='o')
    if price:
        ax.axhline(price,color='white',linestyle='-',alpha=0.9)
        ax.text(79,price,f" {price:.2f} ",color='black',fontsize=8,ha='right',bbox=dict(facecolor='white'))
    ax.set_xlim(-2,82)
    try:
        lows=[float(c[3]) for c in data]; highs=[float(c[2]) for c in data]
        ax.set_ylim(min(lows)*0.995,max(highs)*1.005)
    except: pass
    ax.tick_params(colors='gray')
    plt.title(f"OB + Fibo 38.2% + Liquidity Sweep | {price}", color='white', fontsize=9)
    plt.tight_layout(); plt.savefig(path,dpi=150,facecolor='#0e0e12'); plt.close()
    return path

async def tawsiya(update,context):
    await update.message.reply_text("🔍 عم حلل: OB + فيبو + سيولة...")
    price=get_price()
    c1h=get_candles("1h",200)
    if len(c1h)<50:
        await update.message.reply_text(f"السوق مسكر - {price}")
        return
    mkt=get_market_data()
    zones=find_zones(c1h)
    fib=calc_fibonacci(c1h)
    sweep=detect_liquidity_sweep(c1h) # جديد
    c4h=get_candles("4h",200)
    all_zones=zones+find_zones(c4h)

    highs=[float(c[2]) for c in c1h[-50:]]; lows=[float(c[3]) for c in c1h[-50:]]
    high_50=max(highs); low_50=min(lows)
    closes=[float(c[4]) for c in c1h[-20:]]
    trend_up=closes[-1]>sum(closes)/len(closes)

    demands=[z for z in all_zones if z['type']=="DEMAND"]
    supplies=[z for z in all_zones if z['type']=="SUPPLY"]
    nearest_sup=sorted(supplies, key=lambda x: abs(x['from']-price))[0] if supplies else None
    nearest_dem=sorted(demands, key=lambda x: abs(price-x['to']))[0] if demands else None

    # منطق الدخول مع السيولة
    fib_382=fib['levels']["38.2%"] if fib else 0
    fib_confirm=""
    triple_confirm=False

    if nearest_sup and fib and abs(nearest_sup['from']-fib_382)<8:
        fib_confirm=f"✅ OB+فيبو 38.2% متوافق {fib_382:.1f}"

    sweep_confirm=""
    if sweep and sweep.get("is_valid"):
        sweep_confirm=sweep["msg"]
        if sweep["type"]=="BUY_SWEEP" and nearest_dem:
            if abs(sweep["level"]-nearest_dem['to'])<5 and abs(fib_382-nearest_dem['to'])<10:
                triple_confirm=True
        if sweep["type"]=="SELL_SWEEP" and nearest_sup:
            if abs(sweep["level"]-nearest_sup['from'])<5 and abs(fib_382-nearest_sup['from'])<10:
                triple_confirm=True
    elif sweep and not sweep.get("is_valid"):
        sweep_confirm=sweep["msg"]

    if sweep and sweep["type"]=="BUY_SWEEP" and sweep["is_valid"]:
        entry=sweep["entry"]; sl=sweep["sweep_low"]-1; tp1=entry+8; tp2=high_50
        type_trade="🟢 شراء BUY - سيولة"
        reason=f"اصطياد سيولة تحت {sweep['level']:.1f} + طلب {nearest_dem['from']:.1f} اذا موجود"
    elif sweep and sweep["type"]=="SELL_SWEEP" and sweep["is_valid"]:
        entry=sweep["entry"]; sl=sweep["sweep_high"]+1; tp1=entry-8; tp2=low_50
        type_trade="🔴 بيع SELL - سيولة"
        reason=f"اصطياد سيولة فوق {sweep['level']:.1f} + عرض {nearest_sup['from']:.1f} اذا موجود"
    elif not trend_up and nearest_sup:
        entry=nearest_sup['from']+0.5; sl=nearest_sup['to']+3.8; tp1=entry-8; tp2=low_50
        type_trade="🔴 بيع SELL"
        reason=f"ترند هابط + عرض {nearest_sup['from']:.1f}"
    elif trend_up and nearest_dem:
        entry=nearest_dem['to']-0.5; sl=nearest_dem['from']-3.8; tp1=entry+8; tp2=high_50
        type_trade="🟢 شراء BUY"
        reason=f"ترند صاعد + طلب {nearest_dem['from']:.1f}"
    else:
        entry=price; sl=price-5; tp1=price-8; tp2=low_50
        type_trade="⏸️ انتظار"
        reason="ما في منطقة واضحة"

    chart=draw_chart(c1h,zones,fib,sweep,price)

    triple_txt="🔥🔥🔥 تأكيد ثلاثي OB+فيبو38.2%+سيولة = اقوى دخول" if triple_confirm else "تأكيد ثنائي" if fib_confirm and sweep_confirm else ""

    txt=f"""{type_trade} | {triple_txt}
━━━━━━━━━━━━━━━
💰 السعر: {price:.2f}

🎯 التوصية:
دخول: {entry:.2f}
وقف: {sl:.2f} ({abs(entry-sl):.1f}$)
هدف1: {tp1:.2f} ({abs(tp1-entry):.1f}$)
هدف2: {tp2:.2f}
نسبة: 1:{abs(tp1-entry)/max(1,abs(entry-sl)):.1f}

📍 الفني القديم (ما حذفتو):
{reason}
دعم: {nearest_dem['from']:.1f} | مقاومة: {nearest_sup['from']:.1f}
{len(demands)} طلب | {len(supplies)} عرض
قمة 50: {high_50:.1f} | قاع 50: {low_50:.1f}

📐 فيبو 38.2% (من الفيديو الاول):
الذهبي: {fib_382:.1f}
{fib_confirm}

💧 سيولة (من الفيديو الثاني - الجديد):
{sweep_confirm if sweep_confirm else 'ما في سويب حاليا - انتظر كسر وهمي بذيل طويل + اغلاق داخل'}
{triple_txt}

💡 كيف تدخل مثل الفيديو:
1. شوف مستوى دعم/مقاومة واضح ✅
2. انتظر السعر ياخد السيولة (ذيل طويل برا المستوى)
3. ادخل لما يرجع يغلق داخل المستوى
4. اذا المنطقة = فيبو 38.2% + OB = دخول مؤسسات قوي

🌍 BTC: {mkt.get('btc_change',0):+.1f}%
"""
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(chart,'rb'), caption=txt)

async def alert_on(update,context):
    ALERT_CHATS.add(update.effective_chat.id)
    await update.message.reply_text("✅ تنبيه OB+فيبو+سيولة شغال 🔔")

async def alert_off(update,context):
    ALERT_CHATS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ وقفنا")

async def start(update,context):
    await update.message.reply_text("V21 OB+Fibo+Liquidity\n/tawsiya توصية ثلاثية التأكيد")

async def check_alerts(context):
    if not ALERT_CHATS: return
    price=get_price()
    c1h=get_candles("1h",200)
    zones=find_zones(c1h)
    sweep=detect_liquidity_sweep(c1h)
    fib=calc_fibonacci(c1h)
    for z in zones:
        if z['from']-3 <= price <= z['to']+3:
            extra=""
            if fib and abs(z['from']-fib['levels']["38.2%"])<8: extra+=" + فيبو38.2% 🔥"
            if sweep and sweep.get("is_valid") and abs(sweep["level"]-z['from'])<5: extra+=" + سيولة 🔥"
            key=f"{z['type']}_{z['from']:.0f}"
            if LAST_ALERT.get(key) and abs(price-LAST_ALERT[key])<4: continue
            LAST_ALERT[key]=price
            for chat_id in list(ALERT_CHATS):
                try:
                    await context.bot.send_message(chat_id,f"🚨 {z['type']} {z['from']:.1f}{extra}\n/tawsiya")
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
