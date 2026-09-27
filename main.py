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
        self.wfile.write(b"Gold Bot - Full Pullback Buy/Sell Strategy Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_market_open():
    weekday = datetime.now(timezone.utc).weekday()
    if weekday in [5, 6]:  # السبت والأحد
        return False
    return True

# ==========================================
# حساب المؤشرات واستراتيجية Pullback كاملة (Buy & Sell)
# ==========================================
def calculate_advanced_indicators(df):
    # 1. حساب EMA 50 لتحديد الاتجاه
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()

    # 2. القمم والقيعان (Swing High & Swing Low)
    df['Swing_High'] = df['High'].rolling(window=20).max()
    df['Swing_Low'] = df['Low'].rolling(window=20).min()

    # 3. فيبوناتشي (مستوى 50% لـ Discount & Premium Region)
    high_val = df['Swing_High']
    low_val = df['Swing_Low']
    diff = high_val - low_val

    df['Fib_500'] = high_val - (diff * 0.500)
    df['Fib_382'] = high_val - (diff * 0.382)
    df['Fib_618'] = high_val - (diff * 0.618)

    # 4. ألوان الشموع
    df['Is_Red'] = df['Close'] < df['Open']
    df['Is_Green'] = df['Close'] > df['Open']

    return df

def fetch_spot_gold_data():
    try:
        ticker = yf.Ticker("XAUUSD=X")
        df = ticker.history(period="1mo", interval="15m")
        if not df.empty and float(df.iloc[-1]['Close']) < 3500:
            return df
    except Exception:
        pass

    try:
        res = requests.get("https://api.exchangerate-api.com/v4/latest/XAU", timeout=5).json()
        if "rates" in res and "USD" in res["rates"]:
            gold_price = 1 / res["rates"]["USD"]
            if 1500 < gold_price < 3500:
                dates = pd.date_range(end=datetime.now(), periods=30)
                df = pd.DataFrame({
                    'Open': [gold_price]*30,
                    'High': [gold_price + 10]*30,
                    'Low': [gold_price - 10]*30,
                    'Close': [gold_price]*30,
                }, index=dates)
                return df
    except Exception:
        pass

    return None

def get_live_market_status():
    try:
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        df = fetch_spot_gold_data()
        if df is None or df.empty:
            return "⚠️ تعذر جلب سعر الذهب الفوري حالياً، أعد المحاولة عند افتتاح السوق."

        df = calculate_advanced_indicators(df)
        last_row = df.iloc[-1]

        price = round(float(last_row['Close']), 2)
        ema_50 = round(float(last_row['EMA_50']), 2) if not pd.isna(last_row['EMA_50']) else price
        fib_500 = round(float(last_row['Fib_500']), 2) if not pd.isna(last_row['Fib_500']) else price
        swing_low = round(float(last_row['Swing_Low']), 2) if not pd.isna(last_row['Swing_Low']) else price - 10
        swing_high = round(float(last_row['Swing_High']), 2) if not pd.isna(last_row['Swing_High']) else price + 10

        trend = "ترند صاعد 📈" if price > ema_50 else "ترند هابط 📉"
        
        if price < fib_500:
            zone_status = "منطقة خصم الشراء (Discount Region - تحت Fib 50%) 🛒🟢"
        else:
            zone_status = "منطقة البيع المرتفعة (Premium Region - فوق Fib 50%) 📈🔴"

        return f"""📊 **تقرير الذهب الشامل وفق الاستراتيجية الكاملة:**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحالي:** `{price}$`
📉 **مؤشر EMA 50:** `{ema_50}$` ({trend})
🎯 **مستوى 50% فيبوناتشي:** `{fib_500}$`
🏷️ **التقييم:** {zone_status}

📍 **القاع (الدعم):** `{swing_low}$` | **القمة (المقاومة):** `{swing_high}$`"""
    except Exception as e:
        return f"حدث خطأ أثناء جلب السعر: {e}"

def analyze_full_pullback_strategy():
    """ تطبيق شروط الاستراتيجية الكاملة (شراء + بيع) """
    if not is_market_open():
        return None
    try:
        df = fetch_spot_gold_data()
        if df is None or df.empty or len(df) < 10:
            return None

        df = calculate_advanced_indicators(df)

        c0 = df.iloc[-1]  # الشمعة الحالية (المفروض تكون التأكيدية)
        c1 = df.iloc[-2]  # شمعة التصحيح 1
        c2 = df.iloc[-3]  # شمعة التصحيح 2
        c3 = df.iloc[-4]  # شمعة التصحيح 3

        price = float(c0['Close'])
        ema_50 = float(c0['EMA_50'])
        fib_500 = float(c0['Fib_500'])
        swing_low = float(c0['Swing_Low'])
        swing_high = float(c0['Swing_High'])

        # === 1. شروط الشراء (BUY) ===
        buy_cond1 = price > ema_50  # ترند صاعد
        buy_cond2 = c1['Is_Red'] and c2['Is_Red'] and c3['Is_Red']  # 3 شموع حمراء تصحيحية
        buy_cond3 = price < fib_500 or c1['Low'] < fib_500  # نزول تحت 50% فيبوناتشي
        buy_cond4 = c0['Is_Green']  # شمعة خضراء تأكيدية

        if buy_cond1 and buy_cond2 and buy_cond3 and buy_cond4:
            sl = round(swing_low - 1.5, 2)
            tp = round(swing_high, 2)
            return f"""🚀 **توصية شراء (BUY XAU/USD)** 🚀

📍 **سعر الدخول:** `{round(price, 2)}$`
🟢 **السبب:**
 1. الاتجاه صاعد (السعر فوق EMA 50)
 2. اكتمل تصحيح 3 شموع حمراء
 3. وصل لمنطقة الخصم (تحت 50% Fib)
 4. ظهرت شمعة خضراء تأكيدية

🛑 **وقف الخسارة (تحت الدعم):** `{sl}$`
🎯 **الهدف الرئيسي:** `{tp}$`"""

        # === 2. شروط البيع (SELL) ===
        sell_cond1 = price < ema_50  # ترند هابط
        sell_cond2 = c1['Is_Green'] and c2['Is_Green'] and c3['Is_Green']  # 3 شموع خضراء تصحيحية
        sell_cond3 = price > fib_500 or c1['High'] > fib_500  # صعود فوق 50% فيبوناتشي
        sell_cond4 = c0['Is_Red']  # شمعة حمراء تأكيدية

        if sell_cond1 and sell_cond2 and sell_cond3 and sell_cond4:
            sl = round(swing_high + 1.5, 2)
            tp = round(swing_low, 2)
            return f"""🔻 **توصية بيع (SELL XAU/USD)** 🔻

📍 **سعر الدخول:** `{round(price, 2)}$`
🔴 **السبب:**
 1. الاتجاه هابط (السعر تحت EMA 50)
 2. اكتمل تصحيح 3 شموع خضراء
 3. وصل لمنطقة البيع المرتفعة (فوق 50% Fib)
 4. ظهرت شمعة حمراء تأكيدية

🛑 **وقف الخسارة (فوق المقاومة):** `{sl}$`
🎯 **الهدف الرئيسي:** `{tp}$`"""

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
                        
                        if any(word in msg_text for word in ["سعر", "تحليل", "وضع", "توصية", "فيبوناتشي"]):
                            reply = get_live_market_status()
                            send_telegram_message(reply)
                        elif msg_text in ["/start", "مرحبا", "هلا", "شغال"]:
                            send_telegram_message("أهلاً بك! 🤖 تم تفعيل الاستراتيجية الكاملة (شراء + بيع) لـ EMA و Fib 50% و Pullback. اكتب **سعر** للتحليل.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم تحديث البوت بالاستراتيجية الشاملة للبيع والشراء (EMA + Pullback 3 Candles + Fib 50% Discount/Premium + Confirmation)!**")

    last_trade_time = 0

    while True:
        try:
            current_time = time.time()
            trade_msg = analyze_full_pullback_strategy()
            if trade_msg and (current_time - last_trade_time > 1800):
                send_telegram_message(trade_msg)
                last_trade_time = current_time
        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(60)
