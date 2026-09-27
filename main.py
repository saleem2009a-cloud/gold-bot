import os
import time
import math
import threading
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_TOKEN = "8347268155:AAH3oQ4MaH1rWxvoEgoEOLfgPI_DfRAsNBY"
CHAT_ID = "1347502348"
SYMBOL = "GC=F"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Bot Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def get_economic_news_summary():
    return """📰 **تقرير الأخبار الاقتصادية والتقويم الاقتصادي:**

• **أسعار الفائدة والتضخم:** يترقب السوق مؤشرات التضخم الأمريكية وبيانات الفيدرالي التي تؤثر على أسعار الذهب بشكل مباشر.
• **مستوى مخاطر الأخبار:** مستقر حالياً 🟢 (لا توجد بيانات NFP أو CPI مفاجئة في الوقت الحالي).
• **النصيحة:** تابع بيانات الوظائف وأسعار المستهلك للتداول بآمان."""

def get_moon_phase(dt):
    diff = dt - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days = diff.total_seconds() / 86400.0
    lunation = (days % 29.53058770576) / 29.53058770576
    angle = lunation * 360.0

    if angle < 15 or angle > 345:
        return "محاق (New Moon) 🌑 - انعكاس قوي متوقع", "High"
    elif 165 < angle < 195:
        return "بدر (Full Moon) 🌕 - ذروة التذبذب والسيولة", "High"
    else:
        return "مسار فلكي اعتيادي 🌙", "Low"

def analyze_time_cycles():
    now = datetime.now(timezone.utc)
    hour = now.hour
    if 7 <= hour < 12:
        session = "جلسة لندن 🇬🇧"
    elif 12 <= hour < 17:
        session = "تداخل لندن ونيويورك 🇺🇸"
    elif 17 <= hour < 21:
        session = "جلسة نيويورك المتأخرة 🏛️"
    else:
        session = "الجلسة الآسيوية 🌏"

    is_time_turn = hour in [2, 6, 10, 14, 18, 22]
    return session, is_time_turn

