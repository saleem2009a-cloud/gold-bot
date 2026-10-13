import os, time, json, threading
from datetime import datetime, timezone, timedelta
import requests
import pandas as pd
import gc
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
SESSION = (7, 20)                        # ساعات لندن + نيويورك (UTC) — للاختبارات وفي الوضع العادي
allday = {"on": os.getenv("ALLDAY", "1") == "1"}   # توصيات على مدار الساعة (ما عدا توقف السوق اليومي)


def live_ok(now=None):
    """هل مسموح نطلع توصية جديدة الآن؟"""
    now = now or pd.Timestamp.now(tz="UTC")
    if not allday["on"]:
        return SESSION[0] <= now.hour < SESSION[1]
    ny = now.tz_convert("America/New_York")
    m = ny.hour * 60 + ny.minute
    if 16 * 60 + 45 <= m < 18 * 60 + 15:         # توقف الذهب اليومي 17:00-18:00 نيويورك + سبريد عالي حوله
        return False
    if ny.weekday() == 6 and m < 19 * 60:        # أول ساعة بعد افتتاح الأسبوع (فجوات وسبريد)
        return False
    return True
FIB = [21, 34, 55, 89, 144]
GANN = [90, 180, 360]

app = Flask(__name__)
last = {"dir": None, "t": 0}
status = {"msg": "starting"}
auto = {"on": True}
active = {"sig": None, "t0": None, "be": False}
_cache = {}
used = {"sym": None}
offset = {"auto": 0.0, "manual": float(os.getenv("CALIB_OFFSET", "0") or 0), "n": 0}
daily = {"d": None, "n": 0}
ai_state = {"dir": None, "t": 0, "rejected": False}
ai_err = {"msg": ""}
bt = {"running": False}
snap = {}
scalp = {"on": os.getenv("SCALP_ON", "1") == "1", "sig": None, "t0": None, "t_orig": None, "be": False, "bar": None}
SCALP_EMAD = float(os.getenv("SCALP_EMAD", "1.5"))   # أقصى بعد عن EMA21 (ATR) — 1.5 أحسن من 1.2 باختبار 60 يوم
SPREAD = 0.35                            # تكلفة تقريبية بالدولار لكل صفقة (للاختبار)


# ---------------- بيانات ----------------
OHLC = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}


# ---- بيانات فورية من Twelve Data (مجاني: 800 طلب/يوم، 8/دقيقة) إذا انضاف المفتاح ----
TD_KEY = env("TWELVEDATA_KEY", "TWELVE_DATA_KEY", "TD_KEY")
TD_INT = {"5m": ("5min", 170), "15m": ("15min", 170), "1h": ("1h", 900), "1d": ("1day", 3600)}
TD_SIZE = {"5min": 400, "15min": 1000, "1h": 1500, "1day": 800}   # قد الحاجة بس، لتوفير الذاكرة
TD_MAX_DAYS = {"5m": 1, "15m": 10, "1h": 60, "1d": 1000}
_td = {}
td_err = {"msg": "", "t": 0}


def period_days(period):
    return int(period[:-1]) * (365 if period.endswith("y") else 1)


_td_lock = threading.Lock()
_td_calls = []


def td_fetch(tdi):
    """طلب واحد مع احترام حد 8 طلبات بالدقيقة (نوقف عند 7 للأمان)"""
    now = time.time()
    while _td_calls and now - _td_calls[0] > 60:
        _td_calls.pop(0)
    if len(_td_calls) >= 7:
        time.sleep(61 - (now - _td_calls[0]))
    _td_calls.append(time.time())
    j = requests.get("https://api.twelvedata.com/time_series",
                     params={"symbol": "XAU/USD", "interval": tdi, "outputsize": TD_SIZE[tdi],
                             "timezone": "UTC", "order": "asc", "apikey": TD_KEY},
                     timeout=20).json()
    vals = j.get("values")
    if not vals:
        raise RuntimeError(str(j.get("message", j))[:200])
    df = pd.DataFrame(vals)
    df.index = pd.DatetimeIndex(pd.to_datetime(df["datetime"])).tz_localize("UTC")
    df = df[["open", "high", "low", "close"]].astype(float)
    df.columns = ["Open", "High", "Low", "Close"]
    return df.sort_index()


def td_raw(interval, period):
    """شموع XAU/USD الفورية. إذا فشل طلب، منستخدم آخر نسخة محفوظة بدل ما نخلط مع Yahoo."""
    if not TD_KEY or interval not in TD_INT or period_days(period) > TD_MAX_DAYS[interval]:
        return None
    tdi, ttl = TD_INT[interval]
    with _td_lock:                                  # طلب واحد بنفس الوقت (الحلقة + أوامر تليجرام)
        cached = _td.get(interval)
        fresh = cached and time.time() - cached[0] < ttl
        retry_ok = time.time() - td_err.get(interval, 0) > 60
        if not fresh and (retry_ok or not cached):
            try:
                _td[interval] = (time.time(), td_fetch(tdi))
                td_err["msg"] = ""
            except Exception as e:
                td_err.update(msg=str(e)[:200], t=time.time())
                td_err[interval] = time.time()
                print(f"[twelvedata] {interval}: {e}", flush=True)
        cached = _td.get(interval)
    if not cached or time.time() - cached[0] > 1800:   # ما في بيانات فورية صالحة → Yahoo
        return None
    df = cached[1]
    cut = df.index[-1] - pd.Timedelta(days=period_days(period))
    used["sym"] = "XAU/USD (فوري)"
    return df[df.index >= cut]


def get_raw(interval, period):
    df = td_raw(interval, period)
    if df is not None and len(df) >= 5:
        return df
    for sym in SYMBOLS:
        try:
            import yfinance as yf                    # تحميل عند الحاجة فقط (توفير ذاكرة)
            df = yf.download(sym, interval=interval, period=period,
                             progress=False, auto_adjust=True, timeout=20)
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
    """إذا اضطررنا لاستخدام العقود الآجلة نصحح الفرق بسعر السبوت الحي.
    الفرق بيتنعّم تدريجياً لأن بيانات العقود متأخرة ~10 دقائق والسبوت حي،
    فالفرق اللحظي بيقفز مع كل حركة وبيحرّك كل المستويات (قمة/قاع امبارح) معه."""
    if used["sym"] != "GC=F":
        offset["auto"], offset["n"] = 0.0, 0
        return
    sp = spot_price()
    if not sp:
        return
    new = sp - raw_last
    if offset.get("n", 0) == 0:
        offset["auto"] = new
    elif abs(new - offset["auto"]) <= 15:          # تجاهل القفزات الشاذة
        offset["auto"] = 0.97 * offset["auto"] + 0.03 * new   # فرق العقود/السبوت بيتغير ببطء
    offset["n"] = offset.get("n", 0) + 1


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
        lines.append(f"آخر قاع قبل {days} يوم" + (f" 🔁 دورة {hit[0]}" if hit else ""))
    if sh is not None:
        days = (today - d1.index[sh].date()).days
        hit = [x for x in FIB + GANN if abs(days - x) <= 1]
        high_hit = bool(hit)
        lines.append(f"آخر قمة قبل {days} يوم" + (f" 🔁 دورة {hit[0]}" if hit else ""))
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


