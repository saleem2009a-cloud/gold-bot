import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V49 AUTO WATCHER 2min", flush=True)

import telebot, yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# --- ذاكرة المراقبة ---
AUTO_CHATS = set()
AUTO_ENABLED = True
LAST_ALERT = {} # chat_id -> time

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=3).json()
        return float(r['price'])
    except: return 4153.0

def safe_vals(df, col):
    v = df[col].values
    if len(v.shape)>1: v = v.flatten()
    return v.astype(float)

def get_asia_range(df):
    try:
        cet = pytz.timezone('Europe/Berlin')
        idx = df.index.tz_localize('UTC').tz_convert(cet) if df.index.tz is None else df.index.tz_convert(cet)
        df2 = df.copy(); df2.index = idx
        today = datetime.now(cet).date()
        asia = df2[df2.index.date == today].between_time("01:00","07:59")
        if len(asia) < 5: return 22.0, "ضيق ✅"
        rng = float(np.max(safe_vals(asia,'High')) - np.min(safe_vals(asia,'Low')))
        status = "واسع ⛔" if rng > 35 else "ضيق ✅" if rng < 30 else "متوسط ⚠️"
        return rng, status
    except: return 22.0, "ضيق ✅"

def get_vp(df):
    c = safe_vals(df,'Close')
    lo=float(np.min(safe_vals(df,'Low'))); hi=float(np.max(safe_vals(df,'High')))
    hist,edges=np.histogram(c,bins=25,range=(lo,hi))
    poc=float((edges[np.argmax(hist)]+edges[np.argmax(hist)+1])/2)
    return poc,0,0,None,None

def get_flow(df, poc, price):
    c = safe_vals(df,'Close')
    diffs=np.diff(c)
    d=int(np.sum(diffs[-20:]>0) - np.sum(diffs[-20:]<0))
    d5=int(np.sum(diffs[-5:]>0) - np.sum(diffs[-5:]<0))
    if d==0: d = -3 if price < poc else 3
    if d5==0: d5 = -2 if price < poc else 2
    sig = "🔴 بيع مسيطر" if d5<0 else "🟢 شراء مسيطر"
    if abs(d5)<2: sig = "🔴 ميول بيعي" if d<0 else "🟢 ميول شرائي"
    return d,d5,sig

def detect_engulfing(df):
    try:
        o=safe_vals(df,'Open'); c=safe_vals(df,'Close')
        if len(o)<3: return "لا يوجد", False
        o1,c1=o[-2],c[-2]; o2,c2=o[-1],c[-1]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1==0: body1=0.1
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.999) and (c2<=o1*1.001) and (body2>body1*1.1)
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.001) and (c2>=o1*0.999) and (body2>body1*1.1)
        if bear: return ("🔴 ابتلاع بيعي قوي جداً" if body2/body1>1.8 else "🔴 ابتلاع بيعي مؤكد"), True
        if bull: return ("🟢 ابتلاع شرائي قوي جداً" if body2/body1>1.8 else "🟢 ابتلاع شرائي مؤكد"), True
        return "لا يوجد ابتلاع", False
    except: return "لا يوجد", False

def check_signal():
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        if len(df)<30: return None
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,_,_,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        eng_text, eng_ok = detect_engulfing(df.tail(10))
        dist_poc = abs(price-poc)
        can_trade = True
        reason=[]
        if asia_rng>35: can_trade=False; reason.append(f"اسيا واسع {asia_rng:.1f}")
        if dist_poc<8: can_trade=False; reason.append(f"قريب POC {dist_poc:.1f}")
        if abs(d5)<2 and abs(d)<2: can_trade=False; reason.append("Flow ضعيف")
        if not eng_ok: can_trade=False; reason.append("ما في ابتلاع")
        return {"price":price,"poc":poc,"asia_rng":asia_rng,"asia_status":asia_status,"d":d,"d5":d5,"sig":sig,"eng_text":eng_text,"eng_ok":eng_ok,"can_trade":can_trade,"dist":dist_poc,"df":df.tail(60)}
    except Exception as e:
        print(f"check err {e}"); return None

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id)
    LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ تم تفعيل المراقبة التلقائية كل دقيقتين\n\nراح ابعتلك فوراً لما يطلع:\n🔴/🟢 ابتلاع مؤكد + اسيا ضيق + بعيد عن POC\n\nحتى وانت نايم - لا تكتم اشعارات البوت\n\nلإيقافها ابعت /auto_off")

