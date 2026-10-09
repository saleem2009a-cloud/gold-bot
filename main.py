import os, time, threading
from datetime import datetime, timezone
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
COOLDOWN = 3 * 3600
CHECK_EVERY = 300
FIB = [21, 34, 55, 89, 144]              # دورات فيبوناتشي (أيام)
GANN = [90, 180, 360]                    # دورات جان (أيام)

app = Flask(__name__)
last = {"dir": None, "t": 0}
status = {"msg": "starting"}
auto = {"on": True}


# ---------------- مؤشرات فنية ----------------
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


def engulf(df):
    """ابتلاع على آخر شمعة مغلقة: 1 صاعد، -1 هابط، 0 لا يوجد"""
    o, c = df["Open"], df["Close"]
    po, pc = o.iloc[-3], c.iloc[-3]
    co, cc = o.iloc[-2], c.iloc[-2]
    if pc < po and cc > co and cc >= po and co <= pc:
        return 1
    if pc > po and cc < co and cc <= po and co >= pc:
        return -1
    return 0


# ---------------- الدورات الزمنية ----------------
def cycle(d1):
    h, l = d1["High"], d1["Low"]
    w, n = 5, len(d1)
    sh = sl = None
    for i in range(n - w - 1, max(w, n - 260), -1):
        if sh is None and h.iloc[i] == h.iloc[i - w:i + w + 1].max():
            sh = i
        if sl is None and l.iloc[i] == l.iloc[i - w:i + w + 1].min():
            sl = i
        if sh is not None and sl is not None:
            break
    today = datetime.now(timezone.utc).date()
    res = {"support": 0, "txt": "⏳ الدورات: لا بيانات كافية"}
    lines, low_hit, high_hit = [], False, False
    if sl is not None:
        days = (today - d1.index[sl].date()).days
        hit = [x for x in FIB + GANN if abs(days - x) <= 1]
        low_hit = bool(hit)
        lines.append(f"آخر قاع قبل {days} يوم" + (f" ⚡ نافذة دورية {hit[0]}" if hit else ""))
    if sh is not None:
        days = (today - d1.index[sh].date()).days
        hit = [x for x in FIB + GANN if abs(days - x) <= 1]
        high_hit = bool(hit)
        lines.append(f"آخر قمة قبل {days} يوم" + (f" ⚡ نافذة دورية {hit[0]}" if hit else ""))
    if lines:
        res["txt"] = "⏳ الدورات: " + " | ".join(lines)
    if low_hit and not high_hit:
        res["support"] = 1      # نافذة قاع ← دعم الشراء
    elif high_hit and not low_hit:
        res["support"] = -1     # نافذة قمة ← دعم البيع
    return res


# ---------------- الفلكي (أطوار القمر) ----------------
def moon():
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    syn = 29.530588853
    age = ((datetime.now(timezone.utc) - ref).total_seconds() / 86400) % syn
    if age < 1.0 or age > syn - 1.0:
        return "🌑 قمر جديد: نافذة انعكاس محتملة", True
    if abs(age - syn / 2) < 1.0:
        return "🌕 بدر: نافذة انعكاس محتملة", True
    ph = "هلال متزايد" if age < syn / 2 else "هلال متناقص"
    return f"🌙 {ph} (عمر {age:.0f} يوم)", False


