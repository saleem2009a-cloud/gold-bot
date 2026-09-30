import os, requests, time, numpy as np
from datetime import datetime, timedelta
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print(f"V38 FIXED VP+FLOW", flush=True)

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

def get_volume_profile(df, bins=30):
    try:
        close=get_series(df,'Close'); high=get_series(df,'High'); low=get_series(df,'Low')
        # اذا مافي فوليوم نستخدم 1 لكل شمعة
        if 'Volume' in df.columns:
            vol=get_series(df,'Volume')
            if vol.sum()==0 or vol.isna().all(): vol=pd.Series([1]*len(df), index=df.index)
        else: vol=pd.Series([1]*len(df), index=df.index)
        vol = vol.fillna(1)
        p_min = float(low.min()); p_max = float(high.max())
        if p_max==p_min: return None,None,None,None,None
        hist, edges = np.histogram(close, bins=bins, range=(p_min, p_max), weights=vol)
        if hist.sum()==0: return None,None,None,None,None
        poc_idx = int(np.argmax(hist)); poc = (edges[poc_idx] + edges[poc_idx+1])/2
        total = hist.sum(); sorted_idx = np.argsort(hist)[::-1]
        cum=0; va=[]
        for idx in sorted_idx:
            cum+=hist[idx]; va.append(idx)
            if cum >= total*0.7: break
        if not va: return poc,poc,poc,edges,hist
        va_prices = [(edges[i]+edges[i+1])/2 for i in va]
        return poc, max(va_prices), min(va_prices), edges, hist
    except Exception as e:
        print(f"VP error {e}")
        return None,None,None,None,None

