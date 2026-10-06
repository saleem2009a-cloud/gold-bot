import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V60 FIX AUTO_ON", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS = set()
LAST_ALERT = {}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4147.0

def get_data():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        q = r['chart']['result'][0]['indicators']['quote'][0]
        c = np.array([x for x in q['close'] if x is not None], float)[-60:]
        o = np.array([x for x in q['open'] if x is not None], float)[-60:]
        h = np.array([x for x in q['high'] if x is not None], float)[-60:]
        l = np.array([x for x in q['low'] if x is not None], float)[-60:]
        return o,h,l,c
    except Exception as e:
        print(f"data err {e}")
        return None,None,None,None

def detect_engulfing(o,c):
    try:
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1<0.5: return "لا يوجد ابتلاع واضح", False, "لا يوجد"
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.999) and (c2<=o1*1.001) and body2>body1*1.3
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.001) and (c2>=o1*0.999) and body2>body1*1.3
        if bear: return "🔴 ابتلاع بيعي مؤكد ✅", True, "بيع"
        if bull: return "🟢 ابتلاع شرائي مؤكد ✅", True, "شراء"
        return "لا يوجد ابتلاع واضح", False, "لا يوجد"
    except: return "لا ابتلاع", False, "لا يوجد"

def find_fvg(h,l,price):
    bulls=[]; bears=[]
    for i in range(2,len(h)):
        if l[i] > h[i-2] and 1.0 < (l[i]-h[i-2]) < 7:
            mid=(h[i-2]+l[i])/2
            if abs(mid-price)<20: bulls.append((h[i-2],l[i],mid,abs(mid-price)))
        if h[i] < l[i-2] and 1.0 < (l[i-2]-h[i]) < 7:
            mid=(h[i]+l[i-2])/2
            if abs(mid-price)<20: bears.append((h[i],l[i-2],mid,abs(mid-price)))
    bull = min(bulls, key=lambda x: x[3]) if bulls else None
    bear = min(bears, key=lambda x: x[3]) if bears else None
    return bull, bear

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    s = ma(c,3)-ma(c,6)
    lo = ma(c,3)-ma(c,24)
    return s, lo, f"15د:{s:+.1f}$ | 2س:{lo:+.1f}$"

def check_signal():
    price=get_price()
    o,h,l,c=get_data()
    if o is None:
        return {"price":price,"main":"انتظار","score":3,"txt":"لا بيانات - Yahoo محجوب","can_trade":False,"trend":""}
    eng_txt, eng_ok, eng_side = detect_engulfing(o,c)
    bull_fvg, bear_fvg = find_fvg(h,l,price)
    short, long_, trend_txt = get_trend(c)

    if eng_ok and eng_side=="بيع" and short<0:
        main="بيع"; score=9; reason=f"{eng_txt} + ترند نازل"
    elif eng_ok and eng_side=="شراء" and short>0:
        main="شراء"; score=9; reason=f"{eng_txt} + ترند طالع"
    elif short<-1.8 and long_<-3:
        main="بيع"; score=7; reason=f"ترند هابط قوي {trend_txt}"
    elif short>1.8 and long_>3:
        main="شراء"; score=7; reason=f"ترند صاعد قوي {trend_txt}"
    else:
        main="انتظار"; score=3; reason=f"سوق عرضي {trend_txt} - لا ابتلاع"

    can_trade = main!="انتظار"

    if main=="بيع":
        entry = bear_fvg[2] if bear_fvg and abs(bear_fvg[2]-price)<12 else price
        sl=entry+12; tp1=entry-12; tp2=entry-24
        txt = f"🔴 V60 {main} | سكور {score}/10\n{reason}\n{trend_txt}\n{eng_txt}\n\n🎯 دخول {entry:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n💰 الحالي {price:.1f}"
    elif main=="شراء":
        entry = bull_fvg[2] if bull_fvg and abs(bull_fvg[2]-price)<12 else price
        sl=entry-12; tp1=entry+12; tp2=entry+24
        txt = f"🟢 V60 {main} | سكور {score}/10\n{reason}\n{trend_txt}\n{eng_txt}\n\n🎯 دخول {entry:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n💰 الحالي {price:.1f}"
    else:
        txt = f"⛔ V60 انتظار | سكور {score}/10\n{reason}\n{trend_txt}\n{eng_txt}\n💰 الحالي {price:.1f}\nانتظر ترند واضح"

    return {"price":price,"main":main,"score":score,"txt":txt,"can_trade":can_trade,"trend":trend_txt,"eng":eng_txt}

# كل الأوامر هون - هاد كان ناقص
@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    AUTO_CHATS.add(m.chat.id)
    data=check_signal()
    bot.send_message(m.chat.id, data["txt"])

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id)
    LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id, "✅ V60 المراقبة شغالة\nكل 3 دقايق بفحص السوق\nاذا في توصية قوية 7+ ببعتلك تلقائي\n/وقف للإيقاف\n\nجرب هلا /tawsiya")

@bot.message_handler(commands=['auto_off','وقف','stop'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id, "⛔ وقفت المراقبة")

@bot.message_handler(commands=['help','مساعدة'])
def help_cmd(m):
    bot.send_message(m.chat.id, "/tawsiya - توصية فورية\n/auto_on - شغل المراقبة\n/auto_off - وقف المراقبة")

def auto_watcher():
    while True:
        try:
            time.sleep(180)
            if not AUTO_CHATS: continue
            data=check_signal()
            if not data["can_trade"]: continue
            if data["score"]<7: continue
            now=time.time()
            for chat_id in list(AUTO_CHATS):
                if now-LAST_ALERT.get(chat_id,0) < 900: continue
                try:
                    bot.send_message(chat_id, f"🚨 تنبيه تلقائي 🚨\n{data['txt']}")
                    LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e:
            print(f"watcher err {e}")
            time.sleep(10)

@app.route('/')
def home(): return "V60 AUTO FIXED OK"

def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except Exception as e:
            print(f"polling err {e}")
            time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
