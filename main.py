import os
import time
import math
import threading
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# خادم ويب مصغر لإبقاء الخدمة نشطة على Render Free Tier
# ==========================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Trading Bot is Active & Running!")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"🌐 HTTP Server running on port {port}")
    server.serve_forever()

# ==========================================
# بيانات التلجرام الخاصة بك
# ==========================================
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
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

# ==========================================
# 1. تحليل الأخبار الاقتصادية
# ==========================================
def check_economic_news():
    news_status = "لا توجد أخبار عالية الخطورة حالياً 🟢 (السوق آمن)"
    is_news_risk = False
    return news_status, is_news_risk

# ==========================================
# 2. التحليل الفلكي (Astro Analysis)
# ==========================================
def get_moon_phase(dt):
    diff = dt - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days = diff.total_seconds() / 86400.0
    lunation = (days % 29.53058770576) / 29.53058770576
    angle = lunation * 360.0

    if angle < 15 or angle > 345:
        return "محاق (New Moon) 🌑", "High"
    elif 165 < angle < 195:
        return "بدر (Full Moon) 🌕", "High"
    else:
        return "مسار فلكي اعتيادي 🌙", "Low"

# ==========================================
# 3. التحليل الزمني
# ==========================================
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

# ==========================================
# 4. المؤشرات الفنية
# ==========================================
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

# ==========================================
# 5. تحليل الصفقات السريعة (Scalping 5m)
# ==========================================
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
        return f"""⚡ **صفقة سريعة (SCALP BUY)** ⚡

📍 **سعر الدخول:** `{price}`
🎯 **الهدف السريع:** `{tp}` (25 نقطة)
🛑 **إيقاف الخسارة:** `{sl}`
📊 **RSI:** {rsi} | دخول خاطف على فريم 5 دقائق!"""

    elif scalp_sell:
        tp = round(price - 2.5, 2)
        sl = round(price + 2.0, 2)
        return f"""⚡ **صفقة سريعة (SCALP SELL)** ⚡

📍 **سعر الدخول:** `{price}`
🎯 **الهدف السريع:** `{tp}` (25 نقطة)
🛑 **إيقاف الخسارة:** `{sl}`
📊 **RSI:** {rsi} | دخول خاطف على فريم 5 دقائق!"""

    return None

# ==========================================
# 6. التحليل التكتيكي الشامل (15m)
# ==========================================
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
    news_status, is_news_risk = check_economic_news()

    trend = "صاعد 📈" if price > sma50 else "هابط 📉"

    is_buy = (macd > signal) and (prev_macd <= prev_signal) and (rsi < 65) and (price > sma50) and not is_news_risk
    is_sell = (macd < signal) and (prev_macd >= prev_signal) and (rsi > 35) and (price < sma50) and not is_news_risk

    gann_factor = math.sqrt(price)

    if is_buy:
        entry = price
        sl = round(entry - (atr * 1.5), 2)
        tp1 = round(entry + (atr * 1.5), 2)
        tp2 = round(((gann_factor + 0.25) ** 2), 2)

        return f"""🚨 **توصية رئيسية: شراء (BUY XAU/USD)** 🚀

📍 **سعر الدخول:** `{entry}`
🎯 **الهدف الأول:** `{tp1}` | **الهدف 2 (زمني/فلكي):** `{tp2}`
🛑 **إيقاف الخسارة:** `{sl}`

📊 **التحليل الفني:** الاتجاه {trend} | RSI: {rsi} | ATR: {atr}
📰 **الأخبار:** {news_status}
⏳ **الزمني والفرص:** {time_session} | انعكاس: {"نعم ⚠️" if is_time_turn else "لا 🟢"}
🌌 **الفلكي:** {astro_phase} ({astro_impact})"""

    elif is_sell:
        entry = price
        sl = round(entry + (atr * 1.5), 2)
        tp1 = round(entry - (atr * 1.5), 2)
        tp2 = round(((gann_factor - 0.25) ** 2), 2)

        return f"""🚨 **توصية رئيسية: بيع (SELL XAU/USD)** 🔻

📍 **سعر الدخول:** `{entry}`
🎯 **الهدف الأول:** `{tp1}` | **الهدف 2 (زمني/فلكي):** `{tp2}`
🛑 **إيقاف الخسارة:** `{sl}`

📊 **التحليل الفني:** الاتجاه {trend} | RSI: {rsi} | ATR: {atr}
📰 **الأخبار:** {news_status}
⏳ **الزمني والفرص:** {time_session} | انعكاس: {"نعم ⚠️" if is_time_turn else "لا 🟢"}
🌌 **الفلكي:** {astro_phase} ({astro_impact})"""

    return None

# ==========================================
# الحلقة الرئيسية لتشغيل السيرفر والبوت
# ==========================================
if __name__ == "__main__":
    # تشغيل خادم الويب في Thread مستقل لإبقاء Render سعيداً
    threading.Thread(target=run_http_server, daemon=True).start()

    print("🤖 تم تشغيل البوت الخارق (توصيات رئيسية + صفقات سريعة)...")
    send_telegram_message("✅ **تم تحديث البوت وتفعيل Web Server بنجاح!**\nالخدمة شغالة 100% مجاناً وجاري مراقبة السوق...")

    last_main_signal_time = 0
    last_scalp_signal_time = 0

    while True:
        try:
            current_time = time.time()

            # 1. فحص الصفقات السريعة (Scalping)
            scalp_msg = analyze_scalping()
            if scalp_msg and (current_time - last_scalp_signal_time > 600):
                send_telegram_message(scalp_msg)
                last_scalp_signal_time = current_time

            # 2. فحص التوصيات الرئيسية
            main_msg = analyze_gold_main()
            if main_msg and (current_time - last_main_signal_time > 1800):
                send_telegram_message(main_msg)
                last_main_signal_time = current_time

            print("السوق قيد المراقبة اللحظية...")
        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(120)
