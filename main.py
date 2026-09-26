import os, requests, threading, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "V14 Fixed"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000))), daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")
ALERT_CHATS=set()
LAST_ALERT={}

def get_price():
    for u in ["https://api.gold-api.com/price/XAU","https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT","https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"]:
        try:
            p=float(requests.get(u,timeout=5).json()['price'])
            if p>2000: return p
        except: pass
    return None

def get_candles(tf, lim=200):
    for base in ["https://data-api.binance.vision","https://api.binance.com"]:
        try:
            r=requests.get(f"{base}/api/v3/klines?symbol=PAXGUSDT&interval={tf}&limit={lim}",timeout=6).json()
            if isinstance(r,list) and len(r)>100: return r
        except: pass
    return []

def get_news():
    try:
        r=requests.get("https://api.gold-api.com/news",timeout=4).json()
        return r[0]['title'][:100]
    except: return "لا اخبار قوية"

def find_zones(candles):
    zones=[]
    for i in range(10, len(candles)-5):
        try:
            base_o=float(candles[i][1]); base_c=float(candles[i][4]); base_h=float(candles[i][2]); base_l=float(candles[i][3])
            next4=candles[i+1:i+5]
            if len(next4)<4: continue
            # هنا كان الغلط - صلحتو
            bodies=[abs(float(c[4])-float(c[1])) for c in next4]
            avg=sum(bodies)/4 if bodies else 1
            strong_up=all(float(c[4])>float(c[1]) and abs(float(c[4])-float(c[1]))>avg*0.7 for c in next4)
            strong_down=all(float(c[4])<float(c[1]) and abs(float(c[4])-float(c[1]))>avg*0.7 for c in next4)
            fvg_up=float(candles[i+2][3])>float(candles[i][2])
            fvg_down=float(candles[i+2][2])<float(candles[i][3])
            last_high=max(float(candles[j][2]) for j in range(i-10,i))
            last_low=min(float(candles[j][3]) for j in range(i-10,i))
            bos_up=strong_up and float(next4[-1][4])>last_high
            bos_down=strong_down and float(next4[-1][4])<last_low
            if base_c<base_o and strong_up and (fvg_up or bos_up):
                sc=int(fvg_up)+int(bos_up)+1
                if sc>=2: zones.append({"type":"DEMAND","from":base_l,"to":base_h,"score":sc,"i":i})
            if base_c>base_o and strong_down and (fvg_down or bos_down):
                sc=int(fvg_down)+int(bos_down)+1
                if sc>=2: zones.append({"type":"SUPPLY","from":base_l,"to":base_h,"score":sc,"i":i})
        except: continue
    return zones[-6:]

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
        if x0<0: x0=0
        col='#00ff88' if z['type']=="DEMAND" else '#ff3355'
        rect=patches.Rectangle((x0-1, z['from']), 90, z['to']-z['from'], facecolor=col, alpha=0.25, linewidth=0)
        ax.add_patch(rect)
        ax.text(79, z['from'] if z['type']=="DEMAND" else z['to'], f" {z['type']} {z['from']:.1f}-{z['to']:.1f} ", color=col, fontsize=8, ha='right', bbox=dict(facecolor='#00ff88' if z['type']=="DEMAND" else '#ff3355', alpha=0.2))
    if price:
        ax.axhline(price, color='white', linestyle='--', alpha=0.6)
        ax.text(79, price, f" {price:.2f} ", color='black', fontsize=9, ha='right', bbox=dict(facecolor='white'))
    ax.set_xlim(-2,82)
    try:
        lows=[float(c[3]) for c in data]; highs=[float(c[2]) for c in data]
        ax.set_ylim(min(lows)*0.998, max(highs)*1.002)
    except: pass
    plt.title(f"XAUUSD 1H Supply/Demand {price}", color='white')
    ax.tick_params(colors='gray')
    plt.tight_layout(); plt.savefig(path, dpi=150, facecolor='#0e0e12'); plt.close()
    return path

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not ALERT_CHATS: return
    price=get_price()
    if not price: return
    c1h=get_candles("1h",200)
    if len(c1h)<80: return
    zones=find_zones(c1h)
    for z in zones:
        inside = (z['from']-2 <= price <= z['to']+2)
        if not inside: continue
        key=f"{z['type']}_{z['from']:.0f}"
        if LAST_ALERT.get(key) and abs(price-LAST_ALERT[key])<5: continue
        LAST_ALERT[key]=price
        for chat_id in list(ALERT_CHATS):
            try:
                if z['type']=="DEMAND":
                    msg=f"🚨 شراء! السعر {price:.2f} وصل طلب {z['from']:.1f}-{z['to']:.1f}\nقوة {z['score']}/3 - استنا شمعة ابتلاع\n/tawsiya للشارت"
                else:
                    msg=f"🚨 بيع! السعر {price:.2f} وصل عرض {z['from']:.1f}-{z['to']:.1f}\nقوة {z['score']}/3\n/tawsiya للشارت"
                await context.bot.send_message(chat_id=chat_id, text=msg)
            except: pass

async def tawsiya(update, context):
    await update.message.reply_text("🔍 عم ارسم...")
    try:
        price=get_price()
        c1h=get_candles("1h",200)
        if len(c1h)<80:
            await update.message.reply_text("❌ السوق مسكر اليوم السبت - ما في شموع\nالتنبيهات بتبلش الاحد 11 بالليل\nجرب /alert_on")
            return
        zones=find_zones(c1h)
        chart=draw_chart(c1h, zones, price if price else 4290)
        closes=[float(c[4]) for c in c1h[-30:]]
        trend="صاعد 🟢 دور طلب" if closes[-1]>sum(closes[-20:])/20 else "هابط 🔴 دور عرض"
        txt=f"📈 {trend}\n💰 {price}\n🏦 {len([z for z in zones if z['type']=='DEMAND'])} طلب | {len([z for z in zones if z['type']=='SUPPLY'])} عرض\n📰 {get_news()}\n\n/alert_on شغل التنبيه التلقائي"
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(chart,'rb'), caption=txt)
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def alert_on(update, context):
    ALERT_CHATS.add(update.effective_chat.id)
    await update.message.reply_text("✅ التنبيهات شغالة 🔔\nرح ابعتلك كل ما السعر يوصل منطقة قوية\nالسوق هلا مسكر - التنبيه بيبلش الاحد 11 ليلا\n/alert_off للايقاف")

async def alert_off(update, context):
    ALERT_CHATS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ وقفنا التنبيهات")

async def start(update,context):
    await update.message.reply_text("V14 شغال ✅\n/tawsiya شارت\n/alert_on تنبيهات\n/alert_off ايقاف")

async def news_cmd(update,context):
    await update.message.reply_text(f"📰 {get_news()}")

if __name__=="__main__":
    if TOKEN:
        b=Application.builder().token(TOKEN).build()
        b.add_handler(CommandHandler("start",start))
        b.add_handler(CommandHandler("tawsiya",tawsiya))
        b.add_handler(CommandHandler("tawsiyat",tawsiya))
        b.add_handler(CommandHandler("alert_on",alert_on))
        b.add_handler(CommandHandler("alert_off",alert_off))
        b.add_handler(CommandHandler("news",news_cmd))
        b.job_queue.run_repeating(check_alerts, interval=120, first=10)
        b.run_polling()