# ---------------- التحليل الكامل ----------------
def analyze():
    d1 = get("1d", "2y")
    h1 = get("1h", "60d")
    h4 = h1.resample("4h").agg({"Open": "first", "High": "max", "Low": "min",
                                "Close": "last"}).dropna()
    m15 = get("15m", "5d")

    price = float(h1["Close"].iloc[-1])
    t_d1, t_h4 = trend(d1), trend(h4)
    moon_txt, moon_hit = moon()
    cyc = cycle(d1)
    r = {"price": price, "t_d1": t_d1, "t_h4": t_h4, "moon": moon_txt,
         "cycle": cyc["txt"], "dir": None, "score": 0, "notes": []}
    if t_h4 == 0 or t_d1 == -t_h4:
        return r

    d = t_h4
    notes = [f"اتجاه H4 {nm(d)} (+25)"]
    score = 25
    if t_d1 == d:
        score += 15
        notes.append("D1 يوافق الاتجاه (+15)")

    c = h1["Close"]
    e21, e50 = ema(c, 21), ema(c, 50)
    a = float(atr(h1).iloc[-2])
    rr = rsi(c)
    if (e21.iloc[-2] > e50.iloc[-2]) == (d == 1):
        score += 10
        notes.append("ترتيب المتوسطات H1 (+10)")
    dist = abs(price - float(e21.iloc[-2]))
    if dist <= a:
        score += 15
        notes.append("تصحيح قريب من EMA21 (+15)")
    elif dist > 2 * a:
        score -= 15
        notes.append("السعر ممتد، خطر مطاردة (-15)")
    if d == 1 and 40 <= rr.iloc[-2] <= 62 and rr.iloc[-2] > rr.iloc[-3]:
        score += 5
        notes.append("RSI يدعم الشراء (+5)")
    if d == -1 and 38 <= rr.iloc[-2] <= 60 and rr.iloc[-2] < rr.iloc[-3]:
        score += 5
        notes.append("RSI يدعم البيع (+5)")

    e4, e1, em = engulf(h4), engulf(h1), engulf(m15)
    kind = "صاعد" if d == 1 else "هابط"
    if e4 == d:
        score += 15
        notes.append(f"ابتلاع {kind} على H4 (+15)")
    elif e1 == d:
        score += 15
        notes.append(f"ابتلاع {kind} على H1 (+15)")
    elif em == d:
        score += 8
        notes.append(f"ابتلاع {kind} على M15 (+8)")

    if cyc["support"] == d:
        score += 10
        notes.append("نافذة دورة زمنية تدعم الاتجاه (+10)")
        if moon_hit:
            score += 5
            notes.append("توافق فلكي (+5)")

    sl_dist, tp_dist = 1.5 * a, 3.0 * a
    r.update(dir=d, score=max(0, min(100, score)), notes=notes,
             entry=price, sl=price - d * sl_dist, tp=price + d * tp_dist,
             rr=tp_dist / sl_dist)
    return r


def fmt(r, header="🥇 تحليل الذهب"):
    L = [header, f"💰 السعر: {r['price']:.2f}",
         f"D1: {nm(r['t_d1'])} | H4: {nm(r['t_h4'])}"]
    if r["dir"] is None:
        L.append("⚪ لا توصية: لا اتجاه مشترك واضح")
    else:
        side = "شراء 🟢" if r["dir"] == 1 else "بيع 🔴"
        if r["score"] >= MIN_SCORE:
            L += [f"✅ توصية: {side}", f"الدخول: {r['entry']:.2f}",
                  f"وقف الخسارة: {r['sl']:.2f}", f"الهدف: {r['tp']:.2f}",
                  f"ربح/خسارة: {r['rr']:.1f}"]
        else:
            L.append(f"⚪ لا فرصة قوية بعد ({side} محتمل)، الأفضل الانتظار")
        L.append(f"قوة الإشارة: {r['score']}/100")
        L += ["• " + n for n in r["notes"]]
    L += [r["cycle"], r["moon"],
          "ℹ️ الدورات والفلك عوامل مساعدة بوزن صغير فقط، والقرار للفني.",
          "⚠️ تحليل آلي وليس توصية مالية. خاطر بأقل من 1% من الرصيد."]
    return "\n".join(L)


# ---------------- تليجرام ----------------
def send(text):
    if not TOKEN or not CHAT:
        print(text, flush=True)
        return
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT, "text": text}, timeout=15)


def reply(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": chat_id, "text": text}, timeout=15)


def loop():
    while True:
        try:
            r = analyze()
            status["msg"] = f"سعر {r['price']:.2f} | قوة {r['score']}"
            if auto["on"] and r["dir"] and r["score"] >= MIN_SCORE:
                if r["dir"] != last["dir"] or time.time() - last["t"] > COOLDOWN:
                    send(fmt(r, "🔔 توصية جديدة"))
                    last.update(dir=r["dir"], t=time.time())
        except Exception as e:
            status["msg"] = f"error: {e}"
            print(f"[loop] error: {e}", flush=True)
        time.sleep(CHECK_EVERY)


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
                    reply(cid, fmt(analyze()))
                elif text.startswith("/price"):
                    p = float(get("5m", "1d")["Close"].iloc[-1])
                    reply(cid, f"💰 الذهب الآن: {p:.2f}")
                elif text.startswith("/auto_on"):
                    auto["on"] = True
                    reply(cid, "✅ التوصيات التلقائية مفعّلة")
                elif text.startswith("/auto_off"):
                    auto["on"] = False
                    reply(cid, "⏸️ التوصيات التلقائية متوقفة")
                elif text.startswith("/status"):
                    reply(cid, f"التلقائي: {'شغال' if auto['on'] else 'متوقف'}\nآخر فحص: {status['msg']}")
                elif text.startswith("/start"):
                    reply(cid, "أهلاً! الأوامر:\n/tawsiya تحليل كامل\n/price السعر\n/auto_on /auto_off\n/status")
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
