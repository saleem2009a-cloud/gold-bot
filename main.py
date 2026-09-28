import telebot
import requests
import time
import threading
from flask import Flask
import os

BOT_TOKEN = os.getenv("BOT_TOKEN2")
bot = telebot.TeleBot(BOT_TOKEN)
CHANNEL_ID = "@SalimSignals" # او خليه بدون @ اذا بوت خاص

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is Live 24/7!"

def get_gold_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r['price'])
    except:
        return 3750.50  # سعر افتراضي اذا فشل

@bot.message_handler(commands=['tawsiya', 'start', 'se3r'])
@bot.message_handler(func=lambda m: m.text in ['سعر', 'توصية', '/tawsiya'])
def send_signal(message):
    price = get_gold_price()
    text = f"""
📈 **توصية ذهب مباشرة - Salim Bot V7** 📉

💰 السعر الحالي: **${price}**
📊 النوع: **شراء** 
🎯 الهدف 1: ${price+8:.2f}
🎯 الهدف 2: ${price+15:.2f}
🛑 وقف خسارة: ${price-10:.2f}

🌙 الجلسة الرمضانية: الجلسة الاسيوية
🌌 الدورة الفلكية: مسار فلكي اعتيادي

⏰ الوقت: الان مباشر
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

def auto_signals():
    while True:
        try:
            price = get_gold_price()
            text = f"🔔 توصية تلقائية - الذهب الآن ${price} - راقب السوق"
            # bot.send_message(CHANNEL_ID, text) # شيل # اذا بدك يبعت تلقائي
            time.sleep(1800) # كل 30 دقيقة
        except:
            time.sleep(60)

# تشغيل الويب سيرفر عشان Render ما يطفيه
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=auto_signals, daemon=True).start()

print("Bot started...")
bot.infinity_polling()
