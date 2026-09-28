import os, telebot, requests, threading, time
import yfinance as yf, pandas as pd
from flask import Flask
from datetime import datetime
TOKEN=os.getenv("BOT_TOKEN2") or os.getenv("BOT_TOKEN") or "8347268155:AAH3oQ4MaH1rWxvoEOLfgPI_DfRAsNBY"
MY_ID=1347502348
bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)
auto_mode=True
@app.route('/')
def home(): return "Super Bot V3"
def get_data():
 try:
  d=yf.download("GC=F",period="10d",interval="15m",progress=False)
  return d
 except: return None
def super_analysis():
 data=get_data()
 if data is None or len(data)<100:
  p=4292.0
  try: p=float(requests.get("https://api.gold-api.com/price/XAU",timeout=5).json()['price'])
  except: pass
  return {"price":p,"signal":"WAIT 🟡","rsi":50,"ema50":p,"ema200":p,"sup":p-15,"res":p+15,"atr":10,"gann":0,"zones":[]}
 close=data['Close'];high=data['High'];low=data['Low']
 price=float(close.iloc[-1])
 ema50=float(close.ewm(span=50).mean().iloc[-1])
 ema200=float(close.ewm(span=200).mean().iloc[-1])
 delta=close.diff();gain=delta.where(delta>0,0).rolling(14).mean();loss=-delta.where(delta<0,0).rolling(14).mean();rs=gain/loss;rsi=100-(100/(1+rs));rsi_val=float(rsi.iloc[-1])
 atr=float((high-low).rolling(14).mean().iloc[-1])
 sup=float(low.rolling(50).min().iloc[-1]);res=float(high.rolling(50).max().iloc[-1])
 # مناطق عرض/طلب
 zones=[]
 c=close.values;h=high.values;l=low.values
 for i in range(10,len(data)-5):
  move=(c[i]-c[i-4])/c[i-4]*100
  if abs(move)>0.8:
   if l[i]>h[i-2] or h[i]<l[i-2]:
    t="طلب DEMAND" if move>0 else "عرض SUPPLY"
    zones.append((t,float(l[i-1] if move>0 else h[i-1])))
 zones=zones[-3:]
 if ema50>ema200 and price>ema50 and rsi_val<65: sig="شراء قوي BUY 🟢"
 elif ema50<ema200 and price<ema50 and rsi_val>35: sig="بيع قوي SELL 🔴"
 else: sig="انتظار WAIT 🟡"
 return {"price":price,"signal":sig,"rsi":rsi_val,"ema50":ema50,"ema200":ema200,"sup":sup,"res":res,"atr":atr,"gann":datetime.now().timetuple().tm_yday%90,"zones":zones}
def send_full(chat_id):
 a=super_analysis();price=a['price']
 tp=price+a['atr']*2.5 if "BUY" in a['signal'] else price-a['atr']*2.5
 sl=price-a['atr']*1.5 if "BUY" in a['signal'] else price+a['atr']*1.5
 z="\n".join([f"- {t}: ${p:.2f}" for t,p in a['zones']]) if a['zones'] else "- لا يوجد مناطق قريبة"
 txt=f"🔥 توصية خارقة V3\n⏰ {datetime.now().strftime('%H:%M')}\n\n
