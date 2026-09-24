import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot OK"

def run():
    app.run(host='0.0.0.0', port=10000)

def get_candles():
    try:
        u="https://api.binance.com/api/v3/klines"
        p={"symbol":"PAXGUSDT","interval":"1h","limit":200}
        r=requests.get(u,params=p,timeout=10).json()
        return [float(c[4]) for c in r]
    except:
        u="https://min-api.cryptocompare.com/data/v2/histohour"
        p={"fsym":"PAXG","tsym":"USD","limit":200}
        r=requests.get(u,params=p,timeout=10).json()
        return [float(x['close']) for x in r['Data']['Data']]

def ema(prices,per):
    k=2/(per+1)
    e=sum(prices[:per])/per
    for x in prices[per:]:
        e=x*k+e*(1-k)
    return e

def rsi(prices):
    g=l=0
    for i in range(1,15):
        d=prices[-i]-prices[-i-1]
        if d>0: g+=d
        else: l+=abs(d)
    if l==0: return 70
    rs=g/l
    return 100-(100/(1+rs))

async def start(update,context):
    await update.message.reply_text("/gold /tawsiya")

async def gold(update,context):
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()
        await update.message.reply_text(f"${r['price']}")
    except:
        await update.message.reply_text("خطأ")

async def tawsiya(update,context):
    await update.message.reply_text("⏳ احلل...")
    c=get_candles()
    if len(c)<100:
        await update.message.reply_text("جرب بعد دقيقة")
        return
    price=c[-1]
    e50=ema(c,50)
    e200=ema(c,200)
    r=rsi(c)
    sup=min(c[-20:])
    res=max(c[-20:])
    if price>e50 and r<70:
        sig="🟢 BUY"
        tp=res
        sl=e50-10
    else:
        sig="🔴 SELL"
        tp=sup
        sl=res+10
    msg=f"XAU {sig}\n{price:.2f}\nEMA50 {e50:.2f}\nRSI {r:.1f}\nTP {tp:.2f}\nSL {sl:.2f}"
    await update.message.reply_text(msg)

def main():
    Thread(target=run,daemon=True).start()
    a=Application.builder().token(TOKEN).build()
    a.add_handler(CommandHandler("start",start))
    a.add_handler(CommandHandler("gold",gold))
    a.add_handler(CommandHandler("tawsiya",tawsiya))
    print("Bot started...")
    a.run_polling()

if __name__=="__main__":
    main()
