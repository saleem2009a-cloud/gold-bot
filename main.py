// @version=5
indicator("GOLD V70.9 Early+Confirmed", overlay=true)

// === ER ===
len = 14
chg = math.abs(close - close[len])
vol = math.sum(math.abs(ta.change(close)), len)
er = vol > 0? chg / vol : 0

// === OF مبسط ===
of_raw = (close - open) / (high - low + 0.0001) * 100
of_ma = ta.sma(of_raw, 10)

// === توافق - بدون security معقد ===
m15_diff = close - close[3]
h1_diff = close - close[12]
h2_diff = close - close[24]
agreeBuy = (m15_diff > 0? 1 : 0) + (h1_diff > 0? 1 : 0) + (h2_diff > 0? 1 : 0)
agreeSell = (m15_diff < 0? 1 : 0) + (h1_diff < 0? 1 : 0) + (h2_diff < 0? 1 : 0)

// === ابتلاع ===
bullEng = close > open and close[1] < open[1] and close > open[1] and open < close[1]
bearEng = close < open and close[1] > open[1] and close < open[1] and open > close[1]

// === شروط V70.9 ===
earlyBuyCond = er > 0.28 and er < 0.45 and of_ma > 55 and agreeBuy >= 2 and er > er[1]
confirmedBuyCond = er >= 0.40 and of_ma > 50 and agreeBuy >= 3 and bullEng and h2_diff < 20

earlySellCond = er > 0.28 and er < 0.45 and of_ma < -55 and agreeSell >= 2 and er > er[1]
confirmedSellCond = er >= 0.40 and of_ma < -50 and agreeSell >= 3 and bearEng and h2_diff > -20

// === رسم ===
plotshape(earlyBuyCond, title="تنبيه مبكر شراء 6/10", style=shape.triangleup, location=location.belowbar, color=color.new(color.yellow, 0), size=size.small, text="⚠️6/10 شراء")
plotshape(confirmedBuyCond, title="شراء مؤكد 9/10", style=shape.labelup, location=location.belowbar, color=color.new(color.green, 0), size=size.normal, text="🟢9/10 شراء")

plotshape(earlySellCond, title="تنبيه مبكر بيع 6/10", style=shape.triangledown, location=location.abovebar, color=color.new(color.orange, 0), size=size.small, text="⚠️6/10 بيع")
plotshape(confirmedSellCond, title="بيع مؤكد 9/10", style=shape.labeldown, location=location.abovebar, color=color.new(color.red, 0), size=size.normal, text="🔴9/10 بيع")

plot(er, "ER", color=color.yellow)
hline(0.28, "تنبيه", color=color.new(color.yellow, 50))
hline(0.35, "يشخبط", color=color.new(color.red, 50))
hline(0.45, "ترند", color=color.new(color.green, 50))

// === تنبيهات ===
alertcondition(earlyBuyCond, title="تنبيه مبكر شراء", message="⚠️ V70.9 تنبيه مبكر شراء 6/10 ER:{{plot(\"ER\")}} السعر {{close}} جهز حالك")
alertcondition(confirmedBuyCond, title="شراء مؤكد", message="🟢 V70.9 شراء 9/10 ER:{{plot(\"ER\")}} دخول {{close}} SL {{close}}-12 TP {{close}}+12/+24")
alertcondition(earlySellCond, title="تنبيه مبكر بيع", message="⚠️ V70.9 تنبيه مبكر بيع 6/10")
alertcondition(confirmedSellCond, title="بيع مؤكد", message="🔴 V70.9 بيع 9/10 دخول {{close}}")
