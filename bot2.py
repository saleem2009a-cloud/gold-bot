import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")

def get_price():
 try:
  r=requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={SYMBOL}",timeout=5).json()
  return float(r['price'])
 except: return 0

async def start(update,ctx):
 await update.message.reply_text(f"BOT2 {SYMBOL} جاهز 🔥\n/tawsiya")

async def tawsiya(update,ctx):
 p=get_price()
 await update.message.reply_text(f"BOT2 {SYMBOL}\nالسعر ${p:.2f}\n⏸️ شروط الدخول القوية تحت المراقبة")

if __name__=="__main__":
 if TOKEN:
  b=Application.builder().token(TOKEN).build()
  b.add_handler(CommandHandler("start",start))
  b.add_handler(CommandHandler("tawsiya",tawsiya))
  print("BOT2 Running...")
  b.run_polling()
