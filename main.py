import os
import time
import requests
import pandas as pd
import yfinance as yf

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
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.rolling(14).mean()

    return df

def analyze_gold():
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

    trend = "صاعد 📈" if price > sma50 else "هابط 📉"

    is_buy = (macd > signal) and (prev_macd <= prev_signal) and (rsi < 65) and (price > sma50)
    is_sell = (macd < signal) and (prev_macd >= prev_signal) and (rsi > 35) and (price < sma50)

    if is_buy:
        entry = price
        sl = round(entry - (atr * 1.5), 2)
        tp1 = round(entry + (atr * 1.5), 2)
        tp2 = round(entry + (atr * 3.0), 2)
        
        return f"""🚨 **توصية تداول خارقة: شراء (BUY XAU/USD)** 🚀

📍 **سعر الدخول:** `{entry}`
🎯 **الهدف الأول (TP1):** `{tp1}`
🎯 **الهدف الثاني (TP2):** `{tp2}`
🛑 **إيقاف الخسارة (SL):** `{sl}`

📊 **تفاصيل التحليل الفني:**
• **الاتجاه العام:** {trend}
• **مؤشر RSI:** {rsi}
• **إشارة MACD:** تقاطع إيجابي صاعد
• **مستوى التقلب (ATR):** {atr}

⚠️ *إدارة المخاطر:* لا تتجاوز 1% إلى 2% من رأس المال."""

    elif is_sell:
        entry = price
        sl = round(entry + (atr * 1.5), 2)
        tp1 = round(entry - (atr * 1.5), 2)
        tp2 = round(entry - (atr * 3.0), 2)
        
        return f"""🚨 **توصية تداول خارقة: بيع (SELL XAU/USD)** 🔻

📍 **سعر الدخول:** `{entry}`
🎯 **الهدف الأول (TP1):** `{tp1}`
🎯 **الهدف الثاني (TP2):** `{tp2}`
🛑 **إيقاف الخسارة (SL):** `{sl}`

📊 **تفاصيل التحليل الفني:**
• **الاتجاه العام:** {trend}
• **مؤشر RSI:** {rsi}
• **إشارة MACD:** تقاطع سلبي هابط
• **مستوى التقلب (ATR):** {atr}

⚠️ *إدارة المخاطر:* لا تتجاوز 1% إلى 2% من رأس المال."""

    return None

if __name__ == "__main__":
    print("🤖 تم تشغيل بوت تحليل الذهب الخارق...")
    send_telegram_message("✅ **تم تشغيل بوت تحليل الذهب بنجاح!**\nجاري مراقبة السوق وإرسال التوصيات...")
    
    last_signal_time = 0

    while True:
        try:
            signal_msg = analyze_gold()
            current_time = time.time()
            if signal_msg and (current_time - last_signal_time > 1800):
                send_telegram_message(signal_msg)
                last_signal_time = current_time
            else:
                print("السوق قيد المراقبة...")
        except Exception as e:
            print(f"خطأ: {e}")

        time.sleep(180)
