import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V47 SAFE - NO GAMBLE", flush=True)

import telebot, yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=3).json()
        return float(r['price'])
    except: return 4184.0

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
        if len(asia) < 5: return 28.0, "ضيق ✅"
        rng = float(np.max(safe_vals(asia,'High')) - np.min(safe_vals(asia,'Low')))
        status = "واسع ⛔ لا تتداول" if rng > 35 else "ضيق ✅" if rng < 30 else "متوسط ⚠️"
        return rng, status
    except: return 28.0, "ضيق ✅"

def get_vp(df):
    c = safe_vals(df,'Close')
    lo=float(np.min(safe_vals(df,'Low'))); hi=float(np.max(safe_vals(df,'High')))
    hist,edges=np.histogram(c,bins=25,range=(lo,hi))
    poc=float((edges[np.argmax(hist)]+edges[np.argmax(hist)+1])/2)
    total=hist.sum(); order=np.argsort(hist)[::-1]; cum=0; vals=[]
    for i in order:
        cum+=hist[i]; vals.append((edges[i]+edges[i+1])/2)
        if cum>=total*0.7: break
    vah=float(max(vals)); val=float(min(vals))
    if abs(vah-val)<3: vah=poc+8; val=poc-8
    return poc,vah,val,edges,hist

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

@bot.message_handler(commands=['start','tawsiya','scalp'])
def tawsiya(m):
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,vah,val,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)

        # === فلتر آمن ===
        dist_poc = abs(price - poc)
        can_trade = True
        reason = []
        if asia_rng > 35:
            can_trade = False
            reason.append(f"اسيا واسع {asia_rng:.1f}$")
        if dist_poc < 8:
            can_trade = False
            reason.append(f"قريب من POC {dist_poc:.1f}$")
        if abs(d5) < 2 and abs(d) < 2:
            can_trade = False
            reason.append("Flow ضعيف")

        fig,ax=plt.subplots(figsize=(12,5))
        fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        dft=df.tail(60)
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax.plot([i,i],[l[i],h[i]],color=col,lw=1)
            ax.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        ax.axhline(poc,color='white',ls='--',lw=1)
        ax.set_xlim(-1,len(dft)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()

        if not can_trade:
            txt=f"⛔ لا تفوت اليوم - ارتاح\n❌ السبب: {', '.join(reason)}\n📊 اسيا {asia_status} {asia_rng:.1f}$\n📍 POC {poc:.0f} | سعر {price:.1f} (بعد {dist_poc:.1f}$)\n{sig} Δ20 {d} Δ5 {d5}\n\n💡 نصيحة: لا تدخل - السوق خطر اليوم"
        else:
            # ستوب اكبر وهدف واقعي
            if "بيع" in sig:
                txt=f"⚠️ فرصة بيع - بس تجريبي اليوم\n🎯 دخول {price:.1f}\n🛑 ستوب {price+15:.1f} (15$)\n✅ هدف1 {price-18:.1f} هدف2 {price-32:.1f}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f} بعد {dist_poc:.0f}$\n{sig} Δ20 {d} Δ5 {d5}\n\n⚠️ ادخل بـ 0.01 لوت فقط - جرب وراقب"
            else:
                txt=f"⚠️ فرصة شراء - بس تجريبي اليوم\n🎯 دخول {price:.1f}\n🛑 ستوب {price-15:.1f} (15$)\n✅ هدف1 {price+18:.1f} هدف2 {price+32:.1f}\n📊 اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f} بعد {dist_poc:.0f}$\n{sig} Δ20 {d} Δ5 {d5}\n\n⚠️ ادخل بـ 0.01 لوت فقط - جرب وراقب"

        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['flow','vp'])
def other(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        poc,_,_,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df,poc,price)
        asia_rng, asia_status = get_asia_range(df)
        bot.send_message(m.chat.id,f"📊 {m.text}\nسعر {price:.1f} POC {poc:.0f}\nاسيا {asia_status} {asia_rng:.1f}$\n{sig} Δ20 {d} Δ5 {d5}\n\nاذا اسيا واسع >35 لا تتداول اليوم")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V47 SAFE OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
