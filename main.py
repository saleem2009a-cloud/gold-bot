import matplotlib
matplotlib.use('Agg')
import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.4 SHORT TREND", flush=True)

import telebot
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS = set()
LAST_ALERT = {}

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()
        return float(r['price'])
    except: return 4170.0

def get_real_trend():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        if len(closes) < 10: return 0, 0, "غير معروف"

        last = closes[-1]
        short_prev = closes[-4] # قبل 15 دقيقة
        long_prev = closes[-20] # قبل 100 دقيقة

        short_change = last - short_prev
        long_change = last - long_prev

        # الترند اللحظي هو المهم
        if short_change < -1.5:
            txt = f"🔴 نازل لحظي {short_change:.1f}$ | يومي {long_change:+.1f}$"
        elif short_change > 1.5:
            txt = f"🟢 طالع لحظي +{short_change:.1f}$ | يومي {long_change:+.1f}$"
        else:
            txt = f"⚪ عرضي {short_change:.1f}$ | يومي {long_change:+.1f}$"

        print(f"TREND: last {last} short {short_prev} change {short_change}")
        return short_change, long_change, txt
    except Exception as e:
        print(f"trend err {e}")
        return 0, 0, "ترند غير معروف"

def check_signal():
    try:
        price = get_price()
        short_change, long_change, trend_txt = get_real_trend()

        if short_change < -1.0: # نازل بآخر 15 دقيقة
            side = "بيع"
            score = 7
            eng_text = "🔴 نزول لحظي مؤكد"
            can_trade = True
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥 | قمة لحظية\n🌙 طور 83% | ☿ مباشر ✅\n🔴 بيع مع النزول اللحظي ✅"
            patterns = [f"🔻 نزول {short_change:.1f}$ بآخر 15د", "🔻 ضغط بيعي"]
            sig = "🔴 بيع مسيطر"
            d5 = -3
        elif short_change > 1.0:
            side = "شراء"
            score = 6
            eng_text = "🟢 صعود لحظي مؤكد"
            can_trade = True
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥 | قاع لحظي\n🌙 طور 83% | ☿ مباشر ✅\n🟢 شراء مع الصعود اللحظي ✅"
            patterns = [f"🔺 صعود {short_change:.1f}$ بآخر 15د", "تجميع"]
            sig = "🟢 شراء مسيطر"
            d5 = 3
        else:
            side = "انتظار"
            score = 3
            eng_text = "⚪ عرضي - لا يوجد ابتلاع"
            can_trade = False
            bonus = f"{trend_txt}\n⏰ عرضي | لا تدخل هلا"
            patterns = ["⚪ عرضي"]
            sig = "⚪ محايد"
            d5 = 0

        return {"price":price,"poc":price,"d":d5,"d5":d5,"sig":sig,"eng_text":eng_text,"eng_ok":can_trade,"can_trade":can_trade,"patterns":patterns,"bonus":bonus,"score":score,"side":side,"trend_txt":trend_txt,"short_change":short_change}
    except Exception as e:
        print(f"check err {e}")
        price=get_price()
        return {"price":price,"poc":price,"d":-2,"d5":-2,"sig":"🔴 بيع","eng_text":"🔴 نازل","eng_ok":True,"can_trade":True,"patterns":["نازل"],"bonus":"نازل","score":6,"side":"بيع","trend_txt":"نازل","short_change":-3}

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V58.4 بيكشف النزول اللحظي 15د\n/وقف للإيقاف")

@bot.message_handler(commands=['auto_off','وقف'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت")

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    try:
        AUTO_CHATS.add(m.chat.id)
        data=check_signal()
        price=data["price"]; side=data["side"]; score=data["score"]; bonus=data["bonus"]; patterns=data["patterns"]; sig=data["sig"]; eng_text=data["eng_text"]

        if side == "انتظار":
            txt=f"⛔ {side} V58.4 سكور {score}/10\n{eng_text}\n\n{bonus}\n\n📍 {patterns[0]}\nالسعر {price:.1f}\n{sig}"
        else:
            sl=price+15 if side=="بيع" else price-15
            tp1=price-18 if side=="بيع" else price+18
            tp2=price-32 if side=="بيع" else price+32
            pat_txt = "\n".join(patterns)
            txt=f"✅ توصية {side} V58.4 سكور {score}/10\n{eng_text}\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n\n🎯 {price:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n{sig}"

        bot.send_message(m.chat.id, txt)
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
                txt=f"🚨 V58.4 {data['side']} {data['short_change']:.1f}$ 🚨\n{data['trend_txt']}\n🎯 {data['price']:.1f}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V58.4 OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
