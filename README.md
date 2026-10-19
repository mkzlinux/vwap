# VWAP + 9EMA + ICT Silver Bullet — MT5 Signal Bot for Weltrade

Python signal bot for **MetaTrader 5 (Weltrade)**. It scans **Gold (XAUUSD)**,
**Silver (XAGUSD)** and any Weltrade synthetics you add, on **M15 entries with
H1 bias**, and prints trade ideas you place manually.

**Model:** ICT Silver Bullet — *liquidity sweep → market structure shift (MSS)
→ fair value gap (FVG) entry* — confirmed by **session VWAP** + **9 EMA** trend
filters and traded only inside **Silver Bullet killzones**.

> **Signal-only.** This bot never sends orders. You stay in full control and
> place every trade by hand in the MT5 terminal.

---

## 1. How the strategy works

```
H1 BIAS (must align with M15 direction)
  close > VWAP  +  close > 9EMA  +  last break bullish  →  bullish bias
  close < VWAP  +  close < 9EMA  +  last break bearish  →  bearish bias
  (2 of 3 votes needed, else neutral = no trade)

M15 ENTRY — ICT Silver Bullet
  1. SWEEP   wick takes out a swing high/low (or equal highs/lows pool)
             then closes back inside  →  liquidity raid + reclaim
  2. MSS     displacement candle closes through the last opposite swing
             (range ≥ 0.8× ATR)       →  market structure shift
  3. FVG     fresh 3-candle imbalance on the displacement leg
             Entry = FVG midpoint (limit)  |  SL = beyond sweep ± 0.25× ATR
             TP1 = 2R, TP2 = 3R

FILTERS
  • M15 close on the right side of VWAP + 9EMA (soft mode allows a reclaim
    during the MSS leg, strict mode in config)
  • Inside a Silver Bullet killzone (server time — see §5)
  • Confluence ≥ 5/7 (sweep, MSS, FVG, VWAP, EMA9, HTF, killzone)
```

A signal card looks like this:

```
🟢 BUY  XAUUSDm  (XAUUSD)
Model: VWAP + 9EMA + ICT Silver Bullet (sweep→MSS→FVG)
Bias H1: bullish   Confluence: 7/7
Killzone: NY AM Silver Bullet   Server: 2026-10-16 15:00 | 2026-10-16 15:00 CAT
Entry (FVG 50% limit): 2661.42
FVG zone: 2660.10 – 2662.74
SL (beyond sweep): 2657.90   Risk: 3.52
TP1 (2R): 2668.46   TP2 (3R): 2671.98
```

Signals are also appended to `signals.log`, `signals.json`, `signals.csv`
(and optionally Telegram).

## 2. What you need

| Requirement | Notes |
|---|---|
| Windows PC or Windows VPS | The `MetaTrader5` Python package only runs on Windows with the terminal installed |
| Weltrade MT5 terminal | Download from your Weltrade dashboard; log in to your account (demo first!) |
| Python 3.10+ 64-bit | From python.org — tick **“Add python to PATH”** during install |
| This repo | `git clone` it or download the ZIP |

> On Linux/Mac you can still run the smoke test (`tools/selftest.py`) and the
> demo backtest (`backtest.py --demo`) — live scanning needs Windows + MT5.

## 3. Install (5 minutes)

```powershell
# 1) In the Weltrade MT5 terminal: File → Login to Trade Account, then make
#    sure XAUUSD / XAGUSD are visible (right-click Market Watch → Show All).

# 2) In PowerShell, inside this folder:
pip install -r requirements.txt

# 3) Copy the credentials template and fill it in:
copy .env.example .env
notepad .env
```

`.env` contents:

```ini
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=WeltradeInternational-Server   # exact name from MT5 login window
```

Find the exact server name in MT5 under **File → Login to Trade Account**
(it looks like `WeltradeInternational-Server` / `Weltrade-Server` — copy it
exactly).

## 4. Run

