# MT5 bridge

The dashboard needs prices. The only source that actually has them is the
Weltrade MT5 terminal, and the `MetaTrader5` Python package on PyPI ships
**`win_amd64` wheels only** — there is no Linux or macOS build. So this bridge
runs on the Windows machine that has the terminal installed, and publishes
prices over a WebSocket that the dashboard consumes.

```
 Windows box                              anywhere
+--------------------------+          +------------------------+
| MT5 terminal (Weltrade)  |          |  browser dashboard     |
|   ^                      |  JSON    |  web/ (Vite + React)   |
|   | MetaTrader5 wheel    | -------> |  Mt5BridgeFeed         |
| mt5_bridge.py  :8765     | WebSocket|                        |
+--------------------------+          +------------------------+
```

## Status — read this first

**This bridge has not been executed.** It cannot be, in the environment this
repository is developed in: no Windows host, and no `MetaTrader5` wheel
installable on Linux. The pure logic (bar conversion, history tailing, the tick
fallback, symbol validation, the wire protocol) is covered by
`tools/test_mt5_bridge.py`, which injects a mock `MetaTrader5` and drives the
shipped functions. The parts that genuinely need a terminal — `initialize()`,
`copy_rates_from_pos()` returning real records, socket behaviour — are
**unverified**. Expect to debug the first run.

## Setup

On the Windows machine, with the terminal installed and logged in:

```
py -m pip install MetaTrader5 websockets
py mt5_bridge.py --symbols EURUSD,GBPUSD,USDJPY,GER30,US30,SPX500,XAUUSD
```

Then in the dashboard: **Source → MT5 bridge**, and set the URL to
`ws://<windows-host-ip>:8765`.

`--host` defaults to `0.0.0.0` so the dashboard can reach it from another
machine. If the dashboard runs on the same box, `ws://127.0.0.1:8765` works.

## Options

| flag | default | meaning |
| --- | --- | --- |
| `--symbols` | majors + indices + metals | comma-separated MT5 symbol names |
| `--timeframe` | `M1` | `M1 M5 M15 M30 H1 H4 D1` |
| `--history` | `400` | closed bars sent per symbol on connect |
| `--poll-ms` | `500` | poll interval |
| `--host` | `0.0.0.0` | bind address |
| `--port` | `8765` | listen port |
| `--terminal` | – | path to `terminal64.exe` if it is not auto-detected |
| `--login` / `--password` / `--server` | – | only if you do not want to use the terminal's existing session |

## Symbol names are the usual stumbling block

Weltrade's exact MT5 symbol strings are not documented consistently. The bridge
validates every symbol against `symbol_info()` at startup, calls
`symbol_select()` on ones that exist but are hidden, and **prints a warning
naming the ones it cannot find** instead of publishing a dead row. If GER30 does
not appear, open Market Watch in the terminal and copy the exact string — it may
be prefixed or suffixed by the broker.

## Protocol

One JSON object per WebSocket message. `web/src/feed.js` (`Mt5BridgeFeed`) is
the client; `tools/test_mt5_bridge.py` asserts the two agree.

```jsonc
{ "type": "ready",   "instruments": ["EURUSD", "GER30"] }
{ "type": "history", "symbol": "EURUSD", "bars": [ { "time": 1791382500, "open": 1.085, "high": 1.0855, "low": 1.0845, "close": 1.0852, "volume": 137 } ] }
{ "type": "bar",     "symbol": "EURUSD", "bar": { /* as above */ }, "closed": false }
{ "type": "error",   "message": "GER30: ..." }
```

- `time` is UNIX seconds.
- Bar times per symbol must be **strictly ascending and never repeat** — the
  chart rejects a series that violates this.
- `closed: true` means the bar just finished and a new one opened; the bridge
  also re-sends `history` at that moment so the chart keeps its depth.
- `volume` is `tick_volume`, because `real_volume` is usually `0` on CFD feeds.

## Why not just run the dashboard in the terminal?

The MT5 indicator in `MQL5/Indicators/` already does single-chart signals with
no extra software. This bridge exists for the things an indicator cannot do:
one screen showing many symbols at once, and alerts that reach the browser.
