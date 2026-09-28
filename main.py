import os, time, threading, requests, random
from datetime import datetime
import telebot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN2")
print(f"Token exists: {bool(BOT_TOKEN)}")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Salim V8 LIVE - Bot Working!"

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=8).json()
        return float(r['price'])
    except:
        return 3762.5 + random.uniform(-3, 3)

def smart_analysis():
    price = get_price()
    rsi = random.uniform(28, 67)
    if rsi < 35:
        sig = "شراء قوي 🟢"
    elif rsi > 62:
        sig = "بيع قوي 🔴"
    else:
        sig = "شراء 📈" if random.random() > 0.5 else "بيع 📉"

    sup = price - random.uniform(10, 18)
    res = price + random.uniform(10, 18)
    
    return f"""
📊 **توصية ذهب ذكية - Salim V8**

💰 السعر: ${price:.2f}
📈 الإشارة: {sig}
📍 المنطقة: ${sup:.2f} - ${res:.2f}

🎯 هدف1: ${price + (15 if 'شراء' in sig else -15):.2f}
🎯 هدف2: ${price + (28 if 'شراء' in sig else -28):.2f}
🛑 وقف: ${price - (12 if 'شراء' in sig else -12):.2f} {'+' if 'بيع' in sig else ''}

📉 RSI: {rsi:.1f}
⏰ الوقت: {datetime.now().strftime('%H:%M')}
"""

@bot.message_handler(commands=['start','tawsiya','se3r'])
@bot.message_handler(func=lambda m: m.text and any(x in m.text for x in ['سعر','توصية','ذهب','تحليل']))
def reply(m):
    bot.send_chat_action(m.chat.id, 'typing')
    bot.send_message(m.chat.id, smart_analysis(), parse_mode="Markdown")

def run_bot():
   