def get_order_flow(df):
    try:
        close=get_series(df,'Close'); open_=get_series(df,'Open')
        high=get_series(df,'High'); low=get_series(df,'Low')
        if 'Volume' in df.columns:
            vol=get_series(df,'Volume')
            if vol.sum()==0 or vol.isna().all(): vol=pd.Series([1000]*len(df), index=df.index)
        else: vol=pd.Series([1000]*len(df), index=df.index)
        vol=vol.fillna(1000)
        buy_vol = vol.where(close>=open_, 0); sell_vol = vol.where(close<open_, 0)
        delta = float(buy_vol.tail(20).sum() - sell_vol.tail(20).sum())
        d5 = float(buy_vol.tail(5).sum() - sell_vol.tail(5).sum())
        cvd = float((buy_vol - sell_vol).cumsum().iloc[-1])
        recent_range = float((high.tail(5).max() - low.tail(5).min()))
        recent_vol = float(vol.tail(5).sum())
        avg_vol = float(vol.tail(20).mean()) if len(vol)>=20 else recent_vol
        absorption = recent_vol > avg_vol*1.5 and recent_range < 8
        if d5 > 200: flow_sig = "🟢 شراء مسيطر"
        elif d5 < -200: flow_sig = "🔴 بيع مسيطر"
        elif delta > 0: flow_sig = "🟢 ميول شرائي"
        elif delta < 0: flow_sig = "🔴 ميول بيعي"
        else: flow_sig = "محايد"
        return delta, d5, flow_sig, absorption, cvd
    except: return 0,0,"محايد",False,0

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
        asia_range = asia_high - asia_low
        # صار 35 مو 28 عشان 31 يعتبر ضيق
        is_tight = asia_range <= 35
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
        elif not sweep: txt=f"⛔ لا تفوت - انتظار\nاسيا ضيق {asia_range:.1f}$ ✅\nسعر {price:.1f}"; score=5
        else:
            if is_buy: txt=f"🟢 فوت شراء هلا\n🎯 {price:.1f}\n🛑 {asia_low-4:.1f}\n✅ {price+18:.1f}/{price+35:.1f}\nالسبب: {sweep}"; score=8
            else: txt=f"🔴 فوت بيع هلا\n🎯 {price:.1f}\n🛑 {asia_high+4:.1f}\n✅ {price-18:.1f}/{price-35:.1f}\nالسبب: {sweep}"; score=8
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
    bot.send_message(m.chat.id,"✅ بالخلفية + /vp + /flow شغالين")

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
        last5_high = float(high.tail(5).max()); last5_low = float(low.tail(5).min())
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
        pdf=df.tail(40)
        for i in range(len(pdf)):
            o=float(get_series(pdf,'Open').iloc[i]); h_=float(get_series(pdf,'High').iloc[i]); l_=float(get_series(pdf,'Low').iloc[i]); c=float(get_series(pdf,'Close').iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'; ax.plot([i,i],[l_,h_],color=col,lw=0.8); ax.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax.set_xlim(-1,40); ax.set_xticks([])
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/scalp.png',dpi=180,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
        if price < ema9 < ema21 and rsi < 50:
            sl = last5_high + 3
            if sl - price > 12: sl = price + 7
            t=f"🔴 فوت بيع سكالب\n🎯 {price:.1f}\n🛑 {sl:.1f}\n✅ {price-8:.1f}/{price-15:.1f}"
        elif price > ema9 > ema21 and rsi > 45:
            sl = last5_low - 3
            if price - sl > 12: sl = price - 7
            t=f"🟢 فوت شراء سكالب\n🎯 {price:.1f}\n🛑 {sl:.1f}\n✅ {price+8:.1f}/{price+15:.1f}"
        else:
            t=f"⛔ لا تفوت سكالب\nسعر {price:.1f} RSI {rsi:.0f}"
        with open('/tmp/scalp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=t)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(commands=['vp'])
def vp_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True,group_by='column').dropna().tail(200)
        price=get_live_price() or float(get_series(df,'Close').iloc[-1])
        poc,vah,val,edges,hist = get_volume_profile(df)
        if poc is None:
            bot.send_message(m.chat.id,f"📊 VP ما في داتا كافية هلا سعر {price:.1f} جرب بعد شوي"); return
        fig, (ax1, ax2) = plt.subplots(1,2, figsize=(14,6), gridspec_kw={'width_ratios':[3,1]})
        fig.patch.set_facecolor('#0a0a0a'); ax1.set_facecolor('#0a0a0a'); ax2.set_facecolor('#0a0a0a')
        pdf=df.tail(80)
        for i in range(len(pdf)):
            o=float(get_series(pdf,'Open').iloc[i]); h_=float(get_series(pdf,'High').iloc[i]); l_=float(get_series(pdf,'Low').iloc[i]); c=float(get_series(pdf,'Close').iloc[i])
            col='#00ff7f' if c>=o else '#ff3b3b'; ax1.plot([i,i],[l_,h_],color=col,lw=0.8); ax1.add_patch(Rectangle((i-0.35,min(o,c)),0.7,abs(c-o),fc=col,ec=col))
        ax1.axhline(poc,color='white',lw=2); ax1.axhline(vah,color='magenta',ls='--'); ax1.axhline(val,color='magenta',ls='--')
        ax1.set_title(f"POC {poc:.0f}", color='white'); ax1.set_xticks([])
        ax2.barh((edges[:-1]+edges[1:])/2, hist, height=(edges[1]-edges[0])*0.8, color='cyan', alpha=0.6)
        ax2.axhline(poc,color='white',lw=2); ax2.axhline(vah,color='magenta',ls='--'); ax2.axhline(val,color='magenta',ls='--')
        for s in ax1.spines.values(): s.set_visible(False)
        for s in ax2.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/vp.png',dpi=200,facecolor='#0a0a0a',bbox_inches='tight'); plt.close()
        # توصية
        if price > vah: rec="🔴 فوق القيمة - فوت بيع يرجع ل VAH"
        elif price < val: rec="🟢 تحت القيمة - فوت شراء يرجع ل VAL"
        elif price > poc: rec=f"🟢 فوق POC - فوت شراء هدف {vah:.0f}"
        else: rec=f"🔴 تحت POC - فوت بيع هدف {val:.0f}"
        txt=f"📊 Volume Profile\nPOC {poc:.1f} VAH {vah:.1f} VAL {val:.1f}\nسعر {price:.1f}\n\n{rec}"
        with open('/tmp/vp.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ VP {e}")

@bot.message_handler(commands=['flow'])
def flow_cmd(m):
    CHAT_IDS.add(m.chat.id)
    try:
        df=yf.download("GC=F",period="1d",interval="5m",progress=False,auto_adjust=True,group_by='column').dropna().tail(150)
        price=get_live_price() or float(get_series(df,'Close').iloc[-1])
        delta,d5,flow_sig,absorp,cvd = get_order_flow(df)
        txt=f"📊 Order Flow\nسعر {price:.1f}\n{flow_sig}\nΔ20 {delta:.0f} Δ5 {d5:.0f} CVD {cvd:.0f}\n"
        if absorp:
            txt+=f"⛔ لا تفوت - امتصاص\nفوليوم عالي بدون حركة"
        else:
            if "شراء مسيطر" in flow_sig: txt+=f"🟢 فوت شراء - مشترين قوة"
            elif "بيع مسيطر" in flow_sig: txt+=f"🔴 فوت بيع - بايعين قوة"
            else: txt+=f"⚠️ انتظار - محايد"
        bot.send_message(m.chat.id,txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

@bot.message_handler(func=lambda m: True)
def any_msg(m):
    CHAT_IDS.add(m.chat.id)
    txt,p,s = get_amd_analysis()
    if p:
        with open(p,'rb') as f: bot.send_photo(m.chat.id,f,caption=f"فحصتلك:\n{txt}")
    else: bot.send_message(m.chat.id,txt)

@app.route('/')
def home(): return "V38 FIXED"

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
                        with open(p,'rb') as f: bot.send_photo(cid,f,caption=f"🔔 فرصة\n\n{txt}")
                    except: pass
        except: pass

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_checker,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
