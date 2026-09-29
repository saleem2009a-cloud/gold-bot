import os, requests, time
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V32 FINAL AMD + SCALP", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
CHAT_IDS = set()
LAST_ALERT = 0

def get_series(df,col):
    s=df[col]
    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
    return s.squeeze()

def get_live_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=3).json()
        return float(r['price'])
    except:
        try:
            df=yf.download("GC=F",period="1d",interval="1m",progress=False,auto_adjust=True).dropna()
            return float(get_series(df,'Close').iloc[-1])
        except: return None

def get_amd_analysis():
    try:
        cet = pytz.timezone('Europe/Berlin')
        now = datetime.now(cet)
        df = yf.download("GC=F", period="3d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(1000)
        if len(df)<200: return None, None, 0
        df.index = df.index.tz_localize('UTC').tz_convert(cet) if df.index.tz is None else df.index.tz_convert(cet)
        close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
        price = get_live_price() or float(close.iloc[-1])

        asia_df = df.between_time("01:00","07:59")
        if len(asia_df)<10: asia_df = df.tail(100)
        asia_high = float(get_series(asia_df,'High').max())
        asia_low = float(get_series(asia_df,'Low').min())
        asia_range = asia_high - asia_low
        is_tight = asia_range <= 22
        asia_score = "✅ ضيق ممتاز" if asia_range <=15 else "✅ ضيق" if is_tight else f"❌ واسع {asia_range:.1f}$ - لا تتداول"

        london_df = df.between_time("08:00","13:30")
        london_high = float(get_series(london_df,'High').max()) if len(london_df)>0 else price
        london_low = float(get_series(london_df,'Low').min()) if len(london_df)>0 else price

        sweep_type = None
        if len(london_df)>0:
            last_close = float(get_series(london_df,'Close').iloc[-1])
            if london_high > asia_high + 2 and last_close < asia_high:
                sweep_type = f"🔄 سحب قمة اسيا {asia_high:.0f} -> {london_high:.0f} ثم رجوع - تلاعب بيعي"
            elif london_low < asia_low - 2 and last_close > asia_low:
                sweep_type = f"🔄 سحب قاع اسيا {asia_low:.0f} -> {london_low:.0f} ثم رجوع - تلاعب شرائي"
        if not sweep_type:
            sweep_type = f"⏳ لم يتم سحب سيولة - قمة اسيا {asia_high:.0f} قاع {asia_low:.0f} | لندن H {london_high:.0f} L {london_low:.0f}"

        ny_df = df.between_time("14:30","18:00").tail(100)
        entry_signal = None; sl = tp1 = tp2 = None

        if is_tight and sweep_type and "🔄" in sweep_type and len(ny_df)>15:
            for i in range(len(ny_df)-10, len(ny_df)-3):
                try:
                    if float(get_series(ny_df,'Low').iloc[i+2]) > float(get_series(ny_df,'High').iloc[i]):
                        fvg_low = float(get_series(ny_df,'High').iloc[i])
                        fvg_high = float(get_series(ny_df,'Low').iloc[i+2])
                        c1 = float(get_series(ny_df,'Close').iloc[i+2]); o1 = float(get_series(ny_df,'Open').iloc[i+2])
                        c0 = float(get_series(ny_df,'Close').iloc[i+1])
                        if c1 > o1 and c1 > c0 and "شرائي" in sweep_type:
                            entry_signal = f"🟢 شراء قوي - Order Block + FVG {fvg_low:.0f}-{fvg_high:.0f} + ابتلاع"
                            sl = fvg_low - 4; tp1 = price + 18; tp2 = price + 32; break
                except: pass
            for i in range(len(ny_df)-10, len(ny_df)-3):
                try:
                    if float(get_series(ny_df,'High').iloc[i+2]) < float(get_series(ny_df,'Low').iloc[i]):
                        fvg_high = float(get_series(ny_df,'Low').iloc[i])
                        fvg_low = float(get_series(ny_df,'High').iloc[i+2])
                        c1 = float(get_series(ny_df,'Close').iloc[i+2]); o1 = float(get_series(ny_df,'Open').iloc[i+2])
                        c0 = float(get_series(ny_df,'Close').iloc[i+1])
                        if c1 < o1 and c1 < c0 and "بيعي" in sweep_type:
                            entry_signal = f"🔴 بيع قوي - Order Block + FVG {fvg_low:.0f}-{fvg_high:.0f} + ابتلاع"
                            sl = fvg_high + 4; tp1 = price - 18; tp2 = price - 32; break
                except: pass

        fig,ax=plt.subplots(figsize=(13,6))
        fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(150)
        c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
        for i in range(len(pdf)):
            o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'
            ax.plot([i,i],[l,h],color=col,lw=0.8)
            ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.axhline(asia_high,color='#ffaa00',ls='--',lw=1.2,alpha=0.8)
        ax.axhline(asia_low,color='#00aaff',ls='--',lw=1.2,alpha=0.8)
        ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/chart.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

        txt = f"🧠 AMD SMART {now.strftime('%H:%M CET %d/%m')} | سعر {price:.1f}\n\n"
        txt += f"1️⃣ اسيا (01-08): رينج {asia_range:.1f}$ - {asia_score}\n HIGH {asia_high:.1f} LOW {asia_low:.1f}\n\n"
        txt += f"2️⃣ لندن (08-13:30): {sweep_type}\n\n"
        if entry_signal and sl:
            txt += f"3️⃣ نيويورك: {entry_signal}\n🚀 توصية ممتازة 8/10\n🎯 دخول {price:.1f}\n🛑 وقف {sl:.1f}\n✅ هدف1 {tp1:.1f} | هدف2 {tp2:.1f}\n"
            score = 8
        else:
            if not is_tight: txt += f"3️⃣ نيويورك: ⛔ لا تتداول - اسيا واسع\n"; score=2
            elif "⏳" in sweep_type: txt += f"3️⃣ نيويورك: ⏳ انتظار سحب سيولة\n"; score=4
            else: txt += f"3️⃣ نيويورك: 🔍 تم السحب - انتظر FVG + ابتلاع\n"; score=6
        return txt, '/tmp/chart.png', score
    except Exception as e:
        return f"خطأ AMD {e}", None, 0

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"🧠 عم حلل AMD: اسيا + لندن + نيويورك...")
        txt,p,score = get_amd_analysis()
        if p:
            with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
        else: bot.send_message(m.chat.id,txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['scalp'])
