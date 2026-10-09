import os, time, json, threading
from datetime import datetime, timezone, timedelta
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
ANTHROPIC_KEY = env("ANTHROPIC_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
print(f"[startup] ai review: {bool(ANTHROPIC_KEY)} | token set: {bool(TOKEN)} | chat id set: {bool(CHAT)}", flush=True)

SYMBOLS = ["XAUUSD=X", "GC=F"]           # سبوت أولاً، والعقود احتياطي (تُصحَّح بسعر السبوت)
MIN_SCORE = int(os.getenv("MIN_SCORE", "80"))
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
ai_state = {"dir": None, "t": 0, "rejected": False}
ai_err = {"msg": ""}
bt = {"running": False}
snap = {}
scalp = {"on": False, "sig": None, "t0": None, "t_orig": None, "be": False, "bar": None}
SPREAD = 0.35                            # تكلفة تقريبية بالدولار لكل صفقة (للاختبار)


# ---------------- بيانات ----------------
OHLC = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}


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
def cycle(d1, today=None):
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
    today = today or datetime.now(timezone.utc).date()
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


# ---------------- مفاهيم السيولة (SMC) ----------------
def sweep(df, d, look=20, bars=2):
    """كسر قاع/قمة وهمي: كسر مستوى سابق ثم إغلاق عكسي"""
    n = len(df)
    for k in range(2, 2 + bars):
        i = n - k
        if i - look < 0:
            break
        prior = df.iloc[i - look:i]
        if d == 1:
            lv = float(prior["Low"].min())
            if float(df["Low"].iloc[i]) < lv < float(df["Close"].iloc[i]):
                return True, float(df["Low"].iloc[i])
        else:
            lv = float(prior["High"].max())
            if float(df["High"].iloc[i]) > lv > float(df["Close"].iloc[i]):
                return True, float(df["High"].iloc[i])
    return False, None


def fvg(df, d, price, a, look=40):
    """فجوة القيمة العادلة (3 شموع) غير ممتلئة والسعر داخلها أو قربها"""
    n, H, L = len(df), df["High"], df["Low"]
    for i in range(n - 2, max(n - look, 2), -1):
        if d == 1 and float(L.iloc[i]) > float(H.iloc[i - 2]):
            bot, top = float(H.iloc[i - 2]), float(L.iloc[i])
            if top - bot < 0.3 * a or float(L.iloc[i + 1:].min()) <= bot:
                continue
            if bot - 0.3 * a <= price <= top + 0.3 * a:
                return "فوري" if bot <= price <= top else "قريب"
        if d == -1 and float(H.iloc[i]) < float(L.iloc[i - 2]):
            top, bot = float(L.iloc[i - 2]), float(H.iloc[i])
            if top - bot < 0.3 * a or float(H.iloc[i + 1:].max()) >= top:
                continue
            if bot - 0.3 * a <= price <= top + 0.3 * a:
                return "فوري" if bot <= price <= top else "قريب"
    return None


def order_block(df, d, price, a, look=40):
    """بلوك الأوامر: آخر شمعة عكسية قبل اندفاع قوي، والسعر يعيد اختبارها"""
    n = len(df)
    O, C, H, L = df["Open"], df["Close"], df["High"], df["Low"]
    for i in range(n - 5, max(n - look, 0), -1):
        nxt = df.iloc[i + 1:i + 4]
        lo, hi = float(L.iloc[i]), float(H.iloc[i])
        if d == 1 and C.iloc[i] < O.iloc[i]:
            if (float(nxt["High"].max()) - lo >= 2 * a and float(nxt["Close"].max()) > hi
                    and float(C.iloc[i + 4:].min()) >= lo
                    and lo - 0.3 * a <= price <= hi + 0.3 * a):
                return True
        if d == -1 and C.iloc[i] > O.iloc[i]:
            if (hi - float(nxt["Low"].min()) >= 2 * a and float(nxt["Close"].min()) < lo
                    and float(C.iloc[i + 4:].max()) <= hi
                    and lo - 0.3 * a <= price <= hi + 0.3 * a):
                return True
    return False


