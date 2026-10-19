# Pine Script for MT5 bot

Same model as the Python bot (`bot.py` + `config.yaml`), ported to TradingView.

- **Indicator** (`VWAP_9EMA_ICT_Silver_Bullet_Indicator.pine`) — signal-only, no orders. Plots everything the Python bot prints, fires TradingView alerts. Put it on **M15 XAUUSD / XAGUSD** (any symbol).
- **Strategy** (`VWAP_9EMA_ICT_Silver_Bullet_Strategy.pine`) — same logic but calls `strategy.entry` so you can backtest on TradingView. Same signals, adds SL/TP.

Both use:
- Session (daily) VWAP + 9 EMA + 14 ATR
- ICT Silver Bullet: **liquidity sweep → market structure shift (MSS) → fair value gap (FVG)**
- H1 bias (2-of-3 vote: VWAP + EMA + structure break)
- Server-time killzones with timezone picker (CAT / UTC+2 for Bulawayo)
- 7-point confluence gate

## Install
1. Open TradingView → Pine Editor → New → paste the file.
2. Add to chart on **M15** (the script fetches H1 bias automatically via `request.security`).
3. Settings mirror `config.yaml` — tune killzones / strict|soft filters / minConfluence there.
4. Create Alert → Condition = indicator → "Bullish Silver Bullet" / "Bearish Silver Bullet".

## Weltrade note
TradingView symbols are `OANDA:XAUUSD`, `TVC:GOLD`, `CAPITALCOM:SILVER`, etc. The logic is symbol-agnostic — it works on any chart. For Weltrade live trading, place the trade manually in MT5 when the alert fires (signal-only).
