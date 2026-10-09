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

SYMBOLS = ["XAUUSD=X", "GC=F"]           # سبوت أولاً، والعقود احتياطي (تُصحَّح بسعر السبوت)
MIN_SCORE = int(os.getenv("MIN_SCORE", "85"))
MAX_PER_DAY = 2                          # حد أقصى توصيتين باليوم
CHECK_EVERY = 120                        # فحص كل دقيقتين
COOLDOWN = 3600
SESSION = (7, 20)                        # ساعات لندن + نيويورك (UTC) للتوصيات التلقائية
FIB = [21, 34, 55, 89, 144]
GANN = [90, 180, 360]

app = Flask(__name__)
last = {"dir": None, "t": 0}
status = {"msg": "starting"}
auto = {"on": True}
active = {"sig": None, "t0": None, "be": False}
_cache = {}
used = {"sym": None}
offset = {"auto": 0.0, "manual": 0.0}
daily = {"d": None, "n": 0}


# ---------------- بيانات ----------------
def get_raw(interval, period):
    for sym in SYMBOLS:
        try:
            df = yf.download(sym, interval=interval, period=period,
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            if len(df) >= 5:
                used["sym"] = sym
                return df
        except Exception as e:
            print(f"[data] {sym} {interval} error: {e}", flush=True)
    raise RuntimeError("no price data")


def get_cached(interval, period, ttl):
    k = (interval, period)
    if k in _cache and time.time() - _cache[k][0] < ttl:
        return _cache[k][1]
    df = get_raw(interval, period)
    _cache[k] = (time.time(), df)
    return df


def spot_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=8).json()
        return float(r["price"])
    except Exception:
        return None


def refresh_offset(raw_last):
    """إذا اضطررنا لاستخدام العقود الآجلة نصحح الفرق بسعر السبوت الحي"""
    if used["sym"] == "GC=F":
        sp = spot_price()
        if sp:
            offset["auto"] = sp - raw_last
    else:
        offset["auto"] = 0.0


def shift(df):
    off = offset["auto"] + offset["manual"]
    df = df.copy()
    for k in ("Open", "High", "Low", "Close"):
        df[k] = df[k] + off
    return df


def get(interval, period, ttl=0):
    raw = get_cached(interval, period, ttl) if ttl else get_raw(interval, period)
    return shift(raw)