# ---------------- مستويات الشمعة اليومية (قمة / 50% / قاع امبارح) ----------------
def daily_levels(d1):
    """قمة وقاع ونص آخر يوم مكتمل (آخر صف هو اليوم الحالي اللي لسا ما سكّر)"""
    if d1 is None or len(d1) < 2:
        return None
    p = d1.iloc[-2]
    H, L = float(p["High"]), float(p["Low"])
    if H - L <= 0:
        return None
    return {"high": H, "mid": (H + L) / 2, "low": L}


def daily_conf(lv, d, price, a):
    """عامل مساعد: الشراء بمنطقة الخصم (تحت 50%) والبيع بمنطقة الغلاء (فوق 50%).
    يمنع الشراء تحت قمة امبارح مباشرة والبيع فوق قاعها مباشرة."""
    out = {"zone": False, "near": None, "block": False}
    if not lv:
        return out
    tol = 0.4 * a
    H, M, L = lv["high"], lv["mid"], lv["low"]
    if d == 1:
        out["zone"] = price < M
        if abs(price - L) <= tol:
            out["near"] = f"قاع امبارح {L:.2f}"
        elif abs(price - M) <= tol:
            out["near"] = f"نص شمعة امبارح {M:.2f}"
        out["block"] = H - tol <= price <= H + 0.1 * a
    else:
        out["zone"] = price > M
        if abs(price - H) <= tol:
            out["near"] = f"قمة امبارح {H:.2f}"
        elif abs(price - M) <= tol:
            out["near"] = f"نص شمعة امبارح {M:.2f}"
        out["block"] = L - 0.1 * a <= price <= L + tol
    return out


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

    lv = daily_levels(d1)
    dc = daily_conf(lv, d, price, a)
    if dc["zone"]:
        score += 5
        notes.append(f"{'منطقة خصم (تحت 50% امبارح)' if d == 1 else 'منطقة غلاء (فوق 50% امبارح)'} (+5)")
    if dc["near"]:
        score += 5
        notes.append(f"قرب {dc['near']} (+5)")
    if dc["block"]:
        score -= 20
        notes.append(f"{'شراء تحت قمة امبارح' if d == 1 else 'بيع فوق قاع امبارح'} مباشرة (-20)")

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
          "كسر وهمي": bool(sw), "FVG": bool(fv), "OB": bool(ob), "دورة زمنية": cyc["support"] == d,
          "منطقة 50% يومي": dc["zone"], "قرب مستوى يومي": bool(dc["near"]),
          "عكس مستوى يومي": dc["block"]}
    elite = bool(fl["D1 يوافق"] and fl["ابتلاع H1/H4"] and not dc["block"])
    trig = []
    if em == d:
        trig.append("ابتلاع M15")
    if p1 == d:
        trig.append("Pin Bar H1")
    if sw:
        trig.append("كسر وهمي")
    zone = []
    if ob:
        zone.append("OB")
    if fv:
        zone.append("FVG")
    if lvl is not None:
        zone.append("دعم" if d == 1 else "مقاومة")
    if dist <= a:
        zone.append("EMA21")
    if in_fib:
        zone.append("فيبو")
    fast = bool(not elite and fl["D1 يوافق"] and trig and zone and not dc["block"])
    r.update(dir=d, score=final, notes=notes, missing=missing, met=4 - len(missing), flags=fl,
             elite=elite, fast=fast, fast_txt=f"{' + '.join(trig)} عند {' / '.join(zone)}" if fast else "",
             need=([] if fl["D1 يوافق"] else ["D1 لا يوافق الاتجاه"]) +
                  ([] if fl["ابتلاع H1/H4"] else ["لا ابتلاع على H1/H4"]) +
                  (["السعر لاصق بمستوى امبارح المعاكس"] if dc["block"] else []),
             levels=lv, dconf=dc,
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
    if used["sym"].startswith("XAU/USD"):
        # بين تحديثات Twelve Data (كل ~3 دقائق) منحدّث آخر سعر من مصدر السبوت المجاني
        sp = spot_price()
        if sp and abs(sp - price) < 10:
            price = sp + offset["manual"]
            m15 = m15.copy()
            i = m15.index[-1]
            m15.loc[i, "Close"] = price
            m15.loc[i, "High"] = max(float(m15.loc[i, "High"]), price)
            m15.loc[i, "Low"] = min(float(m15.loc[i, "Low"]), price)
    mc = m15["Close"]
    mom = {"15": price - float(mc.iloc[-2]), "1h": price - float(mc.iloc[-5]),
           "2h": price - float(mc.iloc[-9])}
    hour = datetime.now(timezone.utc).hour
    snap["m15"], snap["h1"] = m15, h1
    snap["t_hi"] = [trend(d1), trend(h4)]
    r = evaluate(d1, h1, h4, m15, price, hour, mom, london_orb(m15))
    if r["dir"] is None and rng_mode["on"]:
        rg = range_eval(h1, m15, price, lo_=False, d1dir=r["t_d1"])
        if not rg and loose["on"]:
            rg = range_eval(h1, m15, price, lo_=True, d1dir=r["t_d1"])
            if rg:
                rg["light"] = True
        if rg:
            r.update(rg, score=0, met=0, notes=rg["notes"], missing=[], elite=False, fast=False,
                     sweep=False, ob=False, fvg=None, levels=daily_levels(d1))
    return r


# ---------------- وضع تداول النطاق (لما H4 محايد) ----------------
rng_mode = {"on": os.getenv("RANGE_ON", "1") == "1"}
loose = {"on": os.getenv("LOOSE_ON", "0") == "1"}   # توصيات خفيفة 🟡 — مطفية: خسرانة بالباك تست (13-10)


def range_eval(h1, m15, price, lo_=None, d1dir=None):
    """شراء قرب أرضية نطاق آخر 24 ساعة وبيع قرب سقفه، بعد ابتلاع أو رفض على M15.
    الوقف ورا طرف النطاق، الهدف 1 نص النطاق، الهدف 2 الطرف الثاني.
    lo_=True: شروط أخف (ADX<30، نطاق 1.5-10 ATR، منطقة الطرف 35%، عائد 1.2R)."""
    L = loose["on"] if lo_ is None else lo_
    if len(h1) < 60 or len(m15) < 40:
        return None
    seg = h1.iloc[-25:-1]
    top, bot = float(seg["High"].max()), float(seg["Low"].min())
    a = float(atr(h1).iloc[-2])
    width = top - bot
    wmin, wmax, adx_max, edge, rr_min = (1.5, 10, 30, 0.35, 1.2) if L else (2, 8, 25, 0.3, 1.5)
    if not a > 0 or width < wmin * a or width > wmax * a or float(adx(h1).iloc[-2]) >= adx_max:
        return None
    e, p = engulf(m15), pinbar(m15)
    pos = (price - bot) / width
    if pos <= edge and (e == 1 or p == 1):
        d = 1
    elif pos >= 1 - edge and (e == -1 or p == -1):
        d = -1
    else:
        return None
    if d1dir and d == -d1dir:                 # لا نطاق ضد اتجاه D1
        return None
    sl = (bot - 0.25 * a) if d == 1 else (top + 0.25 * a)
    min_sd = max(1.0 * float(atr(m15).iloc[-2]), 5.0)   # وقف مو أقرب من 1×ATR M15 ولا من 5$
    if abs(price - sl) < min_sd:
        sl = price - d * min_sd
    risk = abs(price - sl)
    mid = (top + bot) / 2
    tp = (top - 0.1 * width) if d == 1 else (bot + 0.1 * width)
    if (tp - price) * d < rr_min * risk:
        return None
    trig = ("ابتلاع" if e == d else "رفض Pin Bar") + " M15"
    return {"dir": d, "range": True, "entry": price, "sl": sl, "sl0": sl, "tp1": mid, "tp": tp,
            "rr": round(abs(tp - price) / risk, 1), "candle": trig,
            "rng_txt": f"{trig} عند {'أرضية' if d == 1 else 'سقف'} النطاق {bot:.1f}-{top:.1f}",
            "notes": [f"نطاق آخر 24 ساعة: {bot:.2f} - {top:.2f}", f"إشارة: {trig}"]}


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
            neg = name in ("سعر ممتد", "عكس مستوى يومي")
            tag = "✅" if ok else ("⚠️" if neg else "▫️")
            if ok and not neg:
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


def dist_line(r):
    """المسافات بالدولار، لتحطها من سعر دخولك الفعلي على منصتك"""
    e = r["entry"]
    return (f"📏 من سعر دخولك على منصتك: الوقف {abs(r['sl'] - e):.1f}$ | "
            f"الهدف1 {abs(r['tp1'] - e):.1f}$ | الهدف2 {abs(r['tp'] - e):.1f}$")


def fmt(r, header="تحليل الذهب", full=False):
    m = r["mom"]
    L = [f"🚨 {header} 🚨", f"💰 السعر: {r['price']:.2f}",
         f"D1: {nm(r['t_d1'])} | H4: {nm(r['t_h4'])}",
         f"📈 15د: {m['15']:+.1f}$ | 1س: {m['1h']:+.1f}$ | 2س: {m['2h']:+.1f}$"]
    if r["dir"] is None:
        L.append("⚪ لا توصية: لا اتجاه مشترك واضح")
    else:
        side = "بيع 🔴" if r["dir"] == -1 else "شراء 🟢"
        L.append(f"{side} | 🔄 تداول نطاق (H4 محايد)" if r.get("range")
                 else f"{side} | سكور {r['score']}/100 | شروط {r['met']}/4")
        sw_name = "كسر قاع وهمي" if r["dir"] == 1 else "كسر قمة وهمي"
        L += [f"{'🟢' if r['sweep'] else '⚪'} {sw_name if r['sweep'] else 'لا كسر وهمي'}"
              f" | OB: {'نعم' if r['ob'] else 'لا'} | FVG: {r['fvg'] or 'لا'}",
              f"🕯️ {r['candle']}", f"🏦 ORB لندن: {r['orb']}"]
        lv = r.get("levels")
        if lv:
            L.append(f"📊 امبارح: قمة {lv['high']:.2f} | 50% {lv['mid']:.2f} | قاع {lv['low']:.2f}")
        if r["elite"]:
            L += ["✅ توصية: ابتلاع مع الاتجاه (D1 + H1/H4)",
                  f"🎯 الدخول: {r['entry']:.2f}", f"🛑 الوقف: {r['sl']:.2f}",
                  f"✅ الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}",
                  f"💰 الهدف 2: {r['tp']:.2f} (2:1)", dist_line(r)]
        elif r.get("range"):
            L += [f"🔄 توصية نطاق: {r['rng_txt']} (أضعف من توصيات الترند، حجم صغير)",
                  f"🎯 الدخول: {r['entry']:.2f}", f"🛑 الوقف: {r['sl']:.2f}",
                  f"✅ الهدف 1 نص النطاق (انقل الوقف للتعادل): {r['tp1']:.2f}",
                  f"💰 الهدف 2: {r['tp']:.2f} ({r['rr']}:1)",
                  dist_line(r), "⚠️ إذا انكسر النطاق بقوة، اطلع فوراً."]
        elif r.get("fast"):
            L += [f"⚡ توصية سريعة: {r['fast_txt']} (أضعف من التوصية القوية، حجم أصغر)",
                  f"🎯 الدخول: {r['entry']:.2f}", f"🛑 الوقف: {r['sl']:.2f}",
                  f"✅ الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}",
                  f"💰 الهدف 2: {r['tp']:.2f} (2:1)", dist_line(r)]
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


# ---------------- سجل النتائج (محفوظ برسالة مثبتة على تليجرام) ----------------
KINDS = {"strong": "قوية 🚨", "fast": "سريعة ⚡", "range": "نطاق 🔄", "scalp": "سكالب ⚡⚡", "light": "خفيفة 🟡", "trend": "ترند 📈", "brt": "اختراق 🔁"}
RES = {"tp": "🎯 هدف", "sl": "🛑 وقف", "be": "⚪ تعادل", "exp": "⌛ انتهت"}
JTAG = "📒 سجل البوت (لا تحذف ولا تلغي تثبيت هالرسالة)\n"
journal = {"loaded": False, "msg_id": None,
           "db": {"k": {k: {"tp": 0, "sl": 0, "be": 0, "exp": 0, "R": 0.0} for k in KINDS}, "last": []}}


def tg(method, **data):
    try:
        return requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=15).json()
    except Exception as e:
        print(f"[journal] {method}: {e}", flush=True)
        return {}


