import os, requests, time, numpy as np
from datetime import datetime
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V70.8 ANTI-FAKE FIX", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS=set(); LAST_ALERT={}; LAST_SIDE={"side":"انتظار","time":0,"price":0}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4126.8

def get_data_full():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=2d&interval=5m"
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
        return o[-100:],h[-100:],l[-100:],c[-100:],v[-100:],ts[-100:]
    except: return None,None,None,None,None,None

def get_rsi(c,p=14):
    try:
        d=np.diff(c); g=np.where(d>0,d,0); ls=np.where(d<0,-d,0)
        return 100-(100/(1+np.mean(g[-p:])/(np.mean(ls[-p:]) or 0.01)))
    except: return 50

def get_structure(h,l,c):
    try:
        last_high=np.max(h[-20:-2]); last_low=np.min(l[-20:-2])
        if c[-1]>last_high+1.5:
            if c[-1]-last_high < 4: return f"كسر وهمي قمة {last_high:.1f}","لا يوجد"
            return f"BOS صاعد كسر {last_high:.1f}","شراء"
        if c[-1]<last_low-1.5:
            if last_low-c[-1] < 4: return f"كسر وهمي قاع {last_low:.1f}","لا يوجد"
            return f"BOS هابط كسر {last_low:.1f}","بيع"
        return "لا كسر", "لا يوجد"
    except: return "لا هيكل","لا يوجد"

def detect_engulfing(o,c):
    try:
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        b1=abs(c1-o1); b2=abs(c2-o2)
        if b1<0.4: return "لا ابتلاع","لا يوجد"
        if (c1>o1)and(c2<o2)and b2>b1*1.2: return "🔴 ابتلاع بيعي","بيع"
        if (c1<o1)and(c2>o2)and b2>b1*1.2: return "🟢 ابتلاع شرائي","شراء"
    except: pass
    return "لا ابتلاع","لا يوجد"

def detect_flow(o,h,l,c,v):
    try:
        bv=np.sum(v[-10:][c[-10:]>o[-10:]]); sv=np.sum(v[-10:][c[-10:]<o[-10:]])
        tot=bv+sv or 1; delta=(bv-sv)/tot*100
        side="انتظار"
        if delta>=40: side="شراء"
        elif delta<=-40: side="بيع"
        return side,f"OF {delta:+.0f}%",delta
    except: return "انتظار","OF خطأ",0

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    last=ma(c,3); s=last-ma(c,6); m=last-ma(c,12); lo=last-ma(c,24)
    er=abs(c[-1]-c[-20]) / (np.sum(np.abs(np.diff(c[-20:]))) or 1)
    return s,m,lo,er,f"15د:{s:+.1f}$ 1س:{m:+.1f}$ 2س:{lo:+.1f}$ ER:{er:.2f}"

def check_signal():
    global LAST_SIDE
    try:
        price=get_price()
        o,h,l,c,v,ts=get_data_full()
        if o is None: return {"txt":f"⛔ لا بيانات {price}","can":False,"score":0,"main":"انتظار"}

        struct_txt,struct_side=get_structure(h,l,c)
        eng_txt,eng_side=detect_engulfing(o,c)
        flow_side,flow_txt,delta=detect_flow(o,h,l,c,v)
        short,mid,long_,er,trend_txt=get_trend(c)

        votes=[];
        if eng_side!="لا يوجد": votes.append(eng_side)
        if short>1.2: votes.append("شراء")
        elif short<-1.2: votes.append("بيع")
        if flow_side!="انتظار": votes.append(flow_side)
        if struct_side!="لا يوجد": votes.append(struct_side)

        buy_v=votes.count("شراء"); sell_v=votes.count("بيع")
        if buy_v>sell_v: main="شراء"
        elif sell_v>buy_v: main="بيع"
        else: main="انتظار"

        # === فلاتر V70.8 الجديدة ضد العكس ===
        if er < 0.35:
            return {"txt":f"⛔ V70.8 يشخبط ER {er:.2f} لا تدخل\n{trend_txt}\n{flow_txt}\n💰 {price:.1f}","can":False,"score":2,"main":"انتظار"}
        if "وهمي" in struct_txt:
            return {"txt":f"⏳ V70.8 كسر وهمي - استنى\n{struct_txt}\n{trend_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if eng_side=="لا يوجد" and "BOS" not in struct_txt:
            return {"txt":f"⛔ V70.8 ما في تأكيد\n{trend_txt}\n{eng_txt} | {flow_txt} | {struct_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if main=="بيع" and (mid>0 or long_>-2):
            return {"txt":f"⛔ V70.8 الفريمات عكس لا تبيع\n1س {mid:+.1f}$ 2س {long_:+.1f}$\n{trend_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if main=="شراء" and (mid<0 or long_<2):
            return {"txt":f"⛔ V70.8 الفريمات عكس لا تشتري\n1س {mid:+.1f}$ 2س {long_:+.1f}$\n{trend_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if max(buy_v,sell_v)<2:
            return {"txt":f"⛔ V70.8 توافق ضعيف {max(buy_v,sell_v)}/4\n{trend_txt}\n{eng_txt}\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}

        score=7
        if eng_side!="لا يوجد": score+=1
        if abs(delta)>50: score+=1
        if er>0.5: score+=1
        if score>10: score=10

        now=time.time()
        if LAST_SIDE["side"]!=main and LAST_SIDE["side"]!="انتظار" and (now-LAST_SIDE["time"])<900 and abs(price-LAST_SIDE["price"])<8:
            return {"txt":f"⛔ مانع تقلب 15د\n💰 {price:.1f}","can":False,"score":3,"main":"انتظار"}
        if main!="انتظار": LAST_SIDE={"side":main,"time":now,"price":price}

        if main=="بيع":
            txt=f"🔴 V70.8 {main} {score}/10 توافق {sell_v}/4\n{trend_txt}\n{struct_txt}\n{eng_txt}\n{flow_txt}\n🎯 {price:.1f} 🛑 {price+12:.1f} ✅ {price-12:.1f}/{price-24:.1f}\n💰 {price:.1f}"
        else:
            txt=f"🟢 V70.8 {main} {score}/10 توافق {buy_v}/4\n{trend_txt}\n{struct_txt}\n{eng_txt}\n{flow_txt}\n🎯 {price:.1f} 🛑 {price-12:.1f} ✅ {price+12:.1f}/{price+24:.1f}\n💰 {price:.1f}"
        return {"txt":txt,"can":True,"score":score,"main":main}
    except Exception as e:
        return {"txt":f"⛔ خطأ {e}","can":False,"score":0,"main":"انتظار"}

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    bot.send_message(m.chat.id, check_signal()["txt"])
@bot.message_handler(commands=['auto_on'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); bot.send_message(m.chat.id,"✅ V70.8 شغال - فلتر قوي")
@bot.message_handler(commands=['auto_off'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id); bot.send_message(m.chat.id,"⛔ وقف")

def watcher():
    while True:
        time.sleep(180)
        if not AUTO_CHATS: continue
        d=check_signal()
        if not d["can"] or d["score"]<8: continue
        now=time.time()
        for cid in list(AUTO_CHATS):
            if now-LAST_ALERT.get(cid,0)<1200: continue
            try: bot.send_message(cid,f"🚨 V70.8 🚨\n{d['txt']}"); LAST_ALERT[cid]=now
            except: pass

from flask import Flask
app = Flask(__name__)
@app.route('/')
def home(): return "V70.8 OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=watcher,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
