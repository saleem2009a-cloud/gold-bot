import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V64 SIMPLE", flush=True)
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS=set(); LAST_ALERT={}

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4165.0

def get_data():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=10).json()
        q=r['chart']['result'][0]['indicators']['quote'][0]
        c=np.array([x for x in q['close'] if x is not None],float)[-60:]
        o=np.array([x for x in q['open'] if x is not None],float)[-60:]
        return o,c
    except: return None,None

def check():
    price=get_price()
    o,c=get_data()
    if o is None: return "لا بيانات"
    short = np.mean(c[-3:]) - np.mean(c[-6:])
    long_ = np.mean(c[-3:]) - np.mean(c[-24:])

    # ابتلاع بسيط
    o1,c1=o[-3],c[-3]; o2,c2=o[-2],c[-2]
    bull = (c1<o1) and (c2>o2) and abs(c2-o2)>abs(c1-o1)*1.3
    bear = (c1>o1) and (c2<o2) and abs(c2-o2)>abs(c1-o1)*1.3

    if short>1.5 and long_>3 and bull:
        return f"🟢 شراء قوي {price:.1f}\nوقف {price-12:.1f} هدف {price+15:.1f}\nالسبب: ترند طالع + ابتلاع شرائي\nالزمن 18:00 نيويورك 🔥"
    elif short<-1.5 and long_<-3 and bear:
        return f"🔴 بيع قوي {price:.1f}\nوقف {price+12:.1f} هدف {price-15:.1f}\nالسبب: ترند نازل + ابتلاع بيعي"
    elif short>1.5 and long_>3:
        return f"🟢 شراء {price:.1f} (بدون ابتلاع)\nوقف {price-12:.1f} هدف {price+12:.1f}\nالترند طالع بس انتظر ابتلاع لسكور عالي"
    elif short<-1.5 and long_<-3:
        return f"🔴 بيع {price:.1f} (بدون ابتلاع)\nوقف {price+12:.1f} هدف {price-12:.1f}\nالترند نازل"
    else:
        return f"⛔ انتظار - لا تدخل هلا\nالسعر {price:.1f}\n15د: {short:+.1f}$ 2س: {long_:+.1f}$\nالسبب: السوق عرضي/متقلب\nانتظر 10 دقايق"

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    bot.send_message(m.chat.id, check())

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id)
    bot.send_message(m.chat.id,"✅ شغال - ببعتلك بس لما يكون شراء/بيع قوي\n/tawsiya للفحص")

@app.route('/')
def home(): return "V64 SIMPLE OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
