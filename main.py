import os, time, threading, requests, telebot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN2")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN2 not set!")
    
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Salim Bot is LIVE! Gold Price Bot Running"

def get_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        return r['price']
    except:
        return 3765.20

@bot.message_handler(commands=['start','tawsiya','se3r'])
@bot.message_handler(func=lambda m: m.text in ['سعر','/tawsiya','توصية'])
def handle(message):
    p = get_price()
    msg = f"📈 **توصية ذهب لحظية**\n\n💰 السعر: ${p}\n📊 الاتجاه: شراء\n🎯 هدف1: ${float(p)+10}\n🎯 هدف2: ${float(p)+20}\n🛑 وقف: ${float(p)-15}\n\n⏰ الآن مباشر - Salim V7"
    bot.reply_to(message, msg)

def run_bot():
    print("=== Bot started polling ===")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# شغل التنين مع بعض
threading.Thread(target=run_bot, daemon=True).start()