def journal_load():
    """يقرأ السجل من الرسالة المثبتة (لأن ملفات Render المجاني بتنمسح مع كل إعادة تشغيل)"""
    if journal["loaded"] or not TOKEN or not CHAT:
        return
    journal["loaded"] = True
    pm = (tg("getChat", chat_id=CHAT).get("result") or {}).get("pinned_message") or {}
    txt = pm.get("text") or ""
    if txt.startswith(JTAG.strip()[:12]):
        try:
            db = json.loads(txt[txt.index("{"):])
            for k in KINDS:
                db["k"].setdefault(k, {"tp": 0, "sl": 0, "be": 0, "exp": 0, "R": 0.0})
            journal["db"], journal["msg_id"] = db, pm.get("message_id")
            print("[journal] loaded from pinned message", flush=True)
        except Exception as e:
            print(f"[journal] parse error: {e}", flush=True)


def journal_save():
    if not TOKEN or not CHAT:
        return
    txt = JTAG + json.dumps(journal["db"], ensure_ascii=False, separators=(",", ":"))
    if journal["msg_id"]:
        r = tg("editMessageText", chat_id=CHAT, message_id=journal["msg_id"], text=txt)
        if r.get("ok") or "not modified" in str(r.get("description", "")):
            return
    r = tg("sendMessage", chat_id=CHAT, text=txt, disable_notification=True)
    mid = (r.get("result") or {}).get("message_id")
    if mid:
        journal["msg_id"] = mid
        tg("pinChatMessage", chat_id=CHAT, message_id=mid, disable_notification=True)


