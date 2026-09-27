import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_klines():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=1h&limit=100"
  return requests.get(url,timeout=10).json()
 except: return []

def calc_rsi(closes, period=14):
 if len(closes) < period+1: return 50
 deltas=[closes[i]-closes[i-1] for i in range(1,len(closes))]
 gains=[d if d>0 else 0 for d in deltas]
 losses=[-d if d<0 else 0 for d in deltas]
 avg_gain=sum(gains[-period:])/period
 avg_loss=sum(losses[-period:])/period
 if avg_loss==0: return 50
 rs=avg_gain/avg_loss
 return 100-(100/(1+rs))

def get_signal():
 klines=get_klines()
 if len(klines) < 60:
  return False, "⏸️ عم جمع بيانات..."

 closes=[float(k[4]) for k in klines]
 highs=[float(k[2]) for k in klines[-5:]]
 lows=[float(k[3]) for k in klines[-5:]]
 price=closes[-1]

 # === فحص اذا السوق مسكر / ميت ===
 price_change = abs(closes[-1]-closes[-5])/closes[-5]*100
 range_now = (max(highs)-min(lows))/price*100
 
 if price_change < 0.15 and range_now < 0.2:
  return False, f"🏦 السوق مسكر / حركة ميتة\nالسعر ${price:.2f}\nالتغير اخر 5 ساعات {price_change:.2f}%\nما في توصية قوية - السوق نايم 😴"

 ema20=sum(closes[-20:])/20
 ema50=sum(closes[-50:])/50
 rsi=calc_rsi(closes)

 # شروط اقوى وما بيعطي توصية الا اذا الحركة حقيقية
 if ema20 > ema50 and 55 < rsi < 68 and price > ema20 and price_change > 0.15:
  sl=price*0.997
  tp1=price*1.004
  return True, f"🔥 LONG قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${sl:.2f}\nهدف ${tp1:.2f}\nRSI {rsi:.1f}"

 if ema20 < ema50 and 32 < rsi < 48 and price < ema20 and price_change > 0.15:
  sl=price*1.003
  tp1=price*0.996
  return True, f"🔥 SHORT قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${sl:.2f}\nهدف ${tp1:.2f}\nRSI {rsi:.1f}"

 return False, f"⏸️ تحت المراقبة\n${price:.2f} | EMA20 {ema20:.1f} | EMA50 {ema50:.1f} | RSI {rsi:.1f}\nحركة {price_change:.2f}% - لسا ما في دخول قوي"

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
  b.job_queue.run_repeating(auto_check, interval=600, first=20)
  print("BOT2 SAFE Running...")
  b.run_polling()
