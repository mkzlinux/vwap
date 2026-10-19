"""H1 bias + M15 Silver Bullet entry strategy (VWAP + 9EMA + ICT)."""
from __future__ import annotations

from datetime import datetime, time as dtime
from typing import Dict, List, Optional

from .ict import last_structure_break, silver_bullet_scan


def parse_killzones(raw: List[Dict]) -> List[Dict]:
    out = []
    for kz in raw or []:
        s_h, s_m = map(int, str(kz["start"]).split(":"))
        e_h, e_m = map(int, str(kz["end"]).split(":"))
        out.append({"name": kz.get("name", "killzone"),
                    "start": dtime(s_h, s_m), "end": dtime(e_h, e_m)})
    return out


def in_killzone(now: datetime, killzones: List[Dict]) -> Optional[str]:
    t = now.time().replace(second=0, microsecond=0)
    for kz in killzones:
        if kz["start"] <= t <= kz["end"]:
            return kz["name"]
    return None


def compute_bias(df_h1, swing_left: int = 5, swing_right: int = 5) -> Dict:
    """HTF directional bias from VWAP + 9EMA + last structure break."""
    last = df_h1.iloc[-1]
    close, vwap, ema9 = float(last["close"]), float(last["vwap"]), float(last["ema9"])
    above_vwap = close > vwap
    above_ema = close > ema9
    struct = last_structure_break(df_h1, swing_left, swing_right)
    struct_dir = struct["direction"] if struct else None

    votes_bull = sum([above_vwap, above_ema, struct_dir == "bullish"])
    votes_bear = sum([not above_vwap, not above_ema, struct_dir == "bearish"])
    if votes_bull >= 2:
        bias = "bullish"
    elif votes_bear >= 2:
        bias = "bearish"
    else:
        bias = "neutral"
    return {"bias": bias, "close": close, "vwap": vwap, "ema9": ema9,
            "above_vwap": above_vwap, "above_ema": above_ema,
            "structure": struct_dir,
            "structure_bar_time": struct["bar_time"] if struct else None,
            "bar_time": last["time"]}


def _side_ok(direction: str, line_value: float, close: float, mode: str,
             crossed_on_leg: bool) -> bool:
    """VWAP/EMA filter: strict = close must be on the right side;
    soft = also accept a reclaim/cross during the MSS displacement leg."""
    right_side = (close > line_value) if direction == "bullish" else (close < line_value)
    if mode == "off":
        return True
    if right_side:
        return True
    return bool(crossed_on_leg) if mode == "soft" else False


