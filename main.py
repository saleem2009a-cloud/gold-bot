import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V62 FINAL ALL STRATEGIES", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS=set(); LAST_ALERT={}
LAST_SIDE={"side":"انتظار","time":0,"price":0}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4147.0

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

# 1- استراتيجية الابتلاع القديمة
def detect_engulfing(o,c):
    o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
    b1=abs(c1-o1); b2=abs(c2-o2)
    if b1<0.5: return "لا ابتلاع",False,"لا يوجد"
    bear=(c1>o1)and(c2<o2)and(o2>=c1*0.999)and(c2<=o1*1.001)and b2>b1*1.3
    bull=(c1<o1)and(c2>o2)and(o2<=c1*1.001)and(c2>=o1*0.999)and b2>b1*1.3
    if bear: return "🔴 ابتلاع بيعي مؤكد ✅",True,"بيع"
    if bull: return "🟢 ابتلاع شرائي مؤكد ✅",True,"شراء"
    return "لا ابتلاع واضح",False,"لا يوجد"

# 2- FVG القديم بس مصلح قريب
def find_fvg(h,l,price):
    bulls=[]; bears=[]
    for i in range(2,len(h)):
        if l[i]>h[i-2] and 1.0<(l[i]-h[i-2])<7:
            mid=(h[i-2]+l[i])/2
            if abs(mid-price)<20: bulls.append((h[i-2],l[i],mid,abs(mid-price)))
        if h[i]<l[i-2] and 1.0<(l[i-2]-h[i])<7:
            mid=(h[i]+l[i-2])/2
            if abs(mid-price)<20: bears.append((h[i],l[i-2],mid,abs(mid-price)))
    bull=min(bulls,key=lambda x:x[3]) if bulls else None
    bear=min(bears,key=lambda x:x[3]) if bears else None
    return bull,bear

# 3- استراتيجية جديدة Order Flow S Tier
def detect_order_flow(o,h,l,c,v,price):
    buy_vol=np.sum(v[-10:][c[-10:]>o[-10:]])
    sell_vol=np.sum(v[-10:][c[-10:]<o[-10:]])
    total=buy_vol+sell_vol if (buy_vol+sell_vol)>0 else 1
    delta_pct=(buy_vol-sell_vol)/total*100

    ob_side="لا يوجد"; ob_txt="لا OB"
    for i in range(len(c)-5,len(c)-1):
        if c[i]>o[i] and c[i+1]<o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.5:
            ob_side="بيع"; ob_txt=f"OB بيعي {h[i]:.1f}"; break
        if c[i]<o[i] and c[i+1]>o[i+1] and abs(c[i+1]-o[i+1])>abs(c[i]-o[i])*1.5:
            ob_side="شراء"; ob_txt=f"OB شرائي {l[i]:.1f}"; break

    avg_range=np.mean(h[-10:]-l[-10:]); avg_vol=np.mean(v[-10:])
    absorption = v[-1]>avg_vol*1.8 and (h[-1]-l[-1])<avg_range*0.6

    sweep="لا يوجد"
    if h[-2]>np.max(h[-15:-2]) and c[-1]<h[-2]-1.5: sweep="بيع - كسر قمة وهمي"
    elif l[-2]<np.min(l[-15:-2]) and c[-1]>l[-2]+1.5: sweep="شراء - كسر قاع وهمي"

    of_side="انتظار"
    if delta_pct>30 and ob_side=="شراء": of_side="شراء"
    elif delta_pct<-30 and ob_side=="بيع": of_side="بيع"
    elif delta_pct>40: of_side="شراء"
    elif delta_pct<-40: of_side="بيع"
    elif "شراء" in sweep: of_side="شراء"
    elif "بيع" in sweep: of_side="بيع"

    txt=f"OF: Delta {delta_pct:+.0f}% | {ob_txt} | {'امتصاص✅' if absorption else ''} {sweep}"
    return of_side,txt,delta_pct,ob_txt,sweep

# 4- التنين ترندين قديم
def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    last_ma3=ma(c,3); s=last_ma3-ma(c,6); mid=last_ma3-ma(c,12); lo=last_ma3-ma(c,24)
    txt=f"📊 15د:{s:+.1f}$ | 1س:{mid:+.1f}$ | 2س:{lo:+.1f}$"
    return s,mid,lo,txt

