import os, requests, time
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V24 BUY+SELL BOTH", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
CHAT_IDS = set()

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
                    zones.append({'type':'DEMAND','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
        if close.iloc[i-1] > open_.iloc[i-1]:
            if all(close.iloc[i+j] < open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and low.iloc[i-1] > high.iloc[i+1]:
                    zones.append({'type':'SUPPLY','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
    return zones[-6:]

def get_fibo(df):
    high=get_series(df,'High'); low=get_series(df,'Low')
    sw_high=float(high.tail(100).max()); sw_low=float(low.tail(100).min())
    diff=sw_high-sw_low
    return {'0':sw_low,'0.236':sw_low+diff*0.236,'0.618':sw_low+diff*0.618,'1':sw_high,'1.382':sw_high+diff*0.382}, sw_high, sw_low

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

def build_scalp():
    df = yf.download("GC=F", period="1d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(100)
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    price=float(close.iloc[-1])
    ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
    ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    atr=float(ta.volatility.AverageTrueRange(high,low,close,14).average_true_range().iloc[-1])
    recent_low=float(low.tail(10).min())
    recent_high=float(high.tail(10).max())
    if price > ema9 > ema21 and 45 < rsi < 68 and price - recent_low < 4:
        entry=price; sl=recent_low - 1; tp=price + (atr*1.8)
        return f"🟢 سكالب شراء دخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}", entry, sl, tp, "BUY"
    if price < ema9 < ema21 and 32 < rsi < 55 and recent_high - price < 4:
        entry=price; sl=recent_high + 1; tp=price - (atr*1.8)
        return f"🔴 سكالب بيع دخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}", entry, sl, tp, "SELL"
    return None, None, None, None, None

def build():
    live=get_live_price()
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=True,group_by='column').dropna().tail(300)
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    zones=find_zones(df)
    fibo, sw_high, sw_low = get_fibo(df)

    # === هون التغيير الوحيد: بيعطي التنين سوا ===
    demands = [z for z in zones if z['type']=='DEMAND']
    supplys = [z for z in zones if z['type']=='SUPPLY']
    best_demand = demands[-1] if demands else None
    best_supply = supplys[-1] if supplys else None

    # رسم
    fig,ax=plt.subplots(figsize=(12,6))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(100)
    c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    for z in zones[-4:]:
        col='#00ff7f30' if z['type']=='DEMAND' else '#ff3b3b30'
        ax.axhspan(z['low'],z['high'],color=col)
    for k,v in fibo.items():
        if k in ['0.236','0.618','1','0']:
            ax.axhline(v,color='#3b82f6',ls='--',lw=0.5,alpha=0.6)
    if best_supply: ax.axhline((best_supply['low']+best_supply['high'])/2,color='white',ls='--',lw=1.2)
    if best_demand: ax.axhline((best_demand['low']+best_demand['high'])/2,color='white',ls='--',lw=1.2)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=190,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    scalp_txt, s_entry, s_sl, s_tp, s_dir = build_scalp()

    txt = f"💰 {price:.2f} (حي) | EMA20 {ema20:.0f} | RSI {rsi:.0f}\n\n"

    if best_supply:
        e=(best_supply['low']+best_supply['high'])/2; sl=best_supply['high']+2.5; tp=price-(sl-price)*2
        diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}" if diff>0 else "⏳ فاتت"
        txt+=f"🔴 بيع SELL - عرض مؤسسي {status}\n🎯 دخول {e:.1f} | 🛑 {sl:.1f} | ✅ {tp:.1f}\n📊 SUPPLY {best_supply['low']:.0f}-{best_supply['high']:.0f}+FVG\n\n"
    else:
        txt+=f"🔴 بيع: لا يوجد SUPPLY\n\n"

    if best_demand:
        e=(best_demand['low']+best_demand['high'])/2; sl=best_demand['low']-2.5; tp=price+(price-sl)*2
        diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}" if diff<0 else "⏳ فاتت"
        txt+=f"🟢 شراء BUY - طلب مؤسسي {status}\n🎯 دخول {e:.1f} | 🛑 {sl:.1f} | ✅ {tp:.1f}\n📊 DEMAND {best_demand['low']:.0f}-{best_demand['high']:.0f}+FVG\n\n"
    else:
        txt+=f"🟢 شراء: لا يوجد DEMAND\n\n"

    if scalp_txt:
        txt+=f"⚡ سكالب: {scalp_txt}\n"
    else:
        txt+=f"⚡ سكالب: ⏳ لا يوجد دخول مضمون هلا"

    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل بيع + شراء + سكالب...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V24 BOTH"

def auto_check():
    while True:
        time.sleep(300)
        if not CHAT_IDS: continue
        try:
            txt,p = build()
            if "ادخل هلا" in txt:
                for cid in list(CHAT_IDS):
                    try:
                        with open(p,'rb') as f: bot.send_photo(cid,f,caption=f"🚨 تنبيه كل 5 دق:\n{txt}")
                    except: pass
        except: pass

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass

threading.Thread(target=run,daemon=True).start()
threading.Thread(target=auto_check,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
