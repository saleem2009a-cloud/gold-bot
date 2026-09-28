import os, requests, time, math
from datetime import datetime, timezone
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V24 PRO ANALYST + AUTO 5MIN", flush=True)

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

def get_fibo(df):
    high=get_series(df,'High'); low=get_series(df,'Low')
    sw_high=float(high.tail(100).max()); sw_low=float(low.tail(100).min())
    diff=sw_high-sw_low
    return {'0':sw_low,'0.236':sw_low+diff*0.236,'0.618':sw_low+diff*0.618,'1':sw_high,'1.382':sw_high+diff*0.382}, sw_high, sw_low

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
    price=float(close.iloc[-1])
    ema9=float(ta.trend.EMAIndicator(close,9).ema_indicator().iloc[-1])
    ema21=float(ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    atr=float(ta.volatility.AverageTrueRange(high,low,close,14).average_true_range().iloc[-1])
    recent_low=float(low.tail(10).min())
    recent_high=float(high.tail(10).max())
    if price > ema9 > ema21 and 45 < rsi < 68 and price - recent_low < 4:
        entry=price; sl=recent_low - 1; tp=price + (atr*1.8)
        return f"🟢 سكالب شراء دخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}", entry, sl, tp, "BUY"
    if price < ema9 < ema21 and 32 < rsi < 55 and recent_high - price < 4:
        entry=price; sl=recent_high + 1; tp=price - (atr*1.8)
        return f"🔴 سكالب بيع دخول {entry:.1f} وقف {sl:.1f} هدف {tp:.1f}", entry, sl, tp, "SELL"
    return None, None, None, None, None

# ===== تحليل جديد احترافي - ما بيلغي القديم =====
def get_time_cycle_analysis(df):
    now = datetime.now(timezone.utc)
    hour = now.hour
    # ICT Killzone
    if 7 <= hour < 10: kz="🌟 لندن Killzone - سيولة عالية"
    elif 13 <= hour < 16: kz="🌟 نيويورك Killzone - سيولة عالية جدا"
    elif 19 <= hour < 22: kz="🌙 اسيا - سيولة ضعيفة - تجميع"
    else: kz="⏳ خارج الكيلزون - حركة بطيئة"
    # Gann دورة زمنية 90 يوم
    try:
        days_since_low = len(df) - int(get_series(df,'Low').tail(200).idxmin())
        gann = days_since_low % 90
        gann_txt = f"Gann {gann}/90 يوم - {'انعكاس متوقع' if gann>80 else 'باقي '+str(90-gann)+' يوم للانعكاس'}"
    except:
        gann_txt = "Gann: حساب"
    # دورة 5 ايام
    weekday = now.weekday()
    day_txt = ["الاثنين بداية سيولة","الثلاثاء ترند حقيقي","الاربعاء تقلب","الخميس ذروة","الجمعة جني ارباح"][weekday] if weekday<5 else "ويكند"
    return f"📅 الزمني: {kz}\n⏰ {gann_txt}\n📆 اليوم: {day_txt}"

def get_astro_analysis():
    now = datetime.now(timezone.utc)
    # حساب طور القمر مبسط
    known_new_moon = datetime(2024,1,11,tzinfo=timezone.utc)
    days = (now - known_new_moon).days
    lunar = days % 29.53
    if lunar < 7.3: moon="🌑 محاق - تجميع - شراء قادم"
    elif lunar < 14.8: moon="🌓 تربيع اول - صعود"
    elif lunar < 22: moon="🌕 بدر - ذروة - احتمال بيع"
    else: moon="🌗 تربيع اخير - هبوط"
    # يوم كوكبي
    planets = ["شمس - ذهب قوي","قمر - تذبذب","مريخ - حركة عنيفة","عطارد - تذبذب","مشتري - صعود","زهرة - صعود هادئ","زحل - هبوط"]
    planet_day = planets[now.weekday()]
    return f"🔮 الفلكي: {moon}\n🪐 اليوم الكوكبي: {planet_day}\n⚠️ {'تجنب اخبار قوية' if lunar>13 and lunar<16 else 'وضع فلكي مستقر'}"

def get_pro_technical(df, price, ema20, rsi):
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    # ICT BOS
    recent_high = float(high.tail(50).max()); recent_low = float(low.tail(50).min())
    bos = "BOS صاعد" if price > recent_high*0.998 else "BOS هابط" if price < recent_low*1.002 else "عرضي"
    # Divergence
    rsi_series = ta.momentum.RSIIndicator(close,14).rsi()
    div = "تباعد صاعد محتمل" if float(close.iloc[-1]) < float(close.iloc[-10]) and float(rsi_series.iloc[-1]) > float(rsi_series.iloc[-10]) else "لا يوجد تباعد واضح"
    # سيولة
    atr = float(ta.volatility.AverageTrueRange(high,low,close,14).average_true_range().iloc[-1])
    return f"📈 الفني المتقدم:\n- البنية: {bos} (H {recent_high:.0f} / L {recent_low:.0f})\n- RSI {rsi:.0f}: {div}\n- التذبذب ATR {atr:.1f}$ - {'حركة قوية' if atr>12 else 'حركة ضعيفة'}\n- EMA20 {ema20:.0f}: {'فوقه ايجابي' if price>ema20 else 'تحته سلبي'}"

def build():
    live=get_live_price()
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=True,group_by='column').dropna().tail(300)
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
    price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])
    zones=find_zones(df)
    fibo, sw_high, sw_low = get_fibo(df)

    demands = [z for z in zones if z['type']=='DEMAND']
    supplys = [z for z in zones if z['type']=='SUPPLY']
    best_demand = demands[-1] if demands else None
    best_supply = supplys[-1] if supplys else None

    fig,ax=plt.subplots(figsize=(12,6))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(100)
    c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    for z in zones[-4:]:
        col='#00ff7f30' if z['type']=='DEMAND' else '#ff3b3b30'
        ax.axhspan(z['low'],z['high'],color=col)
    for k,v in fibo.items():
        if k in ['0.236','0.618','1','0']:
            ax.axhline(v,color='#3b82f6',ls='--',lw=0.5,alpha=0.6)
    if best_supply: ax.axhline((best_supply['low']+best_supply['high'])/2,color='white',ls='--',lw=1.2)
    if best_demand: ax.axhline((best_demand['low']+best_demand['high'])/2,color='white',ls='--',lw=1.2)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=190,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    scalp_txt, s_entry, s_sl, s_tp, s_dir = build_scalp()

    txt = f"💰 {price:.2f} (حي) | EMA20 {ema20:.0f} | RSI {rsi:.0f}\n\n"

    if best_supply:
        e=(best_supply['low']+best_supply['high'])/2; sl=best_supply['high']+2.5; tp=price-(sl-price)*2
        diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}" if diff>0 else "⏳ فاتت"
        txt+=f"🔴 بيع SELL {status}\n🎯 دخول {e:.1f} | 🛑 {sl:.1f} | ✅ {tp:.1f}\n📊 SUPPLY {best_supply['low']:.0f}-{best_supply['high']:.0f}+FVG\n\n"
    else:
        txt+=f"🔴 بيع: لا يوجد SUPPLY\n\n"

    if best_demand:
        e=(best_demand['low']+best_demand['high'])/2; sl=best_demand['low']-2.5; tp=price+(price-sl)*2
        diff=e-price
        status="✅ ادخل هلا" if abs(diff)<5 else f"⏳ باقي {diff:.0f}$ ل {e:.0f}" if diff<0 else "⏳ فاتت"
        txt+=f"🟢 شراء BUY {status}\n🎯 دخول {e:.1f} | 🛑 {sl:.1f} | ✅ {tp:.1f}\n📊 DEMAND {best_demand['low']:.0f}-{best_demand['high']:.0f}+FVG\n\n"
    else:
        txt+=f"🟢 شراء: لا يوجد DEMAND حاليا\n\n"

    if scalp_txt:
        txt+=f"⚡ سكالب: {scalp_txt}\n\n"
    else:
        txt+=f"⚡ سكالب: ⏳ لا يوجد دخول مضمون هلا\n\n"

    # ===== اضافات جديدة =====
    txt+= get_time_cycle_analysis(df) + "\n\n"
    txt+= get_astro_analysis() + "\n\n"
    txt+= get_pro_technical(df, price, ema20, rsi)

    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    CHAT_IDS.add(m.chat.id)
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل بيع + شراء + سكالب + زمني + فلكي + فني...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}")

@app.route('/')
def home(): return "V24 PRO + AUTO"

def auto_check():
    while True:
        time.sleep(300) # 5 دقايق
        if not CHAT_IDS: continue
        try:
            txt,p = build()
            # هون صار يبعت كل 5 دقايق دائما حتى لو باقي 54$ - لانو هيك طلبت
            for cid in list(CHAT_IDS):
                try:
                    with open(p,'rb') as f:
                        bot.send_photo(cid,f,caption=f"🚨 تحديث تلقائي كل 5 دق\n{txt}")
                except: pass
        except Exception as e:
            print(f"auto {e}", flush=True)

def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass

threading.Thread(target=run,daemon=True).start()
threading.Thread(target=auto_check,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
