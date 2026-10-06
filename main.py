import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.9 FIXED FVG", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4156.0

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
        print(e)
        return None,None,None,None

def detect_engulfing(o,c):
    try:
        o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
        body1=abs(c1-o1); body2=abs(c2-o2)
        if body1<0.5: return "لا ابتلاع", False, "لا يوجد"
        bear = (c1>o1) and (c2<o2) and (o2>=c1*0.999) and (c2<=o1*1.001) and body2>body1*1.2
        bull = (c1<o1) and (c2>o2) and (o2<=c1*1.001) and (c2>=o1*0.999) and body2>body1*1.2
        if bear: return "🔴 ابتلاع بيعي مؤكد", True, "بيع"
        if bull: return "🟢 ابتلاع شرائي مؤكد", True, "شراء"
        return "لا ابتلاع", False, "لا يوجد"
    except: return "لا ابتلاع", False, "لا يوجد"

def find_nearest_fvg(h,l,price):
    bulls=[]; bears=[]
    for i in range(2,len(h)):
        # شرائي: فجوة صاعدة
        if l[i] > h[i-2] and (l[i]-h[i-2])>1.0 and (l[i]-h[i-2])<8:
            mid = (h[i-2]+l[i])/2
            dist = abs(mid-price)
            if dist<25: bulls.append((h[i-2], l[i], mid, dist))
        # بيعي: فجوة هابطة
        if h[i] < l[i-2] and (l[i-2]-h[i])>1.0 and (l[i-2]-h[i])<8:
            mid = (h[i]+l[i-2])/2
            dist = abs(mid-price)
            if dist<25: bears.append((h[i], l[i-2], mid, dist))
    # خذ الأقرب للسعر
    bull_fvg = min(bulls, key=lambda x: x[3]) if bulls else None
    bear_fvg = min(bears, key=lambda x: x[3]) if bears else None
    return bull_fvg, bear_fvg

def get_trend(c):
    def ma(a,n): return np.mean(a[-n:])
    s = ma(c,3)-ma(c,6)
    lo = ma(c,3)-ma(c,24)
    return s, lo, f"15د:{s:+.1f}$ 2س:{lo:+.1f}$"

def check():
    price=get_price()
    o,h,l,c = get_data()
    if o is None: return "لا بيانات"
    eng_txt, eng_ok, eng_side = detect_engulfing(o,c)
    bull_fvg, bear_fvg = find_nearest_fvg(h,l,price)
    short, long_, trend_txt = get_trend(c)

    # تحديد الرئيسي
    if eng_ok and eng_side=="بيع" and short<0: main="بيع"; score=8
    elif eng_ok and eng_side=="شراء" and short>0: main="شراء"; score=8
    elif short<-2 and long_<-2: main="بيع"; score=7
    elif short>2 and long_>2: main="شراء"; score=7
    else: main="انتظار"; score=3

    # مناطق منطقية قريبة
    if bear_fvg:
        sell_entry = bear_fvg[2] # منتصف الفجوة
        sell_sl = bear_fvg[1]+4
        sell_tp1 = sell_entry-12
        sell_tp2 = sell_entry-25
        sell_txt = f"{bear_fvg[0]:.1f}-{bear_fvg[1]:.1f} (قريب {bear_fvg[3]:.0f}$)"
    else:
        sell_entry = price
        sell_sl = price+12
        sell_tp1 = price-12
        sell_tp2 = price-24
        sell_txt = "لا يوجد قريب - بيع فوري"

    if bull_fvg:
        buy_entry = bull_fvg[2]
        buy_sl = bull_fvg[0]-4
        buy_tp1 = buy_entry+12
        buy_tp2 = buy_entry+25
        buy_txt = f"{bull_fvg[0]:.1f}-{bull_fvg[1]:.1f} (قريب {bull_fvg[3]:.0f}$)"
    else:
        buy_entry = price
        buy_sl = price-12
        buy_tp1 = price+12
        buy_tp2 = price+24
        buy_txt = "لا يوجد قريب - شراء فوري"

    # تصحيح: اذا الدخول بعيد اكتر من 10$ عن السعر، لا تعطيه
    if abs(sell_entry-price)>15:
        sell_txt += " ⚠️ بعيد"
        sell_entry=price; sell_sl=price+12; sell_tp1=price-12; sell_tp2=price-24
    if abs(buy_entry-price)>15:
        buy_txt += " ⚠️ بعيد"
        buy_entry=price; buy_sl=price-12; buy_tp1=price+12; buy_tp2=price+24

    txt = f"""✅ V58.9 {main} | سكور {score}/10
{eng_txt}
📊 {trend_txt}

📦 FVG قريب من السعر:
🟢 شراء: {buy_txt}
🔴 بيع: {sell_txt}

— — — — —
🔴 بيع:
دخول {sell_entry:.1f} وقف {sell_sl:.1f}
هدف1 {sell_tp1:.1f} هدف2 {sell_tp2:.1f}

🟢 شراء:
دخول {buy_entry:.1f} وقف {buy_sl:.1f}
هدف1 {buy_tp1:.1f} هدف2 {buy_tp2:.1f}

💰 الحالي {price:.1f}
{main} - {eng_txt}
"""
    return txt

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    txt=check()
    bot.send_message(m.chat.id, txt)

@app.route('/')
def home(): return "V58.9 FIXED"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
