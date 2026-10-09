# main.py - GOLD V70.9 Python for Render
import time
import os

print("V70.9 Python شغال...")

def calculate_er(prices, period=14):
    if len(prices) < period + 1:
        return 0
    change = abs(prices[-1] - prices[-(period+1)])
    vol = sum(abs(prices[i] - prices[i-1]) for i in range(-period, 0))
    return change / vol if vol > 0 else 0

# تخزين اسعار وهمي للتجربة - انت بدلو ب API تبعك
prices = [4150, 4152, 4155, 4158, 4162, 4168, 4171, 4174, 4176]
of_values = [50, 55, 60, 62, 64, 58, 60, 65]

er = calculate_er(prices)
of_ma = sum(of_values[-10:]) / len(of_values)

m15 = prices[-1] - prices[-4] if len(prices) >=4 else 0
h1 = prices[-1] - prices[-8] if len(prices) >=8 else 0
h2 = prices[-1] - prices[-16] if len(prices) >=16 else 0

agree = (1 if m15>0 else 0) + (1 if h1>0 else 0) + (1 if h2>0 else 0)

bullEng = prices[-1] > prices[-2]

earlyBuy = er > 0.28 and er < 0.45 and of_ma > 55 and agree >= 2
confirmedBuy = er >= 0.40 and of_ma > 50 and agree >= 3 and bullEng

if earlyBuy and not confirmedBuy:
    print(f"⚠️ V70.9 تنبيه مبكر شراء 6/10 ER:{er:.2f} OF:{of_ma:.0f}% السعر:{prices[-1]}")

if confirmedBuy:
    if h2 < 20:
        print(f"🟢 V70.9 شراء 9/10 توافق {agree}/4 ER:{er:.2f} دخول {prices[-1]} SL {prices[-1]-12} TP {prices[-1]+12}/{prices[-1]+24}")
    else:
        print(f"⛔ طلع كتير {h2:.1f}$ لا تلحق القمة")

# مشان Render ما يطفي
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return f"V70.9 شغال ER:{er:.2f} السعر:{prices[-1]}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
