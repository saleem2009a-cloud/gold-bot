import os, requests, time
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V26 AUTO ALERT - NO ID", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# فوق - فاضي - بيتعبى لحالو
CHAT_IDS = set()
LAST_ALERT = {}

def get_series(df,col):
    s=df[col]
    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
    return s.squeeze()

def find_zones(df):
    close=get_series(df,'Close'); open_=get_series(df,'Open'); high=get_series(df,'High'); low=get_series(df,'Low')
    zones=[]
    for i in range(30, len(df)-5):
        if close.iloc[i-1] < open_.iloc[i-1]:
            if all(close.iloc[i+j] > open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and high.iloc[i-1] < low.iloc[i+1]:
                    zones.append({'type':'DEMAND','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1])})
        if close.iloc[i-1] > open_.iloc[i-1]:
            if all(close.iloc[i+j] < open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and low.iloc[i-1] > high.iloc[i+1]:
                    zones.append({'type':'SUPPLY','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1])})
    return zones[-6:]

def get_live_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=4).json()
        return float(r['price'])
    except:
        try:
            df=yf.download("GC=F",period="1d",interval="1m",progress=False,auto_adjust=True).dropna()
            c=df['Close']
            if isinstance(c,pd.DataFrame): c=c.iloc[:,0]
            return float(c.iloc[-1])
        except: return None

def build():
    live=get_live_price()
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=True,group_by='column').dropna().tail(300)
    close=get_series(df,'Close')
    price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    zones=find_zones(df)
    best=zones[-1] if zones else None
    if best:
        entry=(best['low']+best['high'])/2; sl=best['high']+2.5 if best['type']=='SUPPLY' else best['low']-2.5
        tp1=price-(sl-price)*2 if best['type']=='SUPPLY' else price+(price-sl)*2
        direction="🔴 بيع SELL" if best['type']=='SUPPLY' else "🟢 شراء BUY"
        extra=f"{best['type']} {best['low']:.0f}-{best['high']:.0f}"
    else:
        entry=price; sl=price+8; tp1=price-12; direction="⏳ انتظر"; extra="لا يوجد منطقة"

    fig,ax=plt.subplots(figsize=(12,5.5))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(90)
    c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    for z in zones[-3:]:
        col='#00ff7f30' if z['type']=='DEMAND' else '#ff3b3b30'
        ax.axhspan(z['low'],z['high'],color=col)
    ax.axhline(entry,color='white',ls='--',lw=1)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    diff=entry-price
    if abs(diff)<3: status="✅ ادخل هلا"
    elif diff>0: status=f"⏳ انتظر - باقي {diff:.0f}$"
    else: status=f"⏳ فاتت"

    txt=f"""{direction} {status}
💰 {price:.2f} (حي)
🎯 {entry:.1f} | 🛑 {sl:.1f} | ✅ {tp1:.1f}
📊 {extra} | RSI {rsi:.0f}
🔔 التنبيه شغال لحالو
"""
    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    bot.send_message(m.chat.id, "✅ تم تفعيل التنبيه التلقائي - رح ابعتلك لحالي وقت الدخول")
    try:
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")

def auto_check():
    while True:
        try:
            live=get_live_price()
            if live and CHAT_IDS:
                df5=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True,group_by='column').dropna().tail(80)
                def gs(df,c):
                    s=df[c]
                    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
                    return s.squeeze()
                close5=gs(df5,'Close')
                ema9=float(ta.trend.EMAIndicator(close5,9).ema_indicator().iloc[-1])
                ema21=float(ta.trend.EMAIndicator(close5,21).ema_indicator().iloc[-1])
                rsi5=float(ta.momentum.RSIIndicator(close5,14).rsi().iloc[-1])
                signal=None
                if live>ema9>ema21 and 45<rsi5<68:
                    signal=f"🚨 تنبيه شراء تلقائي 💰 {live:.1f} 🟢 ادخل هلا"
                elif live<ema9<ema21 and 32<rsi5<55:
                    signal=f"🚨 تنبيه بيع تلقائي 💰 {live:.1f} 🔴 ادخل هلا"
                if signal:
                    now=time.time()
                    for cid in list(CHAT_IDS):
                        if now - LAST_ALERT.get(cid,0) > 1800:
                            try:
                                bot.send_message(cid, signal)
                                LAST_ALERT[cid]=now
                            except: pass
        except: pass
        time.sleep(60)

@app.route('/')
def home(): return "V26 NO ID"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_check,daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
