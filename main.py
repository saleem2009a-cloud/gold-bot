import os, requests
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V24 SCALP ADDED", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

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
    """صفقة سريعة مضمونة - 5 دقايق - مو عشوائية"""
    df = yf.download("GC=F", period="1d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(100)
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')

    price=float(close.iloc[-1])
    ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
    ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    atr=float(ta.volatility.AverageTrueRange(high,low,close,14).average_true_range().iloc[-1])

    # شروط مضمونة للسكالب: لا تدخل الا اذا في تأكيدين
    recent_low=float(low.tail(10).min())
    recent_high=float(high.tail(10).max())

    # سكالب شراء: سعر فوق EMA9 و EMA9 فوق EMA21 و RSI بين 45-65 و ارتداد من دعم
    if price > ema9 > ema21 and 45 < rsi < 68 and price - recent_low < 4:
        entry=price
        sl=recent_low - 1
        tp=price + (atr*1.8)
        return f"🟢 سكالب سريع شراء\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}\nالسبب: فوق EMA9 {ema9:.0f} + EMA21 {ema21:.0f} + RSI {rsi:.0f} + ارتداد من {recent_low:.0f}", entry, sl, tp, "BUY"

    # سكالب بيع: سعر تحت EMA9 و EMA9 تحت EMA21 و RSI بين 32-55 و ارتداد من مقاومة
    if price < ema9 < ema21 and 32 < rsi < 55 and recent_high - price < 4:
        entry=price
        sl=recent_high + 1
        tp=price - (atr*1.8)
        return f"🔴 سكالب سريع بيع\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}\nالسبب: تحت EMA9 {ema9:.0f} + EMA21 {ema21:.0f} + RSI {rsi:.0f} + ارتداد من {recent_high:.0f}", entry, sl, tp, "SELL"

    # اذا ما في شروط مضمونة - لا تعطي صفقة عشوائية
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
    is_uptrend = price > ema20 and ema20 > ema50

    valid_zones = [z for z in zones if (z['type']=='DEMAND' and is_uptrend) or (z['type']=='SUPPLY' and not is_uptrend)]
    best = valid_zones[-1] if valid_zones else (zones[-1] if zones else None)

    if best:
        if best['type']=='DEMAND':
            direction="🟢 شراء BUY - عرض طلب مؤسسي"
            entry=(best['low']+best['high'])/2; sl=best['low']-2.5; tp1=price+(price-sl)*2; tp2=fibo['1.382']
            extra=f"DEMAND {best['low']:.0f}-{best['high']:.0f} + FVG"
        else:
            direction="🔴 بيع SELL - عرض مؤسسي"
            entry=(best['low']+best['high'])/2; sl=best['high']+2.5; tp1=price-(sl-price)*2; tp2=fibo['0']
            extra=f"SUPPLY {best['low']:.0f}-{best['high']:.0f} + FVG"
    else:
        direction="🔴 بيع SELL"; entry=price+2; sl=entry+8; tp1=price-12; tp2=fibo['0']; extra="EMA"

    # سكالب
    scalp_txt, s_entry, s_sl, s_tp, s_dir = build_scalp()

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
    ax.axhline(entry,color='white',ls='--',lw=1.2); ax.axhline(sl,color='#ffaa00',ls='--',lw=1)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=190,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    diff=entry-price
    if abs(diff)<5: status="✅ ادخل هلا"
    elif diff>0: status=f"⏳ انتظر - باقي {diff:.0f}$ ل {entry:.0f}"
    else: status=f"⏳ فاتت - انتظر منطقة جديدة"

    main_txt=f"""{direction} {status}
💰 {price:.2f} (حي)
🎯 دخول {entry:.1f} | 🛑 {sl:.1f} | ✅ {tp1:.1f} | فيبو {tp2:.1f}
📊 {extra} | EMA20 {ema20:.0f} | RSI {rsi:.0f}
"""

    if scalp_txt:
        main_txt+=f"""

⚡ صفقة سريعة مضمونة (5 دقائق):
{scalp_txt}
⏱️ صلاحية 30 دقيقة فقط
"""
    else:
        main_txt+=f"""

⚡ سكالب سريع: ⏳ لا يوجد دخول مضمون هلا - السوق عرضي
لا ادخل عشوائي - انتظر تأكيد EMA9+RSI
"""

    return main_txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل الرئيسي + السكالب المضمون...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}"); print(e, flush=True)

@app.route('/')
def home(): return "V24 Main+Scalp"
def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass
threading.Thread(target=run,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
