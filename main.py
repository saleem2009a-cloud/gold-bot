import os, requests
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V22 SUPPLY+DEMAND+FIBO+BOS", flush=True)

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
    close=get_series(df,'Close'); open_=get_series(df,'Open')
    high=get_series(df,'High'); low=get_series(df,'Low')
    zones=[]
    for i in range(30, len(df)-5):
        # DEMAND: شمعة حمراء قبل 4 خضر كبار + FVG
        if close.iloc[i-1] < open_.iloc[i-1]:
            if all(close.iloc[i+j] > open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and high.iloc[i-1] < low.iloc[i+1]:
                    zones.append({'type':'DEMAND','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
        # SUPPLY: شمعة خضراء قبل 4 حمر كبار + FVG
        if close.iloc[i-1] > open_.iloc[i-1]:
            if all(close.iloc[i+j] < open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and low.iloc[i-1] > high.iloc[i+1]:
                    zones.append({'type':'SUPPLY','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
    return zones[-6:]

def get_fibo(df):
    high=get_series(df,'High'); low=get_series(df,'Low')
    # سوينغ هاي ولو اخر 100 شمعة
    swing_high = float(high.tail(100).max())
    swing_low = float(low.tail(100).min())
    diff = swing_high - swing_low
    levels = {
        '0': swing_low,
        '0.236': swing_low + diff*0.236,
        '0.382': swing_low + diff*0.382,
        '0.5': swing_low + diff*0.5,
        '0.618': swing_low + diff*0.618,
        '1': swing_high,
        '1.382': swing_high + diff*0.382,
        '1.618': swing_high + diff*0.618
    }
    return levels, swing_high, swing_low

def get_bos(df):
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    # BOS هابط: كسر اخر قاع
    last_low = float(low.tail(20).min())
    last_high = float(high.tail(20).max())
    curr = float(close.iloc[-1])
    prev = float(close.iloc[-5])
    if curr < last_low and prev > last_low:
        return f"BOS هابط - كسر قاع {last_low:.1f}", "bearish"
    if curr > last_high and prev < last_high:
        return f"BOS صاعد - كسر قمة {last_high:.1f}", "bullish"
    return "لا يوجد BOS جديد", "none"

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
    close=get_series(df,'Close'); open_=get_series(df,'Open')
    high=get_series(df,'High'); low=get_series(df,'Low')

    price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])

    zones=find_zones(df)
    fibo, sw_high, sw_low = get_fibo(df)
    bos_text, bos_dir = get_bos(df)

    is_uptrend = price > ema20 and ema20 > ema50 and bos_dir!= "bearish"

    valid_zones = [z for z in zones if (z['type']=='DEMAND' and is_uptrend) or (z['type']=='SUPPLY' and not is_uptrend)]
    best = valid_zones[-1] if valid_zones else (zones[-1] if zones else None)

    if best:
        if best['type']=='DEMAND':
            direction="🟢 شراء BUY - طلب مؤسسي"
            entry=(best['low']+best['high'])/2
            sl=best['low']-2.5
            tp1=price + (price-sl)*2
            tp2=fibo['1.382'] # هدف فيبو
            extra = f"DEMAND {best['low']:.0f}-{best['high']:.0f} + FVG + {bos_text}"
        else:
            direction="🔴 بيع SELL - عرض مؤسسي"
            entry=(best['low']+best['high'])/2
            sl=best['high']+2.5
            tp1=price - (sl-price)*2
            tp2=fibo['0'] # هدف فيبو القاع
            extra = f"SUPPLY {best['low']:.0f}-{best['high']:.0f} + FVG + {bos_text}"
    else:
        if is_uptrend:
            direction="🟢 شراء BUY"; entry=price-2; sl=entry-8; tp1=price+12; tp2=fibo['1.382']; extra=f"{bos_text}"
        else:
            direction="🔴 بيع SELL"; entry=price+2; sl=entry+8; tp1=price-12; tp2=fibo['0']; extra=f"{bos_text}"

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
    # مناطق
    for z in zones[-4:]:
        col='#00ff7f30' if z['type']=='DEMAND' else '#ff3b3b30'
        ax.axhspan(z['low'],z['high'],color=col)
        ax.text(len(pdf)-2, (z['low']+z['high'])/2, z['type'], color='white', fontsize=7, va='center')
    # فيبو
    for k,v in fibo.items():
        if k in ['0.236','0.618','1','0']:
            ax.axhline(v, color='#3b82f6', ls='--', lw=0.6, alpha=0.6)
            ax.text(0, v, f'Fibo {k} {v:.0f}', color='#3b82f6', fontsize=6)
    ax.axhline(entry,color='white',ls='--',lw=1.2); ax.axhline(sl,color='#ffaa00',ls='--',lw=1); ax.axhline(tp1,color='#00ff7f',ls=':',lw=1)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([]); ax.tick_params(colors='gray',labelsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=190,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    src="حي" if live else "فيوتشر"
    txt=f"""{direction} 🔥
💰 {price:.2f} ({src})

🎯 دخول: {entry:.1f} (نص المنطقة)
🛑 وقف: {sl:.1f}
✅ هدف1: {tp1:.1f} (1:2)
✅ هدف2 فيبو: {tp2:.1f}

📊 التحليل الكامل:
• {extra}
• فيبو: قاع {sw_low:.0f} - قمة {sw_high:.0f}
• 0.236: {fibo['0.236']:.0f} | 0.618: {fibo['0.618']:.0f} | 1.382: {fibo['1.382']:.0f}
• EMA20 {ema20:.0f} | EMA50 {ema50:.0f} | RSI {rsi:.0f}
• BOS: {bos_text}
• الترند: {'صاعد - ندور طلب فقط' if is_uptrend else 'هابط - ندور عرض فقط'}

الصورة فيها: مناطق خضرا=طلب حمرا=عرض + خطوط زرقا=فيبو"""
    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل Supply/Demand + Fibo + BOS + EMA...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}"); print(e, flush=True)

@app.route('/')
def home(): return "V22 All Strategies"
def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass
threading.Thread(target=run,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
    diff = entry - price
    if diff < 5 and diff > -5:
        status = "✅ ادخل هلا بيع - السعر وصل المنطقة"
    elif diff > 0:
        status = f"⏳ انتظر - لا تدخل - السعر تحت المنطقة ب {diff:.0f}$ - لازم يطلع ل {entry:.0f}"
    else:
        status = f"⏳ فاتت - السعر نزل تحت - انتظر منطقة جديدة"

    txt=f"""{direction} {status}
💰 {price:.2f} (حي)

🎯 دخول: {entry:.1f}
🛑 وقف: {sl:.1f}
✅ هدف1: {tp1:.1f}
✅ هدف2: {tp2:.1f}
"""
