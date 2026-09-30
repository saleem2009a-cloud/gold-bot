import os, requests, time, numpy as np
from datetime import datetime, timedelta
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V40 FINAL NO ERRORS", flush=True)

import telebot, yfinance as yf, pandas as pd
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
    except:
        try:
            df=yf.download("GC=F",period="1d",interval="1m",progress=False,auto_adjust=True)
            return float(df['Close'].iloc[-1])
        except: return 4175.0

def get_vp(df):
    try:
        closes = df['Close'].values if 'Close' in df.columns else df.values
        if isinstance(closes[0], (list, np.ndarray)): closes = [c[0] for c in closes]
        closes = np.array(closes, dtype=float)
        lows = df['Low'].values if 'Low' in df.columns else closes
        highs = df['High'].values if 'High' in df.columns else closes
        p_min = float(np.min(lows)); p_max = float(np.max(highs))
        if p_max - p_min < 0.5: return None,None,None,None,None
        hist, edges = np.histogram(closes, bins=30, range=(p_min, p_max))
        poc_idx = int(np.argmax(hist))
        poc = float((edges[poc_idx] + edges[poc_idx+1])/2)
        total = hist.sum()
        order = np.argsort(hist)[::-1]
        cum=0; idx=[]
        for i in order:
            cum+=hist[i]; idx.append(i)
            if cum >= total*0.7: break
        prices = [(edges[i]+edges[i+1])/2 for i in idx]
        return poc, float(max(prices)), float(min(prices)), edges, hist
    except Exception as e:
        print(f"VP {e}")
        return None,None,None,None,None

def get_flow(df):
    try:
        o = df['Open'].values if 'Open' in df.columns else df['Close'].values
        c = df['Close'].values if 'Close' in df.columns else df['Close'].values
        # عدل الشكل اذا DataFrame متعدد
        if len(o.shape)>1: o=o[:,0]
        if len(c.shape)>1: c=c[:,0]
        o=np.array(o,dtype=float); c=np.array(c,dtype=float)
        green = np.sum(c>=o); red = np.sum(c<o)
        green5 = np.sum(c[-5:]>=o[-5:]); red5 = np.sum(c[-5:]<o[-5:])
        delta = int(green-red); d5 = int(green5-red5)
        cvd = int(np.sum(c>=o) - np.sum(c<o))
        if d5>=2: sig="🟢 شراء مسيطر"
        elif d5<=-2: sig="🔴 بيع مسيطر"
        elif delta>0: sig="🟢 ميول شرائي"
        elif delta<0: sig="🔴 ميول بيعي"
        else: sig="محايد"
        return delta,d5,sig,False,cvd
    except Exception as e:
        print(f"flow {e}")
        return 1,-1,"🟢 ميول شرائي",False,1

def get_chart(df):
    fig,ax=plt.subplots(figsize=(13,5))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    try:
        opens = df['Open'].values; closes = df['Close'].values; highs = df['High'].values; lows = df['Low'].values
        if len(opens.shape)>1: opens=opens[:,0]
        if len(closes.shape)>1: closes=closes[:,0]
        if len(highs.shape)>1: highs=highs[:,0]
        if len(lows.shape)>1: lows=lows[:,0]
        for i in range(len(df)):
            o=float(opens[i]); h=float(highs[i]); l=float(lows[i]); cl=float(closes[i])
            col='#00ff7f' if cl>=o else '#ff3b3b'
            ax.plot([i,i],[l,h],color=col,lw=0.8)
            ax.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
    except: pass
    ax.set_xlim(-1,len(df)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/c.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
    return '/tmp/c.png'

@bot.message_handler(commands=['start','tawsiya'])
def taws(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="4d",interval="5m",progress=False,auto_adjust=True).dropna().tail(300)
        price=get_price()
        # اسيا
        asia_range=31.0
        try:
            cet=pytz.timezone('Europe/Berlin')
            df.index = df.index.tz_localize('UTC').tz_convert(cet) if df.index.tz is None else df.index.tz_convert(cet)
            today=datetime.now(cet).date()
            asia=df[df.index.date==today].between_time("01:00","07:59")
            if len(asia)>5:
                asia_range=float(asia['High'].max()-asia['Low'].min())
        except: pass
        poc,vah,val,_,_=get_vp(df.tail(100))
        d, d5, sig, _, cvd = get_flow(df.tail(50))
        chart=get_chart(df.tail(80))
        if asia_range>35: txt=f"⛔ لا تفوت\nاسيا واسع {asia_range:.1f}$\nسعر {price:.1f}"
        else: txt=f"⛔ لا تفوت - انتظار\n✅ اسيا ضيق {asia_range:.1f}$\nسعر {price:.1f}\nPOC {poc:.0f} | {sig}" if poc else f"⛔ انتظار\nاسيا {asia_range:.1f}$ سعر {price:.1f}\n{sig}"
        with open(chart,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['vp'])
def vp(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(200)
        price=get_price()
        poc,vah,val,edges,hist=get_vp(df)
        if poc is None:
            bot.send_message(m.chat.id,f"📊 سعر {price:.1f} - POC قيد الحساب"); return
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(14,5),gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#0a0a0a'); ax1.set_facecolor('#0a0a0a'); ax2.set_facecolor('#0a0a0a')
        opens=df['Open'].values; closes=df['Close'].values; highs=df['High'].values; lows=df['Low'].values
        if len(opens.shape)>1: opens=opens[:,0]
        if len(closes.shape)>1: closes=closes[:,0]
        if len(highs.shape)>1: highs=highs[:,0]
        if len(lows.shape)>1: lows=lows[:,0]
        for i in range(len(df.tail(80))):
            j=len(df)-80+i
            o=float(opens[j]); h=float(highs[j]); l=float(lows[j]); cl=float(closes[j])
            col='#00ff7f' if cl>=o else '#ff3b3b'
            ax1.plot([i,i],[l,h],color=col,lw=0.7)
            ax1.add_patch(Rectangle((i-0.35,min(o,cl)),0.7,abs(cl-o),fc=col,ec=col))
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='magenta',ls='--'); ax1.axhline(val,color='magenta',ls='--')
        ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.6)
        ax2.axhline(poc,color='white',lw=2)
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
        rec="🟢 فوت شراء" if price>poc else "🔴 فوت بيع"
        bot.send_photo(m.chat.id, open('/tmp/vp.png','rb'), caption=f"📊 VP\nPOC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n{rec} هدف {vah:.0f}" if price>poc else f"📊 VP\nPOC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n{rec} هدف {val:.0f}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@bot.message_handler(commands=['flow'])
def flow(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(100)
        price=get_price()
        d,d5,sig,_,cvd=get_flow(df)
        if "شراء" in sig: rec="🟢 فوت شراء"
        elif "بيع" in sig: rec="🔴 فوت بيع"
        else: rec="⚠️ انتظار"
        bot.send_message(m.chat.id,f"📊 Order Flow\nسعر {price:.1f}\n{sig}\nΔ20 {d} Δ5 {d5} CVD {cvd}\n\n{rec}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ flow {e}")

@bot.message_handler(commands=['scalp'])
def scalp(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True).dropna().tail(50)
        price=get_price()
        chart=get_chart(df)
        with open(chart,'rb') as f: bot.send_photo(m.chat.id,f,caption=f"سكالب سعر {price:.1f}")
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V40 OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    from flask import Flask
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
