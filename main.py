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
# بيانات التلجرام الخاص بك
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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

# ==========================================
# خادم ويب مصغر لإبقاء الخدمة نشطة على Render
# ==========================================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Bot Server Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# ==========================================
# 1. التحليل الإخباري والاقتصادي
# ==========================================
def get_economic_news_summary():
    return """📰 **ملخص الأخبار الاقتصادية للذهب (XAU/USD):**

• **بيانات الفائدة والتضخم الأمريكي:** يتأثر الذهب بشكل مباشر ببيانات أسعار الفائدة وتصريحات الفيدرالي الأمريكي.
• **وضع السوق الحالي:** لا توجد أخبار عالية الخطورة مفاجئة في هذه اللحظة، والسيولة تسير في مجراها الطبيعي.
• **توصية الأخبار:** يُنصح دائماً بمتابعة مواعيد صدور مؤشر مؤشر أسعار المستهلك (CPI) وتقرير الوظائف (NFP)."""

# ==========================================
# 2. التحليل الفلكي (Astro Analysis)
# ==========================================
def get_moon_phase(dt):
    diff = dt - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days = diff.total_seconds() / 86400.0
    lunation = (days % 29.53058770576) / 29.53058770576
    angle = lunation * 360.0

    if angle < 15 or angle > 345:
        return "محاق (New Moon) 🌑 - منطقة انعكاس زمني فلكي", "High"
    elif 165 < angle < 195:
        return "بدر (Full Moon) 🌕 - ذروة التذبذب والسيولة", "High"
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
# 4. حساب المؤشرات الفنية
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
# 5. تقرير التحليل المباشر (عند سؤال البوت)
# ==========================================
def get_live_market_status():
    try:
        data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty:
            return "تعذر جلب أسعار الذهب حالياً، يرجى المحاولة بعد قليل."

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

        return f"""📊 **تقرير الذهب المباشر (XAU/USD):**

💰 **السعر الحالي:** `{price}$`
📈 **الاتجاه العام (SMA50):** {trend}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة الزمنية:** {time_session}
⚠️ **انعكاس زمني (Gann):** {"نعم ⚠️" if is_time_turn else "لا 🟢"}
🌌 **الدورة القمرية:** {astro_phase}

💬 *يمكنك كتابة "اخبار" لطلب ملخص الأخبار، أو "توصية" للفحص المباشر.*"""
    except Exception as e:
        return f"حدث خطأ أثناء جلب البيانات: {e}"

# ==========================================
# 6. التفاعل التفاعلي للرد على رسائلك (Bot Listener)
# ==========================================
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
                                send_telegram_message("أهلاً بك يا سليم! 🤖 أنا جاهز لمساعدتك.\n\n• اسألني عن **التحليل** أو **السعر**\n• اكتب **اخبار** لمعرفة وضع الأخبار\n• اكتب **توصية** لطلب تحليل فوري")
                            elif "خبر" in text or "اخبار" in text or text == "/news":
                                news_msg = get_economic_news_summary()
                                send_telegram_message(news_msg)
                            elif "تحليل" in text or "سعر" in text or "وضع" in text or text in ["/tawsiya", "توصية"]:
                                status_msg = get_live_market_status()
                                send_telegram_message(status_msg)
                            else:
                                send_telegram_message("فهمت طلبك! أستطيع إفادتك بـ:\n1. **التحليل الفوري:** اكتب 'سعر' أو 'توصية'\n2. **الأخبار:** اكتب 'اخبار'")
        except Exception:
            pass
        time.sleep(2)

# ==========================================
# التشغيل الرئيسي
# ==========================================
if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=listen_to_telegram_messages, daemon=True).start()

    send_telegram_message("✅ **تم تفعيل البوت التفاعلي المطور!**\nيمكنك الآن محادثتي وسؤالي عن السعر أو الأخبار والتوصيات في أي وقت.")

    while True:
        time.sleep(60)
