import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V67 ALL STRATEGIES AUTO", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS=set(); LAST_ALERT={}
LAST_SIDE={"side":"انتظار","time":0,"price":0}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4165.0

def get_data():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=10).json()
        q=r['chart']['result'][0]['indicators']['quote'][0]
        c=np.array([x for x in q['close'] if x is not None],float)[-80:]
        o=np.array([x for x in q['open'] if x is not None],float)[-80:]
        h=np.array([x for x in q['high'] if x is not None],float)[-80:]
        l=np.array([x for x in q['low'] if x is not None],float)[-80:]
        v=np.array([x for x in q['volume'] if x is not None],float)[-80:]
        return o,h,l,c,v
    except Exception as e:
        print(f"data err {e}")
        return None,None,None,None,None

def detect_engulfing(o,c):
    o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
    b1=abs(c1-o1); b2=abs(c2-o2)
    if b1<0.4: return "لا ابتلاع",False,"لا يوجد"
    bear=(c1>o1)and(c2<o2)and(o2>=c1*0.998)and(c2<=o1*1.002)and b2>b1*1.2
    bull=(c1<o1)and(c2>o2)and(o2<=c1*1.002)and(c2>=o1*0.998)and b2>b1*1.2
    if bear: return "🔴 ابتلاع بيعي ✅",True,"بيع"
    if bull: return "🟢 ابتلاع شرائي ✅",True,"شراء"
    return "لا ابتلاع",False,"لا يوجد"

def find_fvg(h,l,price):
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

def detect_order_flow(o,h,l,c,v,price):
    buy_vol=np.sum(v[-10:][c[-10:]>o[-10:]])
    sell_vol=np.sum(v[-10:][c[-10:]<o[-10:]])
    total=buy_vol+sell_vol if total>0 else 1
    total = buy_vol+sell_vol if (buy_vol+sell_vol)>0 else 1
    delta=(buy_vol-sell_vol)/total*100
    ob_side="لا يوجد"; ob_txt="لا OB"
    for i in range(len(c)-5,len(c)-1):
        if c[i]>o[i] and c[i+1]<o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.4:
            ob_side="بيع"; ob_txt=f"OB بيعي {h[i]:.1f}"; break
        if c[i]<o[i] and c[i+1]>o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.4:
            ob_side="شراء"; ob_txt=f"OB شرائي {l[i]:.1f}"; break
    sweep="لا يوجد"
    if h[-2]>np.max(h[-12:-2]) and c[-1]<h[-2]-1.2: sweep="كسر قمة وهمي 🔴"
    elif l[-2]<np.min(l[-12:-2]) and c[-1]>l[-2]+1.2: sweep="كسر قاع وهمي 🟢"
    of_side="انتظار"
    if delta>=25: of_side="شراء"
    elif delta<=-25: of_side="بيع"
    if "🟢" in sweep: of_side="شراء"
    elif "🔴" in sweep: of_side="بيع"
    txt=f"OF Delta {delta:+.0f}% | {ob_txt} | {sweep}"
    return of_side,txt,delta

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    last=ma(c,3); s=last-ma(c,6); m=last-ma(c,12); lo=last-ma(c,24)
    return s,m,lo,f"15د:{s:+.1f}$ 1س:{m:+.1f}$ 2س:{lo:+.1f}$"

