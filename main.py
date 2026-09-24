import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# التوكن رح يجي من Render مش من هون - آمن 100%
TOKEN = os.environ.get("BOT_TOKEN")

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Gold Bot is running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً سليم! 👋\nأرسل /gold لمعرفة سعر الذهب الحالي 💰")

async def gold_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # سعر الذهب بالدولار للأونصة
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        price = r.get("price", 0)
        if price:
            await update.message.reply_text(f"💰 سعر أونصة الذهب الآن:\n${price:.2f}\n\nسعر الغرام عيار 24: ${price/31.1035:.2f}")
        else:
            await update.message.reply_text("ما قدرت جيب السعر هلا، جرب بعد شوي")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

def main():
    Thread(target=run_flask, daemon=True).start()
    if not TOKEN:
        print("BOT_TOKEN not set!")
        return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gold", gold_price))
    print("Bot started...")
    application.run_polling()

if __name__ == "__main__":
    main()
