import os, requests
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V20 START", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_live_price():
    # 1. جرب API لحظي
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        return float(r['price'])
    except: pass
    # 2. فال باك yfinance دقيقة بدقيقة
    try:
        df = yf.download("GC=F", period="1d", interval="1m", progress=False, auto_adjust=True).dropna()
        if not df.empty:
            c = df['Close']
            if isinstance(c, pd.DataFrame): c = c.iloc[:,0]
            return float(c.iloc[-1])
    except: pass
    return None

def get_series(df,col):
    s=df[col]
    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
    return s.squeeze()

def build():
    live = get_live_price()
    df = yf.download("GC=F", period="5d", interval="15m", progress=False, auto_adjust=True, group_by='column').dropna().tail(200)
    close=get_series(df,'Close'); open_=get_series(df,'Open')
    high=get_series(df,'High'); low=get_series(df,'Low')

    # استخدم السعر الحي اذا موجود، اذا لا استخدم اخر شمعة
    price = live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])

    recent_high=float(high.tail(20).max())
    recent_low=float(low.tail(20).min())

    is_up = price > ema20 and rsi > 45

    if is_up:
        direction="🟢 شراء BUY"
        entry=price - 2
        sl=recent_low - 1.5
        tp1=price + (price-sl)*1.8
        tp2=price + (price-sl)*3
        reason=f"ترند صاعد - فوق EMA20 {ema20:.1f} - RSI {rsi:.0f}"
    else:
        direction="🔴 بيع SELL"
        entry=price + 2
        sl=recent_high + 1.5
        tp1=price - (sl-price)*1.8
        tp2=price - (sl-price)*3
        reason=f"ترند هابط - تحت EMA20 {ema20:.1f} - RSI {rsi:.0f} - مقاومة {recent_high:.0f}"

    # رسم
    fig, ax = plt.subplots(figsize=(10,5))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(80)
    c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    ax.axhline(entry,color='white',ls='--',lw=1); ax.axhline(sl,color='#ff3b3b',ls='--',lw=1); ax.axhline(tp1,color='#00ff7f',ls='--',lw=1)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([]); ax.tick_params(colors='gray',labelsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    src = "حي مباشر" if live else "فيوتشر 15د تأخير"
    txt = f"""{direction}
💰 {price:.2f} ({src})

🎯 دخول {entry:.1f}
🛑 وقف {sl:.1f}
✅ هدف1 {tp1:.1f}
✅ هدف2 {tp2:.1f}

📊 {reason}
الدعم {recent_low:.1f} - المقاومة {recent_high:.1f}

⚠️ السعر الحقيقي هلا حوالي 4180-4200 حسب السوق اليوم"""
    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        bot.send_message(m.chat.id,"⏳ عم جيب السعر الحي...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}"); print(e, flush=True)

@app.route('/')
def home(): return "V20 live price"

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass
threading.Thread(target=run,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