def london_orb(m15):
    """نطاق أول 30 دقيقة من افتتاح لندن (08:00 بتوقيت لندن)"""
    nowu = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        op = datetime.now(ZoneInfo("Europe/London")).replace(
            hour=8, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    except Exception:
        op = nowu.replace(hour=7, minute=0, second=0, microsecond=0)
    if nowu < op + timedelta(minutes=30):
        return "pre", "قبل الافتتاح أو لا بيانات"
    if nowu > op + timedelta(hours=8):
        return "ended", "انتهت جلسة لندن"
    idx = m15.index
    idx = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")
    rng = m15[(idx >= op) & (idx < op + timedelta(minutes=30))]
    if rng.empty:
        return "nodata", "لا بيانات"
    hi, lo = float(rng["High"].max()), float(rng["Low"].min())
    c = float(m15["Close"].iloc[-2])
    if c > hi:
        return 1, f"اختراق صاعد ↑ ({hi:.1f})"
    if c < lo:
        return -1, f"اختراق هابط ↓ ({lo:.1f})"
    return 0, f"داخل النطاق {lo:.1f}-{hi:.1f}"


# ---------------- التحليل الكامل ----------------
def evaluate(d1, h1, h4, m15, price, hour, mom=None,
             orb=("pre", "قبل الافتتاح أو لا بيانات"), today=None):
    orb_state, orb_txt = orb
    mom = mom or {"15": 0.0, "1h": 0.0, "2h": 0.0}
    t_d1, t_h4 = trend(d1), trend(h4)
    cyc = cycle(d1, today)
    r = {"price": price, "t_d1": t_d1, "t_h4": t_h4, "cycle": cyc["txt"], "mom": mom,
         "orb": orb_txt, "dir": None, "score": 0, "notes": [], "missing": [],
         "met": 0, "elite": False, "in_session": SESSION[0] <= hour < SESSION[1]}
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
    am = float(atr(m15).iloc[-2]) if m15 is not None else a
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
    lvl = near_level(h1, d, price, a)
    if in_fib or dist <= a:
        score += 10
        notes.append("منطقة تصحيح (فيبو 38-62% أو EMA21) (+10)")
    elif dist > 2 * a:
        score -= 15
        notes.append("السعر ممتد، خطر مطاردة (-15)")
    if lvl is not None:
        score += 5
        notes.append(f"قرب {'دعم' if d == 1 else 'مقاومة'} {lvl:.2f} (+5)")

    e4, e1 = engulf(h4), engulf(h1)
    em = engulf(m15) if m15 is not None else 0
    p4, p1 = pinbar(h4), pinbar(h1)
    candle_txt = "لا ابتلاع"
    if e4 == d or e1 == d:
        score += 10
        candle_txt = f"ابتلاع {kind} {'H4' if e4 == d else 'H1'}"
        notes.append(f"{candle_txt} (+10)")
    elif p4 == d or p1 == d:
        score += 7
        candle_txt = f"شمعة رفض (Pin Bar) {kind}"
        notes.append(f"{candle_txt} (+7)")
    elif em == d:
        score += 5
        candle_txt = f"ابتلاع {kind} M15"
        notes.append(f"{candle_txt} (+5)")

    sw, sw_ext = sweep(h1, d, 20, 2)
    if not sw and m15 is not None:
        sw, sw_ext = sweep(m15, d, 24, 4)
    if sw:
        score += 10
        notes.append(f"{'كسر قاع وهمي' if d == 1 else 'كسر قمة وهمي'} (+10)")

    fv = (fvg(m15, d, price, am) if m15 is not None else None) or fvg(h1, d, price, a)
    if fv:
        score += 5
        notes.append(f"FVG {fv} (+5)")
    ob = order_block(h1, d, price, a) or (order_block(m15, d, price, am) if m15 is not None else False)
    if ob:
        score += 5
        notes.append("بلوك أوامر OB (+5)")
    if orb_state == d:
        score += 5
        notes.append("اختراق نطاق لندن باتجاه الصفقة (+5)")
    if cyc["support"] == d:
        score += 5
        notes.append("نافذة دورة زمنية تدعم (+5)")

    missing = []
    if t_d1 != d:
        missing.append("D1 لا يوافق الاتجاه")
    if ax < 20:
        missing.append("الاتجاه ضعيف أو السوق عرضي")
    if not (e4 == d or e1 == d or p4 == d or p1 == d or sw):
        missing.append("لا ابتلاع/رفض/كسر وهمي")
    if not (in_fib or lvl is not None or dist <= a or fv or ob):
        missing.append("السعر ليس عند منطقة دخول")

    sl_dist = 1.5 * a
    if sw and sw_ext is not None:
        sl_dist = min(max(abs(price - (sw_ext - d * 0.3 * a)), 1.0 * a), 2.5 * a)
    elif lvl is not None:
        sl_dist = min(max(abs(price - (lvl - d * 0.4 * a)), 1.0 * a), 2.2 * a)
    final = max(0, min(100, score))
    fl = {"D1 يوافق": t_d1 == d, "ADX>=20": ax >= 20, "فيبو 38-62": bool(in_fib),
          "قرب EMA21": dist <= a, "سعر ممتد": dist > 2 * a, "دعم/مقاومة": lvl is not None,
          "ابتلاع H1/H4": (e4 == d or e1 == d), "Pin Bar": (p4 == d or p1 == d),
          "كسر وهمي": bool(sw), "FVG": bool(fv), "OB": bool(ob), "دورة زمنية": cyc["support"] == d}
    r.update(dir=d, score=final, notes=notes, missing=missing, met=4 - len(missing), flags=fl,
             elite=bool(fl["D1 يوافق"] and fl["ابتلاع H1/H4"]),
             need=([] if fl["D1 يوافق"] else ["D1 لا يوافق الاتجاه"]) +
                  ([] if fl["ابتلاع H1/H4"] else ["لا ابتلاع على H1/H4"]),
             sweep=sw, fvg=fv, ob=ob, candle=candle_txt,
             entry=price, sl=price - d * sl_dist, sl0=price - d * sl_dist,
             tp=price + d * 2 * sl_dist, tp1=price + d * sl_dist, rr=2.0)
    return r


def analyze():
    raw15 = get_raw("15m", "5d")
    refresh_offset(float(raw15["Close"].iloc[-1]))
    d1 = get("1d", "2y", 3600)
    h1 = get("1h", "60d")
    h4 = h1.resample("4h").agg(OHLC).dropna()
    m15 = shift(raw15)
    price = float(m15["Close"].iloc[-1])
    mc = m15["Close"]
    mom = {"15": price - float(mc.iloc[-2]), "1h": price - float(mc.iloc[-5]),
           "2h": price - float(mc.iloc[-9])}
    hour = datetime.now(timezone.utc).hour
    snap["m15"], snap["h1"] = m15, h1
    return evaluate(d1, h1, h4, m15, price, hour, mom, london_orb(m15))


# ---------------- تحسين مع تقسيم تدريب/اختبار ----------------
def take(cands, pred, cool=6):
    out, last = [], {1: -99, -1: -99}
    for c in cands:
        if not pred(c):
            continue
        if c["i"] - last[c["d"]] < cool:
            continue
        last[c["d"]] = c["i"]
        out.append(c["R"])
    return out


def line(R):
    if not R:
        return "لا صفقات"
    st = stats(R)
    pf = "∞" if st["pf"] == float("inf") else f"{st['pf']:.2f}"
    return f"{st['n']} صفقة | نجاح {st['win']:.0f}% | متوسط {st['avg']:+.2f}R | PF {pf}"


def run_optimize(cid, days):
    try:
        reply(cid, f"⏳ بدأ اختبار العناصر ({days} يوم، تدريب/اختبار). ممكن ياخد 15-30 دقيقة، لا تعيد الأمر.")
        raw = get_raw("1h", "730d")
        idx = raw.index.tz_convert("UTC") if raw.index.tz is not None else raw.index.tz_localize("UTC")
        n = len(raw)
        start = max(300, n - int(days * 23))
        cands = []
        for i in range(start, n - 2, 2):
            if not (SESSION[0] <= idx[i].hour < SESSION[1]):
                continue
            try:
                w = raw.iloc[max(0, i - 1500):i + 1].copy()
                o = float(w["Open"].iloc[-1])
                for k in ("Open", "High", "Low", "Close"):
                    w.iloc[-1, w.columns.get_loc(k)] = o
                h4 = w.resample("4h").agg(OHLC).dropna()
                d1 = w.resample("1D").agg(OHLC).dropna()
                if len(d1) < 60 or len(h4) < 60:
                    continue
                r = evaluate(d1, w, h4, None, o, idx[i].hour, today=idx[i].date())
                if not r["dir"]:
                    continue
                cands.append({"i": i, "d": r["dir"], "score": r["score"], "f": r["flags"],
                              "R": simulate(raw, i, r["dir"], r["entry"], r["sl"], r["tp1"], r["tp"])})
            except Exception:
                pass
        if len(cands) < 60:
            reply(cid, f"عدد الإشارات قليل ({len(cands)}) لا يكفي للاختبار.")
            return
        mid = cands[len(cands) // 2]["i"]
        tr = [c for c in cands if c["i"] < mid]
        te = [c for c in cands if c["i"] >= mid]
        L = [f"🔬 اختبار العناصر | {len(cands)} إشارة: تدريب {len(tr)} / اختبار {len(te)}",
             "الأرقام = متوسط R للصفقات اللي فيها العنصر ناقص اللي ما فيها (الأكبر = أفضل).", ""]
        good = []
        for name in cands[0]["f"]:
            row, ok = [], True
            for part in (tr, te):
                a = [c["R"] for c in part if c["f"][name]]
                b = [c["R"] for c in part if not c["f"][name]]
                if len(a) < 15 or len(b) < 15:
                    row.append("قليل")
                    ok = False
                else:
                    dlt = sum(a) / len(a) - sum(b) / len(b)
                    row.append(f"{dlt:+.2f}")
                    ok = ok and dlt > 0
            tag = "✅" if ok else ("⚠️" if name == "سعر ممتد" else "▫️")
            if ok and name != "سعر ممتد":
                good.append(name)
            L.append(f"{tag} {name}: تدريب {row[0]} | اختبار {row[1]}")
        L += ["", "✅ = مفيد بالنصفين (احتمال حقيقي). ▫️ = غير ثابت (غالباً ضجيج).", ""]
        base = lambda c: True
        L.append("الأساس (كل الإشارات)، نصف الاختبار: " + line(take(te, base)))
        L.append("الاستراتيجية الحالية (سكور≥70 + شروط)، نصف الاختبار: " + line(take(te, lambda c: c["score"] >= 70)))
        for k in (2, 3):
            if len(good) >= k:
                rule = lambda c, k=k: sum(1 for g in good if c["f"][g]) >= k
                L.append(f"قاعدة: {k}+ من العناصر المفيدة | تدريب: {line(take(tr, rule))}")
                L.append(f"                            | اختبار: {line(take(te, rule))}")
        L += ["", "العناصر المفيدة: " + ("، ".join(good) if good else "لا يوجد عنصر ثابت"),
              "⚠️ العبرة بنصف الاختبار فقط (لم يُستخدم بالاختيار). إذا ما تحسّن فيه، فلا في ميزة حقيقية."]
        reply(cid, "\n".join(L))
    except Exception as e:
        reply(cid, f"❌ فشل: {e}")
    finally:
        bt["running"] = False


def run_validate(cid):
    """اختبار نظيف: قواعد ثابتة مسبقاً على السنة السابقة (لم تُستخدم بأي اختيار)"""
    try:
        reply(cid, "⏳ بدأ التحقق على السنة السابقة (فترة جديدة تماماً). ممكن ياخد 15-30 دقيقة، لا تعيد الأمر.")
        raw = get_raw("1h", "730d")
        idx = raw.index.tz_convert("UTC") if raw.index.tz is not None else raw.index.tz_localize("UTC")
        n = len(raw)
        end = n - int(365 * 23)
        start = max(300, n - int(715 * 23))
        if end - start < 1000:
            reply(cid, "البيانات المتاحة لا تكفي لفترة سابقة.")
            return
        cands = []
        for i in range(start, end, 2):
            if not (SESSION[0] <= idx[i].hour < SESSION[1]):
                continue
            try:
                w = raw.iloc[max(0, i - 1500):i + 1].copy()
                o = float(w["Open"].iloc[-1])
                for k in ("Open", "High", "Low", "Close"):
                    w.iloc[-1, w.columns.get_loc(k)] = o
                h4 = w.resample("4h").agg(OHLC).dropna()
                d1 = w.resample("1D").agg(OHLC).dropna()
                if len(d1) < 60 or len(h4) < 60:
                    continue
                r = evaluate(d1, w, h4, None, o, idx[i].hour, today=idx[i].date())
                if not r["dir"]:
                    continue
                cands.append({"i": i, "d": r["dir"], "score": r["score"], "f": r["flags"],
                              "miss": bool(r["missing"]),
                              "R": simulate(raw, i, r["dir"], r["entry"], r["sl"], r["tp1"], r["tp"])})
            except Exception:
                pass
        days = (end - start) / 23
        wk = max(days / 7, 1)
        rules = [
            ("كل الإشارات (اتجاه H4 فقط)", lambda c: True),
            ("الاستراتيجية الحالية (سكور≥70 + شروط)", lambda c: c["score"] >= 70 and not c["miss"]),
            ("قاعدة جديدة: D1 يوافق + ابتلاع H1/H4", lambda c: c["f"]["D1 يوافق"] and c["f"]["ابتلاع H1/H4"]),
            ("ابتلاع H1/H4 فقط", lambda c: c["f"]["ابتلاع H1/H4"]),
            ("D1 يوافق فقط", lambda c: c["f"]["D1 يوافق"]),
        ]
        L = [f"✅ تحقق على فترة جديدة ({days:.0f} يوم، {len(cands)} إشارة)", ""]
        for name, fn in rules:
            R = take(cands, fn)
            L.append(name)
            if R:
                st = stats(R)
                L.append(f"   {line(R)} | هبوط {st['dd']:.1f}R | ~{len(R) / wk:.1f} صفقة/أسبوع")
            else:
                L.append("   لا صفقات")
        L += ["", "إذا القاعدة الجديدة موجبة وPF فوق 1.3 هنا كمان (فترة ما استخدمناها بأي اختيار)، فاحتمال الأفضلية حقيقي أكثر.",
              "إذا ضاعت، فالسابقة كانت صدفة ولا نعتمد عليها."]
        reply(cid, "\n".join(L))
    except Exception as e:
        reply(cid, f"❌ فشل: {e}")
    finally:
        bt["running"] = False


# ---------------- الذكاء الاصطناعي (Claude) ----------------
def call_claude(prompt, max_tokens=700, search=True):
    if not ANTHROPIC_KEY:
        return None
    hdr = {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
           "content-type": "application/json"}
    use_search = search
    for attempt in range(3):
        body = {"model": AI_MODEL, "max_tokens": max_tokens + (1500 if use_search else 0),
                "messages": [{"role": "user", "content": prompt}]}
        if use_search:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]
        try:
            resp = requests.post("https://api.anthropic.com/v1/messages",
                                 headers=hdr, json=body, timeout=120)
        except Exception as e:
            ai_err["msg"] = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"[ai] error: {ai_err['msg']}", flush=True)
            return None
        if resp.status_code != 200:
            ai_err["msg"] = f"{resp.status_code}: {resp.text[:250]}"
            print(f"[ai] {ai_err['msg']}", flush=True)
            if use_search:
                use_search = False          # أعد المحاولة بدون بحث الويب
                continue
            return None
        j = resp.json()
        txt = "".join(b.get("text", "") for b in j.get("content", [])
                      if b.get("type") == "text").strip()
        if txt:
            return txt.replace("**", "").replace("##", "").replace("# ", "")
        ai_err["msg"] = f"رد فارغ (stop_reason={j.get('stop_reason')})"
        print(f"[ai] {ai_err['msg']}", flush=True)
        use_search = False                  # جرب بدون بحث
    return None


