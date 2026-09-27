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
SYMBOL = "XAUUSD=X"  # تم تعديله إلى الذهب الفوري Spot Gold لتطابق السعر مع المنصة

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
        self.wfile.write(b"Gold Bot - SMC, Fibonacci & Supply/Demand Active")

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
# حساب المؤشرات واستراتيجيات العرض/الطلب والفيبوناتشي
# ==========================================
def calculate_advanced_indicators(df):
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    # حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # تحديد القمم والقيعان (Swing High / Swing Low)
    df['Swing_High'] = df['High'].rolling(window=20).max()
    df['Swing_Low'] = df['Low'].rolling(window=20).min()
    
    # مستويات الفيبوناتشي التصحيحية (Fibonacci Retracements)
    high_val = df['Swing_High']
    low_val = df['Swing_Low']
    diff = high_val - low_val

    df['Fib_382'] = high_val - (diff * 0.382)
    df['Fib_500'] = high_val - (diff * 0.500)  # Discount Zone (SMC)
    df['Fib_618'] = high_val - (diff * 0.618)  # Golden Zone

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

        df = calculate_advanced_indicators(df)
        last_row = df.iloc[-1]
        
        price = round(float(last_row['Close']), 2)
        swing_high = round(float(last_row['Swing_High']), 2)
        swing_low = round(float(last_row['Swing_Low']), 2)
        fib_382 = round(float(last_row['Fib_382']), 2)
        fib_500 = round(float(last_row['Fib_500']), 2)
        fib_618 = round(float(last_row['Fib_618']), 2)
        rsi = round(float(last_row['RSI']), 2) if not pd.isna(last_row['RSI']) else 50.0

        # تحديد التقييم
        if price <= fib_618:
            zone_desc = "منطقة طلب قوية + المستوى الذهبي (Fib 0.618) 🛒🟢"
        elif price <= fib_500:
            zone_desc = "منطقة خصم الشراء (Discount Region - Fib 0.50) 🟢"
        else:
            zone_desc = "منطقة عرض مرتفعة (Premium Region - Supply) 📈🔴"

        return f"""📊 **تقرير الذهب الشامل (XAU/USD):**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحالي:** `{price}$`
🎯 **مستويات الفيبوناتشي الحالية:**
 • Fib 0.382: `{fib_382}$`
 • Fib 0.500 (Discount): `{fib_500}$`
 • Fib 0.618 (Golden Zone): `{fib_618}$`

📍 **النطاق:** القمة `{swing_high}$` | القاع `{swing_low}$`
🏷️ **التقييم:** {zone_desc}
📉 **مؤشر RSI:** {rsi}"""
    except Exception as e:
        return f"حدث خطأ أثناء جلب السعر: {e}"

def analyze_all_strategies():
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
        fib_382 = float(last_row['Fib_382'])
        fib_500 = float(last_row['Fib_500'])
        fib_618 = float(last_row['Fib_618'])
        swing_high = float(last_row['Swing_High'])
        swing_low = float(last_row['Swing_Low'])
        rsi = float(last_row['RSI'])

        # شرط الشراء
        is_buy_signal = (price <= fib_500) and (prev_row['Close'] < price) and (rsi < 45)
        
        # شرط البيع
        is_sell_signal = (price >= fib_382) and (prev_row['Close'] > price) and (rsi > 65)

        if is_buy_signal:
            tp = round(swing_high, 2)
            sl = round(swing_low - 2.0, 2)
            return f"""💎 **توصية شراء متكاملة (BUY XAU/USD)** 💎

📍 **سعر الدخول:** `{price}$` (في منطقة الطلب + Fib 0.50/0.618)
🎯 **أخذ الربح (Swing High):** `{tp}$`
🛑 **وقف الخسارة (تحت القاع):** `{sl}$`
📊 **التحليل:** ارتداد من منطقة خصم SMC ومستويات الفيبوناتشي الذهبية.
📉 **RSI:** {rsi}"""

        elif is_sell_signal:
            tp = round(swing_low, 2)
            sl = round(swing_high + 2.0, 2)
            return f"""💎 **توصية بيع متكاملة (SELL XAU/USD)** 💎

📍 **سعر الدخول:** `{price}$` (في منطقة العرض Premium Region)
🎯 **أخذ الربح (Swing Low):** `{tp}$`
🛑 **وقف الخسارة (فوق القمة):** `{sl}$`
📊 **التحليل:** وصول لمنطقة العرض واختبار مستويات الفيبوناتشي العليا.
📉 **RSI:** {rsi}"""
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
                        
                        if any(word in msg_text for word in ["سعر", "تحليل", "وضع", "توصية", "فيبوناتشي", "عرض", "طلب", "/tawsiya"]):
                            reply = get_live_market_status()
                            send_telegram_message(reply)
                        elif any(word in msg_text for word in ["خبر", "اخبار", "/news"]):
                            send_telegram_message("📰 **حالة الأخبار:** معالجة مستويات العرض والطلب والفيبوناتشي مستمرة تلقائياً.")
                        elif msg_text in ["/start", "مرحبا", "هلا", "شغال"]:
                            send_telegram_message("أهلاً بك! 🤖 تم تحديث رمز الذهب ليتطابق مع سعر الذهب الفوري (Spot Gold). اكتب **سعر** للتحليل.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم تحديث البوت وضبط رمز السعر على الذهب الفوري (Spot Gold) بنجاح!**")

    last_trade_time = 0

    while True:
        try:
            current_time = time.time()
            trade_msg = analyze_all_strategies()
            if trade_msg and (current_time - last_trade_time > 1800):
                send_telegram_message(trade_msg)
                last_trade_time = current_time
        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(60)
