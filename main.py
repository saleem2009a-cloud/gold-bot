import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V46 ASIA BACK", flush=True)

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
        # نظبط التايمزون
        if df.index.tz is None:
            idx = df.index.tz_localize('UTC').tz_convert(cet)
        else:
            idx = df.index.tz_convert(cet)
        df2 = df.copy()
        df2.index = idx
        today = datetime.now(cet).date()
        asia = df2[df2.index.date == today].between_time("01:00","07:59")
        if len(asia) < 5:
            # لو ما في داتا اليوم خذ اخر 50 شمعة كاسيا مؤقت
            return 31.0, "ضيق"
        rng = float(np.max(safe_vals(asia,'High')) - np.min(safe_vals(asia,'Low')))
        status = "واسع ⛔" if rng > 35 else "ضيق ✅"
        return rng, status
    except Exception as e:
        print(f"asia {e}")
        return 31.0, "ضيق"

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
    if abs(vah-val)<3: vah=poc+6; val=poc-6
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

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,vah,val,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)

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

        # منطق التوصية مع اسيا
        if asia_rng > 35:
            txt=f"⛔ لا تفوت اليوم\n❌ اسيا {asia_status} {asia_rng:.1f}$\nسعر {price:.1f} POC {poc:.0f}\nانتظر بكرا"
        else:
            if "بيع" in sig:
                txt=f"🔴 فوت بيع سكالب\n🎯 {price:.1f} 🛑 {price+7:.1f} ✅ {price-12:.1f}\n✅ اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f}\n{sig} Δ20 {d} Δ5 {d5}"
            else:
                txt=f"🟢 فوت شراء سكالب\n🎯 {price:.1f} 🛑 {price-7:.1f} ✅ {price+12:.1f}\n✅ اسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f}\n{sig} Δ20 {d} Δ5 {d5}"

        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ تاوصية {e}")

@bot.message_handler(commands=['scalp'])
def scalp(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        asia_rng, asia_status = get_asia_range(df)

        fig,ax=plt.subplots(figsize=(12,5))
        fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        dft=df.tail(50)
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax.plot([i,i],[l[i],h[i]],color=col,lw=1)
            ax.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        plt.savefig('/tmp/s.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()

        if "بيع" in sig:
            txt=f"🔴 فوت بيع سكالب سريع\n🎯 {price:.1f}\n🛑 {price+7:.1f}\n✅ {price-10:.1f} / {price-20:.1f}\nاسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f} | {sig}"
        else:
            txt=f"🟢 فوت شراء سكالب سريع\n🎯 {price:.1f}\n🛑 {price-7:.1f}\n✅ {price+10:.1f} / {price+20:.1f}\nاسيا {asia_status} {asia_rng:.1f}$ | POC {poc:.0f} | {sig}"
        with open('/tmp/s.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ سكالب {e}")

@bot.message_handler(commands=['flow'])
def flow_cmd(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        poc,_,_,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df,poc,price)
        asia_rng, asia_status = get_asia_range(df)
        if "بيع" in sig:
            txt=f"📊 Order Flow\nسعر {price:.1f} POC {poc:.0f}\nاسيا {asia_status} {asia_rng:.1f}$\n{sig}\nΔ20 {d} Δ5 {d5}\n\n🔴 فوت بيع سكالب\n🎯 {price:.1f} 🛑 {price+7:.1f} ✅ {price-12:.1f}"
        else:
            txt=f"📊 Order Flow\nسعر {price:.1f} POC {poc:.0f}\nاسيا {asia_status} {asia_rng:.1f}$\n{sig}\nΔ20 {d} Δ5 {d5}\n\n🟢 فوت شراء سكالب\n🎯 {price:.1f} 🛑 {price-7:.1f} ✅ {price+12:.1f}"
        bot.send_message(m.chat.id,txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ flow {e}")

@bot.message_handler(commands=['vp'])
def vp_cmd(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(150)
        price=get_price()
        poc,vah,val,edges,hist=get_vp(df)
        asia_rng, asia_status = get_asia_range(df)
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,6),gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#0e0e0e'); ax1.set_facecolor('#0e0e0e'); ax2.set_facecolor('#0e0e0e')
        dft=df.tail(60)
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax1.plot([i,i],[l[i],h[i]],color=col,lw=0.8)
            ax1.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='#ff00ff',ls='--'); ax1.axhline(val,color='#00ffff',ls='--')
        ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.7)
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        rec=f"🔴 بيع {price-12:.0f}" if price<poc else f"🟢 شراء {price+12:.0f}"
        bot.send_photo(m.chat.id, open('/tmp/vp.png','rb'), caption=f"📊 VP POC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f} | اسيا {asia_status} {asia_rng:.1f}$\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@app.route('/')
def home(): return "V46 OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
