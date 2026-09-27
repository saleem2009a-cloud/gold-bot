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
        self.wfile.write(b"Gold Bot SMC Discount Strategy Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_market_open():
    weekday = datetime.now(timezone.utc).weekday()
    if weekday in [5, 6]:
        return False
    return True

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

def calculate_smc_indicators(df):
    # حساب المتوسط والمؤشرات الأساسية
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    # حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # تحديد أرقام Swing High & Swing Low لمعرفة الـ Discount Zone (50%)
    df['Swing_High'] = df['High'].rolling(window=20).max()
    df['Swing_Low'] = df['Low'].rolling(window=20).min()
    df['Discount_50'] = df['Swing_Low'] + ((df['Swing_High'] - df['Swing_Low']) * 0.5)

    return df

def get_live_market_status():
    try:
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period="1mo", interval="1d" if not market_open else "15m")
        if df.empty:
            df = ticker.history(period="1mo", interval="1d")

        if df.empty:
            return "تعذر جلب البيانات اللحظية حالياً، أعد المحاولة بعد قليل."

        df = calculate_smc_indicators(df)
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

        return f"""📊 **تقرير الذهب وفق استراتيجية SMC & Discount Zone:**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحالي:** `{price}$`
🎯 **مستوى الخصم (50% Fib):** `{discount_level}$`
📍 **النطاق:** High `{swing_high}$` | Low `{swing_low}$`
🏷️ **تقييم المنطقة:** {zone_status}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة:** {time_session}
🌌 **الدورة القمرية:** {astro_phase}"""
    except Exception as e:
        return f"حدث خطأ أثناء جلب السعر: {e}"

def analyze_smc_trades():
    if not is_market_open():
        return None
    try:
        data = yf.download(tickers=SYMBOL, period="5d", interval="15m", progress=False)
        if data.empty or len(data) < 30:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = calculate_smc_indicators(data)
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        price = round(float(last_row['Close']), 2)
        discount = float(last_row['Discount_50'])
        swing_high = float(last_row['Swing_High'])
        swing_low = float(last_row['Swing_Low'])
        rsi = float(last_row['RSI'])

        # شروط الشراء وفق الاستراتيجية: السعر بعد التصحيح (Pullback) وصل منطقة الخصم تحـت الـ 50%
        is_discount_buy = (price <= discount) and (prev_row['Close'] < price) and (rsi < 45)
        
        # شروط البيع: السعر أعلى منطقة الـ 50% وفي حالة التشبع
        is_premium_sell = (price >= discount) and (prev_row['Close'] > price) and (rsi > 65)

        if is_discount_buy:
            tp = round(swing_high, 2)
            sl = round(swing_low - 1.5, 2)
            return f"💎 **صفقة بناءً على استراتيجية SMC Discount 💎**\n\n🟢 **شراء (BUY XAU/USD)**\n📍 **سعر الدخول:** `{price}$` (في منطقة الخصم Discount Region)\n🎯 **الهدف (Swing High):** `{tp}$`\n🛑 **إيقاف الخسارة (تحت القاع):** `{sl}$`\n📊 **مستوى 50% فيبوناتشي:** `{round(discount, 2)}$`"

        elif is_premium_sell:
            tp = round(swing_low, 2)
            sl = round(swing_high + 1.5, 2)
            return f"💎 **صفقة بناءً على استراتيجية SMC Premium 💎**\n\n🔴 **بيع (SELL XAU/USD)**\n📍 **سعر الدخول:** `{price}$` (في منطقة البيع Premium Region)\n🎯 **الهدف (Swing Low):** `{tp}$`\n🛑 **إيقاف الخسارة (فوق القمة):** `{sl}$`\n📊 **مستوى 50% فيبوناتشي:** `{round(discount, 2)}$`"
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
                        
                        if any(word in msg_text for word in ["سعر", "تحليل", "وضع", "توصية", "استراتيجية", "/tawsiya"]):
                            reply = get_live_market_status()
                            send_telegram_message(reply)
                        elif any(word in msg_text for word in ["خبر", "اخبار", "/news"]):
                            send_telegram_message("📰 **حالة الأخبار:** متابعة حركة الأسواق ومستويات الخصم متواصلة أوتوماتيكياً.")
                        elif msg_text in ["/start", "مرحبا", "هلا", "شغال"]:
                            send_telegram_message("أهلاً بك يا سليم! 🤖 تم تفعيل استراتيجية **SMC 50% Discount** بنجاح. اكتب **سعر** للتحليل المباشر.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم دمج وتفعيل استراتيجية Smart Money concepts (SMC & 50% Discount Region) بنجاح مع كافة التوصيات!**")

    last_trade_time = 0

    while True:
        try:
            current_time = time.time()
            trade_msg = analyze_smc_trades()
            if trade_msg and (current_time - last_trade_time > 1800):
                send_telegram_message(trade_msg)
                last_trade_time = current_time
        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(60)
