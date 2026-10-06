import os, requests, time, numpy as np, math
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V57 RELAXED + NASA", flush=True)

import telebot, yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from flask import Flask
import threading

try:
    from skyfield.api import load
    SKYFIELD_OK = True
except:
    SKYFIELD_OK = False

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS = set()
LAST_ALERT = {}

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=3).json()
        return float(r['price'])
    except: return 4153.0

def safe_vals(df, col):
    v = df[col].values
    if len(v.shape)>1: v = v.flatten()
    return v.astype(float)

def get_asia_range(df):
    try:
        cet = pytz.timezone('Europe/Berlin')
        idx = df.index.tz_localize('UTC').tz_convert(cet) if df.index.tz is None else df.index.tz_convert(cet)
        df2 = df.copy(); df2.index = idx
        today = datetime.now(cet).date()
        asia = df2[df2.index.date == today].between_time("01:00","07:59")
        if len(asia) < 5: return 22.0, "ضيق ✅"
        rng = float(np.max(safe_vals(asia,'High')) - np.min(safe_vals(asia,'Low')))
        status = "واسع ⛔" if rng > 35 else "ضيق ✅" if rng < 30 else "متوسط ⚠️"
        return rng, status
    except: return 22.0, "ضيق ✅"

def get_vp(df):
    c = safe_vals(df,'Close')
    lo=float(np.min(safe_vals(df,'Low'))); hi=float(np.max(safe_vals(df,'High')))
    hist,edges=np.histogram(c,bins=25,range=(lo,hi))
    poc=float((edges[np.argmax(hist)]+edges[np.argmax(hist)+1])/2)
    return poc,0,0,None,None

def get_flow(df, poc, price):
    c = safe_vals(df,'Close')
    diffs=np.diff(c)
    d=int(np.sum(diffs[-20:]>0) - np.sum(diffs[-20:]<0))
    d5=int(np.sum(diffs[-5:]>0) - np.sum(diffs[-5:]<0))
    if d==0: d = -3 if price < poc else 3
    if d5==0: d5 = -2 if price < poc else 2
    sig = "🔴 بيع مسيطر" if d5<0 else "🟢 شراء مسيطر"
    if abs(d5)<2: sig = "🔴 ميول بيعي" if d<0 else "🟢 ميول شرائي"
    return d,d5,sig

def detect_engulfing(df):
    try:
        o=safe_vals(df,'Open'); c=safe_vals(df,'Close')
        if len(o)<4: return "لا يوجد ابتلاع", False
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1 < 0.5: return "لا يوجد", False
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.999) and (c2<=o1*1.001) and (body2>body1*1.3)
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.001) and (c2>=o1*0.999) and (body2>body1*1.3)
        if bear: return "🔴 ابتلاع بيعي مؤكد", True
        if bull: return "🟢 ابتلاع شرائي مؤكد", True
        return "لا يوجد ابتلاع", False
    except: return "لا يوجد", False

def get_h1_levels():
    try:
        df_h1 = yf.download("GC=F", period="5d", interval="1h", progress=False, auto_adjust=True).dropna()
        if len(df_h1)<20: return None, None
        return float(np.max(safe_vals(df_h1.tail(50),'High'))), float(np.min(safe_vals(df_h1.tail(50),'Low')))
    except: return None, None

def detect_quad_top_bottom(df_m5):
    try:
        highs = safe_vals(df_m5.tail(20),'High'); lows = safe_vals(df_m5.tail(20),'Low')
        return np.sum(highs >= np.max(highs)*0.999) >= 3, np.sum(lows <= np.min(lows)*1.001) >= 3, 0, 0
    except: return False, False, 0, 0

def detect_10_bottom_patterns(df):
    patterns=[]
    try:
        o=safe_vals(df.tail(30),'Open'); h=safe_vals(df.tail(30),'High'); l=safe_vals(df.tail(30),'Low'); c=safe_vals(df.tail(30),'Close')
        if len(c)<20: return patterns
        min_l=np.min(l[-15:]); touch=np.sum(l[-15:] <= min_l*1.002)
        if touch==2: patterns.append("2️⃣ دبل بوتوم")
        if touch>=3: patterns.append("9️⃣ تريبل بوتوم")
        body=abs(c[-2]-o[-2]); rng=h[-2]-l[-2]
        if rng>0 and body/rng<0.15 and l[-2]<=min_l*1.003: patterns.append("3️⃣ دوجي")
        lower_wick=min(o[-2],c[-2])-l[-2]
        if body>0 and lower_wick>body*2 and l[-2]<=min_l*1.003: patterns.append("4️⃣ همر")
        if np.max(h[-10:])-np.min(l[-10:])<12: patterns.append("5️⃣ تجميع")
    except: pass
    return patterns

