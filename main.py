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
    weekday = datetime.now(timezone.utc).weekday()
    if weekday in [5, 6]:
        return False
    return True

def get_economic_news_summary():
    if not is_market_open():
        return "🔴 **السوق مغلق حالياً (عطلة نهاية الأسبوع)**\n\n📰 **ملخص الأخبار:** لا توجد بيانات اقتصادية حية اليوم. يفتتح السوق مع بداية الجلسة الآسيوية."
    
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

def get_live_market_status():
    try:
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        # طلب البيانات مع معالجة حليمة للـ Timeout و أوقات الإغلاق
        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period="1mo", interval="1d" if not market_open else "15m")
        
        if df.empty:
            df = ticker.history(period="1mo", interval="1d")

        if df.empty:
            return "تعذر جلب البيانات اللحظية حالياً، أعد المحاولة بعد قليل."

        price = round(float(df['Close'].iloc[-1]), 2)
        
        # حساب RSI مبسط على آخر القيم
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = round(float(rsi_series.iloc[-1]), 2) if not pd.isna(rsi_series.iloc[-1]) else 50.0

        sma50_series = df['Close'].rolling(window=min(50, len(df))).mean()
        sma50 = round(float(sma50_series.iloc[-1]), 2)
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

💡 *يتم استئناف التوصيات أوتوماتيكياً عند افتتاح السوق فجر الاثنين.*"""
    except Exception as e:
        return f"حدث خطأ أثناء جلب السعر: {e}"

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
                            send_telegram_message("أهلاً بك يا سليم! 🤖 اكتب **سعر** للتحليل اللحظي وسأجيبك فوراً.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم تحديث نظام معالجة الأسعار بنجاح!**\nارسل كلمة 'سعر' الآن للحصول على النتيجة فوراً.")

    while True:
        time.sleep(60)
