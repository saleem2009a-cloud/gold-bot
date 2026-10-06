import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.6 STABLE", flush=True)

import telebot
from flask import Flask
import threading

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
AUTO_CHATS = set()
LAST_ALERT = {}
LAST_SIDE = {"side":"انتظار","time":0,"price":0}

def get_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()
        return float(r['price'])
    except: return 4163.0

def get_stable_trend():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        closes = np.array([c for c in closes if c is not None], dtype=float)
        if len(closes) < 30: return 0,0,0,"خطأ"

        # متوسط متحرك لتنعيم التقلب
        def ma(arr, n): return np.mean(arr[-n:])

        last_ma3 = ma(closes, 3) # متوسط آخر 3 شموع = 15د مستقر
        short_ma = ma(closes, 6) # متوسط آخر 30د
        long_ma = ma(closes, 24) # متوسط آخر 2س

        short_ch = last_ma3 - short_ma
        long_ch = last_ma3 - long_ma
        # ترند الساعة
        mid_ch = last_ma3 - ma(closes, 12)

        txt = f"📊 15د مستقر: {short_ch:+.1f}$ | 1س: {mid_ch:+.1f}$ | 2س: {long_ch:+.1f}$"
        return short_ch, mid_ch, long_ch, txt
    except Exception as e:
        print(f"trend err {e}")
        return 0,0,0,"خطأ"

def check_signal():
    global LAST_SIDE
    try:
        price = get_price()
        short_ch, mid_ch, long_ch, trend_txt = get_stable_trend()

        # فلتر ثبات - اذا الترند ضعيف (<1.5$) لا تغير رأي
        now = time.time()
        time_since_last = now - LAST_SIDE["time"]

        # تحديد الاتجاه الجديد
        if short_ch > 2.0 and long_ch > 0:
            new_side = "شراء"
            score = 8 if long_ch > 3 else 6
            eng_text = "🟢 شراء مستقر" if long_ch > 0 else "🟢 شراء لحظي"
            can_trade = True
        elif short_ch < -2.0 and long_ch < 0:
            new_side = "بيع"
            score = 8 if long_ch < -3 else 6
            eng_text = "🔴 بيع مستقر" if long_ch < 0 else "🔴 بيع لحظي"
            can_trade = True
        elif short_ch > 2.0 and long_ch < -3:
            new_side = "انتظار"
            score = 4
            eng_text = f"⚠️ ارتداد +{short_ch:.1f}$ ضمن نزول {long_ch:.1f}$ - انتظر بيع"
            can_trade = False
        elif short_ch < -2.0 and long_ch > 3:
            new_side = "انتظار"
            score = 4
            eng_text = f"⚠️ تصحيح {short_ch:.1f}$ ضمن صعود {long_ch:.1f}$ - انتظر شراء"
            can_trade = False
        else:
            new_side = "انتظار"
            score = 3
            eng_text = f"⚪ عرضي {short_ch:+.1f}$ - السوق متقلب"
            can_trade = False

        # مانع التقلب: اذا غير رأيو خلال 10 دقايق والسعر قريب، خليه على القديم
        if LAST_SIDE["side"]!= "انتظار" and new_side!= "انتظار" and LAST_SIDE["side"]!= new_side:
            if time_since_last < 600 and abs(price - LAST_SIDE["price"]) < 5:
                # لا تغير، خليه انتظار
                new_side = "انتظار"
                eng_text = f"⏳ ثبّت - كان {LAST_SIDE['side']} من {int(time_since_last/60)}د، هلا متقلب {short_ch:+.1f}$"
                can_trade = False
                score = 3

        # حدث الذاكرة فقط اذا في تداول حقيقي
        if can_trade and new_side!= "انتظار":
            LAST_SIDE = {"side":new_side,"time":now,"price":price}

        bonus = f"{trend_txt}\n⏰ نيويورك 🔥🔥\n{'🔴 بيع مع الترندين ✅' if new_side=='بيع' else '🟢 شراء مع الترندين ✅' if new_side=='شراء' else '⏳ انتظر ثبات'}"
        patterns = [f"15د: {short_ch:+.1f}$", f"2س: {long_ch:+.1f}$"]
        sig = "🔴 بيع مستقر" if new_side=="بيع" else "🟢 شراء مستقر" if new_side=="شراء" else "⚪ انتظر ثبات"

        return {"price":price,"side":new_side,"score":score,"eng_text":eng_text,"can_trade":can_trade,"bonus":bonus,"patterns":patterns,"sig":sig,"trend_txt":trend_txt,"short_ch":short_ch,"long_ch":long_ch}
    except Exception as e:
        print(f"check err {e}")
        price=get_price()
        return {"price":price,"side":"انتظار","score":3,"eng_text":"خطأ","can_trade":False,"bonus":"خطأ","patterns":["خطأ"],"sig":"خطأ","trend_txt":"خطأ","short_ch":0,"long_ch":0}

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V58.6 مستقر - ما بغير رأيو كل دقيقتين\n/وقف للإيقاف")

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

        pat_txt = "\n".join(patterns)
        if side == "انتظار":
            txt=f"⛔ {eng_text} V58.6 سكور {score}/10\n\n{bonus}\n\n📍 {pat_txt}\n\n💰 {price:.1f}\n{sig}"
        else:
            sl=price+15 if side=="بيع" else price-15
            tp1=price-18 if side=="بيع" else price+18
            tp2=price-32 if side=="بيع" else price+32
            txt=f"✅ توصية {side} V58.6 سكور {score}/10\n{eng_text}\n\n{bonus}\n\n📍\n{pat_txt}\n\n🎯 {price:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n{sig}"

        bot.send_message(m.chat.id, txt)
    except Exception as e: bot.send_message(m.chat.id,f"خطأ {e}")

def auto_watcher():
    while True:
        try:
            time.sleep(180)
            if not AUTO_CHATS: continue
            data=check_signal()
            if not data or not data["can_trade"]: continue
            now=time.time()
            for chat_id in list(AUTO_CHATS):
                if now-LAST_ALERT.get(chat_id,0) < 900: continue
                txt=f"🚨 V58.6 {data['side']} مستقر 🚨\n{data['trend_txt']}\n🎯 {data['price']:.1f}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V58.6 STABLE OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
