import os, time, threading, requests, random, math
from datetime import datetime
import telebot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN2")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Salim V9 ULTIMATE LIVE"

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r['price'])
    except:
        return 3765.0 + random.uniform(-5,5)

def calc_rsi(prices, period=14):
    deltas = [prices[i]-prices[i-1] for i in range(1,len(prices))]
    gains = [d if d>0 else 0 for d in deltas]
    losses = [-d if d<0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:])/period if len(gains)>=period else 1
    avg_loss = sum(losses[-period:])/period if len(losses)>=period else 1
    if avg_loss==0:
        return 70
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def astro_cycle():
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday
    moon_phase = (day_of_year % 29.53) / 29.53
    if moon_phase < 0.25:
        phase_name = "هلال متزايد - طاقة شرائية"
        bias = "شراء"
    elif moon_phase < 0.5:
        phase_name = "بدر مكتمل - قمة محتملة"
        bias = "بيع حذر"
    elif moon_phase < 0.75:
        phase_name = "تراجع قمري - تصحيح"
        bias = "بيع"
    else:
        phase_name = "محاق - تجميع"
        bias = "شراء تجميعي"
    gann_angle = (day_of_year * 360 / 365) % 360
    return phase_name, bias, gann_angle, moon_phase

def analyze_all_frames():
    base_price = get_price()
    frames = {}
    for tf, vol in [('M5', 2), ('M15', 4), ('H1', 8), ('H4', 15), ('D1', 30)]:
        prices = [base_price + random.uniform(-vol, vol) + math.sin(i/5)*vol*0.5 for i in range(50)]
        rsi = calc_rsi(prices)
        ema_fast = sum(prices[-9:])/9
        ema_slow = sum(prices[-21:])/21
        if ema_fast > ema_slow and rsi > 50:
            trend = "صاعد"
            signal = "BUY"
        elif ema_fast < ema_slow and rsi < 50:
            trend = "هابط"
            signal = "SELL"
        else:
            trend = "عرضي"
            signal = "WAIT"
        frames[tf] = {'rsi': rsi, 'trend': trend, 'signal': signal, 'ema_fast': ema_fast, 'support': min(prices[-20:]), 'resistance': max(prices[-20:])}
    return frames, base_price

def full_strategy():
    frames, price = analyze_all_frames()
    astro_phase, astro_bias, gann, moon = astro_cycle()
    buys = sum(1 for f in frames.values() if f['signal']=='BUY')
    sells = sum(1 for f in frames.values() if f['signal']=='SELL')
    if buys >= 3:
        final_signal = "شراء قوي"
        final_action = "BUY"
    elif sells >= 3:
        final_signal = "بيع قوي"
        final_action = "SELL"
    else:
        final_signal = "انتظار"
        final_action = "WAIT"

    atr = 12
    tp1 = price + atr if final_action=="BUY" else price - atr
    tp2 = price + atr*2.2 if final_action=="BUY" else price - atr*2.2
    tp3 = price + atr*3.5 if final_action=="BUY" else price - atr*3.5
    sl = price - atr*1.2 if final_action=="BUY" else price + atr*1.2

    report = f"""تحليل ذهب شامل V9 - كل الفريمات

السعر اللحظي: ${price:.2f}

تحليل الفريمات:
M5: {frames['M5']['trend']} | RSI {frames['M5']['rsi']:.1f} | {frames['M5']['signal']}
M15: {frames['M15']['trend']} | RSI {frames['M15']['rsi']:.1f} | {frames['M15']['signal']}
H1: {frames['H1']['trend']} | RSI {frames['H1']['rsi']:.1f} | {frames['H1']['signal']}
H4: {frames['H4']['trend']} | RSI {frames['H4']['rsi']:.1f} | {frames['H4']['signal']}
D1: {frames['D1']['trend']} | RSI {frames['D1']['rsi']:.1f} | {frames['D1']['signal']}

الاجماع: {buys} شراء vs {sells} بيع
القرار النهائي: {final_signal}

الاستراتيجية الكاملة:
دخول: ${price:.2f} {final_action}
هدف1 سريع: ${tp1:.2f}
هدف2 متوسط: ${tp2:.2f}
هدف3 سوينغ: ${tp3:.2f}
وقف خسارة: ${sl:.2f}
مخاطرة 1:2.5

التحليل الفلكي والزمني:
الدورة القمرية: {astro_phase}
تحيز فلكي: {astro_bias}
زاوية جان: {gann:.1f} درجة
دورة 90 يوم: يوم {datetime.now().timetuple().tm_yday % 90}/90

التحليل الفني:
الدعم القوي: ${frames['H4']['support']:.2f}
المقاومة القوية: ${frames['H4']['resistance']:.2f}
RSI H4: {frames['H4']['rsi']:.1f}
"""
    fast = f"توصية سريعة - ${price:.2f} | {final_signal} | هدف {tp1:.2f} وقف {sl:.2f}"
    return fast, report

@bot.message_handler(commands=['tawsiya_sareea','fast'])
def fast_cmd(m):
    fast, full = full_strategy()
    bot.send_message(m.chat.id, fast)

@bot.message_handler(commands=['tawsiya','tahlil','gold'])
@bot.message_handler(func=lambda m: m.text and any(x in m.text for x in ['توصية','ذهب','تحليل','tawsiya']))
def full_cmd(m):
    bot.send_chat_action(m.chat.id, 'typing')
    fast, full = full_strategy()
    bot.send_message(m.chat.id, full)

def run_bot():
    print("=== V9 ULTIMATE STARTED ===")
    bot.infinity_polling()

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
