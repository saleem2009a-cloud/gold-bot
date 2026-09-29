import os, requests, time
from datetime import datetime, timedelta
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V35 FIXED SCALP+AMD", flush=True)

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
        today = now.date(); yest = today - timedelta(days=1)
        today_asia = df[df.index.date == today].between_time("01:00","07:59")
        yest_asia = df[df.index.date == yest].between_time("01:00","07:59")
        asia_df = today_asia if len(today_asia)>=10 and now.hour>=8 else yest_asia if len(yest_asia)>=10 else df.between_time("01:00","07:59").tail(80)
        asia_high = float(get_series(asia_df,'High').max()); asia_low = float(get_series(asia_df,'Low').min())
        asia_range = asia_high - asia_low; is_tight = asia_range <= 28
        london_df = df[df.index.date == today].between_time("08:00","13:30") if now.hour>=8 else df[df.index.date == yest].between_time("08:00","13:30")
        london_high = float(get_series(london_df,'High').max()) if len(london_df)>0 else price
        london_low = float(get_series(london_df,'Low').min()) if len(london_df)>0 else price
        sweep=None; is_buy=False; is_sell=False
        if len(london_df)>0:
            last_close = float(get_series(london_df,'Close').iloc[-1])
            if london_high > asia_high + 2 and last_close < asia_high: sweep=f"سحب قمة {asia_high:.0f}->{london_high:.0f}"; is_sell=True
            elif london_low < asia_low - 2 and last_close > asia_low: sweep=f"سحب قاع {asia_low:.0f}->{london_low:.0f}"; is_buy=True
        fig,ax=plt.subplots(figsize=(13,6)); fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(120); c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
        for i in range(len(pdf)):
            o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'
            ax.plot([i,i],[l,h],color=col,lw=0.8); ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.axhline(asia_high,color='#ffaa00',ls='--',lw=1.2); ax.axhline(asia_low,color='#00aaff',ls='--',lw=1.2)
        ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/chart.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
        if not is_tight: txt=f"⛔ لا تفوت هلا\nالسبب: اسيا واسع {asia_range:.1f}$\nسعر {price:.1f}\nنصيحة: بكرا 08:30 جرب"; score=2
        elif not sweep: txt=f"⛔ لا تفوت - انتظار\nاسيا ضيق {asia_range:.1f}$ ✅\nبس لندن ما سحبت\nاسيا {asia_high:.0f}/{asia_low:.0f} لندن {london_high:.0f}/{london_low:.0f}\nسعر {price:.1f}"; score=5
        else:
            if is_buy: txt=f"🟢 فوت شراء هلا\n🎯 دخول {price:.1f}\n🛑 وقف {asia_low-4:.1f}\n✅ هدف1 {price+18:.1f} هدف2 {price+35:.1f}\nالسبب: {sweep}"; score=8
            else: txt=f"🔴 فوت بيع هلا\n🎯 دخول {price:.1f}\n🛑 وقف {asia_high+4:.1f}\n✅ هدف1 {price-18:.1f} هدف2 {price-35:.1f}\nالسبب: {sweep}"; score=8
        return txt, '/tmp/chart.png', score
    except Exception as e: return f"خطأ {e}", None, 0

@bot.message_handler(commands=['start','tawsiya'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    bot.send_chat_action(m.chat.id,'typing')
    txt,p,s = get_amd_analysis()
    if p:
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    else: bot.send_message(m.chat.id,txt)
    bot.send_message(m.chat.id,"✅ انا بالخلفية كل 3 دقايق اذا صارت فرصة ببعتلك لحالي")

@bot.message_handler(commands=['scalp'])
def sc(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True,group_by='column').dropna().tail(80)
        close=get_series(df,'Close'); low=get_series(df,'Low'); high=get_series(df,'High')
        price=get_live_price() or float(close.iloc[-1])
        ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
        ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
        rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
        # تصليح السكالب - وقف قريب
        last5_high = float(high.tail(5).max())
        last5_low = float(low.tail(5).min())
        atr = float((high.tail(14) - low.tail(14)).mean())
        if atr < 2: atr = 4
        fig,ax=plt.subplots(figsize=(12,5))
        fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(40)
        for i in range(len(pdf)):
            o=float(get_series(pdf,'Open').iloc[i]); h_=float(get_series(pdf,'High').iloc[i]); l_=float(get_series(pdf,'Low').iloc[i]); c=float(get_series(pdf,'Close').iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'; ax.plot([i,i],[l_,h_],color=col,lw=0.8); ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.set_xlim(-1,40); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/scalp.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

        if price < ema9 < ema21 and rsi < 50:
            sl = last5_high + 3 # وقف فوق اخر 5 شمعات بس
            if sl - price > 12: sl = price + 7 # اذا بعيد كتير خلي 7$
            tp1 = price - 8; tp2 = price - 15
            t=f"🔴 فوت بيع سكالب\n\n🎯 دخول {price:.1f}\n🛑 وقف {sl:.1f} ({sl-price:.1f}$)\n✅ هدف1 {tp1:.1f} هدف2 {tp2:.1f}\n\nEMA هابط RSI {rsi:.0f}"
        elif price > ema9 > ema21 and rsi > 45:
            sl = last5_low - 3
            if price - sl > 12: sl = price - 7
            tp1 = price + 8; tp2 = price + 15
            t=f"🟢 فوت شراء سكالب\n\n🎯 دخول {price:.1f}\n🛑 وقف {sl:.1f} ({price-sl:.1f}$)\n✅ هدف1 {tp1:.1f} هدف2 {tp2:.1f}\n\nEMA صاعد RSI {rsi:.0f}"
        else:
            t=f"⛔ لا تفوت سكالب\nسعر {price:.1f} RSI {rsi:.0f}\nالسوق عرضي - انتظار"
        with open('/tmp/scalp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=t)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(func=lambda m: True)
def any_msg(m):
    CHAT_IDS.add(m.chat.id)
    txt,p,s = get_amd_analysis()
    if p:
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=f"فحصتلك:\n{txt}")
    else: bot.send_message(m.chat.id,txt)

@app.route('/')
def home(): return "V35 FIXED"

def auto_checker():
    global LAST_ALERT
    while True:
        time.sleep(180)
        if not CHAT_IDS: continue
        if time.time()-LAST_ALERT < 2700: continue
        try:
            txt,p,s = get_amd_analysis()
            if s>=7 and p:
                LAST_ALERT=time.time()
                for cid in list(CHAT_IDS):
                    try:
                        with open(p,'rb') as f: bot.send_photo(cid,f,caption=f"🔔 فرصة هلا\n\n{txt}")
                    except: pass
        except: pass

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_checker,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
