import os, requests, time
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V29 EMA BUY-SELL BALANCED", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
CHAT_IDS = set()

def get_series(df,col):
    s=df[col]
    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
    return s.squeeze()

def find_zones(df):
    close=get_series(df,'Close'); open_=get_series(df,'Open'); high=get_series(df,'High'); low=get_series(df,'Low')
    zones=[]
    for i in range(30, len(df)-5):
        if close.iloc[i-1] < open_.iloc[i-1]:
            if all(close.iloc[i+j] > open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and high.iloc[i-1] < low.iloc[i+1]:
                    zones.append({'type':'DEMAND','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
        if close.iloc[i-1] > open_.iloc[i-1]:
            if all(close.iloc[i+j] < open_.iloc[i+j] for j in range(4)):
                avg = np.mean([abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)])
                if avg > 1.2 and low.iloc[i-1] > high.iloc[i+1]:
                    zones.append({'type':'SUPPLY','low':float(low.iloc[i-1]),'high':float(high.iloc[i-1]),'idx':i-1})
    return zones[-6:]

def get_live_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=4).json()
        return float(r['price'])
    except:
        try:
            df=yf.download("GC=F",period="1d",interval="1m",progress=False,auto_adjust=True).dropna()
            c=df['Close']
            if isinstance(c,pd.DataFrame): c=c.iloc[:,0]
            return float(c.iloc[-1])
        except: return None

def build_scalp():
    df = yf.download("GC=F", period="1d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(100)
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    price=float(close.iloc[-1]); ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1]); ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1]); rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]); atr=float(ta.volatility.AverageTrueRange(high,low,close,14).average_true_range().iloc[-1])
    recent_low=float(low.tail(10).min()); recent_high=float(high.tail(10).max())
    if price > ema9 > ema21 and 45 < rsi < 68 and price - recent_low < 4: return f"🟢 سكالب شراء دخول {price:.1f} وقف {recent_low-1:.1f} هدف {price+atr*1.8:.1f}", price, recent_low-1, price+atr*1.8, "BUY"
    if price < ema9 < ema21 and 32 < rsi < 55 and recent_high - price < 4: return f"🔴 سكالب بيع دخول {price:.1f} وقف {recent_high+1:.1f} هدف {price-atr*1.8:.1f}", price, recent_high+1, price-atr*1.8, "SELL"
    return None, None, None, None, None

def get_time_cycle_analysis(df):
    cet = pytz.timezone('Europe/Berlin'); now = datetime.now(cet); hour = now.hour
    if 8 <= hour < 11: kz=f"🌟 لندن {now.strftime('%H:%M CET')}"
    elif 14 <= hour < 17: kz=f"🌟 نيويورك {now.strftime('%H:%M CET')} - سيولة عالية"
    else: kz=f"⏳ خارج الكيلزون {now.strftime('%H:%M CET')}"
    try:
        low_series = get_series(df,'Low'); bars = 200 - int(low_series.tail(200).argmin()); gann = bars % 90
        gann_txt = f"Gann: {bars} شمعة - {gann}/90 {'⚠️ انعكاس' if gann>75 else f'باقي {90-gann}'}"
    except: gann_txt = f"Gann: {now.strftime('%H:%M')}"
    return f"📅 الزمني: {kz}\n⏰ {gann_txt}\n📆 {now.strftime('%A %d %B')}"

def get_astro_analysis():
    cet = pytz.timezone('Europe/Berlin'); now = datetime.now(cet)
    known_new_moon = datetime(2024,1,11,tzinfo=pytz.UTC); days = (now.astimezone(pytz.UTC) - known_new_moon).days; lunar = days % 29.53
    moon="🌕 بدر - ذروة - بيع" if 14<lunar<22 else "🌑 محاق" if lunar<7 else "🌓 تربيع"
    return f"🔮 الفلكي: {moon}\n🪐 اليوم: {['شمس - ذهب قوي','قمر','مريخ','عطارد','مشتري','زهرة','زحل'][now.weekday()]}"

def get_pro_technical(df, price, ema20, rsi):
    high=get_series(df,'High'); low=get_series(df,'Low')
    recent_high = float(high.tail(50).max()); recent_low = float(low.tail(50).min())
    bos = "BOS هابط قوي" if price < recent_low*1.002 else "BOS صاعد" if price > recent_high*0.998 else "عرضي"
    atr = float(ta.volatility.AverageTrueRange(high,low,get_series(df,'Close'),14).average_true_range().iloc[-1])
    return f"📈 الفني: {bos} (H {recent_high:.0f} / L {recent_low:.0f}) | RSI {rsi:.0f} | ATR {atr:.1f}$"

