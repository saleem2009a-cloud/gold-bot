import os, requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_klines():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=15m&limit=100"
  return requests.get(url,timeout=10).json()
 except: return []

def calc_ema(prices, period):
 k=2/(period+1); ema=prices[0]
 for p in prices[1:]: ema=p*k+ema*(1-k)
 return ema

def find_swing(klines):
 highs=[float(k[2]) for k in klines]
 lows=[float(k[3]) for k in klines]
 return min(lows[-20:-5]), max(highs[-20:-5])

def get_signal():
 klines=get_klines()
 if len(klines)<60: return False, "⏸️ عم جمع بيانات..."
 closes=[float(k[4]) for k in klines]
 opens=[float(k[1]) for k in klines]
 price=closes[-1]
 ema50=calc_ema(closes,50)
 swing_low, swing_high=find_swing(klines)
 fib50=swing_low+(swing_high-swing_low)*0.5
 change=abs(closes[-1]-closes[-10])/closes[-10]*100
 wd=datetime.now().weekday()
 days=["الاثنين","الثلاثاء","الاربعاء","الخميس","الجمعة","السبت","الاحد"]
 today=days[wd]

 if wd>=5 or change<0.1:
  return False, f"🏦 {today} - السوق نايم\n${price:.2f}\nما في توصية"

 above=price>ema50
 in_discount=price<fib50
 three_red=all(closes[-i]<opens[-i] for i in range(1,4))
 green=closes[-1]>opens[-1]

 if above and in_discount and three_red and green:
  return True, f"🔥 LONG خارق 🔥\n{SYMBOL} ${price:.2f}\n✅ فوق EMA50 {ema50:.1f}\n✅ تحت 50% فيبو {fib50:.1f}\n✅ 3 شموع تصحيح\n✅ شمعة تأكيد\n\nدخول ${price:.2f}\nستوب ${swing_low*0.998:.2f}\nهدف ${swing_high:.2f}"

 return False, f"⏸️ {today} - عم فتش\n${price:.2f} EMA {ema50:.1f} فيبو50 {fib50:.1f}\nفوق EMA:{above} تحت50%:{in_discount} 3حمراء:{three_red} تأكيد:{green}"

async def start(u,c):
 with open(CHAT_FILE,"w") as f: f.write(str(u.effective_chat.id))
 await u.message.reply_text(f"BOT2 {SYMBOL} الخارق جاهز 🧠\n/tawsiya")

async def tawsiya(u,c):
 s,m=get_signal()
 await u.message.reply_text(m)

async def auto_check(c):
 if not os.path.exists(CHAT_FILE): return
 try:
  with open(CHAT_FILE,"r") as f: cid=int(f.read().strip())
 except: return
 s,m=get_signal()
 if s:
  try: await c.bot.send_message(chat_id=cid, text=f"🚨 توصية خارقة 🚨\n{m}")
  except: pass

if __name__=="__main__":
 if TOKEN:
  b=Application.builder().token(TOKEN).build()
  b.add_handler(CommandHandler("start",start))
  b.add_handler(CommandHandler("tawsiya",tawsiya))
  b.job_queue.run_repeating(auto_check, interval=900, first=30)
  b.run_polling()
