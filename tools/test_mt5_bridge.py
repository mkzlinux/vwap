"""
Executes the shipped web/bridge/mt5_bridge.py against a mock MetaTrader5 module.

The bridge cannot run for real here: the MetaTrader5 package on PyPI ships
win_amd64 wheels only, so there is no way to import it on Linux and no terminal
to connect to. What this test does instead is inject a fake `MetaTrader5` into
sys.modules *before* importing the bridge, then drive the bridge's own
functions. The logic under test is the shipped code, not a reimplementation.

Requires the `websockets` package (the bridge imports it at module scope).

    python3 tools/test_mt5_bridge.py
"""

import importlib
import re
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRIDGE_DIR = REPO / "web" / "bridge"

PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got!r}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print(f"       expected {want!r}")


def check_true(label, cond):
    check(label, bool(cond), True)


# --- fake MT5 ---------------------------------------------------------------

class Rate:
    """Stands in for the structured numpy record MT5 returns."""

    def __init__(self, t, o, h, l, c, v):
        self.time = t
        self.open = o
        self.high = h
        self.low = l
        self.close = c
        self.tick_volume = v


class Tick:
    def __init__(self, t, bid, ask, last):
        self.time = t
        self.bid = bid
        self.ask = ask
        self.last = last


class SymInfo:
    def __init__(self, visible=True):
        self.visible = visible


RATES = {}   # symbol -> list[Rate]
TICKS = {}   # symbol -> Tick
SYMBOLS = {}  # symbol -> SymInfo | None


def make_fake_mt5():
    m = types.ModuleType("MetaTrader5")
    m.TIMEFRAME_M1 = 1
    m.TIMEFRAME_M5 = 5
    m.TIMEFRAME_M15 = 15
    m.TIMEFRAME_M30 = 30
    m.TIMEFRAME_H1 = 60
    m.TIMEFRAME_H4 = 240
    m.TIMEFRAME_D1 = 1440

    def copy_rates_from_pos(symbol, timeframe, start, count):
        bars = RATES.get(symbol)
        if bars is None:
            return None
        # MT5 returns oldest..newest for the requested tail
        tail = bars[len(bars) - count:] if count else bars
        return list(tail)

    def symbol_info_tick(symbol):
        return TICKS.get(symbol)

    def symbol_info(symbol):
        return SYMBOLS.get(symbol)

    def symbol_select(symbol, visible):
        if symbol in SYMBOLS:
            SYMBOLS[symbol].visible = visible
        return True

    m.copy_rates_from_pos = copy_rates_from_pos
    m.symbol_info_tick = symbol_info_tick
    m.symbol_info = symbol_info
    m.symbol_select = symbol_select
    m.initialize = lambda **kw: True
    m.shutdown = lambda: None
    m.last_error = lambda: (0, "ok")
    return m


sys.modules["MetaTrader5"] = make_fake_mt5()
sys.path.insert(0, str(BRIDGE_DIR))
bridge = importlib.import_module("mt5_bridge")


# --- 1. bar conversion ------------------------------------------------------
print("--- 1. bar_from_rate flattens an MT5 record to the wire format ---")
r = Rate(1791382540, 1.0850, 1.0855, 1.0845, 1.0852, 137)
b = bridge.bar_from_rate(r)
check("keys are exactly the wire format", sorted(b), ["close", "high", "low", "open", "time", "volume"])
check("time is an int", (b["time"], type(b["time"]).__name__), (1791382540, "int"))
check("open/high/low/close are floats",
      [type(b[k]).__name__ for k in ("open", "high", "low", "close")], ["float"] * 4)
check("volume carried through", b["volume"], 137)
check("values preserved", [b["open"], b["high"], b["low"], b["close"]],
      [1.0850, 1.0855, 1.0845, 1.0852])

# a zero/None tick_volume must not become None on the wire
b0 = bridge.bar_from_rate(Rate(1, 1, 1, 1, 1, None))
check("None tick_volume becomes 0", b0["volume"], 0)


# --- 2. history fetch -------------------------------------------------------
print("\n--- 2. fetch_history ---")
RATES["EURUSD"] = [Rate(1791382500 + i * 60, 1.08, 1.09, 1.07, 1.08, 10 + i) for i in range(10)]
hist = bridge.fetch_history("EURUSD", 60, 4)
check("returns the requested tail length", len(hist), 4)
check("tail is the NEWEST bars, not the oldest",
      [h["time"] for h in hist], [1791382500 + i * 60 for i in range(6, 10)])
