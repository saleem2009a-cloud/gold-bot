def check_signal():
    try:
        df=yf.download("GC=F",period="3d",interval="5m",progress=False,auto_adjust=True).dropna()
        if len(df)<50: return None
        price=get_price()
        asia_rng, asia_status = get_asia_range(df)
        poc,_,_,_,_=get_vp(df.tail(120))
        d,d5,sig=get_flow(df.tail(60),poc,price)
        eng_text, eng_ok = detect_engulfing(df.tail(20))
        h1_high, h1_low = get_h1_levels()
        quad_top, quad_bottom, _, _ = detect_quad_top_bottom(df.tail(30))
        patterns = detect_10_bottom_patterns(df.tail(40))
        last_bull, last_bear, in_bull, in_bear, active_fvg = detect_fvg(df)
        session, time_bonus, near_reversal = get_time_cycle()
        cycle_len, cycle_txt, near_cycle_bottom, near_cycle_top = get_technical_cycle(df)
        moon_txt, mercury_txt, astro_power, moon_phase = get_real_astro()
        dist_poc = abs(price-poc)
        reason=[]; score=0

        if eng_ok: score+=2
        else: reason.append("لا يوجد ابتلاع")

        if len(patterns)>=2: score+=2
        elif len(patterns)==1: score+=1

        if active_fvg: score+=2
        if in_bull or in_bear: score+=2 # هون زودنا نقطة

        if near_reversal: score+=1
        if near_cycle_bottom or near_cycle_top: score+=1
        if astro_power: score+=1
        if dist_poc>8: score+=1
        if abs(d5)>=2: score+=1

        # الشرط الجديد: حتى بدون ابتلاع
        if eng_ok:
            can_trade = score >= 4
        else:
            # اذا في FVG + 2 نمط + شراء مسيطر = بيعطيك توصية
            can_trade = (score >= 4 and active_fvg and len(patterns)>=1) or score >=5

        bonus=f"{time_bonus} | {cycle_txt}\n{moon_txt}\n{mercury_txt}"
        if last_bull: bonus+=f"\n🟢 FVG {last_bull[0]:.1f}-{last_bull[1]:.1f}"
        if last_bear: bonus+=f" 🔴 FVG {last_bear[0]:.1f}-{last_bear[1]:.1f}"
        if in_bull or in_bear: bonus+= " | 💥 داخل FVG ✅"

        return {"price":price,"poc":poc,"asia_rng":asia_rng,"asia_status":asia_status,"d":d,"d5":d5,"sig":sig,"eng_text":eng_text,"eng_ok":eng_ok,"can_trade":can_trade,"df":df.tail(60),"reason":reason,"h1_high":h1_high,"h1_low":h1_low,"quad_top":quad_top,"quad_bottom":quad_bottom,"patterns":patterns,"last_bull":last_bull,"last_bear":last_bear,"in_bull":in_bull,"in_bear":in_bear,"bonus":bonus,"score":score,"dist":dist_poc}
    except Exception as e:
        print(f"check err {e}"); return None