def brief(r):
    m = r["mom"]
    t = (f"الوقت UTC: {datetime.now(timezone.utc):%Y-%m-%d %H:%M}\n"
         f"سعر الذهب: {r['price']:.2f}\nD1: {nm(r['t_d1'])} | H4: {nm(r['t_h4'])}\n"
         f"زخم 15د/1س/2س: {m['15']:+.1f}/{m['1h']:+.1f}/{m['2h']:+.1f}$\n")
    if r["dir"]:
        side = "شراء" if r["dir"] == 1 else "بيع"
        t += (f"الإشارة: {side} | سكور {r['score']}/100 | شروط ناقصة: {', '.join(r['missing']) or 'لا'}\n"
              f"دخول {r['entry']:.2f} | وقف {r['sl']:.2f} | هدف1 {r['tp1']:.2f} | هدف2 {r['tp']:.2f}\n"
              f"التفاصيل: {'; '.join(r['notes'])}\n")
    return t + r["cycle"]


def ai_review(r):
    prompt = ("أنت مدير مخاطر خبير في الذهب XAUUSD. راجع هذه الإشارة الآلية.\n\n" + brief(r) +
              "\n\nابحث بسرعة عن أخبار الذهب اليوم وأي حدث أمريكي عالي التأثير (CPI, NFP, FOMC, خطابات الفيدرالي) "
              "خلال الساعات الست القادمة وأي حدث جيوسياسي كبير. ارفض الإشارة إذا كان هناك خبر وشيك أو سياق "
              "كلي يعاكسها بوضوح. أجب فقط بـ JSON بدون أي نص آخر:\n"
              '{"verdict":"approve" أو "reject","confidence":0-100,"reason":"جملة عربية قصيرة"}')
    txt = call_claude(prompt, 500)
    if not txt:
        return None
    try:
        j = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        v = str(j.get("verdict", "")).lower()
        return {"verdict": "approve" if v.startswith("approve") else "reject",
                "confidence": int(j.get("confidence", 0)),
                "reason": str(j.get("reason", ""))[:200]}
    except Exception:
        return None


