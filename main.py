import os, requests, threading, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V16 Full Tawsiya"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")
ALERT_CHATS=set()
LAST_ALERT={}

def get_price():
    for u in ["https://api.gold-api.com/price/XAU","https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT"]:
        try:
            p=float(requests.get(u,timeout=4).json()['price'])
            if p>2000: return p
        except: pass
    return 4286.2

def get_candles(tf, lim=200):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=6).json()
            if isinstance(r,list) and len(r)>100: return r
        except: pass
    return []

def find_zones(candles):
    zones=[]
    for i in range(20, len(candles)-3):
        try:
            c0=float(candles[i][4]); o0=float(candles[i][1]); h0=float(candles[i][2]); l0=float(candles[i][3])
            c1=float(candles[i+1][4]); o1=float(candles[i+1][1])
            if c0<o0 and c1>o1 and (c1-o1) > abs(c0-o0)*1.2:
                zones.append({"type":"DEMAND","from":l0,"to":h0,"score":2,"i":i})
            if c0>o0 and c1<o1 and (o1-c1) > abs(c0-o0)*1.2:
                zones.append({"type":"SUPPLY","from":l0,"to":h0,"score":2,"i":i})
        except: continue
    return zones[-10:]

def draw_chart(candles, zones, price, path="/tmp/gold.png"):
    plt.figure(figsize=(12,6), facecolor='#0e0e12')
    ax=plt.gca(); ax.set_facecolor('#0e0e12')
    data=candles[-80:]
    for idx, c in enumerate(data):
        o=float(c[1]); h=float(c[2]); l=float(c[3]); cl=float(c[4])
        color='#00ff88' if cl>=o else '#ff3355'
        ax.plot([idx, idx],[l,h], color=color, linewidth=1)
        ax.plot([idx, idx],[o,cl], color=color, linewidth=4, solid_capstyle='round')
    for z in zones:
        x0=z['i']-len(candles)+len(data)
        if x0<0: continue
        col='#00ff88' if z['type']=="DEMAND" else '#ff3355'
        rect=patches.Rectangle((x0, z['from']), 80-x0, z['to']-z['from'], facecolor=col, alpha=0.3, linewidth=0)
        ax.add_patch(rect)
    if price:
        ax.axhline(price, color='white', linestyle='--', alpha=0.7)
        ax.text(79, price, f" {price:.2f} ", color='black', fontsize=8, ha='right', bbox=dict(facecolor='white'))
    ax.set_xlim(-2,82)
    try:
        lows=[float(c[3]) for c in data]; highs=[float(c[2]) for c in data]
        ax.set_ylim(min(lows)*0.997, max(highs)*1.003)
    except: pass
    plt.title(f"XAUUSD 1H {price}", color='white')
    ax.tick_params(colors='gray')
    plt.tight_layout(); plt.savefig(path, dpi=150, facecolor='#0e0e12'); plt.close()
    return path

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not ALERT_CHATS: return
    price=get_price()
    c1h=get_candles("1h",200)
    zones=find_zones(c1h)
    for z in zones:
        if z['from']-3 <= price <= z['to']+3:
            key=f"{z['type']}_{z['from']:.0f}"
            if LAST_ALERT.get(key) and abs(price-LAST_ALERT[key])<4: continue
            LAST_ALERT[key]=price
            for chat_id in list(ALERT_CHATS):
                try:
                    await context.bot.send_message(chat_id, f"🚨 {'شراء' if z['type']=='DEMAND' else 'بيع'} {price:.2f} وصل {z['from']:.1f}-{z['to']:.1f}\n/tawsiya")
                except: pass

