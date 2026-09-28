import os, requests
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V21 SupplyDemand ADDED", flush=True)

import telebot, yfinance as yf, pandas as pd, ta
import matplotlib.pyplot as plt, matplotlib.patches as mpatches
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_series(df,col):
    s=df[col]
    if isinstance(s,pd.DataFrame): s=s.iloc[:,0]
    return s.squeeze()

def find_zones(df):
    """بيلاقي مناطق العرض والطلب المؤسسية حسب الفيديو"""
    close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low'); open_=get_series(df,'Open')
    zones=[]
    for i in range(20, len(df)-5):
        # طلب: 4 شموع خضرا قوية بعد شمعة حمرا
        if all(close.iloc[i+j] > open_.iloc[i+j] for j in range(4)):
            body_sizes = [abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)]
            avg_body = sum(body_sizes)/4
            if avg_body > 1.5: # شمعة كبيرة
                # هل في FVG؟
                if high.iloc[i-1] < low.iloc[i+1]:
                    # كسر هيكل؟
                    if high.iloc[i+3] > high.iloc[i-5:i].max():
                        zone_low = float(low.iloc[i-1])
                        zone_high = float(high.iloc[i-1])
                        zones.append({'type':'DEMAND','low':zone_low,'high':zone_high,'idx':i-1,'fresh':True})
        # عرض: 4 شموع حمرا قوية بعد شمعة خضرا
        if all(close.iloc[i+j] < open_.iloc[i+j] for j in range(4)):
            body_sizes = [abs(close.iloc[i+j]-open_.iloc[i+j]) for j in range(4)]
            avg_body = sum(body_sizes)/4
            if avg_body > 1.5:
                if low.iloc[i-1] > high.iloc[i+1]:
                    if low.iloc[i+3] < low.iloc[i-5:i].min():
                        zone_low = float(low.iloc[i-1])
                        zone_high = float(high.iloc[i-1])
                        zones.append({'type':'SUPPLY','low':zone_low,'high':zone_high,'idx':i-1,'fresh':True})
    return zones[-6:] # اخر 6 مناطق

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

def build():
    live=get_live_price()
    df=yf.download("GC=F",period="5d",interval="15m",progress=False,auto_adjust=True,group_by='column').dropna().tail(250)
    close=get_series(df,'Close'); open_=get_series(df,'Open')
    high=get_series(df,'High'); low=get_series(df,'Low')

    price=live if live else float(close.iloc[-1])
    ema20=float(ta.trend.EMAIndicator(close,20).ema_indicator().iloc[-1])
    ema50=float(ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1])
    rsi=float(ta.momentum.RSIIndicator(close,14).rsi().iloc[-1])

    zones=find_zones(df)
    # تحديد الترند
    is_uptrend = price > ema20 and ema20 > ema50

    # فلترة حسب الترند - بس طلب اذا صاعد، بس عرض اذا هابط
    valid_zones = [z for z in zones if (z['type']=='DEMAND' and is_uptrend) or (z['type']=='SUPPLY' and not is_uptrend)]
    if not valid_zones: valid_zones = zones[-2:] if zones else []

    # اخر منطقة قوية و فريش
    best_zone = valid_zones[-1] if valid_zones else None

    if best_zone:
        if best_zone['type']=='DEMAND':
            direction="🟢 شراء BUY - منطقة طلب مؤسسية"
            entry=(best_zone['low']+best_zone['high'])/2 # دخول هجومي بنص المنطقة
            sl=best_zone['low'] - 2.5
            tp1=price + (price-sl)*2
            tp2=price + (price-sl)*3.5
            reason=f"DEMAND ZONE {best_zone['low']:.1f}-{best_zone['high']:.1f} + FVG + BOS + ترند صاعد"
        else:
            direction="🔴 بيع SELL - منطقة عرض مؤسسية"
            entry=(best_zone['low']+best_zone['high'])/2
            sl=best_zone['high'] + 2.5
            tp1=price - (sl-price)*2
            tp2=price - (sl-price)*3.5
            reason=f"SUPPLY ZONE {best_zone['low']:.1f}-{best_zone['high']:.1f} + FVG + BOS + ترند هابط"
    else:
        # فال باك للقديم اذا ما في مناطق
        is_up = price > ema20
        if is_up:
            direction="🟢 شراء BUY (EMA)"
            entry=price-2; sl=entry-8; tp1=price+12; tp2=price+20
            reason=f"فوق EMA20 {ema20:.1f} - RSI {rsi:.0f}"
        else:
            direction="🔴 بيع SELL (EMA)"
            entry=price+2; sl=entry+8; tp1=price-12; tp2=price-20
            reason=f"تحت EMA20 {ema20:.1f} - RSI {rsi:.0f}"

    # رسم مع المناطق
    fig,ax=plt.subplots(figsize=(11,5.5))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    pdf=df.tail(90)
    c_=get_series(pdf,'Close'); o_=get_series(pdf,'Open'); h_=get_series(pdf,'High'); l_=get_series(pdf,'Low')
    for i in range(len(pdf)):
        o=float(o_.iloc[i]); h=float(h_.iloc[i]); l=float(l_.iloc[i]); c=float(c_.iloc[i])
        col='#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h],color=col,lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
    # رسم المناطق
    for z in zones[-3:]:
        color='#00ff7f40' if z['type']=='DEMAND' else '#ff3b3b40'
        # نحول اندكس المنطقة للرسم الحالي
        ax.axhspan(z['low'],z['high'],color=color,alpha=0.3)
        ax.text(len(pdf)-1, (z['low']+z['high'])/2, z['type'], color='white', fontsize=6)

    ax.axhline(entry,color='white',ls='--',lw=1); ax.axhline(sl,color='#ffb000',ls='--',lw=1); ax.axhline(tp1,color='#00ff7f',ls=':',lw=1)
    ax.set_xlim(-1,len(pdf)); ax.set_xticks([]); ax.tick_params(colors='gray',labelsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()

    src="حي" if live else "فيوتشر"
    txt=f"""{direction}
💰 {price:.2f} ({src})

🎯 دخول هجومي (نص المنطقة): {entry:.1f}
🛑 وقف: {sl:.1f} تحت الظل
✅ هدف1: {tp1:.1f} (1:2)
✅ هدف2: {tp2:.1f} (1:3.5)

📊 استراتيجية العرض والطلب:
{reason}
EMA20 {ema20:.1f} | EMA50 {ema50:.1f} | RSI {rsi:.0f}
Fresh Zones: {len(zones)} منطقة - الاقوى: {best_zone['type'] if best_zone else 'EMA'}

💡 دخول عادي: انتظر اغلاق شمعة برا المنطقة
💡 محافظ: انتظر شمعة ابتلاعية"""
    return txt,'/tmp/chart.png'

@bot.message_handler(commands=['tawsiya','start'])
def h(m):
    try:
        bot.send_message(m.chat.id,"⏳ عم حلل Supply & Demand + EMA + FVG + BOS...")
        txt,p=build()
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id,f"خطأ {e}"); print(e, flush=True)

@app.route('/')
def home(): return "V21 Supply Demand Added"
def run():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: pass
threading.Thread(target=run,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
