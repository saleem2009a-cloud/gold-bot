def is_market_open():
    """التحقق بدقة من أوقات تداول الذهب العالمية (يغلق السبت ويفتح مساء الأحد)"""
    now = datetime.now(timezone.utc)
    weekday = now.weekday() # 0: الإثنين, ..., 5: السبت, 6: الأحد
    hour = now.hour

    # السبت بالكامل يعتبر عطلة
    if weekday == 5:
        return False
    # الأحد: السوق يفتح عادةً متقدماً (حوالي الساعة 22:00 بتوقيت UTC)
    if weekday == 6 and hour < 22:
        return False
    # الجمعة: السوق يغلق متأخراً (حوالي الساعة 22:00 بتوقيت UTC)
    if weekday == 4 and hour >= 22:
        return False

    return True

def get_comprehensive_market_report():
    """جلب تقرير شامل ومحدث يضمن جلب آخر سعر لحظي بدقة"""
    try:
        market_open = is_market_open()
        market_status_text = "🟢 **السوق مفتوح**" if market_open else "🔴 **السوق مغلق (عطلة نهاية الأسبوع)**"

        ticker = yf.Ticker(SYMBOL)
        
        # محاولة جلب البيانات اللحظية (15 دقيقة) بغض النظر عن حالة السوق الظاهرية لضمان الحصول على آخر سعر إغلاق أو تداول
        df = ticker.history(period="5d", interval="15m")
        if df.empty:
            df = ticker.history(period="1mo", interval="1d")

        if df.empty:
            return "⚠️ تعذر جلب بيانات السوق اللحظية حالياً، يرجى المحاولة لاحقاً."

        df = calculate_advanced_indicators(df)
        last_row = df.iloc[-1]
        
        price = round(float(last_row['Close']), 2)
        discount_level = round(float(last_row['Discount_50']), 2)
        swing_high = round(float(last_row['High'].rolling(window=20).max().iloc[-1]), 2)
        swing_low = round(float(last_row['Low'].rolling(window=20).min().iloc[-1]), 2)
        rsi = round(float(last_row['RSI']), 2) if not pd.isna(last_row['RSI']) else 50.0

        zone_status = "منطقة خصم الشراء (Discount Region) 🛒🟢" if price <= discount_level else "منطقة بيع مرتفعة (Premium Region) 📈🔴"

        now = datetime.now(timezone.utc)
        astro_phase = get_moon_phase(now)
        time_session, is_time_turn = analyze_time_cycles()
        time_turn_alert = " | ⚡ **تنبيه انعطاف زمني!**" if is_time_turn else ""

        return f"""📊 **التقرير الشامل للذهب (SMC + الفلكي + الفني):**

🔒 **حالة السوق:** {market_status_text}
💰 **السعر الحالي:** `{price}$`
🎯 **مستوى الخصم (50% Fib):** `{discount_level}$`
📍 **النطاق:** High `{swing_high}$` | Low `{swing_low}$`
🏷️ **تقييم المنطقة:** {zone_status}
📉 **مؤشر RSI:** {rsi}
⏳ **الجلسة الزمنية:** {time_session}{time_turn_alert}
🌌 **الدورة الفلكية:** {astro_phase}"""
    except Exception as e:
        return f"حدث خطأ أثناء إعداد التقرير: {e}"