async def tawsiya(update, context):
    await update.message.reply_text("🔍 عم حلل وارسم...")
    price=get_price()
    c1h=get_candles("1h",200)
    c15=get_candles("15m",200)
    if len(c1h)<50:
        await update.message.reply_text(f"السوق مسكر السبت - السعر {price}")
        return
    zones=find_zones(c1h)
    zones15=find_zones(c15)
    all_zones=zones+zones15

    # تحليل
    highs=[float(c[2]) for c in c1h[-50:]]; lows=[float(c[3]) for c in c1h[-50:]]
    high_50=max(highs); low_50=min(lows)
    closes=[float(c[4]) for c in c1h[-20:]]
    trend_up=closes[-1]>sum(closes)/len(closes)
    trend_txt="صاعد 🟢 دور طلب فقط" if trend_up else "هابط 🔴 دور عرض فقط"

    demands=[z for z in all_zones if z['type']=="DEMAND"]
    supplies=[z for z in all_zones if z['type']=="SUPPLY"]
    nearest_sup=sorted([z for z in supplies if z['from']>price], key=lambda x: x['from']-price)[0] if [z for z in supplies if z['from']>price] else None
    nearest_dem=sorted([z for z in demands if z['to']<price], key=lambda x: price-x['to'])[0] if [z for z in demands if z['to']<price] else None

    # توصية حسب الصورة
    if trend_up and nearest_dem:
        entry=nearest_dem['to']; sl=nearest_dem['from']-2.5; tp1=entry+8; tp2=high_50; type_trade="🟢 شراء BUY"
        reason=f"ترند صاعد + ارتداد من طلب قوي {nearest_dem['from']:.1f}-{nearest_dem['to']:.1f}"
    elif not trend_up and nearest_sup:
        entry=nearest_sup['from']; sl=nearest_sup['to']+2.5; tp1=entry-8; tp2=low_50; type_trade="🔴 بيع SELL"
        reason=f"ترند هابط + ارتداد من عرض قوي {nearest_sup['from']:.1f}-{nearest_sup['to']:.1f}"
    else:
        if nearest_dem and nearest_sup:
            if abs(price-nearest_dem['to']) < abs(price-nearest_sup['from']):
                entry=nearest_dem['to']; sl=nearest_dem['from']-2.5; tp1=entry+8; tp2=high_50; type_trade="🟢 شراء سكالب"
                reason="اقرب طلب"
            else:
                entry=nearest_sup['from']; sl=nearest_sup['to']+2.5; tp1=entry-8; tp2=low_50; type_trade="🔴 بيع سكالب"
                reason="اقرب عرض"
        elif nearest_dem:
            entry=nearest_dem['to']; sl=nearest_dem['from']-2.5; tp1=entry+8; tp2=high_50; type_trade="🟢 شراء"
            reason="طلب فقط"
        elif nearest_sup:
            entry=nearest_sup['from']; sl=nearest_sup['to']+2.5; tp1=entry-8; tp2=low_50; type_trade="🔴 بيع"
            reason="عرض فقط"
        else:
            entry=price; sl=price-10; tp1=price+10; tp2=price+20; type_trade="⏸️ انتظار"
            reason="مافي مناطق قريبة - انتظر كسر"

    # رسم
    chart=draw_chart(c1h, zones, price)

    txt=f"""{type_trade} | {trend_txt}
━━━━━━━━━━━━━━━
💰 السعر الحالي: {price:.2f}

🎯 التوصية:
دخول: {entry:.2f}
وقف خسارة: {sl:.2f} ({abs(entry-sl):.1f}$)
هدف اول: {tp1:.2f} ({abs(tp1-entry):.1f}$)
هدف ثاني: {tp2:.2f}
نسبة مخاطرة: 1:{abs(tp1-entry)/abs(entry-sl):.1f}

📍 السبب: {reason}

🏦 OB مناطق:
دعم: {nearest_dem['from']:.1f}-{nearest_dem['to']:.1f} طلب | {len(demands)} مناطق
مقاومة: {nearest_sup['from']:.1f}-{nearest_sup['to']:.1f} عرض | {len(supplies)} مناطق

💧 قمة 50 شمعة: {high_50:.1f}
💧 قاع 50 شمعة: {low_50:.1f}
📊 فيبوناتشي خصم: {'رخيص 🟢 دور شراء' if price < (high_50+low_50)/2 else 'غالي 🔴 دور بيع'}

💡 طريقة الدخول:
محافظ: استنا شمعة ابتلاع عند المنطقة
هجومي: امر معلق من {entry:.1f}

✅ التنبيه شغال - رح ابعتلك اذا وصل
"""

    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(chart,'rb'), caption=txt)

async def alert_on(update, context):
    ALERT_CHATS.add(update.effective_chat.id)
    await update.message.reply_text("✅ التنبيهات شغالة 🔔\nرح ابعتلك توصية كاملة كل ما يوصل منطقة\nالسوق بفتح الاحد 11 ليلا")

async def alert_off(update, context):
    ALERT_CHATS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ وقفنا")

async def start(update,context):
    await update.message.reply_text("V16 توصية + شارت\n/tawsiya - توصية كاملة\n/alert_on - تنبيه تلقائي")

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",tawsiya))
        b.add_handler(CommandHandler("alert_on",alert_on))
        b.add_handler(CommandHandler("alert_off",alert_off))
        b.job_queue.run_repeating(check_alerts, interval=120, first=10)
        b.run_polling()