def scalp_now(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"⚡ عم فحص 5د هلا...")
        df = yf.download("GC=F", period="1d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(100)
        close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
        price = get_live_price() or float(close.iloc[-1])
        ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
        ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
        rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
        recent_low = float(low.tail(10).min()); recent_high = float(high.tail(10).max())

        fig,ax=plt.subplots(figsize=(12,6))
        fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(50)
        for i in range(len(pdf)):
            o=float(get_series(pdf,'Open').iloc[i]); h_=float(get_series(pdf,'High').iloc[i]); l_=float(get_series(pdf,'Low').iloc[i]); c=float(get_series(pdf,'Close').iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'
            ax.plot([i,i],[l_,h_],color=col,lw=0.8)
            ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.set_xlim(-1,50); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/scalp.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

        if price > ema9 > ema21 and 35 < rsi < 65:
            txt = f"⚡ سكالب 5د هلا {price:.1f}\n🟢 شراء فوري\n🎯 {price:.1f}\n🛑 {recent_low-2:.1f}\n✅ {price+12:.1f} | {price+25:.1f}\nRSI {rsi:.0f} EMA9 {ema9:.0f}>EMA21 {ema21:.0f}"
        elif price < ema9 < ema21 and 35 < rsi < 65:
            txt = f"⚡ سكالب 5د هلا {price:.1f}\n🔴 بيع فوري\n🎯 {price:.1f}\n🛑 {recent_high+2:.1f}\n✅ {price-12:.1f} | {price-25:.1f}\nRSI {rsi:.0f} EMA9 {ema9:.0f}<EMA21 {ema21:.0f}"
        else:
            txt = f"⚡ سكالب 5د {price:.1f}\n⏳ لا يوجد دخول واضح\nRSI {rsi:.0f} EMA9 {ema9:.0f} EMA21 {ema21:.0f}\nدعم {recent_low:.0f} مقاومة {recent_high:.0f}\nانتظر ابتلاع + FVG"
        with open('/tmp/scalp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V32 FINAL"

def auto_check():
    global LAST_ALERT
    while True:
        time.sleep(180)
        if not CHAT_IDS: continue
        if time.time() - LAST_ALERT < 3600: continue
        try:
            txt,p,score = get_amd_analysis()
            if score >= 7 and p:
                LAST_ALERT = time.time()
                for cid in list(CHAT_IDS):
                    try:
                        with open(p,'rb') as f: bot.send_photo(cid,f,caption=f"🔔 تنبيه AMD\n{txt}")
                    except: pass
        except: pass

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass

threading.Thread(target=run,daemon=True).start()
threading.Thread(target=auto_check,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
