import os
import time
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
        self.wfile.write(b"Gold Bot Active")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_market_open():
    weekday = datetime.now(timezone.utc).weekday()
    if weekday == 5: 
        return False
    if weekday == 6 and datetime.now(timezone.utc).hour < 22:
        return False
    return True

def fetch_real_market_data():
    """ جلب السعر الحقيقي والبيانات الحية مباشرة من بورصة الذهب العالمية عبر yfinance """
    try:
        ticker = yf.Ticker("XAUUSD=X")
        df = ticker.history(period="5d", interval="15m")
        if not df.empty:
            return df
    except Exception:
        pass
    
    # محاولة بديلة بفريم اليوم في حال الضغط
    try:
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="5d", interval="15m")
        if not df.empty:
            return df
    except Exception:
        pass
        
    return None

def get_live_market_status():
    try:
        market_open = is_market_open()
        market_status_text = "🟢 السوق مفتوح" if market_open else "🔴 السوق مغلق"

        df = fetch_real_market_data()
        if df is None or df.empty:
            return "⚠️ تعذر جلب السعر اللحظي من السوق حالياً، أعد المحاولة بعد قليل."

        # حساب المؤشرات الحقيقية من بيانات السوق مباشرة
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Swing_High'] = df['High'].rolling(window=20).max()
        df['Swing_Low'] = df['Low'].rolling(window=20).min()

        high_val = df['Swing_High']
        low_val = df['Swing_Low']
        diff = high_val - low_val
        df['Fib_500'] = high_val - (diff * 0.500)

        last_row = df.iloc[-1]
        price = round(float(last_row['Close']), 2)
        ema_50 = round(float(last_row['EMA_50']), 2) if not pd.isna(last_row['EMA_50']) else price
        fib_500 = round(float(last_row['Fib_500']), 2) if not pd.isna(last_row['Fib_500']) else price
        swing_low = round(float(last_row['Swing_Low']), 2) if not pd.isna(last_row['Swing_Low']) else price - 10
        swing_high = round(float(last_row['Swing_High']), 2) if not pd.isna(last_row['Swing_High']) else price + 10

        trend = "ترند صاعد 📈" if price >= ema_50 else "ترند هابط 📉"
        zone_status = "منطقة خصم الشراء (Discount Region) 🛒🟢" if price <= fib_500 else "منطقة البيع المرتفعة (Premium Region) 📈🔴"

        return f"""📊 **تقرير الذهب الحقيقي المباشر (XAU/USD):**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحقيقي من السوق:** `{price}$`
📉 **مؤشر EMA 50:** `{ema_50}$` ({trend})
🎯 **مستوى 50% فيبوناتشي:** `{fib_500}$`
🏷️ **التقييم:** {zone_status}

📍 **القاع (الدعم):** `{swing_low}$` | **القمة (المقاومة):** `{swing_high}$`"""
    except Exception as e:
        return f"حدث خطأ في جلب بيانات السوق: {e}"

def analyze_full_pullback_strategy():
    if not is_market_open():
        return None
    try:
        df = fetch_real_market_data()
        if df is None or df.empty or len(df) < 10:
            return None

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Swing_High'] = df['High'].rolling(window=20).max()
        df['Swing_Low'] = df['Low'].rolling(window=20).min()
        diff = df['Swing_High'] - df['Swing_Low']
        df['Fib_500'] = df['Swing_High'] - (diff * 0.500)

        df['Is_Red'] = df['Close'] < df['Open']
        df['Is_Green'] = df['Close'] > df['Open']

        c0 = df.iloc[-1]
        c1 = df.iloc[-2]
        c2 = df.iloc[-3]
        c3 = df.iloc[-4]

        price = float(c0['Close'])
        ema_50 = float(c0['EMA_50'])
        fib_500 = float(c0['Fib_500'])
        swing_low = float(c0['Swing_Low'])
        swing_high = float(c0['Swing_High'])

        # شروط الشراء
        buy_cond = (price > ema_50) and (c1['Is_Red'] and c2['Is_Red'] and c3['Is_Red']) and (price < fib_500) and c0['Is_Green']
        if buy_cond:
            sl = round(swing_low - 1.5, 2)
            tp = round(swing_high, 2)
            return f"""🚀 **توصية شراء حقيقية (BUY XAU/USD)** 🚀\n\n📍 **سعر الدخول:** `{round(price, 2)}$` \n🛑 **وقف الخسارة:** `{sl}$` \n🎯 **الهدف:** `{tp}$`"""

        # شروط البيع
        sell_cond = (price < ema_50) and (c1['Is_Green'] and c2['Is_Green'] and c3['Is_Green']) and (price > fib_500) and c0['Is_Red']
        if sell_cond:
            sl = round(swing_high + 1.5, 2)
            tp = round(swing_low, 2)
            return f"""🔻 **توصية بيع حقيقية (SELL XAU/USD)** 🔻\n\n📍 **سعر الدخول:** `{round(price, 2)}$` \n🛑 **وقف الخسارة:** `{sl}$` \n🔥 **الهدف:** `{tp}$`"""

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
                            send_telegram_message("أهلاً بك! البوت متصل بالسوق الحي لجلب الأسعار الحقيقية.")
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()

    send_telegram_message("✅ **تم ربط البوت بجلب السعر الحقيقي المباشر من السوق بنجاح!**")

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
