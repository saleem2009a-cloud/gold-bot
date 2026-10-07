import os, requests, time, numpy as np
from datetime import datetime, timezone
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V70 FINAL FIX", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS=set(); LAST_ALERT={}
LAST_SIDE={"side":"انتظار","time":0,"price":0}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4108.0

def get_data_full():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=10).json()
        res=r['chart']['result'][0]
        ts=np.array(res['timestamp'])
        q=res['indicators']['quote'][0]
        c=np.array([x for x in q['close'] if x is not None],float)
        o=np.array([x for x in q['open'] if x is not None],float)
        h=np.array([x for x in q['high'] if x is not None],float)
        l=np.array([x for x in q['low'] if x is not None],float)
        v=np.array([x for x in q['volume'] if x is not None],float)
        n=len(c); ts=ts[-n:]
        return o[-80:],h[-80:],l[-80:],c[-80:],v[-80:],ts[-80:]
    except Exception as e:
        print(f"data err {e}")
        return None,None,None,None,None,None

def get_orb_levels(o,h,l,ts):
    try:
        orb_h=[]; orb_l=[]
        for i, t in enumerate(ts):
            dt=datetime.fromtimestamp(int(t), tz=timezone.utc)
            if dt.hour==8 and dt.minute<30:
                orb_h.append(h[i]); orb_l.append(l[i])
        if len(orb_h)>=3:
            return max(orb_h), min(orb_l), True
        return None,None,False
    except: return None,None,False

def detect_engulfing(o,c):
    try:
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        b1=abs(c1-o1); b2=abs(c2-o2)
        if b1<0.4: return "لا ابتلاع",False,"لا يوجد"
        bear=(c1>o1)and(c2<o2)and b2>b1*1.2
        bull=(c1<o1)and(c2>o2)and b2>b1*1.2
        if bear: return "🔴 ابتلاع بيعي ✅",True,"بيع"
        if bull: return "🟢 ابتلاع شرائي ✅",True,"شراء"
    except: pass
    return "لا ابتلاع",False,"لا يوجد"

def find_fvg(h,l,price):
    try:
        bulls=[]; bears=[]
        for i in range(2,len(h)):
            if l[i]>h[i-2] and 1<(l[i]-h[i-2])<7:
                mid=(h[i-2]+l[i])/2
                if abs(mid-price)<20: bulls.append((h[i-2],l[i],mid,abs(mid-price)))
            if h[i]<l[i-2] and 1<(l[i-2]-h[i])<7:
                mid=(h[i]+l[i-2])/2
                if abs(mid-price)<20: bears.append((h[i],l[i-2],mid,abs(mid-price)))
        bull=min(bulls,key=lambda x:x[3]) if bulls else None
        bear=min(bears,key=lambda x:x[3]) if bears else None
        return bull,bear
    except: return None,None

def detect_order_flow(o,h,l,c,v):
    try:
        buy_vol=np.sum(v[-10:][c[-10:]>o[-10:]])
        sell_vol=np.sum(v[-10:][c[-10:]<o[-10:]])
        total=buy_vol+sell_vol or 1
        delta=(buy_vol-sell_vol)/total*100
        ob_txt="لا OB"
        for i in range(len(c)-5,len(c)-1):
            if c[i]>o[i] and c[i+1]<o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.4:
                ob_txt=f"OB بيعي {h[i]:.1f}"; break
            if c[i]<o[i] and c[i+1]>o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.4:
                ob_txt=f"OB شرائي {l[i]:.1f}"; break
        sweep="لا يوجد"; of_side="انتظار"
        if h[-2]>np.max(h[-12:-2]) and c[-1]<h[-2]-1.2: sweep="كسر قمة وهمي 🔴"; of_side="بيع"
        elif l[-2]<np.min(l[-12:-2]) and c[-1]>l[-2]+1.2: sweep="كسر قاع وهمي 🟢"; of_side="شراء"
        else:
            if delta>=35: of_side="شراء"
            elif delta<=-35: of_side="بيع"
        txt=f"OF Delta {delta:+.0f}% | {ob_txt} | {sweep}"
        return of_side,txt,delta
    except: return "انتظار","OF خطأ",0

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    last=ma(c,3); s=last-ma(c,6); m=last-ma(c,12); lo=last-ma(c,24)
    return s,m,lo,f"15د:{s:+.1f}$ 1س:{m:+.1f}$ 2س:{lo:+.1f}$"

