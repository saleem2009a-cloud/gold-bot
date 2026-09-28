import os
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V19 START token {len(TOKEN)}", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_series(df, col):
    s = df[col]
    if isinstance(s, pd.DataFrame): s = s.iloc[:,0]
    return s.squeeze()

def build():
    df = yf.download("GC=F", period="5d", interval="15m", progress=False, auto_adjust=True, group_by='column').dropna().tail(200)
    close = get_series(df,'Close'); open_ = get_series(df,'Open')
    high = get_series(df,'High'); low = get_series(df,'Low')

    price = float(close.iloc[-1])
    ema20 = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50 = float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi = float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])

    # سوينغ هاي ولو حقيقي
    recent_high = float(high.tail(20).max())
    recent_low = float(low.tail(20).min())

    # Order Block بسيط: اخر شمعة هابطة قوية قبل صعود
    is_uptrend = price > ema20 > ema50 and rsi > 50

    if is_uptrend:
        direction = "🟢 شراء BUY"
        entry = price - 1.5
        sl = recent_low - 2 if recent_low < price else price - 8
        tp1 = price + (price - sl)*1.5
        tp2 = price + (price - sl)*2.5
        reason = f"السعر فوق EMA20 ({ema20:.1f}) و EMA50 ({ema50:.1f}) - ترند صاعد - RSI {rsi:.0f}"
    else:
        direction = "🔴 بيع SELL"
        entry = price + 1.5
        sl = recent_high + 2 if recent_high > price else price + 8
        tp1 = price - (sl - price)*1.5
        tp2 = price - (sl - price)*2.5
        reason = f"السعر تحت EMA20 ({ema20:.1f}) - ترند هابط - RSI {rsi:.0f} + مقاومة {recent_high:.1f}"

    # رسم
    fig, ax = plt.subplots(figsize=(10,5))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    plot_df = df.tail(80)
    c_ = get_series(plot_df,'Close'); o_ = get_series(plot_df,'Open')
    h_ = get_series(plot_df,'High'); l_ = get_series(plot_df,'Low')
    for i in range(len(plot_df)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--', lw=1, label=f'دخول {entry:.1f}')
    ax.axhline(sl, color='#ff3b3b', ls='--', lw=1, label=f'وقف {sl:.1f}')
    ax.axhline(tp1, color='#00ff7f', ls='--', lw=1, label=f'هدف1 {tp1:.1f}')
    ax.set_xlim(-1,len(plot_df)); ax.set_xticks([]); ax.tick_params(colors='gray', labelsize=8)
    ax.legend(loc='upper left', fontsize=7, facecolor='#1a1a1a', edgecolor='gray', labelcolor='white')
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=180, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()

    txt = f"""{direction} 🔥
💰 السعر الحالي: {price:.2f}

🎯 دخول: {entry:.1f}
🛑 وقف: {sl:.1f} ({abs(price-sl):.1f}$)
✅ هدف1: {tp1:.1f}
✅ هدف2: {tp2:.1f}

📊 التحليل:
{reason}
OB: الدعم {recent_low:.1f} - المقاومة {recent_high:.1f}
الريسك: 1 إلى 2.5

⏰ فريم 15 دقيقة - لا تدخل عكس الترند"""
    return txt, '/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        bot.send_message(m.chat.id, "⏳ عم حلل: EMA + RSI + OB + سوينغ...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"خطأ {e}"); print(e, flush=True)

@app.route('/')
def home(): return "V19 REAL TA Live"

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass
threading.Thread(target=run,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
