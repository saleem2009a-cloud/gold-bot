import os, requests, threading, time, matplotlib, math
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta

app = Flask(__name__)
@app.route('/')
def home(): return "V23 OB+Fibo+Liquidity+Time+Astro+Technical"

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

def find_zones(candles):
    zones=[]
    for i in range(20,len(candles)-3):
        try:
            c0=float(candles[i][4]); o0=float(candles[i][1]); h0=float(candles[i][2]); l0=float(candles[i][3])
            c1=float(candles[i+1][4]); o1=float(candles[i+1][1])
            if c0<o0 and c1>o1 and (c1-o1)>abs(c0-o0)*1.1:
                zones.append({"type":"DEMAND","from":l0,"to":h0,"i":i})
            if c0>o0 and c1<o1 and (o1-c1)>abs(c0-o0)*1.1:
                zones.append({"type":"SUPPLY","from":l0,"to":h0,"i":i})
        except: continue
    return zones[-20:]

def calc_fibonacci(candles):
    if len(candles)<50: return None
    highs=[float(c[2]) for c in candles[-50:]]; lows=[float(c[3]) for c in candles[-50:]]
    sh=max(highs); sl=min(lows); diff=sh-sl
    return {"high":sh,"low":sl,"levels":{"38.2%": sh-diff*0.382,"50%": sh-diff*0.5,"61.8%": sh-diff*0.618}}

def detect_liquidity_sweep(candles):
    if len(candles)<60: return None
    recent=candles[-50:]; lows=[float(c[3]) for c in recent]; highs=[float(c[2]) for c in recent]
    sup=min(lows); res=max(highs)
    for c in candles[-5:]:
        low=float(c[3]); close=float(c[4])
        if low < sup - 1.5 and close > sup:
            return {"type":"BUY_SWEEP","level":sup,"sweep_low":low,"msg":f"سويب شرائي تحت {sup:.1f}","is_valid":True,"entry":sup+1}
    for c in candles[-5:]:
        high=float(c[2]); close=float(c[4])
        if high > res + 1.5 and close < res:
            return {"type":"SELL_SWEEP","level":res,"sweep_high":high,"msg":f"سويب بيعي فوق {res:.1f}","is_valid":True,"entry":res-1}
    return None

# === جديد: تحليل زمني + فلكي + فني ===
def get_time_analysis():
    now=datetime.utcnow()
    # تحليل زمني Gann
    hour=now.hour
    dow=now.weekday() #0 اثنين
    session=""
    if 0 <= hour < 8: session="اسيا - سيولة ضعيفة - حذر"
    elif 8 <= hour < 13: session="لندن - سيولة عالية + اصطياد سيولة"
    elif 13 <= hour < 17: session="لندن+نيويورك - اقوى وقت - ذروة الحركة"
    else: session="نيويورك متأخر - سيولة ضعيفة"

    # دورة زمنية 90 يوم
    day_of_year=now.timetuple().tm_yday
    gann_cycle=day_of_year % 90
    gann_msg=""
    if gann_cycle < 5: gann_msg="بداية دورة 90 يوم جان - انعكاس محتمل"
    elif 44 <= gann_cycle <= 46: gann_msg="منتصف دورة 90 يوم - انعكاس محتمل"
    elif gann_cycle > 85: gann_msg="نهاية دورة 90 يوم - انعكاس محتمل"
    else: gann_msg=f"يوم {gann_cycle} من دورة 90 يوم جان"

    return {"session":session,"gann":gann_msg,"dow":dow,"hour":hour,"day":day_of_year}

def get_moon_phase():
    # حساب تقريبي لطور القمر
    now=datetime.utcnow()
    # قمر جديد معروف 2000-01-06
    known_new_moon=datetime(2000,1,6,18,14)
    diff=(now-known_new_moon).days + (now-known_new_moon).seconds/86400
    lunar_cycle=29.53
    phase=diff % lunar_cycle
    if phase < 1: return {"phase":"قمر جديد 🌑","impact":"انعكاس قوي - بداية ترند - شراء ذهب تاريخيا قوي","energy":"بداية"}
    elif phase < 7.4: return {"phase":"هلال متزايد 🌒","impact":"طاقة صاعدة - استمرار","energy":"صاعد"}
    elif phase < 14.7: return {"phase":"تربيع اول 🌓","impact":"تذبذب - قرار","energy":"متردد"}
    elif phase < 16: return {"phase":"بدر مكتمل 🌕","impact":"ذروة + انعكاس قوي جدا - احذر - تاريخيا قمم الذهب عند البدر","energy":"ذروة"}
    elif phase < 22: return {"phase":"احدب متناقص 🌖","impact":"طاقة هابطة - جني ارباح","energy":"هابط"}
    else: return {"phase":"هلال متناقص 🌘","impact":"نهاية دورة - ضعف","energy":"هابط"}

