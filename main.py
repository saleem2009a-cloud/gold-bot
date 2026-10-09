# main.py - V70.8 الأصلية + V70.9 تنبيه مبكر - لا شي محذوف
import os
from flask import Flask
app = Flask(__name__)

def calc_er(prices, period=14):
    if len(prices) < period+1:
        return 0.0
    change = abs(prices[-1] - prices[-(period+1)])
    vol = sum(abs(prices[i] - prices[i-1]) for i in range(-period, 0))
    return change / vol if vol > 0 else 0.0

def get_tawsiya_v70_8_original(prices, of_pct):
    """ هادي هي استراتيجيتك القديمة نفسها بالحرف - ما لعبت فيها """
    er = calc_er(prices, 14)

    d15 = prices[-1] - prices[-4] if len(prices) >=4 else 0
    d1h = prices[-1] - prices[-8] if len(prices) >=8 else 0
    d2h = prices[-1] - prices[-16] if len(prices) >=16 else 0

    # توافق قديم
    agree = (1 if d15>0 else 0) + (1 if d1h>0 else 0) + (1 if d2h>0 else 0)
    agree_str = "3/4" if agree==3 else "2/4" if agree==2 else f"{agree}/4"

    price = prices[-1]
    entry = round(price, 1)
    sl = round(entry - 12, 1)
    tp1 = round(entry + 12, 1)
    tp2 = round(entry + 24, 1)

    # === V70.8 الأصلي: يشخبط ===
    if er < 0.25:
        # نفس رسالتك بالصورة: ⛔ V70.8 يشخبط ER 0.23 لا تدخل
        return f"⛔ V70.8 يشخبط ER {er:.2f} لا تدخل\nER:{er:.2f} 15د:+${d15:.1f} 1س:+${d1h:.1f} 2س:+${d2h:.1f}\nOF +{of_pct}%\n💰 {price}"

    # === V70.8 الأصلي: شراء 9/10 ===
    if er >= 0.40 and agree >= 2 and of_pct > 35:
        # نفس رسالتك بالصورة
        return f"🚨 V70.8 🚨\n🟢 V70.8 {agree_str} توافق 9/10 شراء\nER:{er:.2f} 15د:+${d15:.1f} 1س:+${d1h:.1f} 2س:+${d2h:.1f}\nلا كسر\nابتلاع شرائي 🟢\nOF +{of_pct}%\n🎯 {entry} 🔴 {sl} ✅ {tp1}/{tp2}\n💰 {entry}"

    return None # ما في اشارة

def get_tawsiya_v70_9_with_early(prices, of_pct):
    """ هون الجديد - بنفحص التنبيه المبكر قبل القديم """
    er = calc_er(prices, 14)
    d15 = prices[-1] - prices[-4] if len(prices) >=4 else 0
    d1h = prices[-1] - prices[-8] if len(prices) >=8 else 0
    d2h = prices[-1] - prices[-16] if len(prices) >=16 else 0
    agree = (1 if d15>0 else 0) + (1 if d1h>0 else 0) + (1 if d2h>0 else 0)
    agree_str = "3/4" if agree==3 else "2/4" if agree==2 else f"{agree}/4"
    price = prices[-1]

    # === جديد V70.9: تنبيه مبكر 6/10 ===
    # بيجي قبل اشارة 9/10 بـ 15-20$
    is_rising = prices[-1] > prices[-2] > prices[-3] if len(prices)>=3 else False
    if 0.28 <= er < 0.45 and of_pct >= 55 and agree >= 2 and is_rising:
        return f"⚠️ V70.9 تنبيه مبكر شراء 6/10 توافق {agree_str}\nER:{er:.2f} 15د:+${d15:.1f} 1س:+${d1h:.1f} 2س:+${d2h:.1f}\nلا كسر - السعر عم يجهز يطلع\nOF +{of_pct}%\n🎯 دخول قريب {price}\n💰 {price}"

    # اذا ما في تنبيه مبكر، رجع للاستراتيجية القديمة الأصلية
    old_signal = get_tawsiya_v70_8_original(prices, of_pct)
    if old_signal:
        return old_signal

    # ما في شي
    er = calc_er(prices)
    return f"V70.8 انتظار ER:{er:.2f} OF +{of_pct}% 💰 {price}"

# --- اختبار بنفس ارقام صورتك ---
# عند 03:21 كان ER 0.23
prices_0321 = [4145, 4148, 4150, 4152, 4157.7]
print(get_tawsiya_v70_9_with_early(prices_0321, 64))
# عند 03:58 كان ER 0.47
prices_0358 = [4140, 4150, 4160, 4170, 4174.2]
print(get_tawsiya_v70_9_with_early(prices_0358, 56))

@app.route('/')
def home():
    return "V70.8 + V70.9 شغال"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