def journal_add(kind, d, entry, res, r_mult):
    try:
        journal_load()
        db = journal["db"]
        k = db["k"][kind]
        k[res] += 1
        k["R"] = round(k["R"] + r_mult, 2)
        db["last"].append([kind, d, round(entry, 1), res, round(r_mult, 2),
                           local_now().strftime("%m-%d %H:%M")])
        db["last"] = db["last"][-20:]
        journal_save()
    except Exception as e:
        print(f"[journal] add error: {e}", flush=True)


def local_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(os.getenv("TZ_LOCAL", "Europe/Berlin")))
    except Exception:
        return datetime.now(timezone.utc)


def mtm(s, risk_key="risk"):
    """ربح/خسارة الصفقة بالـR عند انتهاء صلاحيتها، حسب السعر الحالي"""
    try:
        p = float(get("15m", "1d")["Close"].iloc[-1])
        risk = s.get(risk_key) or abs(s["entry"] - s.get("sl0", s["sl"]))
        return (p - s["entry"]) * s["dir"] / risk if risk else 0.0
    except Exception:
        return 0.0


def stats_text():
    journal_load()
    db = journal["db"]
    L = ["📒 نتائج التوصيات (من وقت ما بلّش السجل)", ""]
    for k, name in KINDS.items():
        x = db["k"][k]
        n = x["tp"] + x["sl"] + x["be"] + x["exp"]
        if not n:
            L.append(f"{name}: لا صفقات بعد")
            continue
        L.append(f"{name}: {n} صفقة | 🎯{x['tp']} 🛑{x['sl']} ⚪{x['be']} ⌛{x['exp']}")
        L.append(f"   نسبة النجاح {100 * x['tp'] / n:.0f}% | المجموع {x['R']:+.1f}R | المتوسط {x['R'] / n:+.2f}R")
    if db["last"]:
        L += ["", "آخر الصفقات:"]
        for kind, d, e, res, rm, t in db["last"][-10:][::-1]:
            L.append(f"{t} | {KINDS[kind].split()[0]} {'شراء' if d == 1 else 'بيع'} {e} | {RES[res]} ({rm:+.1f}R)")
    L += ["", "📏 R يعني مسافة الوقف (‎-1R = خسارة وقف كاملة)",
          "✅ العلامة الجيدة: متوسط موجب بعد ثلاثين صفقة أو أكثر"]
    return "\n".join(L)


# ---------------- تتبع الصفقة ----------------
def track():
    s = active["sig"]
    if not s:
        return
    now = pd.Timestamp.now(tz="UTC")
    if now - active["t0_orig"] > pd.Timedelta(hours=24):
        send("⌛ انتهت صلاحية التوصية (24 ساعة). تجاهلها وانتظر إعداداً جديداً.")
        journal_add(active.get("kind", "strong"), s["dir"], s["entry"], "exp", mtm(s))
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
        journal_add(active.get("kind", "strong"), d, s["entry"], "be" if active["be"] else "sl",
                    0.0 if active["be"] else -1.0)
        last["t"] = time.time()
        active.update(sig=None)
    elif hit_tp:
        rr_ = abs(s["tp"] - s["entry"]) / max(abs(s["entry"] - s.get("sl0", s["entry"])), 1e-9)
        send(f"🎯 تحقق الهدف النهائي! ربح {rr_:.1f}R ✅")
        journal_add(active.get("kind", "strong"), d, s["entry"], "tp", round(rr_, 2))
        last["t"] = time.time()
        active.update(sig=None)
    elif reach1 and not active["be"]:
        s["sl"] = s["entry"]
        active.update(be=True, t0=now)
        send(f"🔔 وصل السعر الهدف 1 ({s['tp1']:.2f}). انقل الوقف إلى الدخول {s['entry']:.2f}.")


# ---------------- فلتر الأخبار الاقتصادية ----------------
# المصدر: تقويم ForexFactory المجاني (JSON). نوقف التوصيات الجديدة حول الأخبار القوية للدولار.
NEWS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_BEFORE = int(os.getenv("NEWS_BEFORE", "30"))     # دقائق قبل الخبر
NEWS_AFTER = int(os.getenv("NEWS_AFTER", "30"))       # دقائق بعد الخبر
NEWS_CCY = {c.strip().upper() for c in os.getenv("NEWS_CCY", "USD").split(",") if c.strip()}
news = {"on": os.getenv("NEWS_ON", "1") == "1", "events": [], "t": 0, "err": "", "warned": set()}


def news_load(force=False):
    """يجيب أخبار الأسبوع مرة كل 3 ساعات (المصدر يحظر الطلبات الكثيرة). يحتفظ بآخر نسخة سليمة عند الفشل."""
    if not force and news["events"] and time.time() - news["t"] < 3 * 3600:
        return news["events"]
    if not force and not news["events"] and news["err"] and time.time() - news["t"] < 600:
        return news["events"]                            # فشل قبل قليل، لا نعيد بسرعة
    try:
        r = requests.get(NEWS_URL, timeout=20, headers={"User-Agent": "Mozilla/5.0 gold-bot"})
        r.raise_for_status()
        ev = []
        for x in r.json():
            if str(x.get("impact", "")).lower() != "high":
                continue
            if str(x.get("country", "")).upper() not in NEWS_CCY:
                continue
            try:
                t = pd.Timestamp(x["date"]).tz_convert("UTC")
            except Exception:
                continue
            ev.append({"t": t, "title": x.get("title", "?"), "ccy": x.get("country", ""),
                       "fc": x.get("forecast") or "", "prev": x.get("previous") or ""})
        news.update(events=sorted(ev, key=lambda e: e["t"]), t=time.time(), err="")
        print(f"[news] loaded {len(ev)} high-impact events", flush=True)
    except Exception as e:
        news.update(err=str(e)[:120], t=time.time())
        print(f"[news] error: {e}", flush=True)
    return news["events"]


def news_block(now=None):
    """يرجع الخبر اللي ضمن نافذة الحظر حالياً، أو None"""
    if not news["on"]:
        return None
    now = now or pd.Timestamp.now(tz="UTC")
    for e in news_load():
        if e["t"] - pd.Timedelta(minutes=NEWS_BEFORE) <= now <= e["t"] + pd.Timedelta(minutes=NEWS_AFTER):
            return e
    return None


def news_local(t):
    try:
        from zoneinfo import ZoneInfo
        return t.tz_convert(ZoneInfo(os.getenv("TZ_LOCAL", "Europe/Berlin")))
    except Exception:
        return t


