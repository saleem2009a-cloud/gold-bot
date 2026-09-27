import os
import time
import threading
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# إعدادات البوت والاتصال
TELEGRAM_TOKEN = "8347268155:AAH3oQ4MaH1rWxvoEgoEOLfgPI_DfRAsNBY"
CHAT_ID = "1347502348"
SYMBOL = "GC=F"

# تنظيف الـ Webhook القديم لضمان عمل getUpdates بكفاءة عالية
try:
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook", timeout=10)
except Exception:
    pass

def send_telegram_message(message):
    """إرسال الرسائل إلى التيليجرام مع دعم تنسيق Markdown"""
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
        self.wfile.write(b"Gold Bot Ultimate SMC & Astro Strategy Active")

def run_http_server():
    """خادم ويب مصغر للحفاظ على نشاط البوت على منصات الاستضافة"""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_market_open():
    """التحقق مما إذا كان سوق الذهب مفتوحاً (تجنب عطلة نهاية الأسبوع)"""
    weekday = datetime.now(timezone.utc).weekday()
    if weekday in [5, 6]:
        return False
    return True

def get_moon_phase(dt):
    """حساب الدورة الفلكية ومرحلة القمر"""
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
    """تحليل الدورات الزمنية والجلسات العالمية"""
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

def calculate_advanced_indicators(df):
    """حساب كافة المؤشرات الفنية واستراتيجية الـ SMC ومناطق الخصم"""
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    # حساب مؤشر القوة النسبية RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # نطاق الـ Swing High و Swing Low لاستراتيجية SMC ونسبة 50% Discount
    df['Swing_High'] = df['High'].rolling(window=20).max()
    df['Swing_Low'] = df['Low'].rolling(window=20).min()
    df['Discount_50'] = df['Swing_Low'] + ((df['Swing_High'] - df['Swing_Low']) * 0.5)

    return df

def get_comprehensive_market_report():
    """جلب تقرير شامل يدمج السعر، المؤشرات، الجلسات، والدورة الفلكية"""
    try:
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period="1mo", interval="1d" if not market_open else "15m")
        if df.empty:
            df = ticker.history(period="1mo", interval="1d")

        if df.empty:
            return "⚠️ تعذر جلب بيانات السوق اللحظية حالياً، يرجى المحاولة لاحقاً."

        df = calculate_advanced_indicators(df)
        last_row = df.iloc[-1]
        
        price = round(float(last_row['Close']), 2)
        discount_level = round(float(last_row['Discount_50']), 2)
        swing_high = round(float(last_row['Swing_High']), 2)
        swing_low = round(float(last_row['Swing_Low']), 2)
        rsi = round(float(last_row['RSI']), 2) if not pd.isna(last_row['RSI']) else 50.0

        zone_status = "منطقة خصم الشراء (Discount Region) 🛒🟢" if price <= discount_level else "منطقة بيع مرتفعة (Premium Region) 📈🔴"

        now = datetime.now(timezone.utc)
        astro_phase = get_moon_phase(now)
        time_session, is_time_turn = analyze_time_cycles()
        time_turn_alert = " | ⚡ **تنبيه انعطاف زمني!**" if is_time_turn else ""

        return f"""📊 **التقرير الشامل للذهب (SMC + الفلكي + الفني):**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحالي:** `{price}$`
🎯 **مستوى الخصم (50% Fib):** `{discount_level}$`
📍 **النطاق:** High `{swing_high}$` | Low `{swing_low}$`
🏷️ **تقييم المنطقة:** {zone_status}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة الزمنية:** {time_session}{time_turn_alert}
🌌 **الدورة الفلكية:** {astro_phase}"""
    except Exception as e:
        return f"حدث خطأ أثناء إعداد التقرير: {e}"

