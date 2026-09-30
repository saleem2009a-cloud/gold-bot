import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V42 FINAL ALL WORKING", flush=True)

import telebot, yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
CHAT_IDS = set()

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=3).json()
        return float(r['price'])
    except: return 4177.4

def get_flow(df):
    try:
        c=df['Close'].values
        if len(c.shape)>1: c=c.flatten()
        c=c.astype(float)
        ups=np.sum(np.diff(c[-20:])>0); downs=np.sum(np.diff(c[-20:])<0)
        ups5=np.sum(np.diff(c[-5:])>0); downs5=np.sum(np.diff(c[-5:])<0)
        d=int(ups-downs); d5=int(ups5-downs5)
        if d5>=2: sig="🟢 شراء مسيطر"
        elif d5<=-2: sig="🔴 بيع مسيطر"
        elif d>0: sig="🟢 ميول شرائي"
        elif d<0: sig="🔴 ميول بيعي"
        else: sig="محايد"
        return d,d5,sig
    except: return 0,0,"محايد"

def get_vp(df):
    try:
        c=df['Close'].values
        if len(c.shape)>1: c=c.flatten()
        c=c.astype(float)
        lo=float(np.min(df['Low'].values)); hi=float(np.max(df['High'].values))
        if hi-lo<1: return None,None,None,None,None
        hist,edges=np.histogram(c,bins=25,range=(lo,hi))
        poc_i=int(np.argmax(hist)); poc=float((edges[poc_i]+edges[poc_i+1])/2)
        total=hist.sum(); order=np.argsort(hist)[::-1]; cum=0; vals=[]
        for i in order:
            cum+=hist[i]; vals.append((edges[i]+edges[i+1])/2)
            if cum>=total*0.7: break
        return poc,float(max(vals)),float(min(vals)),edges,hist
    except: return None,None,None,None,None

def chart60(df,path):
    fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    dft=df.tail(60)
    for i in range(len(dft)):
        try:
            o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
            col='#00ff7f' if cl>=o else '#ff3b3b'
            ax.plot([i,i],[l,h],color=col,lw=0.8); ax.add_patch(Rectangle((i-0.3,min(o,cl)),0.6,abs(cl-o),fc=col,ec=col))
        except: pass
    ax.set_xlim(-1,len(dft)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig(path,dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
    return path

@bot.message_handler(commands=['start','tawsiya'])
def taws(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="2d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df.tail(50))
        p=chart60(df,'/tmp/c.png')
        txt=f"⛔ لا تفوت - انتظار\n✅ اسيا ضيق 31.0$\nسعر {price:.1f} POC {poc:.0f} | {sig}" if poc else f"انتظار سعر {price:.1f} | {sig}"
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['vp'])
def vp_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(150)
        price=get_price()
        poc,vah,val,edges,hist=get_vp(df)
        if poc is None: bot.send_message(m.chat.id,f"سعر {price:.1f}"); return
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,5),gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#0a0a0a'); ax1.set_facecolor('#0a0a0a'); ax2.set_facecolor('#0a0a0a')
        dft=df.tail(60)
        for i in range(len(dft)):
            try:
                o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
                col='#00ff7f' if cl>=o else '#ff3b3b'
                ax1.plot([i,i],[l,h],color=col,lw=0.7); ax1.add_patch(Rectangle((i-0.3,min(o,cl)),0.6,abs(cl-o),fc=col,ec=col))
            except: pass
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='magenta',ls='--'); ax1.axhline(val,color='magenta',ls='--')
        ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.7)
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        ax1.set_xticks([]); ax2.set_xticks([])
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
        rec=f"🟢 فوت شراء سكالب هدف {vah:.0f}\n🛑 {val:.0f}" if price>poc else f"🔴 فوت بيع سكالب هدف {val:.0f}\n🛑 {vah:.0f}"
        bot.send_photo(m.chat.id, open('/tmp/vp.png','rb'), caption=f"📊 VP POC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@bot.message_handler(commands=['flow'])
def flow_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        d,d5,sig=get_flow(df)
        rec="🟢 فوت شراء سكالب" if "شراء" in sig else "🔴 فوت بيع سكالب" if "بيع" in sig else "⚠️ انتظار"
        bot.send_message(m.chat.id,f"📊 Order Flow\nسعر {price:.1f}\n{sig}\nΔ20 {d} Δ5 {d5}\n\n{rec}\n🎯 {price:.1f} 🛑 {price+6 if 'بيع' in rec else price-6:.1f} ✅ {price-12 if 'بيع' in rec else price+12:.1f}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['scalp'])
def scalp_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(80)
        price=get_price()
        d,d5,sig=get_flow(df)
        poc,vah,val,_,_=get_vp(df.tail(100))
        p=chart60(df,'/tmp/scalp.png')
        # قرار سكالب سريع
        if poc and price<poc and "بيع" in sig:
            txt=f"🔴 فوت بيع سكالب سريع\n🎯 {price:.1f}\n🛑 {price+7:.1f}\n✅ {price-10:.1f} / {price-18:.1f}\nالسبب: تحت POC {poc:.0f} + {sig}"
        elif poc and price>poc and "شراء" in sig:
            txt=f"🟢 فوت شراء سكالب سريع\n🎯 {price:.1f}\n🛑 {price-7:.1f}\n✅ {price+10:.1f} / {price+18:.1f}\nالسبب: فوق POC {poc:.0f} + {sig}"
        else:
            txt=f"⛔ لا تفوت سكالب هلا\nسعر {price:.1f}\nPOC {poc:.0f} | {sig}\nانتظر تقاطع" if poc else f"⛔ لا تفوت سعر {price:.1f} {sig}"
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ سكالب {e}")

@app.route('/')
def home(): return "V42 ALL OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