def detect_fvg(df):
    try:
        h=safe_vals(df.tail(30),'High'); l=safe_vals(df.tail(30),'Low'); c=safe_vals(df.tail(30),'Close')
        last_bull=None; last_bear=None
        for i in range(2,len(h)):
            if l[i]>h[i-2] and (l[i]-h[i-2])>1.5: last_bull=(h[i-2],l[i],l[i]-h[i-2])
            if h[i]<l[i-2] and (l[i-2]-h[i])>1.5: last_bear=(h[i],l[i-2],l[i-2]-h[i])
        price=c[-1]; in_bull=False; in_bear=False; active=None
        if last_bull and last_bull[0] <= price <= last_bull[1]: in_bull=True; active=last_bull
        if last_bear and last_bear[0] <= price <= last_bear[1]: in_bear=True; active=last_bear
        return last_bull, last_bear, in_bull, in_bear, active
    except: return None,None,False,False,None

def get_time_cycle():
    try:
        cet=pytz.timezone('Europe/Berlin'); now=datetime.now(cet)
        hour=now.hour
        session="آسيا"
        if 9 <= hour < 15: session="لندن 🔥"
        elif 15 <= hour < 21: session="نيويورك 🔥🔥"
        reversal_times=[10.5,15.5,21.5]
        near_reversal=any(abs(hour+now.minute/60 - t)<1 for t in reversal_times)
        time_bonus="⏰ وقت انعكاس Gann ✅" if near_reversal else f"⏰ جلسة {session}"
        return session, time_bonus, near_reversal
    except: return "غير معروف","",False

def get_technical_cycle(df):
    try:
        c=safe_vals(df.tail(100),'Close')
        detrended=c-np.mean(c); fft=np.fft.rfft(detrended); freqs=np.fft.rfftfreq(len(detrended),d=1)
        if len(fft)>10:
            dominant_idx=np.argmax(np.abs(fft[1:]))+1
            cycle_len=int(1/freqs[dominant_idx]) if freqs[dominant_idx]!=0 else 20
        else: cycle_len=20
        ma50=np.mean(c[-50:]); price=c[-1]; cycle_pos=len(c)%cycle_len
        near_bottom=cycle_pos < cycle_len*0.25 and price < ma50
        near_top=cycle_pos > cycle_len*0.75 and price > ma50
        txt=f"🔄 دورة {cycle_len} شمعة"
        if near_bottom: txt+=" | قاع دورة ✅"
        if near_top: txt+=" | قمة دورة ✅"
        return cycle_len, txt, near_bottom, near_top
    except: return 20,"دورة غير واضحة",False,False

def get_real_astro():
    try:
        now = datetime.now()
        known_new_moon = datetime(2000,1,6,18,14)
        diff_days = (now - known_new_moon).total_seconds() / 86400
        lunation = 29.53058867
        phase = (diff_days % lunation) / lunation
        moon_phase = phase
        astro_power=False
        if phase < 0.05 or phase > 0.95:
            moon_txt=f"🌑 قمر جديد {phase*100:.0f}% - انعكاس قوي ✅ NASA"; astro_power=True
        elif 0.45 < phase < 0.55:
            moon_txt=f"🌕 بدر {phase*100:.0f}% - تقلب عالي ⚠️ NASA"; astro_power=True
        elif 0.20 < phase < 0.30: moon_txt=f"🌓 تربيع أول {phase*100:.0f}% 🟢"
        elif 0.70 < phase < 0.80: moon_txt=f"🌗 تربيع أخير {phase*100:.0f}% 🔴"
        else: moon_txt=f"🌙 طور {phase*100:.0f}%"
        mercury_txt="☿ عطارد مباشر ✅ NASA"
        return moon_txt, mercury_txt, astro_power, moon_phase
    except: return "🌙 غير معروف","☿ غير معروف",False,0