def check_signal():
    try:
        global LAST_SIDE
        price=get_price()
        o,h,l,c,v,ts=get_data_full()
        if o is None:
            return {"txt":f"⛔ انتظار\nالسعر {price}\nلا بيانات","can":False,"score":0,"main":"انتظار"}

        orb_high,orb_low,orb_ok=get_orb_levels(o,h,l,ts)
        eng_txt,eng_ok,eng_side=detect_engulfing(o,c)
        bull_fvg,bear_fvg=find_fvg(h,l,price)
        of_side,of_txt,delta=detect_order_flow(o,h,l,c,v)
        short,mid,long_,trend_txt=get_trend(c)

        orb_txt="ORB: نايم"; orb_side="لا يوجد"
        if orb_ok:
            if price>orb_high+1.5 and short>0: orb_side="شراء"; orb_txt=f"ORB اختراق {orb_high:.1f} ✅"
            elif price<orb_low-1.5 and short<0: orb_side="بيع"; orb_txt=f"ORB كسر {orb_low:.1f} ✅"
            else: orb_txt=f"ORB داخل {orb_low:.1f}-{orb_high:.1f} ⏳"
        else: orb_txt="ORB: خارج وقت لندن"

        votes=[]
        if eng_ok: votes.append(eng_side)
        if short>1.2: votes.append("شراء")
        elif short<-1.2: votes.append("بيع")
        if abs(delta)>=35:
            if delta>0: votes.append("شراء")
            else: votes.append("بيع")
        if orb_side!="لا يوجد": votes.append(orb_side)

        buy_v=votes.count("شراء"); sell_v=votes.count("بيع")

        # فلتر 1: سوق ميت
        if abs(short)<0.8:
            return {"txt":f"⛔ V70 انتظار سوق ميت\n{trend_txt}\n{eng_txt}\n{of_txt}\n🏦 {orb_txt}\n💰 {price:.1f}\nER منخفض","can":False,"score":2,"main":"انتظار"}
        # فلتر 2: تضارب فريمات
        if (short>0 and long_<-2) or (short<0 and long_>2):
            return {"txt":f"⛔ V70 انتظار تضارب فريمات\n{trend_txt}\n{eng_txt}\n{of_txt}\n💰 {price:.1f}\n⏳ 15د عكس 2س","can":False,"score":3,"main":"انتظار"}
        # فلتر 3: لازم توافق 2/4
        if max(buy_v,sell_v)<2:
            return {"txt":f"⛔ V70 انتظار توافق ضعيف {max(buy_v,sell_v)}/4\n{trend_txt}\n{eng_txt}\n{of_txt}\n🏦 {orb_txt}\n💰 {price:.1f}\n⏳ لازم 2/4","can":False,"score":3,"main":"انتظار"}

        score=3
        if eng_ok: score+=2
        if abs(short)>1.5: score+=1
        if abs(long_)>5: score+=2
        if abs(delta)>=35: score+=2
        if orb_side!="لا يوجد": score+=2
        if max(buy_v,sell_v)==4: score=10
        elif max(buy_v,sell_v)==3: score=9
        elif max(buy_v,sell_v)==2: score=7
        if score>10: score=10

        if buy_v>=2 and sell_v==0: main="شراء"
        elif sell_v>=2 and buy_v==0: main="بيع"
        else: main="انتظار"

        now=time.time()
        if LAST_SIDE["side"]!="انتظار" and main!="انتظار" and LAST_SIDE["side"]!=main and (now-LAST_SIDE["time"])<600 and abs(price-LAST_SIDE["price"])<6:
            return {"txt":f"⛔ V70 انتظار مانع تقلب 10د\nاخر اشارة {LAST_SIDE['side']} عند {LAST_SIDE['price']:.1f}\n{trend_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if main!="انتظار": LAST_SIDE={"side":main,"time":now,"price":price}

        if main=="بيع":
            if bear_fvg and bear_fvg[3]<=6: entry=bear_fvg[2]; fvg_info=f"{bear_fvg[0]:.1f}-{bear_fvg[1]:.1f} ✅"
            else: entry=price; fvg_info="فوري"
            txt=f"🔴 V70 {main} سكور {score}/10 توافق {max(buy_v,sell_v)}/4\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 {fvg_info}\n🏦 {orb_txt}\n\n🎯 {entry:.1f} 🛑 {entry+12:.1f} ✅ {entry-12:.1f}/{entry-24:.1f}\n💰 {price:.1f}"
        elif main=="شراء":
            if bull_fvg and bull_fvg[3]<=6: entry=bull_fvg[2]; fvg_info=f"{bull_fvg[0]:.1f}-{bull_fvg[1]:.1f} ✅"
            else: entry=price; fvg_info="فوري"
            txt=f"🟢 V70 {main} سكور {score}/10 توافق {max(buy_v,sell_v)}/4\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 {fvg_info}\n🏦 {orb_txt}\n\n🎯 {entry:.1f} 🛑 {entry-12:.1f} ✅ {entry+12:.1f}/{entry+24:.1f}\n💰 {price:.1f}"
        else:
            txt=f"⛔ V70 انتظار تضارب اصوات {buy_v}/{sell_v}\n{trend_txt}\n{eng_txt}\n{of_txt}\n🏦 {orb_txt}\n💰 {price:.1f}"
        return {"txt":txt,"can":main!="انتظار" and score>=7,"score":score,"main":main}
    except Exception as e:
        print(f"err {e}")
        return {"txt":f"⛔ خطأ {e}","can":False,"score":0,"main":"انتظار"}

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    AUTO_CHATS.add(m.chat.id); bot.send_message(m.chat.id, check_signal()["txt"])
@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V70 شغال\n- لازم توافق 2/4\n- Delta 35%\n- مانع تضارب فريمات\n- مانع سوق ميت\n- ارسال تلقائي 3د")
@bot.message_handler(commands=['auto_off','وقف','stop'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id); bot.send_message(m.chat.id,"⛔ وقفت")
def watcher():
    while True:
        time.sleep(180)
        if not AUTO_CHATS: continue
        d=check_signal()
        if not d["can"] or d["score"]<7: continue
        now=time.time()
        for cid in list(AUTO_CHATS):
            if now-LAST_ALERT.get(cid,0)<900: continue
            try: bot.send_message(cid,f"🚨 V70 تنبيه قوي 🚨\n{d['txt']}"); LAST_ALERT[cid]=now
            except: pass
@app.route('/')
def home(): return "V70 OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=watcher,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
