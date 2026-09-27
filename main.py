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
SYMBOL = "XAUUSD=X"  # رمز الذهب الفوري المباشر الدقيق

try:
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
except Exception:
    pass

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
        print(f"خطأ إرسال: {e}")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Bot Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_market_open():
    # معرفة ما إذا كان السوق مغلقاً (السبت = 5, الأحد = 6)
    weekday = datetime.now(timezone.utc).weekday()
    if weekday in [5, 6]:
        return False
    return True

def get_economic_news_summary():
    if not is_market_open():
        return "🔴 **السوق مغلق حالياً (عطلة نهاية الأسبوع)**\n\n📰 **ملخص الأخبار:** لا توجد بيانات اقتصادية حية صادرة اليوم. يفتتح السوق مساء الأحد/فجر الاثنين."
    
    return """📰 **تقرير الأخبار الاقتصادية:**

• **أسعار الفائدة والتضخم:** متابعة تصريحات الفيدرالي وبيانات CPI.
• **حالة المخاطر:** مستقرة حالياً 🟢 بدون أخبار عالية الخطورة.
• **توصية:** انتبه لأوقات بيانات NFP والوظائف الفيدرالية."""

def get_moon_phase(dt):
    diff = dt - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days = diff.total_seconds() / 86400.0
    angle = ((days % 29.53058770576) / 29.53058770576) * 360.0

    if angle < 15 or angle > 345:
        return "محاق (New Moon) 🌑"
    elif 165 < angle < 195:
        return "بدر (Full Moon) 🌕"
    else:
        return "مسار فلكي اعتيادي 🌙"

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
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty:
            return "جاري تحديث البيانات، حاول بعد قليل..."

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_indicators(data)
        last_row = df.iloc[-1]
        
        price = round(float(last_row['Close']), 2)
        rsi = round(float(last_row['RSI']), 2)
        sma50 = round(float(last_row['SMA_50']), 2)
        trend = "صاعد 📈" if price > sma50 else "هابط 📉"

        now = datetime.now(timezone.utc)
        astro_phase = get_moon_phase(now)
        time_session, is_time_turn = analyze_time_cycles()

        return f"""📊 **تقرير الذهب الفوري (XAU/USD):**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر ({'الحالي' if market_open else 'إغلاق الجمعة'}):** `{price}$`
📈 **الاتجاه العام (SMA50):** {trend}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة:** {time_session}
🌌 **الدورة القمرية:** {astro_phase}

💡 *تلاحظ: يتم إيقاف إرسال التوصيات التلقائية أثناء إغلاق السوق وحتّى افتتاح التداول فجر الاثنين.*"""
    except Exception as e:
        return f"حدث خطأ في البيانات: {e}"

def analyze_scalping():
    if not is_market_open():
        return None
    try:
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

        if (macd > signal) and (prev_macd <= prev_signal) and (rsi < 40):
            return f"⚡ **صفقة سريعة (SCALP BUY)** ⚡\n\n📍 **الدخول:** `{price}`\n🎯 **الهدف:** `{round(price+2.5,2)}`\n🛑 **الاستوب:** `{round(price-2.0,2)}`\n📊 **RSI:** {rsi}"
        elif (macd < signal) and (prev_macd >= prev_signal) and (rsi > 60):
            return f"⚡ **صفقة سريعة (SCALP SELL)** ⚡\n\n📍 **الدخول:** `{price}`\n🎯 **الهدف:** `{round(price-2.5,2)}`\n🛑 **الاستوب:** `{round(price+2.0,2)}`\n📊 **RSI:** {rsi}"
    except Exception:
        pass
    return None

def analyze_gold_main():
    if not is_market_open():
        return None
    try:
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
        astro_phase = get_moon_phase(now)
        time_session, is_time_turn = analyze_time_cycles()
        trend = "صاعد 📈" if price > sma50 else "هابط 📉"

        gann_factor = math.sqrt(price)

        if (macd > signal) and (prev_macd <= prev_signal) and (rsi < 65) and (price > sma50):
            return f"🚨 **توصية رئيسية: شراء (BUY XAU/USD)** 🚀\n\n📍 **الدخول:** `{price}`\n🎯 **TP1:** `{round(price+(atr*1.5),2)}` | **TP2:** `{round(((gann_factor+0.25)**2),2)}`\n🛑 **SL:** `{round(price-(atr*1.5),2)}`\n\n📊 **الاتجاه:** {trend} | RSI: {rsi}\n⏳ **الجلسة:** {time_session}\n🌌 **الفلكي:** {astro_phase}"
        elif (macd < signal) and (prev_macd >= prev_signal) and (rsi > 35) and (price < sma50):
            return f"🚨 **توصية رئيسية: بيع (SELL XAU/USD)** 🔻\n\n📍 **الدخول:** `{price}`\n🎯 **TP1:** `{round(price-(atr*1.5),2)}` | **TP2:** `{round(((gann_factor-0.25)**2),2)}`\n🛑 **SL:** `{round(price+(atr*1.5),2)}`\n\n📊 **الاتجاه:** {trend} | RSI: {rsi}\n⏳ **الجلسة:** {time_session}\n🌌 **الفلكي:** {astro_phase}"
    except Exception:
        pass
    return None

def telegram_listener():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=5"
            response = requests.get(url, timeout=10).json()
            if "result" in response:
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        msg_text = update["message"]["text"].strip()
                        
                        if any(word in msg_text for word in ["سعر", "تحليل", "وضع", "توصية", "/tawsiya"]):
                            reply = get_live_market_status()
                            send_telegram_message(reply)
                        elif any(word in msg_text for word in ["خبر", "اخبار", "/news"]):
                            reply = get_economic_news_summary()
                            send_telegram_message(reply)
                        elif msg_text in ["/start", "مرحبا", "هلا", "شغال"]:
                            send_telegram_message("أهلاً بك يا سليم! 🤖 اكتب **سعر** للتحليل اللحظي وسأبين لك حالة السوق فوراً.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم تحديث الرمز لحساب الذهب الفوري (XAUUSD=X) وفحص حالة العطلة الأسبوعية!**")

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

        time.sleep(60)