# ---------------- مؤشرات ----------------
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(df, n=14):
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(),
                    (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up, dn = df["High"].diff(), -df["Low"].diff()
    pdm = ((up > dn) & (up > 0)) * up
    ndm = ((dn > up) & (dn > 0)) * dn
    a = atr(df, n)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def macd_hist(c):
    m = ema(c, 12) - ema(c, 26)
    return m - ema(m, 9)


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


# ---------------- شموع ----------------
def engulf(df):
    o, c = df["Open"], df["Close"]
    po, pc, co, cc = o.iloc[-3], c.iloc[-3], o.iloc[-2], c.iloc[-2]
    if pc < po and cc > co and cc >= po and co <= pc:
        return 1
    if pc > po and cc < co and cc <= po and co >= pc:
        return -1
    return 0


def pinbar(df):
    o, c, h, l = [float(df[k].iloc[-2]) for k in ("Open", "Close", "High", "Low")]
    body, rng = abs(c - o), h - l
    if rng <= 0:
        return 0
    lw, uw = min(o, c) - l, h - max(o, c)
    b = max(body, rng * 0.05)
    if lw >= 2 * b and lw >= 0.55 * rng:
        return 1
    if uw >= 2 * b and uw >= 0.55 * rng:
        return -1
    return 0


# ---------------- مستويات وفيبو ----------------
def pivots(df, w=3, look=200):
    h, l, n = df["High"], df["Low"], len(df)
    hs, ls = [], []
    for i in range(max(w, n - look), n - w - 1):
        if h.iloc[i] == h.iloc[i - w:i + w + 1].max():
            hs.append(float(h.iloc[i]))
        if l.iloc[i] == l.iloc[i - w:i + w + 1].min():
            ls.append(float(l.iloc[i]))
    return hs, ls


def near_level(h1, d, price, a):
    hs, ls = pivots(h1)
    if d == 1:
        c = [x for x in ls if x <= price + 0.3 * a and price - x <= 0.8 * a]
        return max(c) if c else None
    c = [x for x in hs if x >= price - 0.3 * a and x - price <= 0.8 * a]
    return min(c) if c else None


def fib_zone(h4, d, price):
    seg = h4.iloc[-42:-1]
    ih, il = int(seg["High"].values.argmax()), int(seg["Low"].values.argmin())
    H, L = float(seg["High"].max()), float(seg["Low"].min())
    if H - L <= 0:
        return False
    if d == 1 and il < ih:
        ret = (H - price) / (H - L)
    elif d == -1 and ih < il:
        ret = (price - L) / (H - L)
    else:
        return False
    return 0.382 <= ret <= 0.618


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
        lines.append(f"آخر قاع قبل {days} يوم" + (f" ⚡ دورة {hit[0]}" if hit else ""))
    if sh is not None:
        days = (today - d1.index[sh].date()).days
        hit = [x for x in FIB + GANN if abs(days - x) <= 1]
        high_hit = bool(hit)
        lines.append(f"آخر قمة قبل {days} يوم" + (f" ⚡ دورة {hit[0]}" if hit else ""))
    if lines:
        res["txt"] = "⏳ الدورات: " + " | ".join(lines)
    if low_hit and not high_hit:
        res["support"] = 1
    elif high_hit and not low_hit:
        res["support"] = -1
    return res


# ---------------- التحليل الكامل ----------------
def analyze():
    raw15 = get_raw("15m", "5d")
    refresh_offset(float(raw15["Close"].iloc[-1]))
    d1 = get("1d", "2y", 3600)
    h1 = get("1h", "60d")
    h4 = h1.resample("4h").agg({"Open": "first", "High": "max", "Low": "min",
                                "Close": "last"}).dropna()
    m15 = shift(raw15)

    price = float(m15["Close"].iloc[-1])
    t_d1, t_h4 = trend(d1), trend(h4)
    cyc = cycle(d1)
    hour = datetime.now(timezone.utc).hour
    r = {"price": price, "t_d1": t_d1, "t_h4": t_h4, "cycle": cyc["txt"],
         "dir": None, "score": 0, "notes": [], "missing": [], "elite": False,
         "in_session": SESSION[0] <= hour < SESSION[1]}
    if t_h4 == 0 or t_d1 == -t_h4:
        return r

    d = t_h4
    kind = "صاعد" if d == 1 else "هابط"
    score, notes = 20, [f"اتجاه H4 {nm(d)} (+20)"]
    if t_d1 == d:
        score += 10
        notes.append("D1 يوافق (+10)")

    c = h1["Close"]
    a = float(atr(h1).iloc[-2])
    ax = float(adx(h1).iloc[-2])
    if ax >= 20:
        score += 10
        notes.append(f"سوق ذو اتجاه ADX={ax:.0f} (+10)")
    elif ax < 15:
        score -= 15
        notes.append(f"سوق عرضي ADX={ax:.0f} (-15)")

    e21, e50 = ema(c, 21), ema(c, 50)
    if (e21.iloc[-2] > e50.iloc[-2]) == (d == 1):
        score += 5
        notes.append("ترتيب المتوسطات H1 (+5)")

    in_fib = fib_zone(h4, d, price)
    dist = abs(price - float(e21.iloc[-2]))
    if in_fib or dist <= a:
        score += 15
        notes.append("منطقة تصحيح (فيبو 38-62% أو EMA21) (+15)")
    elif dist > 2 * a:
        score -= 15
        notes.append("السعر ممتد، خطر مطاردة (-15)")

    lvl = near_level(h1, d, price, a)
    if lvl is not None:
        score += 10
        notes.append(f"قرب {'دعم' if d == 1 else 'مقاومة'} {lvl:.2f} (+10)")

    e4, e1, em = engulf(h4), engulf(h1), engulf(m15)
    p4, p1 = pinbar(h4), pinbar(h1)
    if e4 == d or e1 == d:
        score += 15
        notes.append(f"ابتلاع {kind} H4/H1 (+15)")
    elif p4 == d or p1 == d:
        score += 10
        notes.append(f"شمعة رفض (Pin Bar) {kind} (+10)")
    elif em == d:
        score += 8
        notes.append(f"ابتلاع {kind} M15 (+8)")

    mh = macd_hist(c)
    if (mh.iloc[-2] > mh.iloc[-3]) == (d == 1):
        score += 5
        notes.append("زخم MACD يدعم (+5)")

    if cyc["support"] == d:
        score += 10
        notes.append("نافذة دورة زمنية تدعم (+10)")

    missing = []
    if t_d1 != d:
        missing.append("D1 لا يوافق الاتجاه")
    if ax < 20:
        missing.append("الاتجاه ضعيف أو السوق عرضي (ADX<20)")
    if not (e4 == d or e1 == d or p4 == d or p1 == d):
        missing.append("لا شمعة ابتلاع أو رفض على H1/H4")
    if not (in_fib or lvl is not None or dist <= a):
        missing.append("السعر ليس عند منطقة دخول (تصحيح/دعم/مقاومة)")

    sl_dist = 1.5 * a
    if lvl is not None:
        alt = abs(price - (lvl - d * 0.4 * a))
        sl_dist = min(max(alt, 1.0 * a), 2.2 * a)
    final = max(0, min(100, score))
    r.update(dir=d, score=final, notes=notes, missing=missing,
             elite=(final >= MIN_SCORE and not missing),
             entry=price, sl=price - d * sl_dist, sl0=price - d * sl_dist,
             tp=price + d * 2 * sl_dist, tp1=price + d * sl_dist, rr=2.0)
    return r


def fmt(r, header="🥇 تحليل الذهب"):
    L = [header, f"💰 السعر: {r['price']:.2f}",
         f"D1: {nm(r['t_d1'])} | H4: {nm(r['t_h4'])}",
         f"(المصدر: {used['sym']} | تصحيح {offset['auto'] + offset['manual']:+.2f})"]
    if r["dir"] is None:
        L.append("⚪ لا توصية: لا اتجاه مشترك واضح")
    else:
        side = "شراء 🟢" if r["dir"] == 1 else "بيع 🔴"
        if r["elite"]:
            q = "استثنائية 💎" if r["score"] >= 95 else "ممتازة ⭐"
            L += [f"✅ توصية {q}: {side}", f"الدخول: {r['entry']:.2f}",
                  f"وقف الخسارة: {r['sl']:.2f}",
                  f"الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}",
                  f"الهدف النهائي: {r['tp']:.2f} (ربح/خسارة 2:1)"]
        else:
            L.append(f"⚪ لا فرصة ممتازة بعد ({side} محتمل)، الأفضل الانتظار")
            if r["missing"]:
                L.append("شروط ناقصة: " + "، ".join(r["missing"]))
        L.append(f"قوة الإشارة: {r['score']}/100")
        L += ["• " + n for n in r["notes"]]
    L.append(r["cycle"])
    if not r["in_session"]:
        L.append("🕒 خارج جلسة لندن/نيويورك: سيولة أقل")
    L.append("⚠️ تحليل آلي وليس توصية مالية. خاطر بأقل من 1% من الرصيد.")
    return "\n".join(L)


# ---------------- تتبع الصفقة ----------------
def track():
    s = active["sig"]
    if not s:
        return
    now = pd.Timestamp.now(tz="UTC")
    if now - active["t0_orig"] > pd.Timedelta(hours=24):
        send("⌛ انتهت صلاحية التوصية (24 ساعة). تجاهلها وانتظر إعداداً جديداً.")
        active.update(sig=None)
        return
    m = get("15m", "1d")
    bars = m[m.index > active["t0"]]
    if bars.empty:
        return
    hi, lo, d = float(bars["High"].max()), float(bars["Low"].min()), s["dir"]
    hit_sl = lo <= s["sl"] if d == 1 else hi >= s["sl"]
    hit_tp = hi >= s["tp"] if d == 1 else lo <= s["tp"]
    reach1 = hi >= s["tp1"] if d == 1 else lo <= s["tp1"]
    if hit_sl:
        send("🛑 ضرب وقف الخسارة." if not active["be"] else "⚪ خرجت عند التعادل (الوقف المنقول).")
        last["t"] = time.time()
        active.update(sig=None)
    elif hit_tp:
        send("🎯 تحقق الهدف النهائي! ربح 2R ✅")
        last["t"] = time.time()
        active.update(sig=None)
    elif reach1 and not active["be"]:
        s["sl"] = s["entry"]
        active.update(be=True, t0=now)
        send(f"🔔 وصل السعر الهدف 1 ({s['tp1']:.2f}). انقل الوقف إلى الدخول {s['entry']:.2f}.")


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
            track()
            r = analyze()
            status["msg"] = f"سعر {r['price']:.2f} | قوة {r['score']}"
            today = datetime.now(timezone.utc).date()
            if daily["d"] != today:
                daily.update(d=today, n=0)
            if (auto["on"] and r["elite"] and r["in_session"] and daily["n"] < MAX_PER_DAY
                    and active["sig"] is None
                    and (r["dir"] != last["dir"] or time.time() - last["t"] > COOLDOWN)):
                send(fmt(r, "🔔 توصية جديدة"))
                now = pd.Timestamp.now(tz="UTC")
                active.update(sig=r, t0=now, t0_orig=now, be=False)
                last.update(dir=r["dir"], t=time.time())
                daily["n"] += 1
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
                    raw = get_raw("5m", "1d")
                    refresh_offset(float(raw["Close"].iloc[-1]))
                    p = float(shift(raw)["Close"].iloc[-1])
                    reply(cid, f"💰 الذهب الآن: {p:.2f}\n(المصدر: {used['sym']})")
                elif text.startswith("/calib"):
                    parts = text.split()
                    if len(parts) > 1 and parts[1] == "reset":
                        offset["manual"] = 0.0
                        reply(cid, "تم إلغاء المعايرة اليدوية")
                    else:
                        try:
                            target = float(parts[1])
                            raw = get_raw("5m", "1d")
                            last_raw = float(raw["Close"].iloc[-1])
                            refresh_offset(last_raw)
                            offset["manual"] = target - (last_raw + offset["auto"])
                            reply(cid, f"✅ تمت المعايرة على {target:.2f} (فرق {offset['manual']:+.2f})")
                        except Exception:
                            reply(cid, "اكتب السعر من منصتك هكذا: /calib 4193.50")
                elif text.startswith("/auto_on"):
                    auto["on"] = True
                    reply(cid, "✅ التوصيات التلقائية مفعّلة (فحص كل دقيقتين)")
                elif text.startswith("/auto_off"):
                    auto["on"] = False
                    reply(cid, "⏸️ التوصيات التلقائية متوقفة")
                elif text.startswith("/status"):
                    s = active["sig"]
                    t = (f"\nصفقة نشطة: {'شراء' if s['dir'] == 1 else 'بيع'} من {s['entry']:.2f}"
                         f" | SL {s['sl']:.2f} | TP {s['tp']:.2f}") if s else "\nلا صفقة نشطة"
                    reply(cid, f"التلقائي: {'شغال' if auto['on'] else 'متوقف'}\nآخر فحص: {status['msg']}{t}")
                elif text.startswith("/start"):
                    reply(cid, "أهلاً! الأوامر:\n/tawsiya تحليل كامل\n/price السعر\n/calib 4193.5 معايرة السعر على منصتك\n/auto_on /auto_off\n/status")
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