def get_daily_candle_strategy():
    try:
        dfd = yf.download("GC=F", period="10d", interval="1d", progress=False, auto_adjust=True, group_by='column').dropna()
        high = get_series(dfd,'High'); low = get_series(dfd,'Low')
        prev_high = float(high.iloc[-2]); prev_low = float(low.iloc[-2]); prev_50 = (prev_high + prev_low) / 2
        live = get_live_price()
        price = live if live else float(get_series(dfd,'Close').iloc[-1])
        txt = f"📜 اليومية: قمة {prev_high:.0f} | قاع {prev_low:.0f} | 50% {prev_50:.0f} | هلا {price:.0f}\n"
        if price >= prev_high - 10: txt += f"🔴 عند القمة - بيع ✅ {price:.0f} هدف {prev_50:.0f} ثم {prev_low:.0f}"
        elif price <= prev_low + 10: txt += f"🟢 عند القاع - شراء ✅ {price:.0f} هدف {prev_50:.0f} ثم {prev_high:.0f}"
        elif price > prev_50: txt += f"🔴 فوق 50% - انتظار بيع عند {prev_high:.0f}"
        else: txt += f"🟢 تحت 50% - انتظار شراء عند {prev_low:.0f}" if price>prev_low else f"🟢 تحت القاع - شراء وهمي ✅ {price:.0f} هدف {prev_50:.0f}"
        return txt
    except Exception as e: return f"📜 يومية: خطأ {e}"

# ===== EMA 9/21 مصلحة تعطي بيع وشراء =====
def get_ema_cross_strategy():
    try:
        df = yf.download("GC=F", period="5d", interval="5m", progress=False, auto_adjust=True, group_by='column').dropna().tail(300)
        close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
        ema9_s = ta.trend.EMAIndicator(close,9).ema_indicator()
        ema21_s = ta.trend.EMAIndicator(close,21).ema_indicator()
        e9 = float(ema9_s.iloc[-1]); e21 = float(ema21_s.iloc[-1])
        e9_prev = float(ema9_s.iloc[-2]); e21_prev = float(ema21_s.iloc[-2])
        price = float(close.iloc[-1])
        live = get_live_price()
        if live: price = live

        swing_high = float(high.tail(100).max()); swing_low = float(low.tail(100).min())
        fib_50 = (swing_high + swing_low)/2

        recent_low = float(low.tail(30).min())
        recent_high = float(high.tail(30).max())
        lows = []; highs = []
        for i in range(20, len(df)-5):
            h = float(get_series(df,'High').iloc[i]); l = float(get_series(df,'Low').iloc[i])
            if h == float(get_series(df,'High').iloc[i-2:i+3].max()): highs.append(h)
            if l == float(get_series(df,'Low').iloc[i-2:i+3].min()): lows.append(l)
        sup = max([x for x in lows if x < price], default=recent_low)
        res = min([x for x in highs if x > price], default=recent_high)

        txt = f"📊 EMA9/21 (الفيديو الجديد):\n"
        txt += f"ابيض EMA9 {e9:.1f} | ازرق EMA21 {e21:.1f} | سعر {price:.1f}\n"
        txt += f"فيبو 50% {fib_50:.0f} | دعم {sup:.0f} | مقاومة {res:.0f}\n"

        # المنطق الجديد المتوازن - السعر اهم من التقاطع
        if price < e9 and price < e21:
            # السعر تحت الاتنين = هبوط قوي - بيع
            sl = res if res > price else e21 + 6
            if abs(res - price) < 25:
                txt += f"🔴 السعر تحت EMA9 و EMA21 - هبوط قوي ✅ بيع مباشر\n🎯 دخول {price:.1f} | 🛑 {sl:.1f} | ✅ {price - (sl-price)*1.5:.1f}\n💡 السبب: تحت الابيض والازرق + مقاومة {res:.0f} + خصم"
            else:
                txt += f"🔴 السعر تحت EMA9 و EMA21 - هبوط قوي ✅ بيع مباشر\n🎯 دخول {price:.1f} | 🛑 {e21+5:.1f} | ✅ {price-18:.1f}\n💡 مقاومة قادمة {res:.0f}"
        elif price > e9 and price > e21:
            # السعر فوق الاتنين = صعود قوي - شراء
            sl = sup if sup < price else e21 - 6
            txt += f"🟢 السعر فوق EMA9 و EMA21 - صعود قوي ✅ شراء مباشر\n🎯 دخول {price:.1f} | 🛑 {sl:.1f} | ✅ {price + (price-sl)*1.5:.1f}\n💡 السبب: فوق الابيض والازرق + دعم {sup:.0f}"
        else:
            # السعر بين EMA9 و EMA21 = انتظار تقاطع
            if e9 > e21:
                txt += f"🟡 السعر بين EMA9 و EMA21 - ترند صاعد ضعيف\n⏳ انتظر اختراق فوق {e9:.0f} للشراء او كسر تحت {e21:.0f} للبيع\nدعم {sup:.0f} | مقاومة {res:.0f}"
            else:
                txt += f"🟡 السعر بين EMA9 و EMA21 - ترند هابط ضعيف\n⏳ انتظر كسر تحت {e9:.0f} للبيع او اختراق فوق {e21:.0f} للشراء\nدعم {sup:.0f} | مقاومة {res:.0f}"

        return txt
    except Exception as e:
        return f"📊 EMA: خطأ {e}"