def news_warn():
    """تنبيه مرة واحدة قبل كل خبر قوي، مع تذكير بالصفقات المفتوحة"""
    if not news["on"]:
        return
    now = pd.Timestamp.now(tz="UTC")
    soon = [e for e in news_load()
            if now <= e["t"] <= now + pd.Timedelta(minutes=NEWS_BEFORE)
            and (e["t"], e["title"]) not in news["warned"]]
    if not soon:
        return
    t0 = soon[0]["t"]
    group = [e for e in soon if e["t"] == t0]
    for e in group:
        news["warned"].add((e["t"], e["title"]))
    mins = max(int((t0 - now).total_seconds() // 60), 0)
    names = "\n".join(f"• {e['title']} ({e['ccy']})"
                      + (f" | المتوقع {e['fc']} السابق {e['prev']}" if e["fc"] or e["prev"] else "")
                      for e in group)
    open_ = []
    if active["sig"]:
        open_.append("التوصية")
    if scalp["sig"]:
        open_.append("السكالب")
    tail = (f"\n⚠️ عندك صفقة مفتوحة ({' و'.join(open_)}): فكّر بتقريب الوقف أو أخذ الربح قبل الخبر."
            if open_ else "")
    send(f"📰 خبر قوي بعد {mins} دقيقة ({news_local(t0):%H:%M}):\n{names}\n"
         f"⏸️ التوصيات الجديدة متوقفة من {NEWS_BEFORE} دقيقة قبل الخبر حتى {NEWS_AFTER} دقيقة بعده.{tail}")


def news_text():
    ev = news_load(force=not news["events"])
    now = pd.Timestamp.now(tz="UTC")
    up = [e for e in ev if e["t"] >= now - pd.Timedelta(minutes=NEWS_AFTER)]
    L = [f"📰 الأخبار القوية ({', '.join(sorted(NEWS_CCY))}) هذا الأسبوع",
         f"الفلتر: {'شغال ✅' if news['on'] else 'متوقف ⏸️'} | يوقف التوصيات {NEWS_BEFORE} د قبل و{NEWS_AFTER} د بعد", ""]
    if news["err"] and not ev:
        L.append(f"⚠️ ما قدرت أجيب التقويم: {news['err']}")
    elif not up:
        L.append("لا أخبار قوية متبقية هذا الأسبوع.")
    else:
        days = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"}
        for e in up[:15]:
            lt = news_local(e["t"])
            L.append(f"{days[lt.weekday()]} {lt:%d.%m %H:%M} | {e['title']}")
    b = news_block()
    if b:
        L += ["", f"⏸️ الآن داخل نافذة الخبر: {b['title']}"]
    return "\n".join(L)


# ---------------- تليجرام ----------------
def send(text):
    if not TOKEN or not CHAT:
        print(text, flush=True)
        return
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT, "text": text}, timeout=15)


def reply(chat_id, text):
    """بيقسم الرسائل الطويلة، وبيعيد المحاولة إذا فشل الإرسال (حتى ما تضيع نتيجة اختبار)"""
    text = str(text)
    parts = [text[i:i + 3500] for i in range(0, len(text), 3500)] or [""]
    for part in parts:
        for attempt in range(3):
            try:
                j = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                  data={"chat_id": chat_id, "text": part}, timeout=20).json()
                if j.get("ok"):
                    break
                print(f"[reply] telegram error: {j}", flush=True)
            except Exception as e:
                print(f"[reply] error: {e}", flush=True)
            time.sleep(3)


# ---------------- وضع الصفقات السريعة (سكالب) ----------------
def scalp_eval(m15, h1, price, lo_=None, trig=None, emad=None, sdmin=2.0):
    """ابتلاع M15 مع اتجاه H1 وعند منطقة تصحيح قرب EMA21. وقف 1.2×ATR، هدف 1R ثم 2R.
    trig: "e" ابتلاع بس، "ep" ابتلاع أو Pin Bar. emad: أقصى بعد عن EMA21 بوحدات ATR.
    lo_=True (الشروط الأخف): ep و 2.0. بتنفع كمان لفريم 5 دقايق (m15=M5، h1=M15)."""
    L = loose["on"] if lo_ is None else lo_
    trig = trig or ("ep" if L else "e")
    emad = emad or (2.0 if L else SCALP_EMAD)
    if len(m15) < 80 or len(h1) < 60:
        return None
    t, e = trend(h1), engulf(m15)
    if t == 0 or (e != t and not (trig == "ep" and pinbar(m15) == t)):
        return None
    c = m15["Close"]
    a = float(atr(m15).iloc[-2])
    if not a > 0:
        return None
    if abs(float(c.iloc[-2]) - float(ema(c, 21).iloc[-2])) > emad * a:
        return None
    sd = max(1.2 * a, sdmin)
    return {"dir": t, "entry": price, "sl": price - t * sd, "tp1": price + t * sd,
            "tp": price + t * 2 * sd, "risk": sd}


trend_mode = {"on": os.getenv("TREND_ON", "0") == "1"}   # مطفي: خسران بالنصّين بالباك تست (13-10)


def trend_eval(m15, h1, price, hi_dirs):
    """مع الترند 📈: اتجاه H1 + (D1 أو H4) نفس الاتجاه وما في فريم كبير معاكس.
    الدخول لما شمعة M15 ترجع تلمس EMA21 وتسكر باتجاه الترند (ما بدها ابتلاع).
    وقف 1.2×ATR M15 (أقل شي 3$)، هدف 1R ثم 2R."""
    if len(m15) < 80 or len(h1) < 60:
        return None
    t = trend(h1)
    if t == 0 or any(x == -t for x in hi_dirs) or not any(x == t for x in hi_dirs):
        return None
    c, o = float(m15["Close"].iloc[-2]), float(m15["Open"].iloc[-2])
    lo, hi = float(m15["Low"].iloc[-2]), float(m15["High"].iloc[-2])
    e = float(ema(m15["Close"], 21).iloc[-2])
    a = float(atr(m15).iloc[-2])
    if not a > 0:
        return None
    if t == 1:
        ok = lo <= e + 0.3 * a and c > e and c > o and c - e < a
    else:
        ok = hi >= e - 0.3 * a and c < e and c < o and e - c < a
    if not ok:
        return None
    sd = max(1.2 * a, 3.0)
    return {"dir": t, "entry": price, "sl": price - t * sd, "tp1": price + t * sd,
            "tp": price + t * 2 * sd, "risk": sd}


brt_mode = {"on": os.getenv("BRT_ON", "1") == "1"}   # مفعّل: ربحان بالنصّين (26 صفقة، 13-10)


def brt_eval(m15, h1, price, hi_dirs):
    """اختراق وإعادة اختبار 🔁: مع اتجاه H1 (والفريم الكبير مش معاكس)،
    السعر سكّر فوق قمة سابقة (أو تحت قاع)، رجع لمسها وسكّر شمعة باتجاه الترند.
    الوقف ورا المستوى (أقل شي 1×ATR و3$)، هدف 1R ثم 2R."""
    if len(m15) < 80 or len(h1) < 60:
        return None
    t = trend(h1)
    if t == 0 or any(x == -t for x in hi_dirs) or not any(x == t for x in hi_dirs):
        return None
    hi, lo, c, o = m15["High"], m15["Low"], m15["Close"], m15["Open"]
    a = float(atr(m15).iloc[-2])
    if not a > 0:
        return None
    base = (hi if t == 1 else lo).iloc[-40:-12]
    level = float(base.max() if t == 1 else base.min())
    brk = [(float(x) - level) * t > 0.2 * a for x in c.iloc[-11:-2]]
    if not any(brk):
        return None
    c2, o2 = float(c.iloc[-2]), float(o.iloc[-2])
    touch = float(lo.iloc[-2]) <= level + 0.3 * a if t == 1 else float(hi.iloc[-2]) >= level - 0.3 * a
    if not (touch and (c2 - level) * t > 0 and (c2 - o2) * t > 0):
        return None
    sd = max(abs(price - (level - t * 0.5 * a)), 1.0 * a, 3.0)
    if sd > 3 * a:
        return None
    return {"dir": t, "entry": price, "sl": price - t * sd, "tp1": price + t * sd,
            "tp": price + t * 2 * sd, "risk": sd}