def analyze_smc_smart_trades():
    """فحص السوق لاكتشاف الصفقات بناءً على شروط دقيقة لاستراتيجية SMC"""
    if not is_market_open():
        return None
    try:
        data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty or len(data) < 30:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_advanced_indicators(data)
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        price = round(float(last_row['Close']), 2)
        discount = float(last_row['Discount_50'])
        swing_high = float(last_row['Swing_High'])
        swing_low = float(last_row['Swing_Low'])
        rsi = float(last_row['RSI'])

        now = datetime.now(timezone.utc)
        astro_phase = get_moon_phase(now)
        time_session, _ = analyze_time_cycles()

        # شروط صفقات الشراء والبيع بناءً على الـ Discount Zone ومؤشر الـ RSI
        is_discount_buy = (price <= discount) and (prev_row['Close'] < price) and (rsi < 45)
        is_premium_sell = (price >= discount) and (prev_row['Close'] > price) and (rsi > 65)

        if is_discount_buy:
            tp = round(swing_high, 2)
            sl = round(swing_low - 1.5, 2)
            return f"""💎 **توصية قوية - SMC Discount Buy 💎**

🟢 **نوع الصفقة:** شراء (BUY XAU/USD)
📍 **سعر الدخول:** `{price}$` (داخل منطقة الخصم)
🎯 **الهدف (TP):** `{tp}$`
🛑 **وقف الخسارة (SL):** `{sl}$`
📊 **مستوى 50%:** `{round(discount, 2)}$` | **RSI:** `{round(rsi, 2)}`
⏳ **الجلسة:** {time_session} | 🌌 **الفلك:** {astro_phase}"""

        elif is_premium_sell:
            tp = round(swing_low, 2)
            sl = round(swing_high + 1.5, 2)
            return f"""💎 **توصية قوية - SMC Premium Sell 💎**

🔴 **نوع الصفقة:** بيع (SELL XAU/USD)
📍 **سعر الدخول:** `{price}$` (داخل منطقة البيع)
🎯 **الهدف (TP):** `{tp}$`
🛑 **وقف الخسارة (SL):** `{sl}$`
📊 **مستوى 50%:** `{round(discount, 2)}$` | **RSI:** `{round(rsi, 2)}`
⏳ **الجلسة:** {time_session} | 🌌 **الفلك:** {astro_phase}"""
    except Exception:
        pass
    return None

def telegram_listener():
    """مستمع أوتوماتيكي لرسائل التيليجرام للاستجابة الفورية للأوامر"""
    offset = 0
    try:
        init_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=1"
        init_res = requests.get(init_url, timeout=5).json()
        if "result" in init_res and init_res["result"]:
            offset = init_res["result"][-1]["update_id"] + 1
    except Exception:
        pass

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=10"
            response = requests.get(url, timeout=15).json()
            if "result" in response:
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        msg_text = update["message"]["text"].strip()
                        sender_chat_id = str(update["message"]["chat"]["id"])
                        
                        # التأكد من استقبال الأوامر من الشات الخاص بك فقط
                        if sender_chat_id == CHAT_ID:
                            if any(word in msg_text for word in ["سعر", "تحليل", "وضع", "توصية", "استراتيجية", "/tawsiya"]):
                                report = get_comprehensive_market_report()
                                send_telegram_message(report)
                            elif any(word in msg_text for word in ["خبر", "اخبار", "/news"]):
                                send_telegram_message("📰 **حالة الأخبار والأسواق:** المتابعة مستمرة لكافة مستويات الخصم والدورات الفلكية والزمنية لحظياً.")
                            elif msg_text in ["/start", "مرحبا", "هلا", "شغال"]:
                                send_telegram_message("أهلاً بك يا سليم! 🤖 تم تفعيل بوت التداول الشامل (SMC + الفلكي + الفني) بنجاح. اكتب **سعر** أو **تحليل** للحصول على التقرير الكامل فوراً.")
        except Exception as e:
            print(f"خطأ في المستمع: {e}")
            time.sleep(3)
        time.sleep(1)

if __name__ == "__main__":
    # تشغيل خادم الويب ومستمع التيليجرام في خلفية النظام
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("🚀 **تم تشغيل بوت التداول المتكامل (SMC, المؤشرات, الدورات الزمنية والفلكية) بنجاح وجاهز للعمل!**")

    last_trade_time = 0

    # الحلقة الرئيسية لفحص صفقات السوق وتحليلها كل دقيقة
    while True:
        try:
            current_time = time.time()
            trade_message = analyze_smc_smart_trades()
            # إرسال التوصية إذا توفرت شروط الصفقة مع فاصل زمني لا يقل عن نصف ساعة بين التوصيات
            if trade_message and (current_time - last_trade_time > 1800):
                send_telegram_message(trade_message)
                last_trade_time = current_time
        except Exception as e:
            print(f"خطأ في حلقة المراقبة الرئيسية: {e}")

        time.sleep(60)
