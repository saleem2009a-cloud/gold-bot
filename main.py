// © V70.9 - تنبيه بدري + دخول مؤكد
// @version=5
indicator("GOLD V70.9 Early+Confirmed", overlay=true)

// === حساب ER ===
erLength = 14
change = math.abs(close - close[erLength])
volatility = math.sum(math.abs(close - close[1]), erLength)
ER = volatility > 0 ? change / volatility : 0

// === OF محاكاة (دلتا الشموع) ===
OF = (close - open) / (high - low + 0.001) * 100
OF_MA = ta.sma(OF, 10)

// === توافق الفريمات ===
m15 = request.security(syminfo.tickerid, "15", close - close[3])
h1  = request.security(syminfo.tickerid, "60", close - close[5])
h2  = request.security(syminfo.tickerid, "120", close - close[5])
agreeBuy = (m15>0?1:0) + (h1>0?1:0) + (h2>0?1:0)

// === ابتلاع ===
bullEng = close > open and close > high[1] and open < close[1]
bearEng = close < open and close < low[1] and open > close[1]

// === V70.9 منطق جديد ===
earlyBuy = ER > 0.28 and ER < 0.45 and OF_MA > 55 and agreeBuy >= 2 and ta.rising(ER, 3)
confirmedBuy = ER >= 0.40 and OF_MA > 50 and agreeBuy >= 3 and bullEng

earlySell = ER > 0.28 and ER < 0.45 and OF_MA < -55 and agreeBuy <= 1 and ta.rising(ER, 3)
confirmedSell = ER >= 0.40 and OF_MA < -50 and agreeBuy <= 1 and bearEng

// === تنبيه بدري - ما بيدخل، بس بينبهك ===
if earlyBuy and not confirmedBuy
    alert("⚠️ V70.9 تنبيه مبكر شراء 6/10 ER:"+str.tostring(ER, "#.##")+" OF:"+str.tostring(OF_MA, "#")+"% السعر قرب يطلع - جهز حالك", alert.freq_once_per_bar)

if earlySell and not confirmedSell
    alert("⚠️ V70.9 تنبيه مبكر بيع 6/10 ER:"+str.tostring(ER, "#.##")+" OF:"+str.tostring(OF_MA, "#")+"%", alert.freq_once_per_bar)

// === دخول مؤكد ===
if confirmedBuy
    // فلتر القمة - اذا طلع اكتر من 18$ بساعتين لا تدخل بالقمة استنى تصحيح
    if h2 < 20
        alert("🟢 V70.9 شراء 9/10 توافق "+str.tostring(agreeBuy)+"/4 ER:"+str.tostring(ER, "#.##")+" 15د "+str.tostring(m15, "#.#")+"$ 1س "+str.tostring(h1, "#.#")+"$ 2س "+str.tostring(h2, "#.#")+"$ ابتلاع شرائي OF "+str.tostring(OF_MA, "#")+"% دخول "+str.tostring(close)+" SL "+str.tostring(close-12)+" TP "+str.tostring(close+12)+"/"+str.tostring(close+24), alert.freq_once_per_bar)
    else
        alert("⛔ V70.9 طلع كتير "+str.tostring(h2, "#")+"$ - لا تلحق القمة استنى تصحيح", alert.freq_once_per_bar)

if confirmedSell
    if h2 > -20
        alert("🔴 V70.9 بيع 9/10 توافق "+str.tostring(agreeBuy)+"/4 ER:"+str.tostring(ER, "#.##")+" دخول "+str.tostring(close), alert.freq_once_per_bar)

plot(ER, "ER", color=color.yellow)
hline(0.35, "يشخبط", color=color.red)
hline(0.45, "ترند", color=color.green)
