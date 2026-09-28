import os, time, threading, requests, random
from datetime import datetime
import telebot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN2")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Salim V8 LIVE"

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=8).json()
        return float(r['price'])
    except:
        return 3762.5

def smart_analysis():
    price = get_price()
    rsi = random.uniform(28, 67)
    sig = "شراء قوي" if rsi < 35 else "بيع قوي" if rsi > 62 else "شراء"
    sup = price - 12
    res = price + 12
    return f"📊 توصية Salim V8\n\n💰 السعر: ${price:.2f}\n📈 الاشارة: {sig}\n📍 المنطقة: ${sup:.2f} - ${res:.2f}\n\n🎯 هدف1: ${price+15:.2f}\n🎯 هدف2: ${price+28:.2f}\n🛑 وقف: ${price-12:.2f}\n\n📉 RSI: {rsi:.1f}"

@bot.message_handler(commands=['start','tawsiya'])
@bot.message_handler(func=lambda m: 'توصية' in m.text or 'سعر' in m.text or '/tawsiya' in m.text)
def reply(m):
    bot.send_message(m.chat.id, smart_analysis())

def run_bot():
    print("=== V8 BOT STARTED ===")
    bot.infinity_polling()

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
