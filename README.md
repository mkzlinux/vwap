# Weltrade VWAP + 9 EMA signals (MT5)

Session-anchored VWAP on typical price `(O+H+L+C)/4`, no deviation bands, crossed
with a 9 EMA. **Signals only** — the code is an indicator and contains no
order-send API at all, so it cannot open, modify or close a trade. Each signal
paints a TradingView-style risk box: a red zone from entry to the stop, a green
zone from entry to the target, defaulting to **1:3**.

Built for Weltrade synthetics (SyntX), currencies and spot metals.

## Files

| Path | What it is |
| --- | --- |
| `MQL5/Indicators/WeltradeVWAP_9EMA_Signals.mq5` | The main indicator: VWAP, 9 EMA, signals, boxes, alerts |
| `MQL5/Indicators/WeltradeVWAP.mq5` | VWAP line on its own, for overlaying other work |
| `MQL5/Include/WeltradeVWAP/VwapCore.mqh` | Shared VWAP maths (typical price, session anchor, accumulation) |
| `Sets/*.set` | One preset per entry mode |
| `tools/mql5_check.py` | Static checker for the MQL5 sources |
| `tools/test_vwap_core.py` | Executes the real `VwapCore.mqh` logic and asserts the VWAP values |

## Install

1. In MT5 open **File → Open Data Folder**.
2. Copy `MQL5/Indicators/*.mq5` into `MQL5/Indicators/`.
3. Copy `MQL5/Include/WeltradeVWAP/` into `MQL5/Include/` so that
   `MQL5/Include/WeltradeVWAP/VwapCore.mqh` exists. Both indicators include it as
   `<WeltradeVWAP/VwapCore.mqh>`, so the folder name matters.
4. In MetaEditor press **F7** on each file, or use **Navigator → right-click →
   Refresh** after a **Compile all**.
5. Drag `WeltradeVWAP_9EMA_Signals` onto a chart. Tick **Allow live trading**
   nowhere — it is not needed and the indicator will not trade regardless.

Presets: open the indicator's **Inputs** tab, click **Load**, and pick a file
from `Sets/`.

## The three entry modes

`InpEntryMode` selects one at a time so you can compare them on the same chart.

| Value | Name | Long fires when |
| --- | --- | --- |
| 0 | EMA cross VWAP | 9 EMA crosses above VWAP (short: crosses below) |
| 1 | Price+EMA+VWAP stack | first bar where price > VWAP **and** price > EMA **and** EMA > VWAP |
| 2 | VWAP pullback | EMA above VWAP, low comes within `InpTouchTolerancePoints` of VWAP, bar closes back above it |

Every signal is evaluated on **closed bars only** (shift 1 vs shift 2), so a
signal never repaints as the current bar moves.

## How the box is sized

```
stop distance = ATR(InpAtrPeriod) * InpSlAtrMult      (default ATR(14) * 1.5)
target        = entry + stop distance * InpRewardR    (default 3 -> 1:3)
```

Entry is the **close of the signal bar**. The ATR is a simple average of True
Range over `InpAtrPeriod`, computed inline so the indicator needs no external
handles.

The box is drawn from the signal bar forward `InpBoxWidthBars` bars, with an
entry rail, dashed SL/TP rails, a dotted rail at each whole R, and labels
reading `LONG 1:3 (1234 pts risk)`.

Nothing about the box needs setting by hand: the stop distance comes from ATR
and the green zone is always sized to reach the target, so changing
`InpSlAtrMult` or `InpRewardR` rescales both zones together.

Boxes are created newest-first and capped by `InpMaxSignals` (default 40)
searching back at most `InpHistoryBars` bars (default 500). Arrows are drawn for
every signal in the recalculated range, but a box is only ever created for the
newest signals — drawing one for the whole chart history on first load would
create tens of thousands of chart objects before they could be trimmed, which is
enough to stall the terminal. Raise both together if you want more history.

## Marking when the stop or target is hit

With `InpMarkOutcome` on (default), each box is watched forward and marked once
price resolves it:

- an arrow and a `TP +3.0R` / `SL -1.0R` label appear on the bar that hit the
  level, in the profit or loss colour
- with `InpTruncateOnHit` on (default) the box ends on that bar instead of
  running its full width, so the chart reads as a series of closed trades

Rules the marking follows:

- only **closed** bars count, so an outcome never flickers or repaints
- the scan starts on the bar *after* the signal, because entry is the signal
  bar's close — the signal bar is allowed to overshoot both levels without
  counting as a hit
- **touching** a level counts as hitting it. A long stop at 1.08000 is treated
  as filled when the low reaches exactly 1.08000. This is the conservative
  convention for a stop and the optimistic one for a target; flip it if you
  want the opposite
- if one bar spans both levels, the intra-bar order is unknowable from bar data.
  `InpAmbiguousFirst` picks the assumption: `0` stop first (conservative,
  default), `1` target first

The panel then shows a running tally over the boxes on the chart:

