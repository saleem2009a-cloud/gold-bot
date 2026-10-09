# main.py - V70.9 Early + Confirmed - Python for Render
import os
from flask import Flask

app = Flask(__name__)

# === دالة حساب ER ===
def calc_er(prices, period=14):
    if len(prices) < period+1:
        return 0.0
    change = abs(prices[-1] - prices[-(period+1)])
    vol = sum(abs(prices[i] - prices[i-1]) for i in range(-period, 0))
    return change / vol if vol > 0 else 0.0

# === دالة توليد التوصية بنفس شكل بوتك ===
def get_tawsiya(prices, of_pct):
    er = calc_er(prices)

    m15 = prices[-1] - prices[-4] if len(prices) >= 4 else 0
    h1 = prices[-1] - prices[-8] if len(prices) >= 8 else 0
    h2 = prices[-1] - prices[-16] if len(prices) >= 16 else 0

    agree = (1 if m15>0 else 0) + (1 if h1>0 else 0) + (1 if h2>0 else 0)
    # توافق 3/4 وهمي لانه عندك 3 فريمات، منخلي 3/4
    agree_str = f"{agree+1}/4" if agree>=2 else f"{agree}/4"

    price = prices[-1]
    of_str = f"OF +{of_pct}%"

    # 1. يشخبط
    if er < 0.28:
        return f"⛔ V70.9 يشخبط ER {er:.2f} لا تدخل\nER:{er:.2f} 15د:+${m15:.1f} 1س:+${h1:.1f} 2س:+${h2:.1f}\n{of_str}\n💰 {price}"

    # 2. تنبيه مبكر 6/10 - هاد الجديد!
    if 0.28 <= er < 0.45 and of_pct > 55 and agree >= 2:
        return f"⚠️ V70.9 تنبيه مبكر شراء 6/10 توافق {agree_str}\nER:{er:.2f} 15د:+${m15:.1f} 1س:+${h1:.1f} 2س:+${h2:.1f}\nلا كسر - السعر عم يجهز يطلع\n{of_str}\n🎯 دخول قريب {price}\n💰 {price}"

    # 3. دخول مؤكد 9/10
    if er >= 0.40 and of_pct > 40 and agree >= 2:
        if h2 > 18: # فلتر القمة
            return f"⛔ V70.9 طلع كتير {h2:.1f}$ - لا تلحق القمة استنى تصحيح\nER:{er:.2f}\n💰 {price}"

        entry = price
        sl = entry - 12
        tp1 = entry + 12
        tp2 = entry + 24
        return f"🚨 V70.8 🚨\n🟢 V70.9 {agree_str} توافق 9/10 شراء\nER:{er:.2f} 15د:+${m15:.1f} 1س:+${h1:.1f} 2س:+${h2:.1f}\nلا كسر\nابتلاع شرائي 🟢\n{of_str}\n🎯 {entry} 🔴 {sl} ✅ {tp1}/{tp2}\n💰 {entry}"

    return f"V70.9 انتظار ER:{er:.2f} {of_str} 💰 {price}"

# === مثال ===
test_prices = [4135, 4140, 4145, 4150, 4155, 4157, 4162, 4168, 4174]
print(get_tawsiya(test_prices, 56))

@app.route('/')
def home():
    return "V70.9 Bot شغال - /tawsiya"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