def build():
    live=get_live_price()
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=True,group_by='column').dropna().tail(300)
    close=get_series(df,'Close'); price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1]); rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    zones=find_zones(df); demands = [z for z in zones if z['type']=='DEMAND']; supplys = [z for z in zones if z['type']=='SUPPLY']
    best_demand = demands[-1] if demands else None; best_supply = supplys[-1] if supplys else None
    fig,ax=plt.subplots(figsize=(12,6)); fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(100); c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i]); col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8); ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    for z in zones[-4:]: col='#00ff7f30' if z['type']=='DEMAND' else '#ff3b3b30'; ax.axhspan(z['low'],z['high'],color=col)
    if best_supply: ax.axhline((best_supply['low']+best_supply['high'])/2,color='white',ls='--',lw=1.2)
    if best_demand: ax.axhline((best_demand['low']+best_demand['high'])/2,color='white',ls='--',lw=1.2)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=190,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
    scalp_txt, _, _, _, _ = build_scalp()
    cet = pytz.timezone('Europe/Berlin'); now_str = datetime.now(cet).strftime('%H:%M CET %d/%m')
    txt = f"🚨 {now_str}\n💰 {price:.2f} (حي) | EMA20 {ema20:.0f} | RSI {rsi:.0f}\n\n"
    if price < ema20 and rsi < 40: txt+=f"🔴 بيع مباشر هابط NOW ✅ {price:.1f} وقف {ema20+3:.1f} هدف {price-25:.1f}\n\n"
    if best_supply:
        e=(best_supply['low']+best_supply['high'])/2; sl=best_supply['high']+2.5; diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}"
        txt+=f"🔴 بيع مؤسسي {status} SUPPLY {best_supply['low']:.0f}-{best_supply['high']:.0f}\n🎯 {e:.1f} | 🛑 {sl:.1f}\n\n"
    if best_demand:
        e=(best_demand['low']+best_demand['high'])/2; sl=best_demand['low']-2.5; diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}"
        txt+=f"🟢 شراء مؤسسي {status} DEMAND {best_demand['low']:.0f}-{best_demand['high']:.0f}\n🎯 {e:.1f} | 🛑 {sl:.1f}\n\n"
    else: txt+=f"🟢 شراء: لا يوجد DEMAND\n\n"
    if scalp_txt: txt+=f"⚡ سكالب: {scalp_txt}\n\n"
    txt+= get_daily_candle_strategy() + "\n\n"
    txt+= get_ema_cross_strategy() + "\n\n"
    txt+= get_time_cycle_analysis(df) + "\n\n"
    txt+= get_astro_analysis() + "\n\n"
    txt+= get_pro_technical(df, price, ema20, rsi)
    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V29 FIXED"

def auto_check():
    while True:
        time.sleep(300)
        if not CHAT_IDS: continue
        try:
            txt,p = build()
            for cid in list(CHAT_IDS):
                try:
                    with open(p,'rb') as f: bot.send_photo(cid,f,caption=txt)
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
