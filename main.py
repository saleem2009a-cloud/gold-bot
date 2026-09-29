import os, requests, time
from datetime import datetime, timedelta
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V33 FINAL FIXED", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
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
        df = yf.download("GC=F", period="4d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(1200)
        if len(df)<200: return "داتا قليلة", None, 0
        df.index = df.index.tz_localize('UTC').tz_convert(cet) if df.index.tz is None else df.index.tz_convert(cet)
        close=get_series(df,'Close')
        price = get_live_price() or float(close.iloc[-1])

        # === تصليح اسيا - ياخد اسيا اليوم فقط ===
        today = now.date()
        yest = today - timedelta(days=1)

        today_asia = df[df.index.date == today].between_time("01:00","07:59")
        yest_asia = df[df.index.date == yest].between_time("01:00","07:59")

        # اذا اليوم بعد 08:00 خد اسيا اليوم، اذا قبل 08:00 او فاضي خد اسيا امبارح
        if len(today_asia) >= 10 and now.hour >= 8:
            asia_df = today_asia
            asia_label = "اليوم"
        else:
            asia_df = yest_asia if len(yest_asia)>=10 else df.between_time("01:00","07:59").tail(80)
            asia_label = "امبارح"

        asia_high = float(get_series(asia_df,'High').max())
        asia_low = float(get_series(asia_df,'Low').min())
        asia_range = asia_high - asia_low
        is_tight = asia_range <= 22
        asia_score = "✅ ضيق ممتاز" if asia_range <=15 else "✅ ضيق" if is_tight else f"❌ واسع {asia_range:.1f}$"

        london_df = df[df.index.date == today].between_time("08:00","13:30") if now.hour>=8 else df[df.index.date == yest].between_time("08:00","13:30")
        london_high = float(get_series(london_df,'High').max()) if len(london_df)>0 else price
        london_low = float(get_series(london_df,'Low').min()) if len(london_df)>0 else price

        sweep_type = None
        if len(london_df)>0:
            last_close = float(get_series(london_df,'Close').iloc[-1])
            if london_high > asia_high + 2 and last_close < asia_high:
                sweep_type = f"🔄 سحب قمة اسيا {asia_high:.0f} -> {london_high:.0f} ثم رجوع - بيعي"
            elif london_low < asia_low - 2 and last_close > asia_low:
                sweep_type = f"🔄 سحب قاع اسيا {asia_low:.0f} -> {london_low:.0f} ثم رجوع - شرائي"
        if not sweep_type:
            sweep_type = f"⏳ لم يتم سحب - اسيا {asia_high:.0f}/{asia_low:.0f} | لندن H {london_high:.0f} L {london_low:.0f}"

        # شارت
        fig,ax=plt.subplots(figsize=(13,6))
        fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(150)
        c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
        for i in range(len(pdf)):
            o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'
            ax.plot([i,i],[l,h],color=col,lw=0.8)
            ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.axhline(asia_high,color='#ffaa00',ls='--',lw=1.2)
        ax.axhline(asia_low,color='#00aaff',ls='--',lw=1.2)
        ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/chart.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

        txt = f"🧠 AMD SMART {now.strftime('%H:%M %d/%m')} | {price:.1f}\n\n"
        txt += f"1️⃣ اسيا {asia_label} (01-08): {asia_range:.1f}$ {asia_score}\nHIGH {asia_high:.1f} LOW {asia_low:.1f}\n\n"
        txt += f"2️⃣ لندن: {sweep_type}\n\n"
        if not is_tight: txt+=f"3️⃣ ⛔ اسيا واسع - لا تتداول\n"; score=2
        elif "⏳" in sweep_type: txt+=f"3️⃣ ⏳ انتظار سحب سيولة\n"; score=4
        else: txt+=f"3️⃣ 🔍 تم السحب - انتظر FVG+ابتلاع بنيويورك\n"; score=6
        return txt, '/tmp/chart.png', score
    except Exception as e:
        return f"خطأ {e}", None, 0

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    bot.send_message(m.chat.id,"🧠 عم حلل AMD...")
    txt,p,score = get_amd_analysis()
    if p:
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    else: bot.send_message(m.chat.id,txt)

@bot.message_handler(commands=['scalp'])
def scalp_now(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"⚡ فحص 5د...")
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
            txt = f"⚡ سكالب 5د {price:.1f}\n🟢 شراء\n🎯 {price:.1f}\n🛑 {recent_low-2:.1f}\n✅ {price+12:.1f} | {price+25:.1f}\nRSI {rsi:.0f}"
        elif price < ema9 < ema21:
            txt = f"⚡ سكالب 5د {price:.1f}\n🔴 بيع\n🎯 {price:.1f}\n🛑 {recent_high+2:.1f}\n✅ {price-12:.1f} | {price-25:.1f}\nRSI {rsi:.0f} EMA9 {ema9:.0f}<EMA21 {ema21:.0f}"
        else:
            txt = f"⚡ سكالب {price:.1f}\n⏳ لا دخول\nRSI {rsi:.0f} دعم {recent_low:.0f} مقاومة {recent_high:.0f}"
        with open('/tmp/scalp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V33 FIXED"

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
