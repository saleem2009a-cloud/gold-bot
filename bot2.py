import os, requests, pandas as pd
import pandas_ta as ta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SYMBOL="PAXGUSDT"
TOKEN=os.environ.get("BOT_TOKEN2")
CHAT_FILE="chat_id.txt"

def get_df():
 try:
  url=f"https://data-api.binance.vision/api/v3/klines?symbol={SYMBOL}&interval=1h&limit=100"
  klines=requests.get(url,timeout=10).json()
  df=pd.DataFrame(klines, columns=['t','o','h','l','c','v','a','b','c1','d','e','f'])
  df['c']=df['c'].astype(float)
  df['h']=df['h'].astype(float)
  df['l']=df['l'].astype(float)
  return df
 except:
  return None

def get_signal():
 df=get_df()
 if df is None or len(df) < 60:
  return False, "⏸️ عم جمع بيانات..."

 df['EMA20']=ta.ema(df['c'], length=20)
 df['EMA50']=ta.ema(df['c'], length=50)
 df['RSI']=ta.rsi(df['c'], length=14)
 
 price=df['c'].iloc[-1]
 ema20=df['EMA20'].iloc[-1]
 ema50=df['EMA50'].iloc[-1]
 rsi=df['RSI'].iloc[-1]

 # السوق مسكر؟
 change = abs(df['c'].iloc[-1]-df['c'].iloc[-5])/df['c'].iloc[-5]*100
 if change < 0.15:
  return False, f"🏦 السوق نايم\n${price:.2f} | تغير {change:.2f}%\nما في توصية - سبت واحد مسكر"

 if ema20 > ema50 and 55 < rsi < 68:
  return True, f"🔥 LONG قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${price*0.997:.2f}\nهدف ${price*1.005:.2f}\nEMA20 {ema20:.1f}>EMA50 {ema50:.1f} RSI {rsi:.1f}"

 if ema20 < ema50 and 32 < rsi < 48:
  return True, f"🔥 SHORT قوي 🔥\n{SYMBOL} ${price:.2f}\nدخول ${price:.2f}\nستوب ${price*1.003:.2f}\nهدف ${price*0.995:.2f}\nEMA20 {ema20:.1f}<EMA50 {ema50:.1f} RSI {rsi:.1f}"

 return False, f"⏸️ تحت المراقبة\n${price:.2f} | EMA {ema20:.1f}/{ema50:.1f} | RSI {rsi:.1f}"

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
  try: await ctx.bot.send_message(chat_id=cid, text=f"🚨 تلقائي 🚨\n{msg}")
  except: pass

if __name__=="__main__":
 if TOKEN:
  b=Application.builder().token(TOKEN).build()
  b.add_handler(CommandHandler("start",start))
  b.add_handler(CommandHandler("tawsiya",tawsiya))
  b.job_queue.run_repeating(auto_check, interval=600, first=20)
  b.run_polling()