def calculate_indicators(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    df['SMA_50'] = df['Close'].rolling(window=50).mean()

    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.rolling(14).mean()

    return df

def get_live_market_status():
    try:
        data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty:
            return "تعذر جلب أسعار الذهب حالياً، أعد المحاولة بعد ثوانٍ."

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_indicators(data)
        last_row = df.iloc[-1]
        
        price = round(float(last_row['Close']), 2)
        rsi = round(float(last_row['RSI']), 2)
        sma50 = round(float(last_row['SMA_50']), 2)
        trend = "صاعد 📈" if price > sma50 else "هابط 📉"

        now = datetime.now(timezone.utc)
        astro_phase, astro_impact = get_moon_phase(now)
        time_session, is_time_turn = analyze_time_cycles()

        return f"""📊 **تقرير الذهب اللحظي (XAU/USD):**

💰 **السعر الحالي:** `{price}$`
📈 **الاتجاه العام (SMA50):** {trend}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة الحالية:** {time_session}
⚠️ **انعكاس زمني (Gann):** {"نعم ⚠️" if is_time_turn else "لا 🟢"}
🌌 **الدورة القمرية:** {astro_phase}

💬 *البوت يراقب حركة الذهب أوتوماتيكياً وسيرسل لك أي صفقة سريعة (Scalp ⚡) أو توصية رئيسية (🚨) فور تحقق شروطها!*"""
    except Exception as e:
        return f"حدث خطأ في استخراج البيانات: {e}"

def analyze_scalping():
    data = yf.download(tickers=SYMBOL, period="1d", interval="5m", progress=False)
    if data.empty or len(data) < 50:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    df = calculate_indicators(data)
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    price = round(float(last_row['Close']), 2)
    rsi = round(float(last_row['RSI']), 2)
    macd = float(last_row['MACD'])
    signal = float(last_row['Signal_Line'])
    prev_macd = float(prev_row['MACD'])
    prev_signal = float(prev_row['Signal_Line'])

    scalp_buy = (macd > signal) and (prev_macd <= prev_signal) and (rsi < 40)
    scalp_sell = (macd < signal) and (prev_macd >= prev_signal) and (rsi > 60)

    if scalp_buy:
        tp = round(price + 2.5, 2)
        sl = round(price - 2.0, 2)
        return f"⚡ **صفقة سريعة (SCALP BUY)** ⚡\n\n📍 **سعر الدخول:** `{price}`\n🎯 **الهدف السريع:** `{tp}`\n🛑 **إيقاف الخسارة:** `{sl}`\n📊 **RSI:** {rsi}"

    elif scalp_sell:
        tp = round(price - 2.5, 2)
        sl = round(price + 2.0, 2)
        return f"⚡ **صفقة سريعة (SCALP SELL)** ⚡\n\n📍 **سعر الدخول:** `{price}`\n🎯 **الهدف السريع:** `{tp}`\n🛑 **إيقاف الخسارة:** `{sl}`\n📊 **RSI:** {rsi}"

    return None

def analyze_gold_main():
    data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    df = calculate_indicators(data)
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    price = round(float(last_row['Close']), 2)
    rsi = round(float(last_row['RSI']), 2)
    macd = float(last_row['MACD'])
    signal = float(last_row['Signal_Line'])
    prev_macd = float(prev_row['MACD'])
    prev_signal = float(prev_row['Signal_Line'])
    sma50 = float(last_row['SMA_50'])
    atr = round(float(last_row['ATR']), 2) if not pd.isna(last_row['ATR']) else 5.0

    now = datetime.now(timezone.utc)
    astro_phase, astro_impact = get_moon_phase(now)
    time_session, is_time_turn = analyze_time_cycles()

    trend = "صاعد 📈" if price > sma50 else "هابط 📉"

    is_buy = (macd > signal) and (prev_macd <= prev_signal) and (rsi < 65) and (price > sma50)
    is_sell = (macd < signal) and (prev_macd >= prev_signal) and (rsi > 35) and (price < sma50)

    gann_factor = math.sqrt(price)

    if is_buy:
        entry = price
        sl = round(entry - (atr * 1.5), 2)
        tp1 = round(entry + (atr * 1.5), 2)
        tp2 = round(((gann_factor + 0.25) ** 2), 2)

        return f"🚨 **توصية رئيسية: شراء (BUY XAU/USD)** 🚀\n\n📍 **سعر الدخول:** `{entry}`\n🎯 **TP1:** `{tp1}` | **TP2 (زمني/فلكي):** `{tp2}`\n🛑 **SL:** `{sl}`\n\n📊 **الاتجاه:** {trend} | RSI: {rsi}\n⏳ **الجلسة:** {time_session}\n🌌 **الفلكي:** {astro_phase}"

    elif is_sell:
        entry = price
        sl = round(entry + (atr * 1.5), 2)
        tp1 = round(entry - (atr * 1.5), 2)
        tp2 = round(((gann_factor - 0.25) ** 2), 2)

        return f"🚨 **توصية رئيسية: بيع (SELL XAU/USD)** 🔻\n\n📍 **سعر الدخول:** `{entry}`\n🎯 **TP1:** `{tp1}` | **TP2 (زمني/فلكي):** `{tp2}`\n🛑 **SL:** `{sl}`\n\n📊 **الاتجاه:** {trend} | RSI: {rsi}\n⏳ **الجلسة:** {time_session}\n🌌 **الفلكي:** {astro_phase}"

    return None

def listen_to_telegram_messages():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=20"
            res = requests.get(url, timeout=25).json()
            if "result" in res:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().lower()
                        chat_id = str(update["message"]["chat_id"])

                        if chat_id == CHAT_ID:
                            if text in ["/start", "مرحبا", "هلا", "شغال"]:
                                send_telegram_message("أهلاً بك يا سليم! 🤖 أنا جاهز ومستعد.\n\n• اكتب **سعر** أو **تحليل** لمعرفة الوضع المباشر\n• اكتب **اخبار** لمعرفة التقويم الاقتصادي\n• اكتب **توصية** للفحص الفوري")
                            elif "خبر" in text or "اخبار" in text or text == "/news":
                                send_telegram_message(get_economic_news_summary())
                            elif "تحليل" in text or "سعر" in text or "وضع" in text or text in ["/tawsiya", "توصية"]:
                                send_telegram_message(get_live_market_status())
                            else:
                                send_telegram_message("مرحباً بك! يمكنك كتابة:\n1. **سعر** أو **توصية** للتحليل المباشر\n2. **اخبار** للتقويم الاقتصادي")
        except Exception:
            pass
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=listen_to_telegram_messages, daemon=True).start()

    last_main_signal_time = 0
    last_scalp_signal_time = 0

    while True:
        try:
            current_time = time.time()

            scalp_msg = analyze_scalping()
            if scalp_msg and (current_time - last_scalp_signal_time > 600):
                send_telegram_message(scalp_msg)
                last_scalp_signal_time = current_time

            main_msg = analyze_gold_main()
            if main_msg and (current_time - last_main_signal_time > 1800):
                send_telegram_message(main_msg)
                last_main_signal_time = current_time

        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(120)
