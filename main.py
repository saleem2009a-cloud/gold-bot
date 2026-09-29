import os, requests, time
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V31 ULTRA SMART", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
CHAT_IDS = set()
LAST_ALERT = 0 # مشان ما يزعجك كل 5 دقايق

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
            c=get_series(df,'Close')
            return float(c.iloc[-1])
        except: return None

def analyze_tf(tf_name, period, interval):
    try:
        df = yf.download("GC=F", period=period, interval=interval, progress=False, auto_adjust=True, group_by='column').dropna().tail(200)
        if len(df)<50: return None
        close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
        price=float(close.iloc[-1])
        ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
        ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
        rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
        # BOS
        rh=float(high.tail(50).max()); rl=float(low.tail(50).min())
        if price > rh*0.998: bos="صاعد قوي"
        elif price < rl*1.002: bos="هابط قوي"
        elif ema9 > ema21 and price > ema9: bos="صاعد"
        elif ema9 < ema21 and price < ema9: bos="هابط"
        else: bos="عرضي"
        return {"tf":tf_name, "price":price, "ema9":ema9, "ema21":ema21, "rsi":rsi, "bos":bos, "high":rh, "low":rl, "df":df}
    except:
        return None

def get_daily_levels():
    try:
        dfd = yf.download("GC=F", period="10d", interval="1d", progress=False, auto_adjust=True, group_by='column').dropna()
        high=get_series(dfd,'High'); low=get_series(dfd,'Low')
        prev_h=float(high.iloc[-2]); prev_l=float(low.iloc[-2])
        return prev_h, prev_l, (prev_h+prev_l)/2
    except:
        return None,None,None

