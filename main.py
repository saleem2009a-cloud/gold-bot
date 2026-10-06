import matplotlib
matplotlib.use('Agg')
import os, requests, time, numpy as np
from datetime import datetime
import pytz
TOKEN = "".join(os.getenv("BOT_TOKEN","").split())
print("V58.5 DUAL TREND", flush=True)

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

def get_dual_trend():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=1d&interval=5m"
        headers = {"User-Agent":"Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        if len(closes) < 25: return 0,0,"خطأ"

        last = closes[-1]
        short_prev = closes[-4] # 15 دقيقة
        mid_prev = closes[-12] # 60 دقيقة
        long_prev = closes[-24] # 120 دقيقة

        short_ch = last - short_prev
        mid_ch = last - mid_prev
        long_ch = last - long_prev

        txt = f"📉 لحظي 15د: {short_ch:+.1f}$ | 1س: {mid_ch:+.1f}$ | 2س: {long_ch:+.1f}$"
        return short_ch, mid_ch, long_ch, txt, closes
    except Exception as e:
        print(f"trend err {e}")
        return 0,0,0,"ترند غير معروف", []

def check_signal():
    try:
        price = get_price()
        short_ch, mid_ch, long_ch, trend_txt, closes = get_dual_trend()

        # المنطق المزدوج
        if long_ch < -5 and short_ch > 0:
            # نازل كبير وطالع صغير = ارتداد وهمي للبيع
            side = "انتظار"
            score = 4
            eng_text = f"⚠️ ارتداد وهمي +{short_ch:.1f}$ ضمن نزول {long_ch:.1f}$"
            can_trade = False
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥\n⚠️ لا تشتري - ارتداد للبيع فقط\n🌙 طور 83% | ☿ مباشر ✅"
            patterns = [f"⚠️ ارتداد +{short_ch:.1f}$", f"🔻 ترند 2س نازل {long_ch:.1f}$", "انتظر بيع من فوق"]
            sig = "⚪ ارتداد - انتظر بيع"
        elif long_ch < -5 and short_ch < -1:
            # نازل كبير ونازل صغير = بيع قوي
            side = "بيع"
            score = 8
            eng_text = "🔴 بيع قوي - الترندين نازلين"
            can_trade = True
            bonus = f"{trend_txt}\n⏰ جلسة نيويورك 🔥🔥 | قمة للبيع\n🌙 طور 83% | ☿ مباشر ✅\n🔴 بيع مع الترند الكبير والصغير ✅✅"
            patterns = [f"🔻 نزول 15د {short_ch:.1f}$", f"🔻 نزول 2س {long_ch:.1f}$", "🔻 ضغط بيعي قوي"]
            sig = "🔴 بيع مسيطر قوي"
        elif long_ch > 5 and short_ch < 0:
            side = "انتظار"
            score = 4
            eng_text = f"⚠️ هبوط وهمي {short_ch:.1f}$ ضمن صعود {long_ch:.1f}$"
            can_trade = False
            bonus = f"{trend_txt}\n⚠️ لا تبيع - هبوط للشراء فقط"
            patterns = [f"⚠️ هبوط {short_ch:.1f}$", f"🔺 ترند 2س طالع {long_ch:.1f}$"]
            sig = "⚪ هبوط - انتظر شراء"
        elif long_ch > 5 and short_ch > 1:
            side = "شراء"
            score = 8
            eng_text = "🟢 شراء قوي - الترندين طالعين"
            can_trade = True
            bonus = f"{trend_txt}\n🟢 شراء مع الترند الكبير والصغير ✅✅"
            patterns = [f"🔺 صعود 15د {short_ch:.1f}$", f"🔺 صعود 2س {long_ch:.1f}$"]
            sig = "🟢 شراء مسيطر قوي"
        else:
            # عرضي
            if abs(short_ch) < 1 and abs(long_ch) < 5:
                side = "انتظار"
                score = 3
                eng_text = "⚪ عرضي"
                can_trade = False
                bonus = f"{trend_txt}\n⚪ سوق عرضي - لا تدخل"
                patterns = ["⚪ عرضي"]
                sig = "⚪ محايد"
            else:
                # ترند لحظي فقط
                if short_ch < -1:
                    side = "بيع"
                    score = 6
                    eng_text = "🔴 بيع لحظي"
                    can_trade = True
                    bonus = f"{trend_txt}\n🔴 بيع سكالبينج 15د"
                    patterns = [f"🔻 نزول 15د {short_ch:.1f}$"]
                    sig = "🔴 بيع لحظي"
                else:
                    side = "شراء"
                    score = 5
                    eng_text = "🟢 شراء لحظي"
                    can_trade = True
                    bonus = f"{trend_txt}\n🟢 شراء سكالبينج 15د"
                    patterns = [f"🔺 صعود 15د {short_ch:.1f}$"]
                    sig = "🟢 شراء لحظي"

        return {"price":price,"side":side,"score":score,"eng_text":eng_text,"can_trade":can_trade,"bonus":bonus,"patterns":patterns,"sig":sig,"trend_txt":trend_txt,"short_ch":short_ch,"long_ch":long_ch}
    except Exception as e:
        print(f"check err {e}")
        price=get_price()
        return {"price":price,"side":"انتظار","score":3,"eng_text":"خطأ","can_trade":False,"bonus":"خطأ","patterns":["خطأ"],"sig":"خطأ","trend_txt":"خطأ","short_ch":0,"long_ch":0}

@bot.message_handler(commands=['auto_on','راقب'])
def auto_on(m):
    AUTO_CHATS.add(m.chat.id); LAST_ALERT[m.chat.id]=0
    bot.send_message(m.chat.id,"✅ V58.5 التنين سوا\nيومي + لحظي\n/وقف للإيقاف")

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
            txt=f"⛔ {eng_text} V58.5 سكور {score}/10\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n\n💰 السعر {price:.1f}\n{sig}"
        else:
            sl=price+15 if side=="بيع" else price-15
            tp1=price-18 if side=="بيع" else price+18
            tp2=price-32 if side=="بيع" else price+32
            txt=f"✅ توصية {side} V58.5 سكور {score}/10\n{eng_text}\n\n{bonus}\n\n📍 أنماط:\n{pat_txt}\n\n🎯 {price:.1f} 🛑 {sl:.1f} ✅ {tp1:.1f}/{tp2:.1f}\n{sig}"

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
                if now-LAST_ALERT.get(chat_id,0) < 1200: continue
                txt=f"🚨 V58.5 {data['side']} 🚨\n{data['trend_txt']}\n🎯 {data['price']:.1f}"
                try: bot.send_message(chat_id, txt); LAST_ALERT[chat_id]=now
                except: pass
        except Exception as e: print(f"watcher {e}"); time.sleep(10)

@app.route('/')
def home(): return "V58.5 DUAL OK"
def run_bot():
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except: time.sleep(5)

threading.Thread(target=run_bot,daemon=True).start()
threading.Thread(target=auto_watcher,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
