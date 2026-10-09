import os, time, threading
import requests
import pandas as pd
import yfinance as yf
from flask import Flask

def env(*names):
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip().strip('"').strip("'")
    return None


TOKEN = env("TELEGRAM_TOKEN", "BOT_TOKEN", "TOKEN", "TELEGRAM_BOT_TOKEN", "API_TOKEN")
CHAT = env("CHAT_ID", "TELEGRAM_CHAT_ID", "CHAT", "USER_ID")
print(f"[startup] token set: {bool(TOKEN)} | chat id set: {bool(CHAT)}", flush=True)
SYMBOL = "GC=F"                          # عقود الذهب (قريب من السبوت)
MIN_SCORE = int(os.getenv("MIN_SCORE", "70"))
COOLDOWN = 3 * 3600                      # لا تكرر نفس الاتجاه قبل 3 ساعات
CHECK_EVERY = 300                        # فحص كل 5 دقائق

app = Flask(__name__)
last = {"dir": None, "t": 0}
status = {"msg": "starting"}
auto = {"on": True}


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(df, n=14):
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def get(interval, period):
    df = yf.download(SYMBOL, interval=interval, period=period,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def trend(df):
    c = df["Close"]
    p = c.iloc[-2]
    e21, e50 = ema(c, 21).iloc[-2], ema(c, 50).iloc[-2]
    if p > e50 and e21 > e50:
        return 1
    if p < e50 and e21 < e50:
        return -1
    return 0


def nm(t):
    return {1: "صاعد 🟢", -1: "هابط 🔴", 0: "محايد ⚪"}[t]


def analyze():
    d1 = get("1d", "2y")
    h1 = get("1h", "60d")
    h4 = h1.resample("4h").agg({"Open": "first", "High": "max", "Low": "min",
                                "Close": "last"}).dropna()
    m15 = get("15m", "5d")

    t_d1, t_h4 = trend(d1), trend(h4)
    if t_h4 == 0 or t_d1 == -t_h4:
        return None, f"D1: {nm(t_d1)} | H4: {nm(t_h4)} ← لا اتجاه مشترك واضح"
    d = t_h4
    score = 30                                  # اتجاه H4
    score += 20 if t_d1 == d else 0             # توافق D1

    c = h1["Close"]
    e21, e50 = ema(c, 21), ema(c, 50)
    a = atr(h1).iloc[-2]
    price = c.iloc[-1]
    r = rsi(c)
    if (e21.iloc[-2] > e50.iloc[-2]) == (d == 1):
        score += 15                             # ترتيب المتوسطات على H1
    if abs(price - e21.iloc[-2]) <= a:          # تصحيح قريب (ليس مطاردة)
        score += 20
    elif abs(price - e21.iloc[-2]) > 2 * a:
        score -= 15                             # السعر ممتد، خطر مطاردة
    if d == 1 and 40 <= r.iloc[-2] <= 62 and r.iloc[-2] > r.iloc[-3]:
        score += 10
    if d == -1 and 38 <= r.iloc[-2] <= 60 and r.iloc[-2] < r.iloc[-3]:
        score += 10
    m = m15["Close"]
    if (m.iloc[-2] > ema(m, 21).iloc[-2]) == (d == 1):
        score += 5                              # تأكيد M15

    sl_dist, tp_dist = 1.5 * a, 3.0 * a
    entry = float(price)
    sl = entry - d * sl_dist
    tp = entry + d * tp_dist
    return {"dir": d, "score": score, "entry": entry, "sl": sl, "tp": tp,
            "rr": tp_dist / sl_dist}, f"score={score}"


def send(text):
    if not TOKEN or not CHAT:
        print(text)
        return
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT, "text": text}, timeout=15)


def loop():
    while True:
        try:
            sig, info = analyze()
            status["msg"] = info
            if auto["on"] and sig and sig["score"] >= MIN_SCORE:
                if sig["dir"] != last["dir"] or time.time() - last["t"] > COOLDOWN:
                    send(fmt(sig))
                    last.update(dir=sig["dir"], t=time.time())
        except Exception as e:
            status["msg"] = f"error: {e}"
            print(f"[loop] error: {e}", flush=True)
        time.sleep(CHECK_EVERY)


def fmt(sig):
    side = "شراء 🟢" if sig["dir"] == 1 else "بيع 🔴"
    return (f"🥇 توصية ذهب: {side}\n"
            f"الدخول: {sig['entry']:.2f}\n"
            f"وقف الخسارة: {sig['sl']:.2f}\n"
            f"الهدف: {sig['tp']:.2f}\n"
            f"نسبة ربح/خسارة: {sig['rr']:.1f}\n"
            f"قوة الإشارة: {sig['score']}/100\n"
            f"⚠️ تحليل آلي وليس توصية مالية. خاطر بأقل من 1% من الرصيد.")


def reply(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": chat_id, "text": text}, timeout=15)


def commands():
    if not TOKEN:
        print("[commands] NO TOKEN FOUND - add TELEGRAM_TOKEN in Render Environment", flush=True)
        return
    try:
        me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15).json()
        print(f"[commands] getMe: {me.get('ok')} {me.get('description', '')}", flush=True)
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", timeout=15)
    except Exception as e:
        print(f"[commands] startup error: {e}", flush=True)
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                             params={"offset": offset, "timeout": 30}, timeout=40).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                text = (msg.get("text") or "").strip().lower()
                cid = msg.get("chat", {}).get("id")
                if not cid:
                    continue
                print(f"[commands] got: {text}", flush=True)
                if text.startswith("/tawsiya"):
                    reply(cid, "⏳ جاري التحليل...")
                    sig, info = analyze()
                    if sig is None:
                        reply(cid, f"⚪ لا توصية الآن: {info}")
                    elif sig["score"] >= MIN_SCORE:
                        reply(cid, fmt(sig))
                    else:
                        reply(cid, f"⚪ لا فرصة قوية الآن (قوة {sig['score']}/100، "
                                   f"الاتجاه {'صاعد' if sig['dir'] == 1 else 'هابط'}). "
                                   "الأفضل الانتظار.")
                elif text.startswith("/auto_on"):
                    auto["on"] = True
                    reply(cid, "✅ التوصيات التلقائية مفعّلة")
                elif text.startswith("/auto_off"):
                    auto["on"] = False
                    reply(cid, "⏸️ التوصيات التلقائية متوقفة")
                elif text.startswith("/status"):
                    reply(cid, f"التلقائي: {'شغال' if auto['on'] else 'متوقف'}\nآخر فحص: {status['msg']}")
                elif text.startswith("/start"):
                    reply(cid, "أهلاً! أرسل /tawsiya للحصول على تحليل الذهب الآن.")
        except Exception as e:
            status["msg"] = f"cmd error: {e}"
            print(f"[commands] error: {e}", flush=True)
            time.sleep(5)


@app.route("/")
def home():
    return f"gold-bot running | {status['msg']}"


threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=commands, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