def sim_r(raw, i, d, entry, sl, tp1, tp, maxbars):
    """بترجع (R الحقيقي، رقم شمعة الخروج)."""
    n, risk, be, stop = len(raw), abs(entry - sl), False, sl
    end = min(i + maxbars, n)
    for j in range(i, end):
        hi, lo = float(raw["High"].iloc[j]), float(raw["Low"].iloc[j])
        if (lo <= stop) if d == 1 else (hi >= stop):
            return (0.0 if be else -1.0), j
        if (hi >= tp) if d == 1 else (lo <= tp):
            return (tp - entry) * d / risk, j
        if not be and ((hi >= tp1) if d == 1 else (lo <= tp1)):
            be, stop = True, entry
    return (float(raw["Close"].iloc[end - 1]) - entry) * d / risk, end - 1


def _bt_pass(raw, step_fn, maxbars, slots):
    """يمشي على الشموع بجلسة لندن+نيويورك، وما بيفتح أكتر من slots صفقات بنفس الوقت (متل البوت الحقيقي)."""
    idx = raw.index.tz_convert("UTC") if raw.index.tz is not None else raw.index.tz_localize("UTC")
    out, last_i, busy = {}, {}, {}
    for i in range(250, len(raw) - 2):
        if not (SESSION[0] <= idx[i].hour < SESSION[1]):
            continue
        try:
            sigs = step_fn(raw, i)
        except Exception:
            continue
        for key, s, mb in sigs:
            if not s:
                continue
            li = last_i.setdefault(key, {1: -99, -1: -99})
            if i - li[s["dir"]] < 4:
                continue
            for k2, sl_ in slots.get(key, [(key, 1)]):
                b = busy.setdefault(k2, [])
                b[:] = [x for x in b if x > i]
                if len(b) >= sl_:
                    continue
                risk = abs(s["entry"] - s["sl"])
                R, j = sim_r(raw, i, s["dir"], s["entry"], s["sl"], s["tp1"], s["tp"], mb)
                b.append(j)
                out.setdefault(k2, []).append(R - SPREAD / risk)
            li[s["dir"]] = i
    return out


def run_scalp_bt(cid):
    """مقارنة نسخ السكالب (والنطاق) على آخر ~60 يوم، بعد السبريد، صفقة وحدة بنفس الوقت."""
    try:
        reply(cid, "⏳ اختبار نسخ السكالب (M15 + M5) والنطاق على آخر ~60 يوم. ممكن ياخد 5-10 دقائق...")
        variants = [("base", "e", 1.2), ("pin", "ep", 1.2), ("e15", "e", 1.5), ("pin15", "ep", 1.5), ("loose", "ep", 2.0)]

        pre = {}

        def step15(raw, i):
            if "h1" not in pre:                       # الفريمات الكبيرة مرة وحدة بدل كل شمعة (أسرع بكتير)
                pre["h1"] = raw.resample("1h").agg(OHLC).dropna()
                pre["h4"] = raw.resample("4h").agg(OHLC).dropna()
            w = raw.iloc[max(0, i - 300):i + 1].copy()
            o = float(w["Open"].iloc[-1])
            for k in ("Open", "High", "Low", "Close"):
                w.iloc[-1, w.columns.get_loc(k)] = o
            t_i = raw.index[i]
            def upto(big, fr, n):                     # الشموع المكتملة + الشمعة الحالية من شموع M15 لحد هلأ (بدون نظر للمستقبل)
                st = t_i.floor(fr)
                done = big[big.index < st].iloc[-n:]
                cur = w[w.index >= st].resample(fr).agg(OHLC).dropna()
                return pd.concat([done, cur])
            h1, h4 = upto(pre["h1"], "1h", 300), upto(pre["h4"], "4h", 120)
            sigs = [(v, scalp_eval(w, h1, o, trig=t, emad=e), 16) for v, t, e in variants]
            if len(h4) >= 60:
                sigs.append(("trend", trend_eval(w, h1, o, [trend(h4)]), 16))
                sigs.append(("brt", brt_eval(w, h1, o, [trend(h4)]), 16))
            if len(h4) >= 60 and trend(h4) == 0:
                for v, L in (("range", False), ("range_l", True)):
                    sigs.append((v, range_eval(h1, w, o, lo_=L), 32))
            return sigs

        raw = get_raw("15m", "60d")
        days15 = max((raw.index[-1] - raw.index[0]).days, 1)
        slots = {v: [(v, 1)] for v, _, _ in variants}
        slots["base"] = [("base", 1), ("base2", 2)]       # نفس الشروط بس صفقتين بنفس الوقت
        r15 = _bt_pass(raw, step15, 16, slots)
        reply(cid, "⏳ خلص M15، هلأ عم يختبر M5...")

        def step5(raw, i):
            w = raw.iloc[max(0, i - 900):i + 1].copy()
            o = float(w["Open"].iloc[-1])
            for k in ("Open", "High", "Low", "Close"):
                w.iloc[-1, w.columns.get_loc(k)] = o
            m15 = w.resample("15min").agg(OHLC).dropna()
            return [("m5", scalp_eval(w, m15, o, trig="e", emad=1.2, sdmin=1.5), 48),
                    ("m5p", scalp_eval(w, m15, o, trig="ep", emad=1.2, sdmin=1.5), 48)]

        r5, days5 = {}, 1
        try:
            raw5 = get_raw("5m", "60d")
            days5 = max((raw5.index[-1] - raw5.index[0]).days, 1)
            r5 = _bt_pass(raw5, step5, 48, {})
            del raw5
        except Exception as e:
            r5 = {"err": str(e)[:100]}

        names = [("base", "القديم (ابتلاع، EMA 1.2)", days15), ("base2", "القديم + صفقتين بنفس الوقت", days15),
                 ("pin", "ابتلاع أو Pin Bar، EMA 1.2", days15), ("e15", "الحالي ✔️ (ابتلاع، EMA 1.5)", days15),
                 ("pin15", "ابتلاع أو Pin Bar، EMA 1.5", days15), ("loose", "الأخف (Pin Bar، EMA 2.0)", days15),
                 ("m5", "M5 ابتلاع (اتجاه M15)", days5), ("m5p", "M5 ابتلاع أو Pin Bar", days5),
                 ("trend", "📈 مع الترند (رجوع EMA21)", days15),
                 ("brt", "🔁 اختراق وإعادة اختبار", days15),
                 ("range", "🔄 النطاق الحالي", days15), ("range_l", "🔄 النطاق الأخف", days15)]
        L = [f"📊 مقارنة النسخ (بعد سبريد {SPREAD}$، جلسة لندن+نيويورك)"]
        allr = {**r15, **{k: v for k, v in r5.items() if k != "err"}}
        for k, title, dd in names:
            r = allr.get(k, [])
            h = len(r) // 2
            ok = bool(h and stats(r[:h])["avg"] > 0 and stats(r[h:])["avg"] > 0)
            L += ["", f"{'✅' if ok else '❌'} {title}",
                  f"{line(r)} | ~{len(r) / dd * 7:.1f}/أسبوع"]
            if h:
                L.append(f"   نص1 {stats(r[:h])['avg']:+.2f}R | نص2 {stats(r[h:])['avg']:+.2f}R")
        if "err" in r5:
            L.append(f"\n⚠️ M5 ما اشتغل: {r5['err']}")
        L += ["", "✅ = ربحان بالنصّين. ابعت الصورة لـ Claude ليختار ويفعّل الأحسن."]
        reply(cid, "\n".join(L))
    except Exception as e:
        reply(cid, f"❌ فشل الاختبار: {e}")
    finally:
        bt["running"] = False


