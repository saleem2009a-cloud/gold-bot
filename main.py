import os,telebot,requests,threading,time,math
import yfinance as yf
from flask import Flask
from datetime import datetime

TOKEN=os.getenv("BOT_TOKEN2") or "8347268155:AAH3oQ4MaH1rWxvoEgoEOLfgPI_DfRAsNBY"
MY_ID=1347502348
bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)

@app.route('/')
def home(): return "V6 ULTRA"

def get_data():
 try:
  d=yf.download("GC=F",period="10d",interval="15m",progress=False)
  if len(d)<150: d=yf.download("XAUUSD=X",period="10d",interval="15m",progress=False)
  return d
 except: return None

def moon_phase():
 # حساب فلكي بسيط
 now=datetime.now()
 # دورة القمر 29.53 يوم
 known_new_moon=datetime(2024,1,11)
 diff=(now-known_new_moon).days
 phase=(diff % 29.53)/29.53*100
 if phase<25: return f"هلال جديد 🌙 {phase:.0f}% - صعود ضعيف"
 elif phase<50: return f"تربيع اول 🌓 {phase:.0f}% - صعود قوي"
 elif phase<75: return f"بدر 🌕 {phase:.0f}% - قمة محتملة"
 else: return f"تربيع ثاني 🌗 {phase:.0f}% - هبوط"

def ultra_analysis():
 d=get_data()
 if d is None:
  return None
 c=d['Close'];h=d['High'];l=d['Low'];o=d['Open']
 price=float(c.iloc[-1])

 # فني
 ema50=float(c.ewm(50).mean().iloc[-1]);ema200=float(c.ewm(200).mean().iloc[-1])
 delta=c.diff();gain=delta.where(delta>0,0).rolling(14).mean();loss=-delta.where(delta<0,0).rolling(14).mean();rsi=100-(100/(1+gain/loss));rsi_v=float(rsi.iloc[-1])
 atr=float((h-l).rolling(14).mean().iloc[-1])
 sup=float(l.rolling(50).min().iloc[-1]);res=float(h.rolling(50).max().iloc[-1])

 # عرض وطلب من الفيديو 1
 zones=[]
 closes=c.values;highs=h.values;lows=l.values
 for i in range(20,len(d)-5):
  move=(closes[i]-closes[i-4])/closes[i-4]*100
  if abs(move)>0.7:
   if lows[i]>highs[i-2] or highs[i]<lows[i-2]: # FVG
    typ="طلب DEMAND" if move>0 else "عرض SUPPLY"
    zones.append((typ,float(lows[i-1] if move>0 else highs[i-1])))
 zones=zones[-3:]

 # 50% مخفض من الفيديو 2
 last50=d.tail(60);sw_low=float(last50['Low'].min());sw_high=float(last50['High'].max())
 fib50=sw_low+(sw_high-sw_low)*0.5
 discount=price<fib50
 red=0
 for i in range(len(c.tail(5))-1,0,-1):
  if c.tail(5).values[i]<c.tail(5).values[i-1]: red+=1
  else: break
 green=c.iloc[-1]>o.iloc[-1]

 # دورة زمنية Gann
 day=datetime.now().timetuple().tm_yday
 gann=day % 90
 gann_txt="وقت دخول" if gann<10 or gann>80 else "وسط الدورة"

 # قرار نهائي خارق
 score=0
 if price>ema50: score+=1
 if price>ema200: score+=1
 if rsi_v>40 and rsi_v<65: score+=1
 if discount: score+=1
 if red>=2: score+=1
 if green: score+=1
 if len([z for z in zones if "DEMAND" in z[0] and price<z[1]+10])>0: score+=1

 if score>=5:
  sig="شراء قوي BUY 🟢🟢";quick="BUY سريع ⚡";tp=price+atr*3;sl=sup
 elif score>=3:
  sig="شراء متوسط BUY 🟡";quick="انتظار BUY";tp=price+atr*2;sl=price-atr*1.5
 elif price<ema50 and price<ema200:
  sig="بيع SELL 🔴";quick="SELL سريع ⚡";tp=price-atr*2.8;sl=res
 else:
  sig="انتظار WAIT ⚪";quick="لا دخول";tp=price+12;sl=price-12

 return {"price":price,"sig":sig,"quick":quick,"rsi":rsi_v,"ema50":ema50,"ema200":ema200,"sup":sup,"res":res,"fib50":fib50,"discount":discount,"red":red,"green":green,"atr":atr,"tp":tp,"sl":sl,"zones":zones,"gann":gann,"gann_txt":gann_txt,"score":score,"sw_low":sw_low,"sw_high":sw_high}

def send(chat_id):
 a=ultra_analysis()
 if not a:
  bot.send_message(chat_id,"⚠️ خطأ بيانات");return
 zones_txt="\n".join([f"- {t}: ${p:.2f}" for t,p in a['zones']]) if a['zones'] else "- لا يوجد"
 txt=f"""🚀 البوت الخارق V6 - كل الاستراتيجيات

⚡ السريع: {a['quick']} - {a['sig']}
💰 ${a['price']:.2f} | قوة: {a['score']}/7

📈 الفيديو 1 (عرض وطلب):
{zones_txt}

📉 الفيديو 2 (50% مخفض):
- فيبو 50%: ${a['fib50']:.2f} - {"✅ مخفض" if a['discount'] else "❌ فوق"}
- قاع: ${a['sw_low']:.2f} قمة: ${a['sw_high']:.2f}
- تصحيح: {a['red']} شموع | تأكيد: {"✅" if a['green'] else "❌"}

📊 الفني القديم:
- RSI: {a['rsi']:.1f} | EMA50/200: {a['ema50']:.1f}/{a['ema200']:.1f}
- دعم: ${a['sup']:.2f} مقاومة: ${a['res']:.2f}
- ATR: {a['atr']:.2f}

⏳ زمني Gann: {a['gann']}° - {a['gann_txt']}
🌙 فلكي: {moon_phase()}

🎯 TP: ${a['tp']:.2f} 🛑 SL: ${a['sl']:.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}

💬 اسألني: /se3r /news
"""
 bot.send_message(chat_id,txt)

@bot.message_handler(commands=['start','tawsiya','se3r','price','chart','news'])
def cmds(m):
 if m.text=='/news':
  bot.send_message(m.chat.id,"📢 اخبار: تضخم امريكي + قرار فائدة - تأثير مباشر على الذهب")
 else:
  send(m.chat.id)

def auto():
 while True:
  time.sleep(600) # 10 دقايق
  try: send(MY_ID)
  except: pass

threading.Thread(target=auto,daemon=True).start()
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=int(os.environ.get("PORT",10000))),daemon=True).start()
bot.infinity_polling()
from flask import Flask
import threading
import os

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is Live!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()
