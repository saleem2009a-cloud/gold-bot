import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.8 DUAL ZONES", flush=True)

import telebot
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS = set()

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4163.0

def get_data():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        q = r['chart']['result'][0]['indicators']['quote'][0]
        c = np.array([x for x in q['close'] if x is not None], float)[-40:]
        o = np.array([x for x in q['open'] if x is not None], float)[-40:]
        h = np.array([x for x in q['high'] if x is not None], float)[-40:]
        l = np.array([x for x in q['low'] if x is not None], float)[-40:]
        return o,h,l,c
    except: return None,None,None,None

def detect_engulfing(o,c):
    try:
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1<0.6: return "لا ابتلاع", False, "لا يوجد"
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.9995) and (c2<=o1*1.0005) and body2>body1*1.2
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.0005) and (c2>=o1*0.9995) and body2>body1*1.2
        if bear: return "🔴 ابتلاع بيعي", True, "بيع"
        if bull: return "🟢 ابتلاع شرائي", True, "شراء"
        return "لا ابتلاع", False, "لا يوجد"
    except: return "لا ابتلاع", False, "لا يوجد"

def detect_fvg(h,l):
    bull_fvg=None; bear_fvg=None
    for i in range(2,len(h)):
        if l[i] > h[i-2] and (l[i]-h[i-2])>1.2: bull_fvg = (h[i-2], l[i])
        if h[i] < l[i-2] and (l[i-2]-h[i])>1.2: bear_fvg = (h[i], l[i-2])
    return bull_fvg, bear_fvg

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    s = ma(c,3)-ma(c,6)
    lo = ma(c,3)-ma(c,24)
    return s, lo, f"15د:{s:+.1f}$ 2س:{lo:+.1f}$"

def check():
    price=get_price()
    o,h,l,c = get_data()
    if o is None: return {"price":price,"txt":"لا بيانات"}
    eng_txt, eng_ok, eng_side = detect_engulfing(o,c)
    bull_fvg, bear_fvg = detect_fvg(h,l)
    short, long_, trend_txt = get_trend(c)

    # بناء توصيتين
    # 1- بيع
    sell_entry = price
    sell_sl = price+14
    sell_tp1 = price-15
    sell_tp2 = price-28
    if bear_fvg: sell_entry = bear_fvg[0] # بيع من FVG البيعي

    # 2- شراء
    buy_entry = price
    buy_sl = price-14
    buy_tp1 = price+15
    buy_tp2 = price+28
    if bull_fvg: buy_entry = bull_fvg[1] # شراء من FVG الشرائي

    # القرار الرئيسي
    if eng_ok and eng_side=="بيع" and short<0:
        main = "بيع"
        score = 8 if long_<0 else 6
    elif eng_ok and eng_side=="شراء" and short>0:
        main = "شراء"
        score = 8 if long_>0 else 6
    elif short<-2 and long_<-2:
        main="بيع ترند"; score=7
    elif short>2 and long_>2:
        main="شراء ترند"; score=7
    else:
        main="انتظار"; score=3

    txt = f"""✅ V58.8 سكور {score}/10 | {main}
{eng_txt}
📊 {trend_txt}

📦 مناطق FVG:
🟢 شراء FVG: {f'{bull_fvg[0]:.1f}-{bull_fvg[1]:.1f}' if bull_fvg else 'لا يوجد'}
🔴 بيع FVG: {f'{bear_fvg[0]:.1f}-{bear_fvg[1]:.1f}' if bear_fvg else 'لا يوجد'}

— — — — —
🔴 توصية بيع:
دخول: {sell_entry:.1f}
وقف: {sell_sl:.1f}
هدف1: {sell_tp1:.1f} هدف2: {sell_tp2:.1f}

🟢 توصية شراء (معلقة):
دخول: {buy_entry:.1f}
وقف: {buy_sl:.1f}
هدف1: {buy_tp1:.1f} هدف2: {buy_tp2:.1f}

💰 السعر الحالي: {price:.1f}
{ '🔴 ابتلاع بيعي + ترند نازل ✅' if main.startswith('بيع') and eng_ok else '🟢 ابتلاع شرائي + ترند طالع ✅' if main.startswith('شراء') and eng_ok else '⏳ انتظر منطقة FVG' }
"""
    return {"price":price,"txt":txt,"main":main,"score":score}

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    data=check()
    bot.send_message(m.chat.id, data["txt"])

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    bot.send_message(m.chat.id,"✅ V58.8 منطقتين بيع وشراء")

@app.route('/')
def home(): return "V58.8 DUAL ZONES OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