def scalp_persist():
    """بيحفظ صفقة السكالب المفتوحة بالسجل المثبت، حتى ما ينساها البوت إذا أعاد التشغيل"""
    try:
        journal_load()
        s = scalp["sig"]
        journal["db"]["scalp_open"] = None if not s else {
            "sig": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in s.items()},
            "kind": scalp.get("kind", "scalp"), "be": scalp["be"],
            "t0": scalp["t0"].isoformat(), "t_orig": scalp["t_orig"].isoformat()}
        journal_save()
    except Exception as e:
        print(f"[scalp] persist error: {e}", flush=True)


def scalp_restore():
    try:
        journal_load()
        o = journal["db"].get("scalp_open")
        if not o:
            return
        t_orig = pd.Timestamp(o["t_orig"])
        if pd.Timestamp.now(tz="UTC") - t_orig > pd.Timedelta(hours=4):
            return
        scalp.update(sig=o["sig"], kind=o["kind"], be=o["be"], t0=pd.Timestamp(o["t0"]), t_orig=t_orig)
        s = o["sig"]
        send(f"♻️ البوت تذكّر صفقته المفتوحة: {'شراء' if s['dir'] == 1 else 'بيع'} من {s['entry']:.2f}"
             f" | الوقف {s['sl']:.2f} | الهدف {s['tp']:.2f}")
    except Exception as e:
        print(f"[scalp] restore error: {e}", flush=True)


def scalp_step():
    before = (id(scalp["sig"]), scalp["be"])
    _scalp_step()
    if (id(scalp["sig"]), scalp["be"]) != before:
        scalp_persist()


def _scalp_step():
    m15, h1 = snap.get("m15"), snap.get("h1")
    if not scalp["on"] or m15 is None:
        return
    now = pd.Timestamp.now(tz="UTC")
    s = scalp["sig"]
    if s:
        if now - scalp["t_orig"] > pd.Timedelta(hours=4):
            send("⌛ انتهت صلاحية صفقة السكالب (4 ساعات).")
            journal_add(scalp.get("kind", "scalp"), s["dir"], s["entry"], "exp", mtm(s))
            scalp["sig"] = None
        else:
            bars = m15[m15.index > scalp["t0"]]
            if not bars.empty:
                hi, lo, d = float(bars["High"].max()), float(bars["Low"].min()), s["dir"]
                if (lo <= s["sl"]) if d == 1 else (hi >= s["sl"]):
                    send("⚡🛑 السكالب: ضرب الوقف." if not scalp["be"] else "⚡⚪ السكالب: خروج عند التعادل.")
                    journal_add(scalp.get("kind", "scalp"), d, s["entry"], "be" if scalp["be"] else "sl",
                                0.0 if scalp["be"] else -1.0)
                    scalp["sig"] = None
                elif (hi >= s["tp"]) if d == 1 else (lo <= s["tp"]):
                    send("⚡🎯 السكالب: تحقق الهدف 2 (+2R) ✅")
                    journal_add(scalp.get("kind", "scalp"), d, s["entry"], "tp", 2.0)
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
    if now - bar > pd.Timedelta(minutes=45):          # بيانات ياهو متأخرة ~10-15 دقيقة
        return
    if not live_ok(now):
        return
    if news_block(now):                               # خبر قوي قريب: لا صفقات سكالب جديدة
        return
    px = float(m15["Close"].iloc[-1])
    r, kind = scalp_eval(m15, h1, px, lo_=False), "scalp"
    if not r and loose["on"]:
        r, kind = scalp_eval(m15, h1, px, lo_=True), "light"
    if not r and trend_mode["on"]:
        r, kind = trend_eval(m15, h1, px, snap.get("t_hi", [])), "trend"
    if not r and brt_mode["on"]:
        r, kind = brt_eval(m15, h1, px, snap.get("t_hi", [])), "brt"
    if r:
        side = "شراء 🟢" if r["dir"] == 1 else "بيع 🔴"
        title = {"light": "🟡 صفقة خفيفة (شروط أخف)", "trend": "📈 صفقة مع الترند (رجوع لـ EMA21)",
                 "brt": "🔁 صفقة اختراق وإعادة اختبار"}.get(
            kind, "⚡ صفقة سريعة (سكالب)")
        send(f"{title} — {side}\n🎯 الدخول: {r['entry']:.2f}\n🛑 الوقف: {r['sl']:.2f}\n"
             f"✅ الهدف 1 (انقل الوقف للتعادل): {r['tp1']:.2f}\n💰 الهدف 2: {r['tp']:.2f}\n"
             f"{dist_line(r)}\n⚠️ صفقة قصيرة (حتى 4 ساعات)، حجم صغير.")
        scalp.update(sig=r, t0=now, t_orig=now, be=False, kind=kind)