def get_technical(candles):
    if len(candles)<50: return {}
    closes=[float(c[4]) for c in candles]
    # RSI 14
    gains=[]; losses=[]
    for i in range(1,15):
        diff=closes[-i]-closes[-i-1]
        if diff>0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain=sum(gains)/14 if gains else 0.1
    avg_loss=sum(losses)/14 if losses else 0.1
    rs=avg_gain/(avg_loss+0.001)
    rsi=100-(100/(1+rs))
    # EMA 20/50
    ema20=sum(closes[-20:])/20
    ema50=sum(closes[-50:])/50
    # MACD تقريبي
    ema12=sum(closes[-12:])/12
    ema26=sum(closes[-26:])/26
    macd=ema12-ema26

    trend="صاعد" if ema20>ema50 and macd>0 else "هابط" if ema20<ema50 and macd<0 else "عرضي"
    rsi_msg="تشبع شرائي - بيع" if rsi>70 else "تشبع بيعي - شراء" if rsi<30 else "متوازن"

    return {"rsi":rsi,"ema20":ema20,"ema50":ema50,"macd":macd,"trend":trend,"rsi_msg":rsi_msg}

def draw_chart(candles,zones,fib,sweep,tech,price,path="/tmp/gold.png"):
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
        ax.add_patch(patches.Rectangle((x0,z['from']),80-x0,z['to']-z['from'],facecolor=col,alpha=0.2,linewidth=0))
    if fib:
        for k,v in fib['levels'].items():
            ax.axhline(v, color='#ffaa00' if '38.2' in k else '#888', linestyle='--', alpha=0.7, linewidth=2 if '38.2' in k else 1)
    if sweep and "level" in sweep:
        ax.axhline(sweep["level"], color='#ff00ff', alpha=0.9, linewidth=2)
    if tech:
        ax.plot([0,79],[tech['ema20'],tech['ema20']], color='#00aaff', linestyle=':', alpha=0.8, label='EMA20')
        ax.plot([0,79],[tech['ema50'],tech['ema50']], color='#ffaa00', linestyle=':', alpha=0.8, label='EMA50')
    if price:
        ax.axhline(price,color='white',alpha=1,linewidth=1.5)
        ax.text(79,price,f" {price:.1f} ",color='black',fontsize=8,bbox=dict(facecolor='white'))
    ax.set_xlim(-2,82)
    try:
        lows=[float(c[3]) for c in data]; highs=[float(c[2]) for c in data]
        ax.set_ylim(min(lows)*0.995,max(highs)*1.005)
    except: pass
    ax.tick_params(colors='gray')
    plt.title(f"{price} | RSI {tech.get('rsi',0):.0f} | {tech.get('trend','')} | {tech.get('rsi_msg','')}", color='white', fontsize=9)
    plt.tight_layout(); plt.savefig(path,dpi=150,facecolor='#0e0e12'); plt.close()
    return path