def ai_commentary(r):
    prompt = ("أنت محلل ذهب خبير. هذه قراءة البوت الآلية الآن:\n\n" + brief(r) +
              "\n\nابحث عن أخبار الذهب والأحداث الاقتصادية المهمة اليوم، ثم اكتب قراءة سوق مختصرة بالعربية "
              "(حتى 10 أسطر): الصورة العامة، ما الذي يجب انتظاره، مستويات الشراء/البيع المهمة، وأهم المخاطر. "
              "لا تضمن أرباحاً.")
    return call_claude(prompt, 800) or f"تعذر الاتصال بالذكاء الاصطناعي.\nالسبب: {ai_err['msg'] or 'غير معروف'}"


# ---------------- اختبار تاريخي ----------------
def simulate(raw, i, d, entry, sl, tp1, tp, maxbars=24):
    n, risk, be, stop = len(raw), abs(entry - sl), False, sl
    end = min(i + maxbars, n)
    for j in range(i, end):
        hi, lo = float(raw["High"].iloc[j]), float(raw["Low"].iloc[j])
        if (lo <= stop) if d == 1 else (hi >= stop):
            return 0.0 if be else -1.0
        if (hi >= tp) if d == 1 else (lo <= tp):
            return 2.0
        if not be and ((hi >= tp1) if d == 1 else (lo <= tp1)):
            be, stop = True, entry
    return (float(raw["Close"].iloc[end - 1]) - entry) * d / risk


