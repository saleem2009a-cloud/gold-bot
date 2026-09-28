import os, threading
RAW = os.getenv("BOT_TOKEN","")
TOKEN = RAW.strip().replace("\n","").replace("\r","").replace(" ","")
print(f"TOKEN len {len(TOKEN)}")

from flask import Flask
import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_close(df):
    # yfinance الجديد بيرجع Close كـ DataFrame مو Series
    c = df['Close']
    if isinstance(c, pd.DataFrame):
        return c.iloc[:,0]
    return c
def get_open(df):
    c = df['Open']
    if isinstance(c, pd.DataFrame):
        return c.iloc[:,0]
    return c
def get_high(df):
    c = df['High']
    if isinstance(c, pd.DataFrame):
        return c.iloc[:,0]
    return c
def get_low(df):
    c = df['Low']
    if isinstance(c, pd.DataFrame):
        return c.iloc[:,0]
    return c

def build():
    df = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True).dropna().tail(80)
    close = get_close(df)
    open_ = get_open(df)
    high = get_high(df)
    low = get_low(df)

    price = float(close.iloc[-1])
    ema = float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    rsi = float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])

    entry = price - 0.8 if price < ema else price + 0.8
    sl = entry + 6 if price < ema else entry - 6
    tp = entry - 9 if price < ema else entry + 9

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

    txt = f"""🔴 بيع SELL 🔥🔥🔥
💰 {price:.2f}
🎯 دخول {entry:.1f} | وقف {sl:.1f} | هدف {tp:.1f}
RSI: {rsi:.1f} | EMA20: {ema:.1f}
OB: دعم و مقاومة على الشارت"""