def check_signal():
    global LAST_SIDE
    price=get_price()
    o,h,l,c,v=get_data()
    if o is None:
        return {"txt":f"⛔ انتظار\nالسعر {price}\nلا بيانات","can":False,"score":0,"main":"انتظار"}
    eng_txt,eng_ok,eng_side=detect_engulfing(o,c)
    bull_fvg,bear_fvg=find_fvg(h,l,price)
    of_side,of_txt,delta=detect_order_flow(o,h,l,c,v,price)
    short,mid,long_,trend_txt=get_trend(c)

    votes=[]
    if eng_ok: votes.append(eng_side)
    if short>1.2: votes.append("شراء")
    elif short<-1.2: votes.append("بيع")
    if of_side!="انتظار": votes.append(of_side)
    buy_v=votes.count("شراء"); sell_v=votes.count("بيع")

    score=3
    if eng_ok: score+=2
    if abs(short)>1.5: score+=1
    if abs(long_)>5: score+=2
    if of_side!="انتظار": score+=2
    if max(buy_v,sell_v)==3: score=9
    elif max(buy_v,sell_v)==2 and score<7: score=7
    if score>10: score=10

    if sell_v>=2 and short<0: main="بيع"
    elif buy_v>=2 and short>0: main="شراء"
    elif short<-2 and long_<-3: main="بيع"
    elif short>2 and long_>3: main="شراء"
    else: main="انتظار"

    now=time.time()
    if LAST_SIDE["side"]!="انتظار" and main!="انتظار" and LAST_SIDE["side"]!=main and (now-LAST_SIDE["time"])<600 and abs(price-LAST_SIDE["price"])<6:
        main="انتظار"; score=3

    if main!="انتظار": LAST_SIDE={"side":main,"time":now,"price":price}

    if main=="بيع":
        if bear_fvg and bear_fvg[3]<=6: entry=bear_fvg[2]; fvg_info=f"{bear_fvg[0]:.1f}-{bear_fvg[1]:.1f} قريب ✅"
        else: entry=price; fvg_info="دخول فوري - لا FVG قريب"
        txt=f"🔴 V67 {main} سكور {score}/10 توافق {max(buy_v,sell_v)}/3\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 FVG: {fvg_info}\n\n🎯 {entry:.1f} 🛑 {entry+12:.1f} ✅ {entry-12:.1f}/{entry-24:.1f}\n💰 {price:.1f}"
    elif main=="شراء":
        if bull_fvg and bull_fvg[3]<=6: entry=bull_fvg[2]; fvg_info=f"{bull_fvg[0]:.1f}-{bull_fvg[1]:.1f} قريب ✅"
        else: entry=price; fvg_info="دخول فوري - لا FVG قريب"
        txt=f"🟢 V67 {main} سكور {score}/10 توافق {max(buy_v,sell_v)}/3\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 FVG: {fvg_info}\n\n🎯 {entry:.1f} 🛑 {entry-12:.1f} ✅ {entry+12:.1f}/{entry+24:.1f}\n💰 {price:.1f}"
    else:
        txt=f"⛔ V67 انتظار سكور {score}/10\n{trend_txt}\n{eng_txt}\n{of_txt}\n💰 {price:.1f}\n⏳ تضارب - انتظر توافق"

    return {"txt":txt,"can":main!="انتظار" and score>=6,"score":score,"main":main}

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    AUTO_CHATS.add(m.chat.id)
    bot.send_message(m.chat.id, check_signal()["txt"])

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V67 شغال بكل الاستراتيجيات\n1- ابتلاع ✅\n2- ترند 15د+1س+2س ✅\n3- FVG ✅\n4- Order Flow S Tier ✅\n5- مانع تقلب 10د ✅\n6- ارسال تلقائي كل 3د ✅\n\n/tawsiya فحص\n/وقف ايقاف")

@bot.message_handler(commands=['auto_off','وقف','stop'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت المراقبة")

def watcher():
    while True:
        time.sleep(180)
        if not AUTO_CHATS: continue
        d=check_signal()
        if not d["can"] or d["score"]<7: continue
        now=time.time()
        for cid in list(AUTO_CHATS):
            if now-LAST_ALERT.get(cid,0)<900: continue
            try: bot.send_message(cid,f"🚨 تنبيه V67 تلقائي 🚨\n{d['txt']}"); LAST_ALERT[cid]=now
            except: pass

@app.route('/')
def home(): return "V67 ALL OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=watcher,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
