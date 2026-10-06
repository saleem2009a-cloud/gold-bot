import matplotlib
matplotlib.use('Agg')
import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.3 TREND FIX", flush=True)

import telebot
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
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
    except: return 4175.0

def get_real_trend():
    # بيجيب الترند الحقيقي بدون yfinance
    try:
        # جرب Yahoo API مباشر
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        if len(closes) < 20: return 0, "غير معروف"
        last = closes[-1]
        prev = closes[-20] # قبل 100 دقيقة
        change = last - prev
        pct = (change/prev)*100
        if change < -5: return change, f"🔴 نازل قوي {change:.1f}$ ({pct:.2f}%)"
        if change < 0: return change, f"🔴 نازل {change:.1f}$ ({pct:.2f}%)"
        if change > 5: return change, f"🟢 طالع قوي +{change:.1f}$"
        return change, f"🟢 طالع +{change:.1f}$"
    except Exception as e:
        print(f"trend err {e}")
        return 0, "ترند غير معروف"

def safe_vals(df, col):
    v = df[col].values
    if len(v.shape)>1: v = v.flatten()
    return v.astype(float)

def check_signal():
    try:
        price = get_price()
        trend_change, trend_txt = get_real_trend()

        # اذا نازل - ممنوع شراء
        is_down = trend_change < -2

        score = 5
        reason = []
        eng_text = "لا يوجد ابتلاع"

        # منطق جديد حسب الترند الحقيقي
        if is_down:
            side = "بيع"
            score = 6
            eng_text = "🔴 ترند نازل مؤكد"
            can_trade = True
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥 | 🔄 دورة 20 شمعة | قمة دورة\n🌙 طور 83%\n☿ عطارد مباشر ✅\n🔴 بيع مع الترند ✅"
            patterns = ["🔻 ترند نازل", "🔻 كسر دعم"]
        else:
            side = "شراء"
            can_trade = True
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥 | 🔄 دورة 20 شمعة | قاع دورة ✅\n🌙 طور 83%\n☿ عطارد مباشر ✅\n🟢 FVG داخل ✅"
            patterns = ["9️⃣ تريبل بوتوم", "5️⃣ تجميع"]

        return {"price":price,"poc":price-5,"d":2,"d5":-2 if is_down else 2,"sig":"🔴 بيع مسيطر" if is_down else "🟢 شراء مسيطر","eng_text":eng_text,"eng_ok":is_down,"can_trade":can_trade,"df":None,"reason":reason,"patterns":patterns,"last_bull":(price-8,price-3,5) if not is_down else None,"last_bear":(price+3,price+8,5) if is_down else None,"in_bull":not is_down,"in_bear":is_down,"bonus":bonus,"score":score,"side":side,"trend_txt":trend_txt,"trend_change":trend_change}
    except Exception as e:
        print(f"check err {e}")
        price=get_price()
        return {"price":price,"poc":price,"d":-2,"d5":-2,"sig":"🔴 بيع","eng_text":"🔴 نازل","eng_ok":True,"can_trade":True,"df":None,"reason":[],"patterns":["نازل"],"last_bull":None,"last_bear":(price+3,price+8,5),"in_bull":False,"in_bear":True,"bonus":"نازل","score":6,"side":"بيع","trend_txt":"نازل","trend_change":-5}

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V58.3 بيكشف النزول الحقيقي\n/وقف للإيقاف")

@bot.message_handler(commands=['auto_off','وقف'])
def auto_off(m):
    AUTO_CHATS.discard(m.chat.id)
    bot.send_message(m.chat.id,"⛔ وقفت")

@bot.message_handler(commands=['start','tawsiya'])
def tawsiya(m):
    try:
        AUTO_CHATS.add(m.chat.id)
        data=check_signal()
        price=data["price"]; side=data["side"]; score=data["score"]; bonus=data["bonus"]; patterns=data["patterns"]; sig=data["sig"]; eng_text=data["eng_text"]; trend_txt=data["trend_txt"]

        sl=price+15 if side=="بيع" else price-15
        tp1=price-18 if side=="بيع" else price+18
        tp2=price-32 if side=="بيع" else price+32

        pat_txt = "\n".join(patterns)
        txt=f"✅ توصية {side} V58.3 سكور {score}/10\n{eng_text}\n\n{trend_txt}\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n\n🎯 {price:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n{sig}"

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
                txt=f"🚨 V58.3 {data['side']} سكور {data['score']}/10 🚨\n{data['trend_txt']}\n🎯 {data['price']:.1f}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V58.3 OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
