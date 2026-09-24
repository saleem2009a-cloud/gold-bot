import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Gold Professional Bot is running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

def get_real_candles():
    """يجيب 200 شمعة حقيقية من"""
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": "PAXGUSDT", "interval": "1h", "limit": 200}
        r = requests.get(url, params=params, timeout=10).json()
        closes = [float(c[4]) for c in r] # close price
        if len(closes) >= 150:
            print(f"Got {len(closes)} candles from Binance")
            return closes
    except Exception as e:
        print(f"Binance error: {e}")

    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        params = {"interval": "1h", "range": "1mo"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=15).json()
        result = r['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        return closes
    except Exception as e:
        print(f"Yahoo error: {e}")
        return []

def calc_ema(prices, period):
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 70
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_gold_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r.get("price", 0))
    except:
        candles = get_real_candles()
        return candles[-1] if candles else 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً سليم! 👋 بوت الذهب الاحترافي جاهز\n\n/gold - سعر لحظي\n/tawsiya - تحليل فني احترافي كامل")

async def gold_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_gold_price()
    await update.message.reply_text(f"💰 سعر الأونصة الآن: ${price:.2f}\nغرام 24: ${price/31.1035:.2f}" if price else "خطأ بجلب السعر")

async def tawsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ عم حلل الشارت الحقيقي... ثواني")
    candles = get_real_candles()
    if len(candles) < 200:
        await update.message.reply_text("ما قدرت جيب شمعات كافية هلا، جرب بعد دقيقة")
        return
    price = candles[-1]
    ema50 = calc_ema(candles, 50)
    ema200 = calc_ema(candles, 200)
    rsi = calc_rsi(candles, 14)
    support = min(candles[-20:])
    resistance = max(candles[-20:])
    if price > ema50 and ema50 > ema200 and 50 < rsi < 70:
        signal = "🟢 BUY شراء قوي"
        tp1 = resistance
        tp2 = resistance + 15
        sl = ema50 - 10
        trend = "صاعد - السعر فوق EMA50 و EMA200"
    elif price < ema50 and ema50 < ema200 and rsi < 45:
        signal = "🔴 SELL بيع قوي"
        tp1 = support
        tp2 = support - 15
        sl = ema50 + 10
        trend = "هابط - السعر تحت EMA50 و EMA200"
    elif price > ema50:
        signal = "🟡 BUY ضعيف (حذر)"
        tp1 = resistance
        tp2 = resistance + 10
        sl = support
        trend = "صاعد ضعيف"
    else:
        signal = "🟡 SELL ضعيف (حذر)"
        tp1 = support
        tp2 = support - 10
        sl = resistance
        trend = "هابط ضعيف"
    msg = f"""📊 تحليل احترافي XAU/USD

{signal}

💰 السعر: ${price:.2f}
📉 EMA50: ${ema50:.2f}
📈 EMA200: ${ema200:.2f}
📊 RSI: {rsi:.1f}
📍 دعم: ${support:.2f}
📍 مقاومة: ${resistance:.2f}

🎯 TP1: ${tp1:.2f}
🎯 TP2: ${tp2:.2f}
⛔ SL: ${sl:.2f}

📝 {trend}
"""
    await update.message.reply_text(msg)

def main():
    Thread(target=run_flask, daemon=True).start()
    if not TOKEN:
        print("BOT_TOKEN not set!")
        return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gold", gold_price))
    application.add_handler(CommandHandler("tawsiya", tawsiya))
    print("Professional Bot started...")
    application.run_polling()

if __name__ == "__main__":
    main()