def loop():
    while True:
        try:
            track()
            try:
                news_warn()
            except Exception as e:
                print(f"[news] warn error: {e}", flush=True)
            r = analyze()
            try:
                scalp_step()
            except Exception as e:
                print(f"[scalp] error: {e}", flush=True)
            nb = news_block()
            side = {1: "شراء", -1: "بيع"}.get(r["dir"], "لا اتجاه مشترك D1/H4")
            status["msg"] = (f"سعر {r['price']:.2f} | {side} | قوة {r['score']}"
                             f"{' ✅ قوية' if r.get('elite') else (' ⚡ سريعة' if r.get('fast') else '')}"
                             f"{(' | ⏸️ خبر: ' + nb['title']) if nb else ''}")
            status["t"] = time.time()
            if (auto["on"] and (r["elite"] or r.get("fast") or r.get("range")) and live_ok()
                    and not nb
                    and active["sig"] is None
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
                    send(fmt(r, "توصية جديدة" if r["elite"] else
                             (("توصية نطاق خفيفة 🟡" if r.get("light") else "توصية نطاق 🔄") if r.get("range")
                              else "توصية سريعة ⚡")))
                    now = pd.Timestamp.now(tz="UTC")
                    active.update(sig=r, t0=now, t0_orig=now, be=False,
                                  kind="strong" if r["elite"] else ("light" if r.get("light") else
                                                    ("range" if r.get("range") else "fast")))
                    last.update(dir=r["dir"], t=time.time())
        except Exception as e:
            status["msg"] = f"error: {e}"
            print(f"[loop] error: {e}", flush=True)
        gc.collect()
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
                    if (rr["elite"] or rr.get("fast") or rr.get("range")) and ANTHROPIC_KEY:
                        rr["ai"] = ai_review(rr)
                    nb = news_block()
                    reply(cid, fmt(rr, full=True) + (
                        f"\n\n📰⚠️ انتبه: خبر قوي قريب ({nb['title']} {news_local(nb['t']):%H:%M}). "
                        "الأفضل عدم الدخول الآن." if nb else ""))
                elif text.startswith("/allday_on"):
                    allday["on"] = True
                    reply(cid, "🌍 التوصيات على مدار الساعة (ما عدا توقف السوق اليومي 23:00-00:00 تقريباً).\n"
                               "🕒 التوصيات خارج لندن/نيويورك بيكون مكتوب عليها 'سيولة أقل'.")
                elif text.startswith("/allday_off"):
                    allday["on"] = False
                    reply(cid, "🕘 التوصيات بس بجلسة لندن + نيويورك (09:00-22:00 بتوقيت ألمانيا).")
                elif text.startswith("/news_on"):
                    news["on"] = True
                    reply(cid, f"📰 فلتر الأخبار مفعّل ({NEWS_BEFORE} د قبل الخبر و{NEWS_AFTER} د بعده).")
                elif text.startswith("/news_off"):
                    news["on"] = False
                    reply(cid, "⏸️ فلتر الأخبار متوقف (التوصيات بتطلع حتى وقت الأخبار).")
                elif text.startswith("/news"):
                    reply(cid, news_text())
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
                elif text.startswith("/stats_reset"):
                    journal_load()
                    journal["db"] = {"k": {k: {"tp": 0, "sl": 0, "be": 0, "exp": 0, "R": 0.0} for k in KINDS},
                                     "last": []}
                    journal_save()
                    reply(cid, "🧹 تم تصفير السجل.")
                elif text.startswith("/stats"):
                    reply(cid, stats_text())
                elif text.startswith("/range_on"):
                    rng_mode["on"] = True
                    reply(cid, "🔄 وضع تداول النطاق مفعّل (بيشتغل بس لما H4 محايد).")
                elif text.startswith("/range_off"):
                    rng_mode["on"] = False
                    reply(cid, "⏸️ وضع تداول النطاق متوقف.")
                elif text.startswith("/loose_on"):
                    loose["on"] = True
                    reply(cid, "🟡 التوصيات الخفيفة مفعّلة فوق الأصلية: لما الشروط الأصلية ما تكتمل، "
                               "البوت بيجرب شروط أخف وبيبعتها مكتوب عليها 'خفيفة 🟡'. الأصلية ما تغيرت.")
                elif text.startswith("/loose_off"):
                    loose["on"] = False
                    reply(cid, "🔒 التوصيات الخفيفة متوقفة، بس الأصلية شغالة.")
                elif text.startswith("/trend_on"):
                    trend_mode["on"] = True
                    reply(cid, "📈 صفقات مع الترند مفعّلة.")
                elif text.startswith("/trend_off"):
                    trend_mode["on"] = False
                    reply(cid, "⏸️ صفقات مع الترند متوقفة.")
                elif text.startswith("/brt_on"):
                    brt_mode["on"] = True
                    reply(cid, "🔁 صفقات الاختراق وإعادة الاختبار مفعّلة.")
                elif text.startswith("/brt_off"):
                    brt_mode["on"] = False
                    reply(cid, "⏸️ صفقات الاختراق وإعادة الاختبار متوقفة.")
                elif text.startswith("/scalp_on"):
                    scalp["on"] = True
                    reply(cid, "⚡ وضع السكالب مفعّل.")
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
                elif text.startswith("/levels"):
                    rr = analyze()
                    lv = daily_levels(get("1d", "2y", 3600))
                    if not lv:
                        reply(cid, "ما في بيانات كافية للشمعة اليومية.")
                    else:
                        p = rr["price"]
                        where = "فوق 50% (منطقة غلاء ← الأفضلية للبيع)" if p > lv["mid"] else "تحت 50% (منطقة خصم ← الأفضلية للشراء)"
                        reply(cid, f"📊 مستويات شمعة امبارح\n🔺 القمة: {lv['high']:.2f}\n"
                                   f"⚖️ النص 50%: {lv['mid']:.2f}\n🔻 القاع: {lv['low']:.2f}\n\n"
                                   f"💰 السعر الآن: {p:.2f}\n{where}")
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
                    reply(cid, f"التلقائي: {'شغال' if auto['on'] else 'متوقف'}\n"
                               f"السكالب: {'شغال ⚡' if scalp['on'] else 'متوقف'}\n"
                               f"الساعات: {'على مدار الساعة 🌍' if allday['on'] else 'لندن+نيويورك فقط'}\n"
                               f"الشروط: {'أصلية + خفيفة 🟡' if loose['on'] else 'أصلية بس 🔒'}\n"
                               f"فلتر الأخبار: {'شغال 📰' if news['on'] else 'متوقف'}"
                               f"{(' ⚠️ ' + news['err']) if news['err'] else ''}\n"
                               f"البيانات: {used['sym']}"
                               f"{(' ⚠️ ' + td_err['msg']) if TD_KEY and td_err['msg'] else ''}\n"
                               f"آخر فحص: {status['msg']} (قبل {int(time.time() - status.get('t', time.time()))} ثانية)"
                               f"{' ⚠️ الفحص التلقائي واقف!' if time.time() - status.get('t', time.time()) > 600 else ''}{t}")
                elif text.startswith("/start"):
                    reply(cid, "أهلاً! الأوامر:\n/tawsiya تحليل كامل\n/price السعر\n/levels قمة ونص وقاع شمعة امبارح\n/ai قراءة السوق بالذكاء الاصطناعي مع الأخبار\n/backtest 180 اختبار الاستراتيجية على التاريخ\n/calib 4193.5 معايرة السعر على منصتك\n/auto_on /auto_off\n/scalp_on /scalp_off\n/scalpbt مقارنة الشروط الحالية مع الأخف\n/loose_on /loose_off شروط أخف = صفقات أكتر\n/range_on /range_off تداول النطاق\n/news الأخبار القوية هذا الأسبوع\n/news_on /news_off فلتر الأخبار\n/allday_on /allday_off توصيات على مدار الساعة\n/stats نتائج التوصيات\n/stats_reset تصفير السجل\n/status")
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


try:
    send(f"🔄 البوت اشتغل من جديد | السكالب: {'شغال ⚡' if scalp['on'] else 'متوقف'}"
         f" | البيانات: {'فورية (Twelve Data)' if TD_KEY else 'Yahoo (متأخرة ~10 دقائق)'}")
except Exception as e:
    print(f"[startup] {e}", flush=True)

scalp_restore()
threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=commands, daemon=True).start()
threading.Thread(target=keepalive, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
