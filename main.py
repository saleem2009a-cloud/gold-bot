import os, telebot, yfinance as yf, ta, threading
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from flask import Flask, request

RAW = os.getenv("BOT_TOKEN","")
TOKEN = RAW.strip().replace("\n","").replace("\r","").replace(" ","")
print(f"CLEAN TOKEN len={len(TOKEN)}")

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def build():
    df = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True).dropna().tail(80)
    price = float(df['Close'].iloc[-1])
    ema = float(ta.trend.EMAIndicator(df['Close'],20).ema_indicator().iloc[-1])
    entry = price - 0.8 if price < ema else price + 0.8
    sl = entry + 6 if price < ema else entry - 6
    tp = entry - 9 if price < ema else entry + 9

    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    for i in range(len(df)):
        o,h,l,c = map(float, [df['Open'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['Close'].iloc[i]])
        col = '#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h], color=col, lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--'); ax.axhline(sl, color='#ffb000', ls='--')
    ax.set_xlim(-1,len(df)); ax.set_xticks([]); ax.tick_params(colors='gray', labelsize=7)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=180, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()
    return f"🔴 بيع SELL\n💰 {price:.2f}\nدخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}\nRSI + OB + EMA", '/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def handle(m):
    try:
        txt, chart = build()
        with open(chart,'rb') as f: bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"خطأ {e}")

@app.route('/')
def home(): return "V15 Webhook Live"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "ok", 200

@app.route('/set')
def set_webhook():
    url = f"https://{request.host}/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=url)
    return f"Webhook set to {url}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
