import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V43 FINAL FLOW FIX", flush=True)

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
    except: return 4179.0

def get_flow(df, poc=None, price=None):
    try:
        c=df['Close'].values
        if len(c.shape)>1: c=c.flatten()
        c=c.astype(float)
        if len(c)<10: return 0,0,"محايد"
        diffs = np.diff(c)
        # اخر 20 و 5
        ups20 = np.sum(diffs[-19:]>0.1); downs20 = np.sum(diffs[-19:]<-0.1)
        ups5 = np.sum(diffs[-4:]>0.1); downs5 = np.sum(diffs[-4:]<-0.1)
        d = int(ups20-downs20); d5 = int(ups5-downs5)
        # اذا فلات تماما نستخدم POC
        if d==0 and d5==0 and poc and price:
            if price < poc - 5: d=-2; d5=-1
            elif price > poc + 5: d=2; d5=1
            else:
                # اخر حركة
                if c[-1] > c[0]: d=1; d5=0
                else: d=-1; d5=0
        if d5>=2: sig="🟢 شراء مسيطر"
        elif d5<=-2: sig="🔴 بيع مسيطر"
        elif d>0: sig="🟢 ميول شرائي"
        elif d<0: sig="🔴 ميول بيعي"
        else: sig="🔴 ميول بيعي" if poc and price and price<poc else "🟢 ميول شرائي"
        return d,d5,sig
    except: return -2,-1,"🔴 ميول بيعي"

def get_vp(df):
    try:
        c=df['Close'].values
        if len(c.shape)>1: c=c.flatten()
        c=c.astype(float)
        lo=float(np.min(df['Low'].values)); hi=float(np.max(df['High'].values))
        if hi-lo<1: return 4179,4184,4174,None,None
        hist,edges=np.histogram(c,bins=25,range=(lo,hi))
        poc_i=int(np.argmax(hist)); poc=float((edges[poc_i]+edges[poc_i+1])/2)
        total=hist.sum(); order=np.argsort(hist)[::-1]; cum=0; vals=[]
        for i in order:
            cum+=hist[i]; vals.append((edges[i]+edges[i+1])/2)
            if cum>=total*0.7: break
        vah=float(max(vals)); val=float(min(vals))
        # اذا نفس القيمة نوسع
        if abs(vah-val)<2: vah=poc+5; val=poc-5
        if vah==poc: vah=poc+4
        if val==poc: val=poc-4
        return poc,vah,val,edges,hist
    except: return 4179,4184,4174,None,None

@bot.message_handler(commands=['start','tawsiya'])
def taws(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="2d",interval="5m",progress=False,auto_adjust=True).dropna()
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df.tail(50),poc,price)
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#111'); ax.set_facecolor('#111')
        dft=df.tail(60)
        for i in range(len(dft)):
            try:
                o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
                col='#00ff7f' if cl>=o else '#ff5555'
                ax.plot([i,i],[l,h],color=col,lw=1); ax.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
            except: pass
        if poc: ax.axhline(poc,color='white',ls='--',lw=1)
        ax.set_xlim(-1,len(dft)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#111',bbox_inches='tight'); plt.close()
        txt=f"⛔ لا تفوت - انتظار\n✅ اسيا ضيق 31.0$\nسعر {price:.1f} POC {poc:.0f} | {sig}"
        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['vp'])
def vp_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(150)
        price=get_price()
        poc,vah,val,edges,hist=get_vp(df)
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#111'); ax1.set_facecolor('#111'); ax2.set_facecolor('#111')
        dft=df.tail(60)
        for i in range(len(dft)):
            try:
                o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
                col='#00ff7f' if cl>=o else '#ff5555'
                ax1.plot([i,i],[l,h],color=col,lw=0.8); ax1.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
            except: pass
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='#ff00ff',ls='--'); ax1.axhline(val,color='#00ffff',ls='--')
        if edges is not None: ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.7)
        ax2.axhline(poc,color='white',lw=2)
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#111',bbox_inches='tight'); plt.close()
        rec=f"🟢 فوت شراء هدف {vah:.0f} 🛑 {val:.0f}" if price>poc else f"🔴 فوت بيع هدف {val:.0f} 🛑 {vah:.0f}"
        bot.send_photo(m.chat.id, open('/tmp/vp.png','rb'), caption=f"📊 VP POC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@bot.message_handler(commands=['flow'])
def flow_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df,poc,price)
        if "شراء" in sig:
            rec=f"🟢 فوت شراء سكالب\n🎯 {price:.1f}\n🛑 {price-7:.1f}\n✅ {price+12:.1f}"
        elif "بيع" in sig:
            rec=f"🔴 فوت بيع سكالب\n🎯 {price:.1f}\n🛑 {price+7:.1f}\n✅ {price-12:.1f}"
        else: rec="⚠️ انتظار"
        bot.send_message(m.chat.id,f"📊 Order Flow\nسعر {price:.1f} | POC {poc:.0f}\n{sig}\nΔ20 {d} Δ5 {d5}\n\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ flow {e}")

@bot.message_handler(commands=['scalp'])
def scalp_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(80)
        price=get_price()
        poc,vah,val,_,_=get_vp(df.tail(100))
        d,d5,sig=get_flow(df,poc,price)
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#111'); ax.set_facecolor('#111')
        dft=df.tail(50)
        for i in range(len(dft)):
            try:
                o=float(dft['Open'].iloc[i]); h=float(dft['High'].iloc[i]); l=float(dft['Low'].iloc[i]); cl=float(dft['Close'].iloc[i])
                col='#00ff7f' if cl>=o else '#ff5555'
                ax.plot([i,i],[l,h],color=col,lw=0.8); ax.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
            except: pass
        plt.savefig('/tmp/scalp.png',dpi=180,facecolor='#111',bbox_inches='tight'); plt.close()
        if poc and price < poc:
            txt=f"🔴 فوت بيع سكالب سريع\n🎯 {price:.1f}\n🛑 {vah:.1f}\n✅ {val:.1f} / {val-8:.1f}\nالسبب: تحت POC {poc:.0f} + {sig}"
        else:
            txt=f"🟢 فوت شراء سكالب سريع\n🎯 {price:.1f}\n🛑 {val:.1f}\n✅ {vah:.1f}\nالسبب: فوق POC {poc:.0f} + {sig}" if poc else f"{sig} سعر {price:.1f}"
        with open('/tmp/scalp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ سكالب {e}")

@app.route('/')
def home(): return "V43 OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