@bot.message_handler(commands=['auto_off','وقف'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت المراقبة التلقائية")

@bot.message_handler(commands=['start','tawsiya','scalp','engulf','flow','vp'])
def tawsiya(m):
    try:
        AUTO_CHATS.add(m.chat.id) # يحفظ شاتك تلقائي
        data=check_signal()
        if not data: bot.send_message(m.chat.id,"خطأ جلب بيانات"); return
        price=data["price"]; poc=data["poc"]; asia_rng=data["asia_rng"]; asia_status=data["asia_status"]
        d=data["d"]; d5=data["d5"]; sig=data["sig"]; eng_text=data["eng_text"]; eng_ok=data["eng_ok"]; can_trade=data["can_trade"]; dist=data["dist"]
        dft=data["df"]
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax.plot([i,i],[l[i],h[i]],color=col,lw=1); ax.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        ax.axhline(poc,color='white',ls='--',lw=1)
        if eng_ok: ax.add_patch(Rectangle((len(dft)-2-0.4, min(l[-2],l[-1])-2), 2.8, (max(h[-2],h[-1])-min(l[-2],l[-1])+4), fill=False, ec='yellow', lw=2, ls='--'))
        ax.set_xlim(-1,len(dft)); ax.set_xticks([]);
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        if not can_trade:
            txt=f"⛔ لا تفوت - {eng_text}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f} سعر {price:.1f}\n{sig} Δ20 {d} Δ5 {d5}\n{eng_text} {'✅' if eng_ok else '❌'}\n\n🔔 المراقبة شغالة كل 2 دقيقة - راح اخبرك فوراً"
        else:
            if "بيع" in eng_text:
                txt=f"🚨🚨 فرصة بيع الآن 🚨🚨\n{eng_text} ✅\n🎯 {price:.1f} 🛑 {price+15:.1f} ✅ {price-18:.1f}/{price-32:.1f}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f}\n{sig} Δ20 {d} Δ5 {d5}\n⚠️ 0.01 لوت فقط"
            else:
                txt=f"🚨🚨 فرصة شراء الآن 🚨🚨\n{eng_text} ✅\n🎯 {price:.1f} 🛑 {price-15:.1f} ✅ {price+18:.1f}/{price+32:.1f}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f}\n{sig} Δ20 {d} Δ5 {d5}\n⚠️ 0.01 لوت فقط"
        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

def auto_watcher():
    print("Auto watcher started",flush=True)
    while True:
        try:
            time.sleep(120) # كل دقيقتين
            if not AUTO_CHATS: continue
            data=check_signal()
            if not data or not data["can_trade"]: continue
            # منع السبام - لا يرسل نفس الفرصة الا بعد 20 دقيقة
            now=time.time()
            for chat_id in list(AUTO_CHATS):
                last=LAST_ALERT.get(chat_id,0)
                if now-last < 1200: continue # 20 دقيقة
                price=data["price"]; poc=data["poc"]; eng_text=data["eng_text"]
                d=data["d"]; d5=data["d5"]; sig=data["sig"]; asia_rng=data["asia_rng"]; asia_status=data["asia_status"]
                if "بيع" in eng_text:
                    txt=f"🚨🚨 تنبيه تلقائي - ابتلاع بيعي 🚨🚨\n{eng_text} ✅ ظهر الآن!\n🎯 دخول {price:.1f} 🛑 {price+15:.1f}\n✅ هدف {price-18:.1f} / {price-32:.1f}\n📊 POC {poc:.0f} | اسيا {asia_status} {asia_rng:.1f}$\n{sig} Δ20 {d} Δ5 {d5}\n\n⏰ {datetime.now(pytz.timezone('Europe/Berlin')).strftime('%H:%M:%S')} بتوقيت برلين\nارسل /tawsiya لتشوف الشارت"
                else:
                    txt=f"🚨🚨 تنبيه تلقائي - ابتلاع شرائي 🚨🚨\n{eng_text} ✅ ظهر الآن!\n🎯 دخول {price:.1f} 🛑 {price-15:.1f}\n✅ هدف {price+18:.1f} / {price+32:.1f}\n📊 POC {poc:.0f} | اسيا {asia_status} {asia_rng:.1f}$\n{sig} Δ20 {d} Δ5 {d5}\n\n⏰ {datetime.now(pytz.timezone('Europe/Berlin')).strftime('%H:%M:%S')}\nارسل /tawsiya لتشوف الشارت"
                try:
                    bot.send_message(chat_id, txt)
                    LAST_ALERT[chat_id]=now
                except Exception as e: print(f"send auto err {e}")
        except Exception as e:
            print(f"watcher err {e}"); time.sleep(10)

@app.route('/')
def home(): return "V49 AUTO 2min OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