def stats(R):
    n = len(R)
    gp = sum(x for x in R if x > 0)
    gl = -sum(x for x in R if x < 0)
    eq = peak = dd = 0.0
    for x in R:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"n": n, "win": 100 * sum(1 for x in R if x > 0) / n, "avg": sum(R) / n,
            "tot": sum(R), "pf": (gp / gl if gl > 0 else float("inf")), "dd": dd}


def run_backtest(cid, days):
    try:
        reply(cid, f"⏳ بدأ الاختبار التاريخي ({days} يوم). ممكن ياخد عدة دقائق على السيرفر المجاني...")
        raw = get_raw("1h", "730d")
        idx = raw.index.tz_convert("UTC") if raw.index.tz is not None else raw.index.tz_localize("UTC")
        n = len(raw)
        start = max(300, n - int(days * 23))
        cands, last_i, errs = [], {1: -99, -1: -99}, 0
        for i in range(start, n - 2):
            if not (SESSION[0] <= idx[i].hour < SESSION[1]):
                continue
            try:
                w = raw.iloc[max(0, i - 1500):i + 1].copy()
                o = float(w["Open"].iloc[-1])
                for k in ("Open", "High", "Low", "Close"):
                    w.iloc[-1, w.columns.get_loc(k)] = o     # الشمعة الحالية لم تُغلق بعد
                h4 = w.resample("4h").agg(OHLC).dropna()
                d1 = w.resample("1D").agg(OHLC).dropna()
                if len(d1) < 60 or len(h4) < 60:
                    continue
                r = evaluate(d1, w, h4, None, o, idx[i].hour, today=idx[i].date())
                if not r["dir"] or not r["elite"]:
                    continue
                d = r["dir"]
                if i - last_i[d] < 6:
                    continue
                last_i[d] = i
                cands.append((r["score"], simulate(raw, i, d, r["entry"], r["sl"], r["tp1"], r["tp"])))
            except Exception:
                errs += 1
        L = [f"📊 اختبار تاريخي: آخر {days} يوم على H1 (سبوت)",
             "⚠️ تقريبي: بدون مؤشرات M15 (ORB وغيرها)، والوقف/الهدف بالـR (1R = مسافة الوقف).", ""]
        for th in (60, 70, 80, 90):
            R = [x for sc, x in cands if sc >= th]
            if not R:
                L.append(f"سكور ≥{th}: لا صفقات")
                continue
            st = stats(R)
            pf = "∞" if st["pf"] == float("inf") else f"{st['pf']:.2f}"
            L.append(f"سكور ≥{th}: {st['n']} صفقة | نجاح {st['win']:.0f}% | متوسط {st['avg']:+.2f}R | "
                     f"المجموع {st['tot']:+.1f}R | PF {pf} | أقصى هبوط {st['dd']:.1f}R")
        L += ["", "كيف تقرأها: الاستراتيجية تستحق الثقة فقط إذا كان المتوسط موجباً وPF أكبر من 1.3 "
                  "وعدد الصفقات 30 أو أكثر. أقل من ذلك = عينة صغيرة لا يعتمد عليها."]
        reply(cid, "\n".join(L))
    except Exception as e:
        reply(cid, f"❌ فشل الاختبار: {e}")
    finally:
        bt["running"] = False


