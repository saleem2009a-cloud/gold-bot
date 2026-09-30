import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V44 FINAL LOGIC FIX", flush=True)

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
    except: return 4179.5

def get_vp(df):
    c=df['Close'].values
    if len(c.shape)>1: c=c.flatten()
    c=c.astype(float)
    lo=float(np.min(df['Low'].values)); hi=float(np.max(df['High'].values))
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
    c=df['Close'].values
    if len(c.shape)>1: c=c.flatten()
    c=c.astype(float)
    # نحسب الميل الحقيقي - حتى لو 0.01$
    diffs=np.diff(c)
    ups20=np.sum(diffs[-20:]>0); downs20=np.sum(diffs[-20:]<0)
    d=int(ups20-downs20)
    ups5=np.sum(diffs[-5:]>0); downs5=np.sum(diffs[-5:]<0)
    d5=int(ups5-downs5)
    # مستحيل 0 - اذا 0 نستخدم POC
    if d==0:
        if price < poc: d=-3
        else: d=3
    if d5==0:
        if price < poc: d5=-2
        else: d5=2
    if d5<0: sig="🔴 بيع مسيطر"
    elif d5>0: sig="🟢 شراء مسيطر"
    elif d<0: sig="🔴 ميول بيعي"
    else: sig="🟢 ميول شرائي"
    return d,d5,sig

@bot.message_handler(commands=['start','tawsiya','scalp'])
def all_cmd(m):
    try:
        df=yf.download("GC=F",period="2d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        dft=df.tail(60)
        for i in range(len(dft)):
            o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
            col='#00ff88' if cl>=o else '#ff4444'
            ax.plot([i,i],[l,h],color=col,lw=1); ax.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
        ax.axhline(poc,color='white',ls='--',lw=1); ax.set_xlim(-1,len(dft)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        # قرار سكالب منطقي
        if price < poc:
            txt=f"🔴 فوت بيع سكالب\n🎯 دخول {price:.1f}\n🛑 ستوب {price+7:.1f}\n✅ هدف1 {price-10:.1f} هدف2 {price-20:.1f}\nالسبب: سعر تحت POC {poc:.0f} + {sig}\nΔ20 {d} Δ5 {d5}"
        else:
            txt=f"🟢 فوت شراء سكالب\n🎯 دخول {price:.1f}\n🛑 ستوب {price-7:.1f}\n✅ هدف1 {price+10:.1f} هدف2 {price+20:.1f}\nالسبب: سعر فوق POC {poc:.0f} + {sig}\nΔ20 {d} Δ5 {d5}"
        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['vp'])
def vp_cmd(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(150)
        price=get_price()
        poc,vah,val,edges,hist=get_vp(df)
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,6),gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#0e0e0e'); ax1.set_facecolor('#0e0e0e'); ax2.set_facecolor('#0e0e0e')
        dft=df.tail(60)
        for i in range(len(dft)):
            o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
            col='#00ff88' if cl>=o else '#ff4444'
            ax1.plot([i,i],[l,h],color=col,lw=0.8); ax1.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='#ff00ff',ls='--'); ax1.axhline(val,color='#00ffff',ls='--')
        ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.7)
        ax2.axhline(poc,color='white',lw=2)
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        if price < poc:
            rec=f"🔴 فوت بيع سكالب\n🎯 {price:.1f}\n🛑 {price+7:.1f}\n✅ {price-12:.1f}\nPOC {poc:.0f} فوقك - بيع"
        else:
            rec=f"🟢 فوت شراء سكالب\n🎯 {price:.1f}\n🛑 {price-7:.1f}\n✅ {price+12:.1f}\nPOC {poc:.0f} تحتك - شراء"
        bot.send_photo(m.chat.id, open('/tmp/vp.png','rb'), caption=f"📊 VP POC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@bot.message_handler(commands=['flow'])
def flow_cmd(m):
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df,poc,price)
        if "بيع" in sig:
            txt=f"📊 Order Flow\nسعر {price:.1f} POC {poc:.0f}\n{sig}\nΔ20 {d} Δ5 {d5}\n\n🔴 فوت بيع سكالب\n🎯 {price:.1f} 🛑 {price+7:.1f} ✅ {price-12:.1f}"
        else:
            txt=f"📊 Order Flow\nسعر {price:.1f} POC {poc:.0f}\n{sig}\nΔ20 {d} Δ5 {d5}\n\n🟢 فوت شراء سكالب\n🎯 {price:.1f} 🛑 {price-7:.1f} ✅ {price+12:.1f}"
        bot.send_message(m.chat.id,txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ flow {e}")

@app.route('/')
def home(): return "V44 OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

import threading
threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    from flask import Flask
    app=Flask(__name__)
    @app.route('/')
    def h(): return "V44 OK"
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
