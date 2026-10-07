"""
MT5 -> WebSocket bridge for the signal pad.

WHY THIS EXISTS
---------------
The MetaTrader5 package on PyPI ships win_amd64 wheels only, so it cannot be
imported on Linux or macOS. The bridge therefore runs on the Windows machine
that has the Weltrade terminal installed, and publishes prices over the network
to the dashboard, which runs anywhere.

    pip install MetaTrader5 websockets

    python mt5_bridge.py --symbols EURUSD,GBPUSD,USDJPY,GER30,XAUUSD

Then point the dashboard at it: Source -> "MT5 bridge", URL ws://<host>:8765

STATUS
------
This script has NOT been executed. It cannot be: there is no Windows host and
no MetaTrader5 wheel in the build environment this repository is checked in
the standard MT5 patterns, but treat the first run as unverified.

PROTOCOL (must match web/src/feed.js Mt5BridgeFeed)
---------------------------------------------------
outbound, one JSON object per WebSocket message:
    {"type": "ready",   "instruments": ["EURUSD", ...]}
    {"type": "history", "symbol": "EURUSD", "bars": [bar, ...]}
    {"type": "bar",     "symbol": "EURUSD", "bar": bar, "closed": false}
    {"type": "error",   "message": "..."}

where bar = {"time": <unix seconds>, "open":, "high":, "low":, "close":,
             "volume": <int>}

The dashboard requires strictly ascending, non-duplicate bar times per symbol.
"""

import argparse
import asyncio
import json
import sys
import time

try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit(
        "MetaTrader5 is not installed. It only ships win_amd64 wheels, so run "
        "this on Windows next to the terminal:  pip install MetaTrader5"
    )

try:
    import websockets
except ImportError:
    sys.exit("websockets is not installed:  pip install websockets")


# Kept aligned with INSTRUMENTS in web/src/feed.js so the pad does not show
# rows the bridge never publishes. Weltrade symbol strings are not guaranteed
# to match these - the bridge validates each one at startup and warns.
DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD",
    "GER30", "US30", "SPX500", "UK100",
    "XAUUSD", "XAGUSD",
    "AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "GOOGL", "META",
]

# Map dashboard timeframes onto MT5 constants.
TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def bar_from_rate(rate):
    """An MT5 rate is a structured record; flatten it to the wire format."""
    return {
        "time": int(rate.time),
        "open": float(rate.open),
        "high": float(rate.high),
        "low": float(rate.low),
        "close": float(rate.close),
        # tick_volume is what Weltrade exposes; real_volume is usually 0 on CFDs
        "volume": int(rate.tick_volume or 0),
    }


def fetch_history(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return []
    return [bar_from_rate(r) for r in rates]


def fetch_current(symbol, timeframe):
    """The forming bar, rebuilt from the last tick if needed."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
    if rates is not None and len(rates) == 1:
        return bar_from_rate(rates[0])

    # No bar yet for this period - synthesise one from the tick so the chart
    # has something to draw while the first bar is still empty.
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    now = int(tick.time)
    price = float(tick.bid or tick.last or tick.ask)
    return {
        "time": now - (now % 60),
        "open": price, "high": price, "low": price, "close": price,
        "volume": 0,
    }


async def serve(symbols, timeframe, history_bars, poll_ms, host, port):
    clients = set()

    async def broadcast(payload):
        if not clients:
            return
        msg = json.dumps(payload)
        # a client that vanished mid-send must not stop the others
        for ws in list(clients):
            try:
                await ws.send(msg)
            except websockets.ConnectionClosed:
                clients.discard(ws)

    async def poller():
        # last bar time per symbol, so a bar is only announced once per change
        last_time = {}
        while True:
            for symbol in symbols:
                try:
                    bar = fetch_current(symbol, timeframe)
                except Exception as exc:  # keep the loop alive
                    await broadcast({"type": "error", "message": f"{symbol}: {exc}"})
                    continue

                if bar is None:
                    continue

                prev = last_time.get(symbol)
                closed = prev is not None and bar["time"] > prev
                last_time[symbol] = bar["time"]

                await broadcast({
                    "type": "bar",
                    "symbol": symbol,
                    "bar": bar,
                    "closed": closed,
                })

                if closed:
                    # a new bar opened: top up the tail so the chart has depth
                    hist = fetch_history(symbol, timeframe, history_bars)
                    if hist:
                        await broadcast({
                            "type": "history", "symbol": symbol, "bars": hist,
                        })

            await asyncio.sleep(poll_ms / 1000.0)

    async def handler(ws):
        clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "ready", "instruments": symbols}))
            # seed this client immediately rather than waiting for the next tick
            for symbol in symbols:
                hist = fetch_history(symbol, timeframe, history_bars)
                if hist:
                    await ws.send(json.dumps({
                        "type": "history", "symbol": symbol, "bars": hist,
                    }))
        except websockets.ConnectionClosed:
            pass
        finally:
            clients.discard(ws)

    async with websockets.serve(handler, host, port):
        print(f"bridge listening on ws://{host}:{port} "
              f"({len(symbols)} symbols, {timeframe} name)")
        await poller()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                    help="comma-separated MT5 symbol names")
    ap.add_argument("--timeframe", default="M1", choices=sorted(TIMEFRAMES),
                    help="bar period to publish (default M1)")
    ap.add_argument("--history", type=int, default=400,
                    help="closed bars to send per symbol (default 400)")
    ap.add_argument("--poll-ms", type=int, default=500,
                    help="poll interval in milliseconds (default 500)")
    ap.add_argument("--host", default="0.0.0.0",
                    help="bind address (default 0.0.0.0 so the dashboard can reach it)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--terminal", default=None,
                    help="optional path to terminal64.exe")
    ap.add_argument("--login", type=int, default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--server", default=None)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tf = TIMEFRAMES[args.timeframe]

    init_kwargs = {}
    if args.terminal:
        init_kwargs["path"] = args.terminal
    if args.login:
        init_kwargs.update(login=args.login, password=args.password or "",
                           server=args.server or "")

    if not mt5.initialize(**init_kwargs):
        sys.exit(f"mt5.initialize() failed: {mt5.last_error()}")

    # Weltrade symbol names vary; confirm each one resolves before publishing
    # nothing, otherwise the dashboard shows a dead row with no explanation.
    missing = []
    for s in symbols:
        info = mt5.symbol_info(s)
        if info is None:
            missing.append(s)
            continue
        if not info.visible:
            mt5.symbol_select(s, True)

    if missing:
        print("WARNING: these symbols do not exist on this terminal and will "
              "not be published:", ", ".join(missing), file=sys.stderr)
        print("         check the exact names in Market Watch (Weltrade may "
              "prefix them).", file=sys.stderr)
        symbols = [s for s in symbols if s not in missing]

    if not symbols:
        mt5.shutdown()
        sys.exit("no usable symbols left")

    try:
        asyncio.run(serve(symbols, tf, args.history, args.poll_ms,
                          args.host, args.port))
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
