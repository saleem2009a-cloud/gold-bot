import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V53 VIP VIDEO+XAU", flush=True)

import telebot, yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

AUTO_CHATS = set()
LAST_ALERT = {}

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
        if len(o)<4: return "لا يوجد ابتلاع", False
        o1,c1=o[-3],c[-3]
        o2,c2=o[-2],c[-2]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1 < 0.5: return "لا يوجد - شمعة صغيرة", False
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.999) and (c2<=o1*1.001) and (body2>body1*1.3)
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.001) and (c2>=o1*0.999) and (body2>body1*1.3)
        if bear: return ("🔴 ابتلاع بيعي قوي جداً" if body2/body1>1.8 else "🔴 ابتلاع بيعي مؤكد"), True
        if bull: return ("🟢 ابتلاع شرائي قوي جداً" if body2/body1>1.8 else "🟢 ابتلاع شرائي مؤكد"), True
        return "لا يوجد ابتلاع", False
    except: return "لا يوجد", False

# === جديد: استراتيجية الفيديو للذهب ===
def get_h1_levels():
    try:
        df_h1 = yf.download("GC=F", period="5d", interval="1h", progress=False, auto_adjust=True).dropna()
        if len(df_h1)<20: return None, None
        h1_high = float(np.max(safe_vals(df_h1.tail(50),'High')))
        h1_low = float(np.min(safe_vals(df_h1.tail(50),'Low')))
        return h1_high, h1_low
    except: return None, None

def detect_quad_top_bottom(df_m5):
    try:
        highs = safe_vals(df_m5.tail(20),'High')
        lows = safe_vals(df_m5.tail(20),'Low')
        max_h = np.max(highs)
        min_l = np.min(lows)
        quad_top = np.sum(highs >= max_h*0.999) >= 3
        quad_bottom = np.sum(lows <= min_l*1.001) >= 3
        return quad_top, quad_bottom, max_h, min_l
    except: return False, False, 0, 0

def check_signal():
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        if len(df)<30: return None
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,_,_,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        eng_text, eng_ok = detect_engulfing(df.tail(20))
        h1_high, h1_low = get_h1_levels()
        quad_top, quad_bottom, _, _ = detect_quad_top_bottom(df.tail(30))
        dist_poc = abs(price-poc)
        can_trade = True
        reason=[]
        if asia_rng>35: can_trade=False; reason.append(f"اسيا واسع {asia_rng:.1f}")
        if dist_poc<8: can_trade=False; reason.append(f"قريب POC {dist_poc:.1f}")
        if abs(d5)<2 and abs(d)<2: can_trade=False; reason.append("Flow ضعيف")
        if not eng_ok: can_trade=False; reason.append("ما في ابتلاع")
        if eng_ok:
            if "بيع" in eng_text and d5>0: can_trade=False; reason.append("تناقض بيع+شراء")
            if "شراء" in eng_text and d5<0: can_trade=False; reason.append("تناقض شراء+بيع")
        # فلتر الفيديو الاضافي
        near_h1_res = h1_high and abs(price-h1_high) < 12
        near_h1_sup = h1_low and abs(price-h1_low) < 12
        video_bonus = ""
        if eng_ok and "بيع" in eng_text and quad_top and near_h1_res:
            video_bonus = "💎 قمة رباعية + مقاومة H1 ✅"
        elif eng_ok and "شراء" in eng_text and quad_bottom and near_h1_sup:
            video_bonus = "💎 قاع رباعي + دعم H1 ✅"
        return {"price":price,"poc":poc,"asia_rng":asia_rng,"asia_status":asia_status,"d":d,"d5":d5,"sig":sig,"eng_text":eng_text,"eng_ok":eng_ok,"can_trade":can_trade,"dist":dist_poc,"df":df.tail(60),"reason":reason,"h1_high":h1_high,"h1_low":h1_low,"quad_top":quad_top,"quad_bottom":quad_bottom,"video_bonus":video_bonus}
    except Exception as e:
        print(f"check err {e}"); return None

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V53 VIP شغال - ذهب + قمة رباعية\nما ببعت الا اذا ابتلاع مؤكد + فلو متطابق\nلإيقاف /auto_off")

@bot.message_handler(commands=['auto_off','وقف'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت المراقبة")

@bot.message_handler(commands=['start','tawsiya','scalp','engulf','flow','vp'])
def tawsiya(m):
    try:
        AUTO_CHATS.add(m.chat.id)
        data=check_signal()
        if not data: bot.send_message(m.chat.id,"خطأ بيانات"); return
        price=data["price"]; poc=data["poc"]; asia_rng=data["asia_rng"]; asia_status=data["asia_status"]
        d=data["d"]; d5=data["d5"]; sig=data["sig"]; eng_text=data["eng_text"]; eng_ok=data["eng_ok"]; can_trade=data["can_trade"]
        reason=data["reason"]; dft=data["df"]; h1_high=data["h1_high"]; h1_low=data["h1_low"]; quad_top=data["quad_top"]; quad_bottom=data["quad_bottom"]; video_bonus=data["video_bonus"]
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax.plot([i,i],[l[i],h[i]],color=col,lw=1); ax.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        ax.axhline(poc,color='white',ls='--',lw=1)
        if h1_high: ax.axhline(h1_high,color='red',ls=':',lw=1)
        if h1_low: ax.axhline(h1_low,color='green',ls=':',lw=1)
        if eng_ok: ax.add_patch(Rectangle((len(dft)-2-0.4, min(l[-2],l[-1])-2), 2.8, (max(h[-2],h[-1])-min(l[-2],l[-1])+4), fill=False, ec='yellow', lw=2, ls='--'))
        ax.set_xlim(-1,len(dft)); ax.set_xticks([]);
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        quad_info = f"قمة رباعية {'✅' if quad_top else '❌'} | قاع رباعي {'✅' if quad_bottom else '❌'}"
        h1_info = f"H1 مقاومة {h1_high:.1f} دعم {h1_low:.1f}" if h1_high else ""
        if not can_trade:
            txt=f"⛔ لا تفوت - {eng_text}\n❌ {', '.join(reason)}\n{quad_info}\n{h1_info}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f}\n{sig} Δ20 {d} Δ5 {d5}"
        else:
            bonus = f"\n{video_bonus}" if video_bonus else ""
            if "بيع" in eng_text:
                txt=f"🚨 فوت بيع VIP ✅{bonus}\n{eng_text}\n🎯 {price:.1f} 🛑 {price+15:.1f} ✅ {price-18:.1f}/{price-32:.1f}\n{quad_info}\n{h1_info}\n{sig} Δ20 {d} Δ5 {d5}"
            else:
                txt=f"🚨 فوت شراء VIP ✅{bonus}\n{eng_text}\n🎯 {price:.1f} 🛑 {price-15:.1f} ✅ {price+18:.1f}/{price+32:.1f}\n{quad_info}\n{h1_info}\n{sig} Δ20 {d} Δ5 {d5}"
        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

def auto_watcher():
    while True:
        try:
            time.sleep(120)
            if not AUTO_CHATS: continue
            data=check_signal()
            if not data or not data["can_trade"]: continue
            now=time.time()
            for chat_id in list(AUTO_CHATS):
                if now-LAST_ALERT.get(chat_id,0) < 1200: continue
                txt=f"🚨 تنبيه VIP مؤكد 🚨\n{data['eng_text']} {data['video_bonus']}\n🎯 {data['price']:.1f} | POC {data['poc']:.0f}\n{data['sig']} Δ20 {data['d']} Δ5 {data['d5']}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V53 VIP VIDEO OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
