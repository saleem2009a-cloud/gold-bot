import os, threading
RAW = os.getenv("BOT_TOKEN","")
TOKEN = RAW.strip().replace("\n","").replace("\r","").replace(" ","")
print(f"TOKEN len {len(TOKEN)}")

from flask import Flask
import telebot, yfinance as yf, pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def build():
    # تحميل بدون MultiIndex
    df = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True, group_by='column')
    df = df.dropna().tail(80)

    # تحويل لأرقام عادية مهما كان شكل الجدول
    close = df['Close'].squeeze() if hasattr(df['Close'], 'squeeze') else df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:,0]
    open_ = df['Open'].squeeze()
    if isinstance(open_, pd.DataFrame):
        open_ = open_.iloc[:,0]
    high = df['High'].squeeze()
    if isinstance(high, pd.DataFrame):
        high = high.iloc[:,0]
    low = df['Low'].squeeze()
    if isinstance(low, pd.DataFrame):
        low = low.iloc[:,0]

    price = float(close.iloc[-1])
    entry = price - 0.8
    sl = entry + 6
    tp = entry - 9

    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    for i in range(len(df)):
        o = float(open_.iloc[i]); h = float(high.iloc[i]); l = float(low.iloc[i]); c = float(close.iloc[i])
        col = '#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h], color=col, lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--'); ax.axhline(sl, color='#ffb000', ls='--')
    ax.set_xlim(-1,len(df)); ax.set_xticks([]); ax.tick_params(colors='gray', labelsize=7)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=180, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()

    txt = f"🔴 بيع SELL 🔥🔥🔥\n💰 {price:.2f}\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}\n\nتم اصلاح خطأ Series ✅"
    return txt, '/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def handle(m):
    try:
        bot.send_message(m.chat.id, "⏳ عم حلل...")
        txt, chart = build()
        with open(chart,'rb') as f: bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"خطأ: {e}")
        print(f"ERROR: {e}")

@app.route('/')
def home(): return "V17 Fixed - Series Bug Solved"

def run_bot():
    while True:
        try: bot.infinity_polling()
        except Exception as e: print(e)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
