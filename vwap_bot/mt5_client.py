"""MetaTrader 5 connection helper with Weltrade symbol auto-resolution.

Weltrade (like most MT5 brokers) adds a suffix to raw symbol names, e.g.
``XAUUSD`` -> ``XAUUSDm``. This module tries common suffix variants and
falls back to a wildcard search so the user can configure clean base names
(``XAUUSD``, ``XAGUSD``) in config.yaml.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

try:  # MetaTrader5 only exists on Windows with the MT5 terminal installed.
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:  # pragma: no cover - expected on Linux/Mac dev machines
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

log = logging.getLogger(__name__)

TIMEFRAME_MAP = {}  # filled lazily once mt5 is imported


def _timeframes():
    if not MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 package not installed (Windows + MT5 terminal required).")
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }


# Suffixes seen across Weltrade / MT5 brokers. Order matters (most likely first).
SUFFIX_CANDIDATES = ["", "m", ".m", "_m", "-m", "i", ".i", "pro", ".pro", "s", ".s", "ecn", ".ecn"]


class MT5Client:
    """Thin wrapper around the MetaTrader5 terminal connection."""

    def __init__(self, path: str = "", login: int = 0, password: str = "",
                 server: str = "", timeout_ms: int = 60000) -> None:
        if not MT5_AVAILABLE:
            raise RuntimeError(
                "MetaTrader5 module not available. Install the Weltrade MT5 terminal on "
                "Windows and `pip install MetaTrader5`, then re-run."
            )
        self.path = path
        self.login = int(login or 0)
        self.password = password or ""
        self.server = server or ""
        self.timeout_ms = timeout_ms
        self._resolved: Dict[str, str] = {}

    # ── connection ──────────────────────────────────────────
    def connect(self) -> bool:
        kwargs = {"timeout": self.timeout_ms}
        if self.path:
            kwargs["path"] = self.path
        if not mt5.initialize(**kwargs):
            log.error("mt5.initialize() failed: %s", mt5.last_error())
            return False
        if self.login and self.server:
            ok = mt5.login(self.login, password=self.password, server=self.server)
            if not ok:
                log.error("mt5.login() failed for %s on %s: %s",
                          self.login, self.server, mt5.last_error())
                return False
        acc = mt5.account_info()
        term = mt5.terminal_info()
        log.info("Connected: account=%s server=%s balance=%.2f %s | terminal=%s",
                 getattr(acc, "login", "?"), getattr(acc, "server", "?"),
                 getattr(acc, "balance", 0.0), getattr(acc, "currency", ""),
                 getattr(term, "company", "MT5"))
        return True

    def shutdown(self) -> None:
        if MT5_AVAILABLE:
            mt5.shutdown()

    # ── symbols ─────────────────────────────────────────────
    def resolve_symbol(self, base: str) -> Optional[str]:
        """Map a base name (XAUUSD) to the real broker symbol (XAUUSDm)."""
        base = base.strip()
        if base in self._resolved:
            return self._resolved[base]
        for suffix in SUFFIX_CANDIDATES:
            cand = base + suffix
            info = mt5.symbol_info(cand)
            if info is not None:
                self._resolved[base] = cand
                if not info.visible:
                    mt5.symbol_select(cand, True)
                log.info("Symbol %s resolved to %s (digits=%d, spread=%s)",
                         base, cand, info.digits, info.spread)
                return cand
        # Fallback: wildcard search (covers exotic Weltrade synthetic names)
        try:
            matches = mt5.symbol_get(group=f"*{base}*")
        except Exception:
            matches = []
        if matches:
            cand = matches[0].name
            self._resolved[base] = cand
            mt5.symbol_select(cand, True)
            log.info("Symbol %s resolved via search to %s", base, cand)
            return cand
        log.error("Could not resolve symbol %s — is it enabled in Market Watch?", base)
        return None

    def find_symbols(self, needle: str) -> List[str]:
        try:
            found = mt5.symbol_get(group=f"*{needle}*") or []
        except Exception:
            found = []
        return sorted(s.name for s in found)

    # ── market data ─────────────────────────────────────────
    def get_rates(self, symbol: str, timeframe: str, bars: int = 400) -> pd.DataFrame:
        tf = _timeframes().get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Unsupported timeframe '{timeframe}'. Use M1/M5/M15/M30/H1/H4/D1.")
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No rates for {symbol} {timeframe}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df[["time", "open", "high", "low", "close", "tick_volume",
                   "real_volume", "spread"]]

    def server_time(self, symbol: str) -> datetime:
        tick = mt5.symbol_info_tick(symbol)
        if tick is not None and tick.time:
            return datetime.fromtimestamp(tick.time)
        # Fallback: time of the latest M1 bar.
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
        if rates is not None and len(rates):
            return datetime.fromtimestamp(int(rates[0]["time"]))
        return datetime.now()