```powershell
# Check which gold/silver/synthetic symbols your Weltrade account has:
python tools/check_symbols.py

# Single test scan (prints any live setup, or "no setup"):
python bot.py --once

# Live signal loop (scans every 30s — set poll_seconds in config.yaml):
python bot.py
```

Useful flags:

```powershell
python bot.py --symbols XAUUSD,XAGUSD   # override config symbols
python bot.py --no-killzone             # testing only: ignore killzones
python backtest.py --demo               # synthetic-data backtest (any OS)
python backtest.py --symbol XAUUSD      # real Weltrade history (Windows/MT5)
python tools/selftest.py                # strategy smoke test (any OS)
```

## 5. Killzones & time (important for Bulawayo/CAT)

ICT Silver Bullet windows are configured in **MT5 server time**
(`config.yaml → strategy.killzones`). Weltrade server time is ≈ GMT+2/+3,
which is usually the same as CAT (Bulawayo, UTC+2) ±1h during DST weeks.

| Killzone (config) | Server time | ≈ CAT |
|---|---|---|
| London Silver Bullet | 07:00–10:00 | 07:00–10:00 |
| NY AM Silver Bullet | 14:30–16:00 | 14:30–16:00 |
| NY PM Silver Bullet | 19:00–20:00 | 19:00–20:00 |

**Verify once:** compare the clock in MT5's Market Watch with your local time
and shift the killzones in `config.yaml` if they differ by an hour.

## 6. Adding Weltrade synthetics / more symbols

1. Run `python tools/check_symbols.py` (or `--needle SYNTH`) to see exact
   broker names.
2. Add the **base** name to `config.yaml`:

```yaml
symbols:
  - XAUUSD
  - XAGUSD
  - XAUEUR     # example extra metal
  - BTCUSD     # example synthetic/crypto CFD
```

The bot auto-resolves suffixes (`XAUUSD` → `XAUUSDm` / `XAUUSD.m` …), so you
never need to type the suffix yourself.

## 7. Tuning

All logic lives in `config.yaml` — no code changes needed:

| Setting | Effect |
|---|---|
| `require_htf_alignment` | `false` = allow counter-bias M15 setups (more, weaker signals) |
| `vwap_filter_mode` / `ema_filter_mode` | `strict` (close must hold the side), `soft` (reclaim ok), `off` |
| `min_confluence` | Lower to 4 for more signals, raise to 7 for only perfect setups |
| `use_killzone` | `false` = scan around the clock |
| `sl_buffer_atr`, `tp1_r`, `tp2_r` | Suggested SL/TP geometry |
| `vwap_mode: rolling` + `vwap_rolling_period` | Intraday rolling VWAP instead of daily-session VWAP |

## 8. Telegram alerts (optional)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Message your bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat id`.
3. Add to `.env`, set `telegram_enabled: true` in `config.yaml`:

```ini
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
TELEGRAM_CHAT_ID=123456789
```

## 9. Project layout

```
bot.py                 live signal loop (SIGNAL ONLY — no order_send anywhere)
backtest.py            offline backtest (MT5 history or --demo synthetic data)
config.yaml            all strategy / symbol / killzone settings
vwap_bot/
  mt5_client.py        MT5 connection + Weltrade symbol auto-resolution
  indicators.py        session/rolling VWAP, 9EMA, ATR
  ict.py               swings, liquidity sweep, MSS, FVG, order blocks
  strategy.py          H1 bias + M15 Silver Bullet + confluence gates
  signals.py           console / log / JSON / CSV / Telegram outputs
tools/
  check_symbols.py     list your Weltrade gold/silver/synthetic symbols
  selftest.py          no-MT5 smoke test with a scripted setup
```

## 10. Risk disclaimer

Trading XAUUSD/XAGUSD on leverage is high risk. This is an educational signal
tool, **not financial advice**: always test on a **Weltrade demo account**
first, risk only what you can afford to lose (common practice: ≤1% per idea),
and never leave signals unattended through major news (NFP, CPI, FOMC).
Backtest results — especially `--demo` synthetic data — do not predict live
performance.
