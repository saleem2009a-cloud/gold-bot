import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_klines():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=1h&limit=100"
  return requests.get(url,timeout=10).json()
 except: return []

def calc_ema(prices, period):
 k=2/(period+1)
 ema=prices[0]
 for p in prices[1:]:
  ema = p*k + ema*(1-k)
 return ema

def calc_rsi(prices, period=14):
 if len(prices) < period+1: return 50
 deltas=[prices[i]-prices[i-1] for i in range(1,len(prices))]
 gains=[d if d>0 else 0 for d in deltas]
 losses=[-d if d<0 else 0 for d in deltas]
 avg_gain=sum(gains[-period:])/period
 avg_loss=sum(losses[-period:])/period
 if avg_loss==0: return 50
 rs=avg_gain/avg_loss
 return 100-(100/(1+rs))

def get_signal():
 klines=get_klines()
 if len(klines)<60: return False, "⏸️ عم جمع بيانات..."

 closes=[float(k[4]) for k in klines]
 price=closes[-1]

 ema20=calc_ema(closes[-20:],20)
 ema50=calc_ema(closes[-50:],50)
 rsi=calc_rsi(closes)

 change=abs(closes[-1]-closes[-5])/closes[-5]*100
 if change<0.15:
  return False, f"🏦 السوق نايم 😴\n${price:.2f} تغير {change:.2f}%\nاليوم سبت - ما في توصية"

 if ema20>ema50 and 55<rsi<68:
  return True, f"🔥 LONG قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${price*0.997:.2f}\nهدف ${price*1.005:.2f}\nRSI {rsi:.1f}"

 if ema20<ema50 and 32<rsi<48:
  return True, f"🔥 SHORT قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${price*1.003:.2f}\nهدف ${price*0.995:.2f}\nRSI {rsi:.1f}"

 return False, f"⏸️ تحت المراقبة\n${price:.2f} | EMA20 {ema20:.1f} | EMA50 {ema50:.1f} | RSI {rsi:.1f}"

async def start(update,ctx):
 with open(CHAT_FILE,"w") as f: f.write(str(update.effective_chat.id))
 await update.message.reply_text(f"BOT2 {SYMBOL} جاهز 🔥\n/tawsiya")

async def tawsiya(update,ctx):
 s,m=get_signal()
 await update.message.reply_text(m)

async def auto_check(ctx):
 if not os.path.exists(CHAT_FILE): return
 try:
  with open(CHAT_FILE,"r") as f: cid=int(f.read().strip())
 except: return
 s,m=get_signal()
 if s:
  try: await ctx.bot.send_message(chat_id=cid, text=f"🚨 تلقائي 🚨\n{m}")
  except: pass

if __name__=="__main__":
 if TOKEN:
  b=Application.builder().token(TOKEN).build()
  b.add_handler(CommandHandler("start",start))
  b.add_handler(CommandHandler("tawsiya",tawsiya))
  b.job_queue.run_repeating(auto_check, interval=600, first=20)
  print("BOT2 SAFE Running...")
  b.run_polling()
