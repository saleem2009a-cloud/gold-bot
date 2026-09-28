import os
RAW = os.getenv("BOT_TOKEN","")
TOKEN = "".join(RAW.split())
print(f"TOKEN len={len(TOKEN)} STARTED V18", flush=True)

import telebot, yfinance as yf, pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def build():
    df = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True, group_by='column')
    df = df.dropna().tail(60)
    # حل نهائي لمشكلة Series
    close = df['Close']
    if isinstance(close, pd.DataFrame): close = close.iloc[:,0]
    open_ = df['Open']
    if isinstance(open_, pd.DataFrame): open_ = open_.iloc[:,0]
    high = df['High']
    if isinstance(high, pd.DataFrame): high = high.iloc[:,0]
    low = df['Low']
    if isinstance(low, pd.DataFrame): low = low.iloc[:,0]

    price = float(close.iloc[-1])
    entry = price - 1
    sl = entry + 6
    tp = entry - 10

    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    for i in range(len(df)):
        o=float(open_.iloc[i]); h=float(high.iloc[i]); l=float(low.iloc[i]); c=float(close.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry,color='white',ls='--'); ax.axhline(sl,color='#ffb000',ls='--')
    ax.set_xlim(-1,len(df)); ax.set_xticks([]);
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=150,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
    return f"🔴 SELL\n💰 {price:.2f}\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}\n✅ V18 شغال",'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")
        print(f"ERR {e}", flush=True)

@app.route('/')
def home(): return f"V18 live token {len(TOKEN)}"

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except Exception as e: print(f"poll err {e}", flush=True)

threading.Thread(target=run,daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