def evaluate_symbol(symbol: str, broker_symbol: str, df_h1, df_m15,
                    server_now: datetime, cfg: Dict) -> Optional[Dict]:
    """Return a signal dict if the M15 setup passes all confluence gates."""
    st = cfg["strategy"]

    bias = compute_bias(df_h1, st.get("swing_left", 5), st.get("swing_right", 5))

    setup = silver_bullet_scan(
        df_m15,
        swing_left=st.get("swing_left", 5),
        swing_right=st.get("swing_right", 5),
        sweep_lookback=st.get("sweep_lookback", 30),
        mss_lookback_after_sweep=st.get("mss_lookback_after_sweep", 5),
        fvg_lookback=st.get("fvg_lookback", 5),
        fvg_min_size_atr=st.get("fvg_min_size_atr", 0.10),
        displacement_atr_mult=st.get("displacement_atr_mult", 0.8),
    )
    if setup is None:
        return None
    direction = setup["direction"]

    # HTF alignment
    htf_ok = (bias["bias"] == direction)
    if st.get("require_htf_alignment", True) and not htf_ok:
        return None

    # VWAP / EMA9 trend filters on the entry timeframe.
    m15_last = df_m15.iloc[-1]
    close, vwap, ema9 = float(m15_last["close"]), float(m15_last["vwap"]), float(m15_last["ema9"])
    leg = df_m15.iloc[setup["mss_bar_pos"]: setup["fvg_bar_pos"] + 1]
    if direction == "bullish":
        crossed_vwap = bool((leg["close"] > leg["vwap"]).any())
        crossed_ema = bool((leg["close"] > leg["ema9"]).any())
    else:
        crossed_vwap = bool((leg["close"] < leg["vwap"]).any())
        crossed_ema = bool((leg["close"] < leg["ema9"]).any())
    vwap_ok = _side_ok(direction, vwap, close, st.get("vwap_filter_mode", "soft"), crossed_vwap) \
        if st.get("use_vwap_filter", True) else True
    ema_ok = _side_ok(direction, ema9, close, st.get("ema_filter_mode", "soft"), crossed_ema) \
        if st.get("use_ema9_filter", True) else True

    # Killzone gate
    killzones = parse_killzones(st.get("killzones", []))
    kz_name = in_killzone(server_now, killzones)
    kz_ok = (kz_name is not None)
    if st.get("use_killzone", True) and not kz_ok:
        return None

    # Confluence score (7 max): sweep, mss, fvg, vwap, ema9, htf, killzone.
    parts = {"sweep": True, "mss": True, "fvg": True, "vwap": vwap_ok,
             "ema9": ema_ok, "htf": htf_ok, "killzone": kz_ok}
    if not vwap_ok or not ema_ok:
        return None  # hard gate: trend filters must pass (soft mode already lenient)
    score = sum(1 for v in parts.values() if v)
    if score < int(st.get("min_confluence", 5)):
        return None

    # ── Suggested levels for manual placement ──
    atr = setup["atr_last"]
    buffer = float(st.get("sl_buffer_atr", 0.25)) * atr
    entry = setup["fvg_mid"]
    if direction == "bullish":
        sl = setup["sweep_extreme"] - buffer
        risk = entry - sl
    else:
        sl = setup["sweep_extreme"] + buffer
        risk = sl - entry
    if risk <= 0:
        return None
    tp1 = entry + float(st.get("tp1_r", 2.0)) * risk if direction == "bullish" \
        else entry - float(st.get("tp1_r", 2.0)) * risk
    tp2 = entry + float(st.get("tp2_r", 3.0)) * risk if direction == "bullish" \
        else entry - float(st.get("tp2_r", 3.0)) * risk

    reasons = [
        f"H1 bias {bias['bias']} (close {bias['close']:.2f} vs VWAP {bias['vwap']:.2f} / EMA9 {bias['ema9']:.2f})",
        f"Liquidity sweep of {setup['swept_level']:.2f} @ {setup['sweep_bar_time']}"
        + (" (equal highs/lows pool)" if setup["swept_eql"] else ""),
        f"MSS through {setup['broken_level']:.2f} @ {setup['mss_bar_time']}",
        f"{'Bullish' if direction == 'bullish' else 'Bearish'} FVG "
        f"{setup['fvg_bottom']:.2f}–{setup['fvg_top']:.2f} @ {setup['fvg_bar_time']}",
        f"Killzone: {kz_name}",
    ]
    return {
        "symbol": symbol, "broker_symbol": broker_symbol,
        "direction": direction, "bias_htf": bias["bias"],
        "entry": round(entry, 5), "sl": round(sl, 5),
        "tp1": round(tp1, 5), "tp2": round(tp2, 5),
        "risk_distance": round(risk, 5),
        "fvg_top": setup["fvg_top"], "fvg_bottom": setup["fvg_bottom"],
        "swept_level": setup["swept_level"], "sweep_extreme": setup["sweep_extreme"],
        "broken_level": setup["broken_level"],
        "ob_top": setup["ob_top"], "ob_bottom": setup["ob_bottom"],
        "vwap_m15": vwap, "ema9_m15": ema9, "atr_m15": atr,
        "vwap_h1": bias["vwap"], "ema9_h1": bias["ema9"],
        "killzone": kz_name, "confluence": f"{score}/7",
        "confluence_parts": parts,
        "price_in_zone": setup["price_in_zone"],
        "sweep_bar_time": str(setup["sweep_bar_time"]),
        "mss_bar_time": str(setup["mss_bar_time"]),
        "fvg_bar_time": str(setup["fvg_bar_time"]),
        "setup_bar_time": str(df_m15.iloc[-1]["time"]),
        "reasons": reasons,
    }