def check_signal():
    global LAST_SIDE
    price=get_price()
    o,h,l,c,v=get_data()
    if o is None:
        return {"txt":"لا بيانات","can":False,"score":0,"main":"انتظار","price":price}

    eng_txt,eng_ok,eng_side=detect_engulfing(o,c)
    bull_fvg,bear_fvg=find_fvg(h,l,price)
    of_side,of_txt,delta,ob,sweep=detect_order_flow(o,h,l,c,v,price)
    short,mid,long_,trend_txt=get_trend(c)

    # حساب السكور مع كل الاستراتيجيات
    score=0
    if eng_ok: score+=3
    if abs(short)>1.8: score+=2
    if abs(long_)>3: score+=2
    if of_side!="انتظار": score+=3
    if eng_ok and of_side==eng_side: score+=2 # توافق

    votes=[]
    if eng_ok: votes.append(eng_side)
    if short<-1.5: votes.append("بيع")
    elif short>1.5: votes.append("شراء")
    if of_side!="انتظار": votes.append(of_side)

    buy_v=votes.count("شراء"); sell_v=votes.count("بيع")

    # قرار واحد واضح
    if sell_v>=2 and short<0:
        main="بيع"; reason=f"توافق {sell_v}/3 استراتيجيات"
    elif buy_v>=2 and short>0:
        main="شراء"; reason=f"توافق {buy_v}/3 استراتيجيات"
    elif short<-1.8 and long_<-2:
        main="بيع"; reason="ترند هابط قوي"
    elif short>1.8 and long_>2:
        main="شراء"; reason="ترند صاعد قوي"
    else:
        main="انتظار"; reason="تضارب"

    # مانع التقلب القديم - ما بغير كل دقيقتين
    now=time.time()
    time_since=now-LAST_SIDE["time"]
    if LAST_SIDE["side"]!="انتظار" and main!="انتظار" and LAST_SIDE["side"]!=main and time_since<600 and abs(price-LAST_SIDE["price"])<5:
        main="انتظار"; reason=f"⏳ ثبّت - كان {LAST_SIDE['side']} من {int(time_since/60)}د - سوق متقلب"
        score=3

    if main!="انتظار" and main==LAST_SIDE.get("side") or score>=5:
        if main!="انتظار":
            LAST_SIDE={"side":main,"time":now,"price":price}

    can=main!="انتظار" and score>=5

    if main=="بيع":
        entry=bear_fvg[2] if bear_fvg and abs(bear_fvg[2]-price)<10 else price
        sl=entry+12; tp1=entry-12; tp2=entry-25
        txt=f"🔴 V62 {main} سكور {score}/10 - {reason}\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 FVG بيع: {bear_fvg[0]:.1f}-{bear_fvg[1]:.1f} " if bear_fvg else f"🔴 V62 {main} سكور {score}/10 - {reason}\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 لا FVG قريب\n"
        txt+=f"\n🎯 دخول {entry:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n💰 الحالي {price:.1f}"
    elif main=="شراء":
        entry=bull_fvg[2] if bull_fvg and abs(bull_fvg[2]-price)<10 else price
        sl=entry-12; tp1=entry+12; tp2=entry+25
        txt=f"🟢 V62 {main} سكور {score}/10 - {reason}\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 FVG شراء: {bull_fvg[0]:.1f}-{bull_fvg[1]:.1f} " if bull_fvg else f"🟢 V62 {main} سكور {score}/10 - {reason}\n{trend_txt}\n{eng_txt}\n{of_txt}\n📦 لا FVG قريب\n"
        txt+=f"\n🎯 دخول {entry:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n💰 الحالي {price:.1f}"
    else:
        txt=f"⛔ V62 انتظار سكور {score}/10 - {reason}\n{trend_txt}\n{eng_txt}\n{of_txt}\n💰 الحالي {price:.1f}\n⏳ انتظر توافق"

    return {"txt":txt,"can":can,"score":score,"main":main,"price":price}

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    AUTO_CHATS.add(m.chat.id)
    bot.send_message(m.chat.id, check_signal()["txt"])

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V62 شغال بكل الاستراتيجيات:\n1- ابتلاع ✅\n2- ترند 15د+2س ✅\n3- FVG ✅\n4- Order Flow S Tier ✅\n5- مانع تقلب ✅\n\n/tawsiya فحص فوري\n/وقف ايقاف")

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
        for chat_id in list(AUTO_CHATS):
            if now-LAST_ALERT.get(chat_id,0)<900: continue
            try: bot.send_message(chat_id,f"🚨 تنبيه V62 🚨\n{d['txt']}"); LAST_ALERT[chat_id]=now
            except: pass

@app.route('/')
def home(): return "V62 ALL STRATEGIES OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=watcher,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
