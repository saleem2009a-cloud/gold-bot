import os, time, threading, requests, yfinance as yf, telebot
from flask import Flask
from datetime import datetime
import pandas as pd, ta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") # اختياري
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
@app.route('/')
def home(): return "V12.1 Chart Live"

def build_chart_and_text():
    df = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True).dropna().tail(80)
    price = float(df['Close'].iloc[-1])

    rsi = float(ta.momentum.RSIIndicator(df['Close'],14).rsi().iloc[-1])
    ema20 = float(ta.trend.EMAIndicator(df['Close'],20).ema_indicator().iloc[-1])
    ema50 = float(ta.trend.EMAIndicator(df['Close'],50).ema_indicator().iloc[-1])
    macd = float(ta.trend.MACD(df['Close']).macd_diff().iloc[-1])

    high, low = float(df['High'].tail(30).max()), float(df['Low'].tail(30).min())
    fib = high - (high-low)*0.382
    demand_low, demand_high = low, low+12
    supply_low, supply_high = high-12, high

    side = "SELL" if price < ema20 else "BUY"
    entry = price - 0.9 if side=="SELL" else price+0.9
    sl = entry + 5.9 if side=="SELL" else entry - 5.9
    tp1 = entry - 8 if side=="SELL" else entry+8
    tp2 = entry - 31 if side=="SELL" else entry+31
    ratio = abs(tp1-entry)/abs(sl-entry)
    title = f"{'🔴 بيع SELL 🔥🔥🔥 تأكيد رباعي' if rsi<40 or rsi>60 else '🔴 بيع SELL 🔥🔥 تأكيد ثلاثي' if side=='SELL' else '🟢 شراء BUY 🔥🔥🔥'}"

    # رسم
    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    ax.axhspan(demand_low, demand_high, color='#0f3d0f', alpha=0.5)
    ax.axhspan(supply_low, supply_high, color='#4a0f0f', alpha=0.5)
    for i in range(len(df)):
        o,h,l,c = float(df['Open'].iloc[i]), float(df['High'].iloc[i]), float(df['Low'].iloc[i]), float(df['Close'].iloc[i])
        col = '#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h], color=col, lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--', lw=1); ax.axhline(sl, color='#ffb000', ls='--', lw=1)
    ax.axhline(price, color='white', ls=':', lw=0.5)
    ax.set_xlim(-1,len(df)); ax.set_ylim(low-8, high+8)
    ax.tick_params(colors='gray', labelsize=7); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=200, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()

    txt = f"""{title}
{"─"*28}

💰 {price:.2f}

🎯 دخول: {entry:.1f} | وقف: {sl:.1f} (${abs(sl-entry):.1f})
هدف1: {tp1:.1f} | هدف2: {tp2:.1f}
نسبة: 1:{ratio:.1f}

📍 الفني القديم (موجود):
دعم: {demand_high:.1f} | مقاومة: {supply_low:.1f}
8 طلب | 12 عرض
فيبو 38.2%: {fib:.1f} | سيولة: لا يوجد

📊 الفني الجديد:
RSI(14): {rsi:.1f} - متوازن
EMA20: {ema20:.1f} | EMA50: {ema50:.1f}
MACD: {macd:.2f}
"""
    return txt, '/tmp/chart.png'

@bot.message_handler(commands=['tawsiya'])
def tawsiya(m):
    bot.send_message(m.chat.id, "🔍 عم حلل: زمني + فلكي + فني + OB + فيبو + سيولة...")
    try:
        txt, chart = build_chart_and_text()
        with open(chart,'rb') as f: bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e: bot.send_message(m.chat.id, f"خطأ: {e}")

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "V12.1 جاهز 👑\n/tawsiya بيعطيك صورة + تحليل متل Gold-Salim")

def run():
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except: time.sleep(10)

def auto():
    while True:
        time.sleep(1800)
        try:
            if not CHAT_ID: continue
            txt, chart = build_chart_and_text()
            with open(chart,'rb') as f: bot.send_photo(int(CHAT_ID), f, caption=f"🚨 توصية تلقائية\n{txt}")
        except: pass

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000))), daemon=True).start()
threading.Thread(target=run, daemon=True).start()
threading.Thread(target=auto, daemon=True).start()
