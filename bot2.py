import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_klines():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=15m&limit=100"
  return requests.get(url,timeout=5).json()
 except: return []

def calc_rsi(prices, period=14):
 if len(prices) < period+1: return 50
 gains=0; losses=0
 for i in range(1, period+1):
  d=prices[-i]-prices[-i-1]
  if d>0: gains+=d
  else: losses+=-d
 if losses==0: return 70
 return 100-(100/(1+gains/losses))

def get_signal():
 klines=get_klines()
 if len(klines) < 60: return False, "⏸️ عم جمع بيانات..."
 closes=[float(k[4]) for k in klines]
 price=closes[-1]
 ema20=sum(closes[-20:])/20
 ema50=sum(closes[-50:])/50
 rsi=calc_rsi(closes)
 vol=[float(k[5]) for k in klines[-6:]]
 vol_strong=vol[-1] > (sum(vol[:-1])/5 * 1.4)

 # LONG قوي
 if ema20 > ema50 and 55 < rsi < 72 and vol_strong and price > ema20:
  sl=price*0.998
  tp1=price*1.003
  tp2=price*1.006
  return True, f"🔥🔥 توصية LONG قوية 🔥🔥\n\n📊 {SYMBOL}\n💰 دخول: ${price:.2f}\n🛑 ستوب: ${sl:.2f}\n🎯 هدف1: ${tp1:.2f}\n🎯 هدف2: ${tp2:.2f}\n\nالسبب: EMA20>{ema20:.1f} فوق EMA50>{ema50:.1f}\nRSI {rsi:.1f} + فوليوم قوي 🚀"

 # SHORT قوي
 if ema20 < ema50 and 28 < rsi < 45 and vol_strong and price < ema20:
  sl=price*1.002
  tp1=price*0.997
  tp2=price*0.994
  return True, f"🔥🔥 توصية SHORT قوية 🔥🔥\n\n📊 {SYMBOL}\n💰 دخول: ${price:.2f}\n🛑 ستوب: ${sl:.2f}\n🎯 هدف1: ${tp1:.2f}\n🎯 هدف2: ${tp2:.2f}\n\nالسبب: EMA20<{ema20:.1f} تحت EMA50<{ema50:.1f}\nRSI {rsi:.1f} + فوليوم قوي 📉"

 return False, f"⏸️ {SYMBOL} تحت المراقبة\nالسعر ${price:.2f}\nEMA20 {ema20:.1f} | EMA50 {ema50:.1f} | RSI {rsi:.1f}\nلسا ما في توصية قوية - عم راقب السوق 🧠"

async def start(update,ctx):
 with open(CHAT_FILE,"w") as f: f.write(str(update.effective_chat.id))
 await update.message.reply_text(f"BOT2 {SYMBOL} الذكي جاهز 🧠🔥\nبيعطيك توصية قوية حسب السوق\n/tawsiya")

async def tawsiya(update,ctx):
 strong,msg=get_signal()
 await update.message.reply_text(msg)

async def auto_check(ctx):
 if not os.path.exists(CHAT_FILE): return
 try:
  with open(CHAT_FILE,"r") as f: cid=int(f.read().strip())
 except: return
 strong,msg=get_signal()
 if strong:
  try: await ctx.bot.send_message(chat_id=cid, text=f"🚨 توصية تلقائية 🚨\n{msg}")
  except: pass

if __name__=="__main__":
 if TOKEN:
  b=Application.builder().token(TOKEN).build()
  b.add_handler(CommandHandler("start",start))
  b.add_handler(CommandHandler("tawsiya",tawsiya))
  b.job_queue.run_repeating(auto_check, interval=300, first=20)
  print("BOT2 STRONG Running...")
  b.run_polling()