async def tawsiya(update,context):
    await update.message.reply_text("🔍 عم حلل: زمني + فلكي + فني + OB + فيبو + سيولة...")
    price=get_price()
    c1h=get_candles("1h",200)
    if len(c1h)<50:
        await update.message.reply_text(f"السوق مسكر {price}")
        return
    zones=find_zones(c1h)
    fib=calc_fibonacci(c1h)
    sweep=detect_liquidity_sweep(c1h)
    tech=get_technical(c1h)
    time_an=get_time_analysis()
    moon=get_moon_phase()

    demands=[z for z in zones if z['type']=="DEMAND"]
    supplies=[z for z in zones if z['type']=="SUPPLY"]
    nearest_sup=sorted(supplies, key=lambda x: abs(x['from']-price))[0] if supplies else None
    nearest_dem=sorted(demands, key=lambda x: abs(price-x['to']))[0] if demands else None
    highs=[float(c[2]) for c in c1h[-50:]]; lows=[float(c[3]) for c in c1h[-50:]]
    high_50=max(highs); low_50=min(lows)
    closes=[float(c[4]) for c in c1h[-20:]]
    trend_up=closes[-1]>sum(closes)/len(closes)

    # منطق دخول مع كلشي
    confirmations=[]
    if nearest_sup and fib and abs(nearest_sup['from']-fib['levels']["38.2%"])<8:
        confirmations.append("OB+فيبو38.2%")
    if sweep and sweep.get("is_valid"):
        confirmations.append("سيولة")
    if tech.get("rsi",50)<30 or tech.get("rsi",50)>70:
        confirmations.append(f"RSI {tech['rsi']:.0f} تشبع")
    if "انعكاس" in time_an["gann"]:
        confirmations.append(f"زمني {time_an['gann']}")
    if "بدر" in moon["phase"] or "جديد" in moon["phase"]:
        confirmations.append(f"فلكي {moon['phase']}")

    triple="🔥🔥🔥 تأكيد رباعي" if len(confirmations)>=3 else "🔥🔥 تأكيد ثلاثي" if len(confirmations)>=2 else ""

    if sweep and sweep["type"]=="BUY_SWEEP" and sweep["is_valid"]:
        entry=sweep["entry"]; sl=sweep["sweep_low"]-1; tp1=entry+8; tp2=high_50; type_trade="🟢 شراء BUY - سيولة"
    elif sweep and sweep["type"]=="SELL_SWEEP" and sweep["is_valid"]:
        entry=sweep["entry"]; sl=sweep["sweep_high"]+1; tp1=entry-8; tp2=low_50; type_trade="🔴 بيع SELL - سيولة"
    elif not trend_up and nearest_sup:
        entry=nearest_sup['from']+0.5; sl=nearest_sup['to']+3.8; tp1=entry-8; tp2=low_50; type_trade="🔴 بيع SELL"
    elif trend_up and nearest_dem:
        entry=nearest_dem['to']-0.5; sl=nearest_dem['from']-3.8; tp1=entry+8; tp2=high_50; type_trade="🟢 شراء BUY"
    else:
        entry=price; sl=price-5; tp1=price+8; tp2=high_50; type_trade="⏸️ انتظار"

    chart=draw_chart(c1h,zones,fib,sweep,tech,price)

    txt=f"""{type_trade} {triple}
━━━━━━━━━━━━━━━
💰 {price:.2f}

🎯 دخول: {entry:.1f} | وقف: {sl:.1f} ({abs(entry-sl):.1f}$) | هدف1: {tp1:.1f} | هدف2: {tp2:.1f}
نسبة: 1:{abs(tp1-entry)/max(1,abs(entry-sl)):.1f}

📍 الفني القديم (موجود):
دعم: {nearest_dem['from']:.1f} | مقاومة: {nearest_sup['from']:.1f}
{len(demands)} طلب | {len(supplies)} عرض
فيبو 38.2%: {fib['levels']['38.2%']:.1f} | سيولة: {sweep['msg'] if sweep else 'لا يوجد'}

📊 الفني الجديد:
RSI(14): {tech['rsi']:.1f} - {tech['rsi_msg']}
EMA20: {tech['ema20']:.1f} | EMA50: {tech['ema50']:.1f}
MACD: {tech['macd']:+.2f}
الترند الفني: {tech['trend']} | {'صاعد' if trend_up else 'هابط'} (سعر vs متوسط 20)

⏰ الزمني الجديد (Gann):
الجلسة: {time_an['session']}
دورة جان: {time_an['gann']}
اليوم: {time_an['day']} من السنة | الساعة UTC: {time_an['hour']}:00
{"⚠️ وقت انعكاس زمني - انتبه" if "انعكاس" in time_an['gann'] else "وقت عادي"}

🌙 الفلكي الجديد (ترفيهي):
الطور: {moon['phase']}
التأثير: {moon['impact']}
الطاقة: {moon['energy']}
{"⚠️ بدر مكتمل - تاريخيا الذهب يعمل قمة" if "بدر" in moon['phase'] else "🌑 قمر جديد - بداية ترند جديد محتمل" if "جديد" in moon['phase'] else ""}

✅ التأكيدات المجتمعة:
{', '.join(confirmations) if confirmations else 'بانتظار تأكيد'}
{triple}

💡 كيف تستخدم الكل:
1. OB + فيبو 38.2% = منطقة
2. + سيولة سويب = دخول مؤسسات
3. + RSI تشبع 30/70 = تأكيد فني
4. + زمني انعكاس جان + فلكي بدر/قمر جديد = توقيت الانعكاس
= دخول قوي جدا اذا اجتمعو
"""
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(chart,'rb'), caption=txt)

async def alert_on(update,context):
    ALERT_CHATS.add(update.effective_chat.id)
    await update.message.reply_text("✅ تنبيه شامل شغال: OB+فيبو+سيولة+زمني+فلكي+فني")

async def alert_off(update,context):
    ALERT_CHATS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ وقفنا")

async def start(update,context):
    await update.message.reply_text("V23 شامل\n/tawsiya تحليل كامل\n/alert_on تنبيه شامل")

async def check_alerts(context):
    if not ALERT_CHATS: return
    price=get_price()
    c1h=get_candles("1h",200)
    zones=find_zones(c1h)
    fib=calc_fibonacci(c1h)
    sweep=detect_liquidity_sweep(c1h)
    tech=get_technical(c1h)
    for z in zones:
        if z['from']-3 <= price <= z['to']+3:
            extra=""
            if fib and abs(z['from']-fib['levels']["38.2%"])<8: extra+=" + فيبو38.2% 🔥"
            if sweep and sweep.get("is_valid") and abs(sweep["level"]-z['from'])<5: extra+=" + سيولة 🔥"
            if tech and (tech['rsi']<30 or tech['rsi']>70): extra+=f" + RSI {tech['rsi']:.0f} 🔥"
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