def fmt(r, header="تحليل الذهب", full=False):
    m = r["mom"]
    L = [f"🚨 {header} 🚨", f"💰 السعر: {r['price']:.2f}",
         f"D1: {nm(r['t_d1'])} | H4: {nm(r['t_h4'])}",
         f"⚡ 15د: {m['15']:+.1f}$ | 1س: {m['1h']:+.1f}$ | 2س: {m['2h']:+.1f}$"]
    if r["dir"] is None:
        L.append("⚪ لا توصية: لا اتجاه مشترك واضح")
    else:
        side = "بيع 🔴" if r["dir"] == -1 else "شراء 🟢"
        L.append(f"{side} | سكور {r['score']}/100 | شروط {r['met']}/4")
        sw_name = "كسر قاع وهمي" if r["dir"] == 1 else "كسر قمة وهمي"
        L += [f"{'🟢' if r['sweep'] else '⚪'} {sw_name if r['sweep'] else 'لا كسر وهمي'}"
              f" | OB: {'نعم' if r['ob'] else 'لا'} | FVG: {r['fvg'] or 'لا'}",
              f"🕯️ {r['candle']}", f"🏦 ORB لندن: {r['orb']}"]
        if r["elite"]:
            L += ["✅ توصية: ابتلاع مع الاتجاه (D1 + H1/H4)",
                  f"🎯 الدخول: {r['entry']:.2f}", f"🛑 الوقف: {r['sl']:.2f}",
                  f"✅ الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}",
                  f"💰 الهدف 2: {r['tp']:.2f} (2:1)"]
        else:
            L.append(f"⚪ لا توصية الآن ({side.split()[0]} محتمل)، الأفضل الانتظار")
            if r.get("need"):
                L.append("شروط ناقصة: " + "، ".join(r["need"]))
        if r.get("ai"):
            ai = r["ai"]
            L.append(f"🧠 مراجعة ذكية: {'موافقة ✅' if ai['verdict'] == 'approve' else 'رفض ❌'}"
                     f" (ثقة {ai['confidence']}%) — {ai['reason']}")
        if full:
            L += ["• " + n for n in r["notes"]]
    if full:
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