times = [h["time"] for h in hist]
check_true("times strictly ascending (chart requirement)",
           all(times[i] > times[i - 1] for i in range(1, len(times))))

check("unknown symbol returns empty, not None", bridge.fetch_history("NOPE", 60, 4), [])

RATES["EMPTY"] = []
check("empty series returns empty", bridge.fetch_history("EMPTY", 60, 4), [])

full = bridge.fetch_history("EURUSD", 60, 9999)
check("asking for more bars than exist returns all", len(full), 10)


# --- 3. forming bar ---------------------------------------------------------
print("\n--- 3. fetch_current, including the tick fallback ---")
cur = bridge.fetch_current("EURUSD", 60)
check("uses the newest bar", cur["time"], 1791382500 + 9 * 60)
check("close from that bar", cur["close"], 1.08)

# no bars for the period yet -> synthesise from the tick
TICKS["GER30"] = Tick(1791382547, 18250.5, 18251.0, 18250.7)
syn = bridge.fetch_current("GER30", 60)
check("tick fallback fires when there is no bar", syn is not None, True)
check("synthesised time snapped to the minute", syn["time"], 1791382547 - (1791382547 % 60))
check("OHLC all set from the tick price", [syn["open"], syn["high"], syn["low"], syn["close"]],
      [18250.5] * 4)
check("synthesised bar has zero volume", syn["volume"], 0)

# tick with no bid falls back to last, then ask
TICKS["UK100"] = Tick(1791382547, None, 7950.0, 7949.5)
check("falls back to last when bid is missing",
      bridge.fetch_current("UK100", 60)["close"], 7949.5)
TICKS["UK100"] = Tick(1791382547, None, 7950.0, None)
check("falls back to ask when bid and last are missing",
      bridge.fetch_current("UK100", 60)["close"], 7950.0)

# neither bars nor tick
check("returns None when there is no bar and no tick", bridge.fetch_current("GHOST", 60), None)


# --- 4. timeframe map -------------------------------------------------------
print("\n--- 4. timeframe names the dashboard can request ---")
check("TIMEFRAMES covers M1..D1", sorted(bridge.TIMEFRAMES),
      ["D1", "H1", "H4", "M1", "M15", "M30", "M5"])
check_true("every timeframe maps to a real MT5 constant",
           all(isinstance(v, int) for v in bridge.TIMEFRAMES.values()))


# --- 5. defaults ------------------------------------------------------------
print("\n--- 5. the symbol list the dashboard advertises ---")
check("default symbols include the majors and indices",
      [s for s in bridge.DEFAULT_SYMBOLS if s in ("EURUSD", "GER30", "XAUUSD", "SPX500")],
      ["EURUSD", "GER30", "SPX500", "XAUUSD"])
check_true("no duplicate default symbols",
           len(bridge.DEFAULT_SYMBOLS) == len(set(bridge.DEFAULT_SYMBOLS)))


# --- 6. the wire protocol matches feed.js -----------------------------------
print("\n--- 6. protocol keys match web/src/feed.js Mt5BridgeFeed ---")
feed_src = (REPO / "web" / "src" / "feed.js").read_text(encoding="utf-8")
for key in ('"ready"', '"history"', '"bar"', '"error"', '"closed"', '"symbol"', '"bars"'):
    check_true(f"feed.js documents {key}", key in feed_src)

# bar keys the JS side reads off the wire
for k in ("time", "open", "high", "low", "close", "volume"):
    check_true(f"bar field {k!r} is consumed by feed.js", k in feed_src)

# --- 7. the bridge publishes what the pad advertises -------------------------
print("\n--- 7. bridge symbols stay aligned with web/src/feed.js ---")
feed_src_full = (REPO / "web" / "src" / "feed.js").read_text(encoding="utf-8")
pad_block = feed_src_full.split("INSTRUMENTS = [", 1)[1].split("\n];", 1)[0]
pad_symbols = re.findall(r"symbol:\s*'([A-Z0-9]+)'", pad_block)

check_true("pad advertises instruments", len(pad_symbols) > 0)
check("no duplicate pad symbols",
      len(pad_symbols), len(set(pad_symbols)))
check("every pad symbol is published by the bridge by default",
      sorted(set(pad_symbols) - set(bridge.DEFAULT_SYMBOLS)), [])
check("every default bridge symbol has a pad row",
      sorted(set(bridge.DEFAULT_SYMBOLS) - set(pad_symbols)), [])


print()
print(f"{PASS} assertion(s) passed, {FAIL} failed")
print("ALL TESTS PASSED" if not FAIL else "FAILURES PRESENT")
sys.exit(1 if FAIL else 0)