```
Last 40 signals:  11 TP / 22 SL / 7 open
Hit rate 33.3%     Expectancy -0.07R
```

Expectancy is `(wins x InpRewardR - losses) / resolved`, in R. At 1:3 you need a
hit rate above 25% to be positive, so this tells you quickly whether the mode
and timeframe suit the instrument. The tally covers only the signals currently
boxed, so it changes as `InpMaxSignals` and `InpHistoryBars` change — it is a
read on recent form, not a full backtest. Use the Strategy Tester for that.

## VWAP anchor

`InpAnchor` decides when the running totals reset:

| Value | Anchor |
| --- | --- |
| 0 | Daily at `InpSessionHour`:`InpSessionMinute` (server time) |
| 1 | Daily at 00:00 server time |
| 2 | Weekly, from Monday at the session hour |
| 3 | Rolling over `InpRollingBars` bars |

Weltrade synthetics run 24/7 with no session close, so the default daily anchor
at `00:00` server time gives one VWAP per calendar day. Check your terminal's
server time (it is shown in Market Watch) before setting a custom hour. For
currencies and spot, if you want the VWAP to line up with a specific market open,
set `InpSessionHour` to that hour in server time.

VWAP is `Σ(typical price × volume) / Σ(volume)` where typical price is
`(O+H+L+C)/4`. Tick volume is used by default; set `InpUseRealVolume=true` only
if your feed actually publishes real volume — the indicator falls back to tick
volume automatically when the real-volume column is all zeros.

## Notes for Weltrade instruments

- **Synthetics (SyntX)** trade 24/7, so there is no weekend gap and the daily
  anchor never has to bridge a closure. Spread is normally tight and stable,
  which suits an ATR-sized stop.
- **Currencies** have a session close. If a bar's volume is zero the indicator
  simply excludes it; if an entire window has no volume the line falls back to
  the typical price rather than breaking.
- **Spot metals** have large point values relative to price. Distances are shown
  in points in the box label, so compare `InpSlAtrMult` in ATR terms rather than
  trying to convert to pips.

One chart per symbol — an indicator can only draw on the chart it is attached
to. Attach it to each symbol you want signals on, and give each chart a
different timeframe if you want to compare.

## Verification

MetaEditor is Windows-only and does not run in this repository's build
environment, so **the indicators have not been compiled**. What has been run:

`python3 tools/mql5_check.py --stdlib=<MQL5 Include> --corpus=<MQL5 sources>`

- balanced delimiters in all three files
- `#property indicator_buffers` matches the `SetIndexBuffer` calls, and the
  plot count matches the buffers each plot consumes
- every call site resolves to a definition with a matching argument count
- every identifier resolves to a declaration
- all 81 MQL5 builtins used are confirmed present in a 3,162-file corpus of
  real MQL5 source
- every key in every `Sets/*.set` preset is a declared input of the indicator,
  no input is missing, and none is duplicated

That checker was mutation-tested: an unclosed brace, a wrong argument count, a
dropped `SetIndexBuffer`, a misspelled builtin, an undeclared variable and a
misspelled `VwapCore` symbol all fail it. The preset check was mutation-tested
separately — a renamed key, a deleted key, an empty value and a duplicate key
all fail it.

`python3 tools/test_vwap_core.py`

- translates `VwapCore.mqh` to C mechanically (array-reference parameters to
  pointers, scalar out-parameters to dereferenced pointers, `datetime` to
  `long`, `TimeToStruct` to a `gmtime` shim, `ArrayResize` to a no-op) and runs
  the **shipped** logic under gcc
- asserts the typical price, all four session anchors, daily accumulation, the
  custom-hour mid-series reset, weekly no-reset-inside-the-week, the rolling
  window, partial-range fills and the zero-volume fallback, each against an
  independently written textbook VWAP
- asserts the outcome scan: long and short TP/SL resolution, which level wins
  when both are touched on different bars, that a hit beyond `last_closed` does
  not count, that the signal bar's own range cannot resolve the trade, both
  assumptions for a bar spanning both levels, and the exact-touch boundary in
  all four directions
- 9 test groups, all passing

The outcome tests found a gap in themselves: the first version used only clear
level breaks, so changing `<=` to `<` went unnoticed. Four boundary assertions
were added and all four strict-comparison mutations now fail. Ten logic
mutations are caught in total — wrong typical price, rolling off-by-one, session
that never resets, flipped rollback sign, wrong Monday offset, removed
zero-volume fallback, scan starting on the signal bar, inverted ambiguity rule,
short target tested against the wrong extreme, and scan running one bar past
`last_closed`.

What this does **not** cover: compilation under MetaEditor, and the chart-object,
buffer and alert plumbing in the indicators. Those need one run in the terminal.
Three things to check first there: that the boxes appear at the right bars, that
the TP/SL arrows land on the bars you expect, and that `InpUseTransparency` is
left off — ARGB alpha on a chart object's `OBJPROP_COLOR` is documented MQL5
behaviour but appears nowhere in the reference corpus, so the default path uses
solid fill plus draw order instead.
