import os, time, threading
print("=== STARTING ===")
BOT_TOKEN_ENV = os.getenv("BOT_TOKEN")
print(f"ENV BOT_TOKEN exists: {bool(BOT_TOKEN_ENV)}")

# اذا مافي توكن حط واحد وهمي حتى ما يكرش
SAFE_TOKEN = BOT_TOKEN_ENV if BOT_TOKEN_ENV else "123456:TEST_TOKEN_FOR_FLASK_ONLY"

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from flask import Flask

bot = telebot.TeleBot(SAFE_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    if not BOT_TOKEN_ENV:
        return "❌ BOT_TOKEN ناقص - روح Environment وضيفو وبعدها Manual Deploy"
    return "✅ V12.4 Live - Bot Token موجود - جرب /tawsiya بتيليجرام"

def build():
    df = yf.download("GC=F", period="3mo", interval="60m", progress=False, auto_adjust=True).dropna()
    price = float(df['Close'].iloc[-1])
    rsi = float(ta.momentum.RSIIndicator(df['Close'],14).rsi().iloc[-1])
    ema = float(ta.trend.EMAIndicator(df['Close'],20).ema_indicator().iloc[-1])
    support = float(df['Low'].tail(20).min())
    resist = float(df['High'].tail(20).max())
    side = "SELL" if price < ema else "BUY"
    entry = price - 0.5 if side=="SELL" else price+0.5
    sl = entry+14 if side=="SELL" else entry-14
    tp1 = entry-12 if side=="SELL" else entry+12

    df_plot = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True).dropna().tail(80)
    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    for i in range(len(df_plot)):
        o,h,l,c = map(float, [df_plot['Open'].iloc[i], df_plot['High'].iloc[i], df_plot['Low'].iloc[i], df_plot['Close'].iloc[i]])
        col = '#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h], color=col, lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--', lw=1)
    ax.axhline(sl, color='#ffb000', ls='--', lw=1)
    ax.set_xlim(-1,len(df_plot)); ax.set_xticks([]); ax.tick_params(colors='gray', labelsize=7)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=180, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()

    txt = f"🔴 بيع SELL - {side}\n💰 {price:.2f}\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp1:.1f}\nدعم {support:.1f} مقاومة {resist:.1f}\nRSI {rsi:.1f} EMA {ema:.1f}"
    return txt, '/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def handle(m):
    if not BOT_TOKEN_ENV:
        bot.send_message(m.chat.id, "❌ BOT_TOKEN ناقص على Render - ضيفو")
        return
    try:
        txt, chart = build()
        with open(chart,'rb') as f: bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"خطأ {e}")

def run_bot():
    if not BOT_TOKEN_ENV:
        print("ما رح شغل polling لان التوكن ناقص")
        return
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e: print(e); time.sleep(5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
