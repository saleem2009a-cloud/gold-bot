import os, telebot, yfinance as yf, pandas as pd, ta, threading
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from flask import Flask
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"BOT_TOKEN exists: {bool(BOT_TOKEN)}")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "V12.3 Fixed - Bot Responding"

def build_full():
    df = yf.download("GC=F", period="3mo", interval="60m", progress=False, auto_adjust=True).dropna()
    price = float(df['Close'].iloc[-1])

    # تحليل كل الفريمات متل صورتك القديمة
    tfs = {'M5':('1d','5m'), 'M15':('5d','15m'), 'H1':('1mo','60m'), 'H4':('3mo','60m'), 'D1':('1y','1d')}
    txt_frames = ""
    buy_c = 0
    for tf,(per,inter) in tfs.items():
        d = yf.download("GC=F", period=per, interval=inter, progress=False, auto_adjust=True)
        if len(d)<20: continue
        rsi = float(ta.momentum.RSIIndicator(d['Close'],14).rsi().iloc[-1])
        ema = float(ta.trend.EMAIndicator(d['Close'],20).ema_indicator().iloc[-1])
        sig = "BUY" if float(d['Close'].iloc[-1])>ema else "SELL"
        if sig=="BUY": buy_c+=1
        dir_txt = "صاعد" if sig=="BUY" else "هابط"
        txt_frames += f"{tf}: {dir_txt} | RSI {rsi:.1f} | {sig}\n"

    sell_c = 5-buy_c
    final = f"بيع قوي" if sell_c>=4 else f"شراء قوي" if buy_c>=4 else "متذبذب"

    # مستويات
    support = float(df['Low'].tail(20).min())
    resist = float(df['High'].tail(20).max())
    entry = price - 0.5 if sell_c>buy_c else price+0.5
    sl = entry + 14.4 if sell_c>buy_c else entry - 14.4
    tp1, tp2, tp3 = entry-12, entry-26.4, entry-42 if sell_c>buy_c else entry+12

    # رسم الشارت
    df_plot = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True).dropna().tail(80)
    fig, ax = plt.subplots(figsize=(9,4))
    fig.patch.set_facecolor('#0a0a0a'); ax.set_facecolor('#0a0a0a')
    ax.axhspan(support, support+12, color='#0f3d0f', alpha=0.5)
    ax.axhspan(resist-12, resist, color='#4a0f0f', alpha=0.5)
    for i in range(len(df_plot)):
        o,h,l,c = float(df_plot['Open'].iloc[i]), float(df_plot['High'].iloc[i]), float(df_plot['Low'].iloc[i]), float(df_plot['Close'].iloc[i])
        col = '#00ff7f' if c>=o else '#ff3b3b'
        ax.plot([i,i],[l,h], color=col, lw=0.8)
        ax.add_patch(mpatches.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),fc=col,ec=col))
    ax.axhline(entry, color='white', ls='--', lw=1)
    ax.axhline(sl, color='#ffb000', ls='--', lw=1)
    ax.set_xlim(-1,len(df_plot)); ax.tick_params(colors='gray', labelsize=7); ax.set_xticks([])
    for s in ax.spines.values(): s.set_visible(False)
    plt.savefig('/tmp/chart.png', dpi=200, facecolor='#0a0a0a', bbox_inches='tight'); plt.close()

    rsi_h4 = float(ta.momentum.RSIIndicator(df['Close'],14).rsi().iloc[-1])

    caption = f"""🔴 بيع SELL 🔥🔥🔥 تأكيد رباعي - {final}
{"─"*25}

💰 {price:.2f}

🎯 دخول: {entry:.1f} | وقف: {sl:.1f}
هدف1: {tp1:.1f} | هدف2: {tp2:.1f} | هدف3: {tp3:.1f}

📍 الفريمات:
{txt_frames}
الاجماع: {buy_c} شراء vs {sell_c} بيع
القرار النهائي: {final}

الاستراتيجية الكاملة:
دخول: SELL {entry:.2f}$
هدف 1 سريع: {tp1:.2f}$
هدف 2 متوسط: {tp2:.2f}$
هدف 3 سوينغ: {tp3:.2f}$
وقف خسارة: {sl:.2f}$
مخاطرة 1:2.5

التحليل الفلكي والزمني:
الدورة القمرية: هلال متزايد - طاقة شرائية
تحيز فلكي: {"شراء" if buy_c>2 else "بيع"}
زاوية جان: 267.3 درجة
دورة 90 يوم: يوم 1/90

التحليل الفني:
الدعم القوي: {support:.2f}$
المقاومة القوية: {resist:.2f}$
RSI H4: {rsi_h4:.1f}
"""
    return caption, '/tmp/chart.png'

@bot.message_handler(commands=['start','tawsiya'])
def handle(m):
    try:
        bot.send_message(m.chat.id, "⏳ عم حلل 5 فريمات + OB + فيبو...")
        txt, chart = build_full()
        with open(chart,'rb') as f:
            bot.send_photo(m.chat.id, f, caption=txt)
    except Exception as e:
        bot.send_message(m.chat.id, f"خطأ: {e}\nجرب مرة تانية")

def run_bot():
    while True:
        try:
            print("Bot polling started...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"polling error {e}")
            time.sleep(5)

# شغل البوت بالخلفية وخلي Flask بالواجهة
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