def build_ultra():
    live=get_live_price()
    # نحلل كل الفريمات
    tfs = [
        analyze_tf("5د", "5d", "5m"),
        analyze_tf("15د", "5d", "15m"),
        analyze_tf("1س", "30d", "60m"),
        analyze_tf("4س", "60d", "240m"),
        analyze_tf("يومي", "30d", "1d"),
    ]
    tfs = [x for x in tfs if x]
    if not tfs: return None, None, 0

    price = live if live else tfs[1]['price'] if len(tfs)>1 else tfs[0]['price']
    prev_h, prev_l, prev_50 = get_daily_levels()

    # حساب نقاط التلاقي - Confluence Score
    score = 0
    reasons = []
    buy_votes = 0
    sell_votes = 0

    for tf in tfs:
        if "صاعد" in tf['bos']:
            buy_votes+=1
            score+=1 if tf['tf'] in ["1س","4س"] else 0.5
        if "هابط" in tf['bos']:
            sell_votes+=1
            score+=1 if tf['tf'] in ["1س","4س"] else 0.5

        # RSI
        if tf['rsi'] < 30:
            buy_votes+=1; reasons.append(f"{tf['tf']} RSI {tf['rsi']:.0f} تشبع بيع")
            score+=1.5
        if tf['rsi'] > 70:
            sell_votes+=1; reasons.append(f"{tf['tf']} RSI {tf['rsi']:.0f} تشبع شراء")
            score+=1.5

    # يومية
    if prev_h and prev_l:
        if price <= prev_l + 12:
            buy_votes+=2; score+=2; reasons.append(f"عند قاع امبارح {prev_l:.0f} - شراء")
        elif price >= prev_h - 12:
            sell_votes+=2; score+=2; reasons.append(f"عند قمة امبارح {prev_h:.0f} - بيع")
        elif price < prev_50:
            buy_votes+=0.5; reasons.append("تحت 50% اليومية")
        else:
            sell_votes+=0.5; reasons.append("فوق 50% اليومية")

    # ترند حقيقي اليوم
    try:
        dfd = yf.download("GC=F", period="5d", interval="1d", progress=False, auto_adjust=True, group_by='column').dropna()
        change = (float(get_series(dfd,'Close').iloc[-1]) - float(get_series(dfd,'Close').iloc[-2]))/float(get_series(dfd,'Close').iloc[-2])*100
        if change > 2: buy_votes+=2; score+=1.5; reasons.append(f"اليوم صاعد قوي +{change:.1f}%")
        if change < -2: sell_votes+=2; score+=1.5; reasons.append(f"اليوم هابط قوي {change:.1f}%")
    except:
        change=0

    # قرار نهائي
    total = buy_votes + sell_votes
    if total==0: return None, None, 0

    # نرسم شارت نظيف
    df = tfs[1]['df'].tail(100) if len(tfs)>1 else tfs[0]['df'].tail(100)
    fig,ax=plt.subplots(figsize=(12,6))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    c_=get_series(df,'Close'); o_=get_series(df,'Open'); h_=get_series(df,'High'); l_=get_series(df,'Low')
    for i in range(len(df)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    if prev_h: ax.axhline(prev_h,color='#ffaa00',ls='--',lw=1,label=f'قمة {prev_h:.0f}')
    if prev_l: ax.axhline(prev_l,color='#00aaff',ls='--',lw=1,label=f'قاع {prev_l:.0f}')
    if prev_50: ax.axhline(prev_50,color='white',ls=':',lw=0.8)
    ax.set_xlim(-1,len(df)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.legend(loc='upper left', fontsize=8, facecolor='#1a1a1a', edgecolor='white', labelcolor='white')
    plt.savefig('/tmp/chart.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    cet = pytz.timezone('Europe/Berlin')
    now = datetime.now(cet).strftime('%H:%M CET %d/%m')

    # بس اذا النقاط 7+ = توصية ممتازة
    confluence = min(10, score)
    if confluence < 6:
        txt = f"🔍 {now}\n💰 {price:.2f} | نقاط {confluence:.1f}/10 - لا يوجد فرصة ممتازة\n\n"
        for tf in tfs:
            txt+=f"{tf['tf']}: {tf['bos']} RSI {tf['rsi']:.0f} | EMA9 {tf['ema9']:.0f} EMA21 {tf['ema21']:.0f}\n"
        txt+=f"\nانتظار تلاقي اقوى..."
        return txt, '/tmp/chart.png', confluence

    if buy_votes > sell_votes:
        sl = price - 15 if prev_l is None else min(price-8, prev_l-5)
        tp1 = price + 20; tp2 = price + 35
        txt = f"🚀🚀 توصية ممتازة {confluence:.1f}/10\n"
        txt+=f"🟢 شراء قوي ✅ {now}\n💰 دخول {price:.1f}\n🛑 وقف {sl:.1f}\n✅ هدف1 {tp1:.1f} | هدف2 {tp2:.1f}\n\n"
        txt+=f"📌 السبب ({len(reasons)} تلاقي):\n" + "\n".join([f"• {r}" for r in reasons[:5]]) + "\n\n"
        for tf in tfs: txt+=f"{tf['tf']}: {tf['bos']} | "
        return txt, '/tmp/chart.png', confluence
    else:
        sl = price + 15 if prev_h is None else max(price+8, prev_h+5)
        tp1 = price - 20; tp2 = price - 35
        txt = f"🚀🚀🚀 توصية ممتازة {confluence:.1f}/10\n"
        txt+=f"🔴 بيع قوي ✅ {now}\n💰 دخول {price:.1f}\n🛑 وقف {sl:.1f}\n✅ هدف1 {tp1:.1f} | هدف2 {tp2:.1f}\n\n"
        txt+=f"📌 السبب ({len(reasons)} تلاقي):\n" + "\n".join([f"• {r}" for r in reasons[:5]]) + "\n\n"
        for tf in tfs: txt+=f"{tf['tf']}: {tf['bos']} | "
        return txt, '/tmp/chart.png', confluence

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"🧠 عم حلل كل الفريمات... 5د 15د 1س 4س يومي")
        txt,p,score = build_ultra()
        if txt and p:
            with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V31 ULTRA"

def auto_check():
    global LAST_ALERT
    while True:
        time.sleep(120) # يشيك كل دقيقتين
        if not CHAT_IDS: continue
        # بس اذا مر ساعة من اخر تنبيه
        if time.time() - LAST_ALERT < 3600: continue
        try:
            txt,p,score = build_ultra()
            if score >= 7: # بس يبعت اذا ممتازة 7+/10
                LAST_ALERT = time.time()
                for cid in list(CHAT_IDS):
                    try:
                        with open(p,'rb') as f: bot.send_photo(cid,f,caption=f"🔔 تنبيه تلقائي\n{txt}")
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