# ---------------- وضع الصفقات السريعة (سكالب) ----------------
def scalp_eval(m15, h1, price):
    """ابتلاع M15 مع اتجاه H1 وعند منطقة تصحيح قرب EMA21. وقف 1.2×ATR، هدف 1R ثم 2R."""
    if len(m15) < 80 or len(h1) < 60:
        return None
    t, e = trend(h1), engulf(m15)
    if t == 0 or e != t:
        return None
    c = m15["Close"]
    a = float(atr(m15).iloc[-2])
    if not a > 0:
        return None
    if abs(float(c.iloc[-2]) - float(ema(c, 21).iloc[-2])) > 1.2 * a:
        return None
    sd = max(1.2 * a, 2.0)
    return {"dir": t, "entry": price, "sl": price - t * sd, "tp1": price + t * sd,
            "tp": price + t * 2 * sd, "risk": sd}


def run_scalp_bt(cid):
    try:
        reply(cid, "⏳ اختبار السكالب على آخر ~60 يوم (M15). دقائق...")
        raw = get_raw("15m", "60d")
        idx = raw.index.tz_convert("UTC") if raw.index.tz is not None else raw.index.tz_localize("UTC")
        n, res, last_i = len(raw), [], {1: -99, -1: -99}
        for i in range(250, n - 2):
            if not (SESSION[0] <= idx[i].hour < SESSION[1]):
                continue
            try:
                w = raw.iloc[max(0, i - 1200):i + 1].copy()
                o = float(w["Open"].iloc[-1])
                for k in ("Open", "High", "Low", "Close"):
                    w.iloc[-1, w.columns.get_loc(k)] = o
                h1 = w.resample("1h").agg(OHLC).dropna()
                s = scalp_eval(w, h1, o)
                if not s or i - last_i[s["dir"]] < 4:
                    continue
                last_i[s["dir"]] = i
                R = simulate(raw, i, s["dir"], s["entry"], s["sl"], s["tp1"], s["tp"], maxbars=16)
                res.append((R, s["risk"]))
            except Exception:
                pass
        if not res:
            reply(cid, "لا صفقات في الفترة.")
            return
        gross = [r for r, _ in res]
        net = [r - SPREAD / k for r, k in res]
        h = len(res) // 2
        L = ["📊 اختبار السكالب (آخر ~60 يوم، M15)",
             f"قبل التكلفة: {line(gross)}",
             f"بعد سبريد {SPREAD}$: {line(net)}",
             f"النصف الأول: {line(net[:h])}",
             f"النصف الثاني: {line(net[h:])}",
             f"تقريباً {len(res) / 8.5:.1f} صفقة بالأسبوع",
             "", "فقط إذا كان المتوسط بعد السبريد موجباً في النصفين، فعّله بـ /scalp_on وجرّبه ديمو."]
        reply(cid, "\n".join(L))
    except Exception as e:
        reply(cid, f"❌ فشل اختبار السكالب: {e}")
    finally:
        bt["running"] = False


def scalp_step():
    m15, h1 = snap.get("m15"), snap.get("h1")
    if not scalp["on"] or m15 is None:
        return
    now = pd.Timestamp.now(tz="UTC")
    s = scalp["sig"]
    if s:
        if now - scalp["t_orig"] > pd.Timedelta(hours=4):
            send("⌛ انتهت صلاحية صفقة السكالب (4 ساعات).")
            scalp["sig"] = None
        else:
            bars = m15[m15.index > scalp["t0"]]
            if not bars.empty:
                hi, lo, d = float(bars["High"].max()), float(bars["Low"].min()), s["dir"]
                if (lo <= s["sl"]) if d == 1 else (hi >= s["sl"]):
                    send("⚡🛑 السكالب: ضرب الوقف." if not scalp["be"] else "⚡⚪ السكالب: خروج عند التعادل.")
                    scalp["sig"] = None
                elif (hi >= s["tp"]) if d == 1 else (lo <= s["tp"]):
                    send("⚡🎯 السكالب: تحقق الهدف 2 (+2R) ✅")
                    scalp["sig"] = None
                elif not scalp["be"] and ((hi >= s["tp1"]) if d == 1 else (lo <= s["tp1"])):
                    s["sl"] = s["entry"]
                    scalp.update(be=True, t0=now)
                    send(f"⚡🔔 السكالب: وصل الهدف 1 ({s['tp1']:.2f}). انقل الوقف إلى {s['entry']:.2f}.")
        return
    bar = m15.index[-2]
    if bar == scalp["bar"]:
        return
    scalp["bar"] = bar
    if now - bar > pd.Timedelta(minutes=25):
        return
    if not (SESSION[0] <= now.hour < SESSION[1]):
        return
    r = scalp_eval(m15, h1, float(m15["Close"].iloc[-1]))
    if r:
        side = "شراء 🟢" if r["dir"] == 1 else "بيع 🔴"
        send(f"⚡ صفقة سريعة (سكالب) — {side}\n🎯 الدخول: {r['entry']:.2f}\n🛑 الوقف: {r['sl']:.2f}\n"
             f"✅ الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}\n💰 الهدف 2: {r['tp']:.2f}\n"
             "⚠️ صفقة قصيرة (حتى 4 ساعات)، حجم صغير.")
        scalp.update(sig=r, t0=now, t_orig=now, be=False)


