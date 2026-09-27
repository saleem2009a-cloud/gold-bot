import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_klines():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=1h&limit=100"
  r=requests.get(url,timeout=10).json()
  return r
 except:
  return []

def calc_rsi(closes, period=14):
 if len(closes) < period+1:
  return 50
 deltas = [closes[i]-closes[i-1] for i in range(1,len(closes))]
 gains = [d if d>0 else 0 for d in deltas]
 losses = [-d if d<0 else 0 for d in deltas]
 avg_gain = sum(gains[-period:]) / period
 avg_loss = sum(losses[-period:]) / period
 if avg_loss == 0:
  return 70
 rs = avg_gain / avg_loss
 rsi = 100 - (100 / (1+rs))
 return rsi

def get_signal():
 klines=get_klines()
 if len(klines) < 60:
  return False, "⏸️ عم جمع بيانات السوق..."

 closes=[float(k[4]) for k in klines]
 price=closes[-1]
 ema20=sum(closes[-20:])/20
 ema50=sum(closes[-50:])/50
 rsi=calc_rsi(closes)

 vol=[float(k[5]) for k in klines[-6:]]
 vol_avg=sum(vol[:-1])/5
 vol_strong=vol[-1] > vol_avg*1.3

 # LONG
 if ema20 > ema50 and 50 < rsi < 70 and price > ema20:
  sl=price*0.997
  tp1=price*1.004
  tp2=price*1.008
  return True, f"🔥 LONG قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${sl:.2f}\nهدف1 ${tp1:.2f}\nهدف2 ${tp2:.2f}\nEMA20 {ema20:.1f} > EMA50 {ema50:.1f}\nRSI {rsi:.1f}"

 # SHORT
 if ema20 < ema50 and 30 < rsi < 50 and price < ema20:
  sl=price*1.003
  tp1=price*0.996
  tp2=price*0.992
  return True, f"🔥 SHORT قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${sl:.2f}\nهدف1 ${tp1:.2f}\nهدف2 ${tp2:.2f}\nEMA20 {ema20:.1f} < EMA50 {ema50:.1f}\nRSI {rsi:.1f}"

 return False, f"⏸️ {SYMBOL} تحت المراقبة\nالسعر ${price:.2f}\nEMA20 {ema20:.2f} | EMA50 {ema50:.2f} | RSI {rsi:.1f}\nلسا ما في توصية قوية"

async def start(update,ctx):
 with open(CHAT_FILE,"w") as f: f.write(str(update.effective_chat.id))
 await update.message.reply_text(f"BOT2 {SYMBOL} جاهز 🔥\n/tawsiya")

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
  print("BOT2 Fixed Running...")
  b.run_polling()
