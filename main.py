async def tawsiya(update, context):
    try:
        await update.message.reply_text("🔥 عم حلل... 3 ثواني")
        price=get_price()
        d5=get_candles("5m", 100)
        d60=get_candles("1h", 100)
        d240=get_candles("4h", 100)

        if len(d5)<50:
            await update.message.reply_text("❌ بينانس معلق - جرب بعد دقيقة /test")
            return

        c5=[float(x[4]) for x in d5]
        c60=[float(x[4]) for x in d60] if len(d60)>50 else c5
        c240=[float(x[4]) for x in d240] if len(d240)>50 else c5

        e9=ema(c5,9); e21=ema(c5,21); e50=ema(c5,50); e50_60=ema(c60,50); e200_60=ema(c60,200); e50_240=ema(c240,50)
        r5=rsi(c5); r60=rsi(c60); r240=rsi(c240)

        score=50; reasons=[]
        if c240[-1]>e50_240: score+=20; reasons.append("✅ 4H فوق 50")
        else: score-=20; reasons.append("🔴 4H تحت 50")
        if c60[-1]>e50_60 and c60[-1]>e200_60: score+=20; reasons.append("✅ 1H فوق 50+200 قوي")
        elif c60[-1]>e50_60: score+=8; reasons.append("⚠️ 1H فوق 50")
        else: score-=15; reasons.append("🔴 1H هابط")
        if c5[-1]>e9 and e9>e21 and c5[-1]>e50: score+=20; reasons.append("✅ 5M ترند صاعد كامل")
        elif c5[-1]>e9: score+=8; reasons.append("⚠️ 5M صاعد ضعيف")
        else: score-=10; reasons.append("🔴 5M هابط")

        if r5>75: score-=10; reasons.append(f"⚠️ تشبع شراء RSI {r5:.0f}")
        if r5<25: score+=10; reasons.append(f"⚠️ تشبع بيع RSI {r5:.0f}")

        # قرار
        if score>=70:
            txt=f"🟢💎 **شراء قوي جدا {score:.0f}/100**\n💵 {price:.2f} 🛑 {price-6:.2f} 🎯 {price+12:.2f}\n{chr(10).join(reasons)}\nRSI 5M {r5:.1f} 1H {r60:.1f} 4H {r240:.1f}"
        elif score>=58:
            txt=f"🟢 **شراء {score:.0f}/100**\n💵 {price:.2f} 🛑 {price-5:.2f} 🎯 {price+6:.2f}\n{chr(10).join(reasons)}"
        elif score<=30:
            txt=f"🔴💎 **بيع قوي جدا {score:.0f}/100**\n💵 {price:.2f} 🛑 {price+6:.2f} 🎯 {price-12:.2f}\n{chr(10).join(reasons)}\nRSI 5M {r5:.1f} 1H {r60:.1f} 4H {r240:.1f}"
        elif score<=42:
            txt=f"🔴 **بيع {score:.0f}/100**\n💵 {price:.2f} 🛑 {price+5:.2f} 🎯 {price-6:.2f}\n{chr(10).join(reasons)}"
        else:
            txt=f"⏸️ **حيادي {score:.0f}/100 لا تدخل**\nالسعر {price:.2f}\n{chr(10).join(reasons)}\nRSI {r5:.1f}/{r60:.1f}/{r240:.1f}\nانتظر 15د"

        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"❌ صار خطأ: {e}\nجرب /test")