def loop():
    while True:
        try:
            track()
            r = analyze()
            try:
                scalp_step()
            except Exception as e:
                print(f"[scalp] error: {e}", flush=True)
            status["msg"] = f"سعر {r['price']:.2f} | قوة {r['score']}"
            if (auto["on"] and r["elite"] and r["in_session"] and active["sig"] is None
                    and (r["dir"] != last["dir"] or time.time() - last["t"] > COOLDOWN)):
                go = True
                if ANTHROPIC_KEY:
                    if (ai_state["rejected"] and ai_state["dir"] == r["dir"]
                            and time.time() - ai_state["t"] < 1800):
                        go = False                      # رُفضت قبل قليل، لا تكرر المراجعة
                    else:
                        rev = ai_review(r)
                        rej = bool(rev and rev["verdict"] == "reject")
                        ai_state.update(dir=r["dir"], t=time.time(), rejected=rej)
                        if rej:
                            go = False
                            side = "شراء" if r["dir"] == 1 else "بيع"
                            send(f"🧠 المراجعة الذكية رفضت إشارة {side} عند {r['price']:.2f}: {rev['reason']}")
                        r["ai"] = rev
                if go:
                    send(fmt(r, "توصية جديدة"))
                    now = pd.Timestamp.now(tz="UTC")
                    active.update(sig=r, t0=now, t0_orig=now, be=False)
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
                global CHAT
                if not CHAT:
                    CHAT = str(cid)
                    print(f"[commands] CHAT_ID auto-set to {CHAT}", flush=True)
                if text.startswith("/tawsiya"):
                    reply(cid, "⏳ جاري التحليل...")
                    rr = analyze()
                    if rr["elite"] and ANTHROPIC_KEY:
                        rr["ai"] = ai_review(rr)
                    reply(cid, fmt(rr, full=True))
                elif text.startswith("/ai"):
                    if not ANTHROPIC_KEY:
                        reply(cid, "أضف ANTHROPIC_API_KEY في Environment على Render لتفعيل العقل الذكي.")
                    else:
                        reply(cid, "🧠 جاري التفكير والبحث بالأخبار...")
                        reply(cid, ai_commentary(analyze()))
                elif text.startswith("/scalpbt"):
                    if bt["running"]:
                        reply(cid, "اختبار شغال حالياً، انتظر النتيجة.")
                    else:
                        bt["running"] = True
                        threading.Thread(target=run_scalp_bt, args=(cid,), daemon=True).start()
                elif text.startswith("/scalp_on"):
                    scalp["on"] = True
                    reply(cid, "⚡ وضع السكالب مفعّل (يتوقف عند إعادة تشغيل السيرفر).")
                elif text.startswith("/scalp_off"):
                    scalp["on"] = False
                    reply(cid, "⏸️ السكالب متوقف")
                elif text.startswith("/validate"):
                    if bt["running"]:
                        reply(cid, "اختبار شغال حالياً، انتظر النتيجة.")
                    else:
                        bt["running"] = True
                        threading.Thread(target=run_validate, args=(cid,), daemon=True).start()
                elif text.startswith("/optimize"):
                    if bt["running"]:
                        reply(cid, "اختبار شغال حالياً، انتظر النتيجة.")
                    else:
                        try:
                            days = int(text.split()[1])
                        except Exception:
                            days = 365
                        bt["running"] = True
                        threading.Thread(target=run_optimize, args=(cid, min(max(days, 120), 700)),
                                         daemon=True).start()
                elif text.startswith("/backtest"):
                    if bt["running"]:
                        reply(cid, "الاختبار شغال حالياً، انتظر النتيجة.")
                    else:
                        try:
                            days = int(text.split()[1])
                        except Exception:
                            days = 180
                        bt["running"] = True
                        threading.Thread(target=run_backtest, args=(cid, min(max(days, 30), 600)),
                                         daemon=True).start()
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
                    reply(cid, "أهلاً! الأوامر:\n/tawsiya تحليل كامل\n/price السعر\n/ai قراءة السوق بالذكاء الاصطناعي مع الأخبار\n/backtest 180 اختبار الاستراتيجية على التاريخ\n/calib 4193.5 معايرة السعر على منصتك\n/auto_on /auto_off\n/status")
        except Exception as e:
            status["msg"] = f"cmd error: {e}"
            print(f"[commands] error: {e}", flush=True)
            time.sleep(5)


def keepalive():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        print("[keepalive] RENDER_EXTERNAL_URL not set, skipping", flush=True)
        return
    while True:
        time.sleep(600)
        try:
            requests.get(url, timeout=20)
        except Exception as e:
            print(f"[keepalive] {e}", flush=True)


@app.route("/")
def home():
    return f"gold-bot running | {status['msg']}"


threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=commands, daemon=True).start()
threading.Thread(target=keepalive, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