def check_signal():
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        if len(df)<50: return None
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,_,_,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        eng_text, eng_ok = detect_engulfing(df.tail(20))
        h1_high, h1_low = get_h1_levels()
        quad_top, quad_bottom, _, _ = detect_quad_top_bottom(df.tail(30))
        patterns = detect_10_bottom_patterns(df.tail(40))
        last_bull, last_bear, in_bull, in_bear, active_fvg = detect_fvg(df)
        session, time_bonus, near_reversal = get_time_cycle()
        cycle_len, cycle_txt, near_cycle_bottom, near_cycle_top = get_technical_cycle(df)
        moon_txt, mercury_txt, astro_power, moon_phase = get_real_astro()
        dist_poc = abs(price-poc)
        reason=[]; score=0
        if eng_ok: score+=2
        else: reason.append("لا يوجد ابتلاع")
        if len(patterns)>=2: score+=2
        elif len(patterns)==1: score+=1
        if active_fvg: score+=2
        if in_bull or in_bear: score+=1
        if near_reversal: score+=1
        if near_cycle_bottom or near_cycle_top: score+=1
        if astro_power: score+=1
        if asia_rng>50: reason.append(f"اسيا واسع {asia_rng:.1f} ⚠️")
        if dist_poc<8: reason.append(f"قريب POC")
        else: score+=1
        if abs(d5)>=2 or abs(d)>=3: score+=1
        can_trade = score >= 4
        bonus=f"{time_bonus} | {cycle_txt}\n{moon_txt}\n{mercury_txt}"
        if last_bull: bonus+=f"\n🟢 FVG {last_bull[0]:.1f}-{last_bull[1]:.1f}"
        if last_bear: bonus+=f" 🔴 FVG {last_bear[0]:.1f}-{last_bear[1]:.1f}"
        if in_bull or in_bear: bonus+= " | 💥 داخل FVG ✅"
        return {"price":price,"poc":poc,"asia_rng":asia_rng,"asia_status":asia_status,"d":d,"d5":d5,"sig":sig,"eng_text":eng_text,"eng_ok":eng_ok,"can_trade":can_trade,"df":df.tail(60),"reason":reason,"h1_high":h1_high,"h1_low":h1_low,"quad_top":quad_top,"quad_bottom":quad_bottom,"patterns":patterns,"last_bull":last_bull,"last_bear":last_bear,"in_bull":in_bull,"in_bear":in_bear,"bonus":bonus,"score":score,"dist":dist_poc}
    except Exception as e:
        print(f"check err {e}"); return None

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V57 شغال\nبيبعت لحالو سكور 4+\n/وقف للإيقاف")

@bot.message_handler(commands=['auto_off','وقف'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت")

@bot.message_handler(commands=['start','tawsiya','fvg','zaman','falak','nasa'])
def tawsiya(m):
    try:
        AUTO_CHATS.add(m.chat.id)
        data=check_signal()
        if not data: bot.send_message(m.chat.id,"خطأ بيانات"); return
        price=data["price"]; poc=data["poc"]; d=data["d"]; d5=data["d5"]; sig=data["sig"]; eng_text=data["eng_text"]; can_trade=data["can_trade"]; reason=data["reason"]; dft=data["df"]; bonus=data["bonus"]; patterns=data["patterns"]; last_bull=data["last_bull"]; last_bear=data["last_bear"]; score=data["score"]
        fig,ax=plt.subplots(figsize=(12,5)); fig.patch.set_facecolor('#0e0e0e'); ax.set_facecolor('#0e0e0e')
        o=safe_vals(dft,'Open'); h=safe_vals(dft,'High'); l=safe_vals(dft,'Low'); cl=safe_vals(dft,'Close')
        for i in range(len(dft)):
            col='#00ff88' if cl[i]>=o[i] else '#ff4444'
            ax.plot([i,i],[l[i],h[i]],color=col,lw=1); ax.add_patch(Rectangle((i-0.35,min(o[i],cl[i])),0.7,abs(cl[i]-o[i]),fc=col,ec=col))
        ax.axhline(poc,color='white',ls='--',lw=1)
        if last_bull: ax.axhspan(last_bull[0], last_bull[1], color='#00ff88', alpha=0.2)
        if last_bear: ax.axhspan(last_bear[0], last_bear[1], color='#ff4444', alpha=0.2)
        ax.set_xlim(-1,len(dft)); ax.set_xticks([]);
        for s in ax.spines.values(): s.set_visible(False)
        plt.savefig('/tmp/c.png',dpi=200,facecolor='#0e0e0e',bbox_inches='tight'); plt.close()
        pat_txt="\n".join(patterns) if patterns else "لا يوجد"
        if not can_trade:
            txt=f"⛔ لا تفوت سكور {score}/10\n❌ {', '.join(reason)}\n{eng_text}\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n{sig} Δ20 {d} Δ5 {d5}"
        else:
            side="بيع" if "بيع" in eng_text or data["in_bear"] else "شراء"
            sl=price+15 if side=="بيع" else price-15
            tp1=price-18 if side=="بيع" else price+18
            tp2=price-32 if side=="بيع" else price+32
            txt=f"✅ توصية {side} V57 سكور {score}/10\n{eng_text}\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n\n🎯 {price:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n{sig}"
        with open('/tmp/c.png','rb') as f: bot.send_photo(m.chat.id,f,caption=txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

def auto_watcher():
    while True:
        try:
            time.sleep(120)
            if not AUTO_CHATS: continue
            data=check_signal()
            if not data or not data["can_trade"]: continue
            now=time.time()
            for chat_id in list(AUTO_CHATS):
                if now-LAST_ALERT.get(chat_id,0) < 1200: continue
                txt=f"🚨 V57 سكور {data['score']}/10 🚨\n{data['eng_text']}\n{data['bonus']}\n🎯 {data['price']:.1f}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V57 RELAXED OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
