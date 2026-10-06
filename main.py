import os, requests, time, numpy as np
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
import telebot
from flask import Flask
import threading
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def get_price():
    try: return float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
    except: return 4164.0

def get_data():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=10).json()
        q=r['chart']['result'][0]['indicators']['quote'][0]
        c=np.array([x for x in q['close'] if x is not None],float)[-60:]
        return c
    except: return None

def check():
    price=get_price()
    c=get_data()
    if c is None: return f"❌ لا بيانات\nالسعر {price}"
    s = np.mean(c[-3:]) - np.mean(c[-6:])
    l = np.mean(c[-3:]) - np.mean(c[-24:])

    if s>1.5 and l>3:
        return f"""🟢 شراء

السعر: {price:.1f}
دخول: {price:.1f}
وقف: {price-12:.1f}
هدف: {price+15:.1f}

ترند 15د صاعد و 2س صاعد"""
    elif s<-1.5 and l<-3:
        return f"""🔴 بيع

السعر: {price:.1f}
دخول: {price:.1f}
وقف: {price+12:.1f}
هدف: {price-15:.1f}

ترند 15د نازل و 2س نازل"""
    else:
        return f"""⛔ انتظار

السعر: {price:.1f}

15د: {s:+.1f}
2س: {l:+.1f}

السوق عرضي
لا تدخل
انتظر 10 دقايق"""

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    bot.send_message(m.chat.id, check())

@app.route('/')
def home(): return "V65 OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)
threading.Thread(target=run_bot,daemon=True).start()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
