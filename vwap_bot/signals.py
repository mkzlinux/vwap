"""Signal output: console, log/JSON/CSV files, optional Telegram."""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pytz
    CAT = pytz.timezone("Africa/Harare")
except Exception:  # pragma: no cover
    CAT = None

log = logging.getLogger(__name__)


def now_stamps(server_now: datetime) -> Dict[str, str]:
    utc_now = datetime.now(timezone.utc)
    stamps = {"server": server_now.strftime("%Y-%m-%d %H:%M"),
              "utc": utc_now.strftime("%Y-%m-%d %H:%M")}
    if CAT is not None:
        stamps["cat"] = utc_now.astimezone(CAT).strftime("%Y-%m-%d %H:%M CAT")
    else:
        stamps["cat"] = utc_now.strftime("%Y-%m-%d %H:%M UTC")
    return stamps


def format_signal(sig: Dict, stamps: Dict[str, str]) -> str:
    arrow = "🟢 BUY" if sig["direction"] == "bullish" else "🔴 SELL"
    lines = [
        "══════════════════════════════════════════",
        f"{arrow}  {sig['broker_symbol']}  ({sig['symbol']})",
        f"Model: VWAP + 9EMA + ICT Silver Bullet (sweep→MSS→FVG)",
        f"Bias H1: {sig['bias_htf']}   Confluence: {sig['confluence']}",
        f"Killzone: {sig['killzone']}   Server: {stamps['server']} | {stamps['cat']}",
        f"Entry (FVG 50% limit): {sig['entry']}",
        f"FVG zone: {sig['fvg_bottom']:.5f} – {sig['fvg_top']:.5f}",
        f"SL (beyond sweep): {sig['sl']}   Risk: {sig['risk_distance']}",
        f"TP1 (2R): {sig['tp1']}   TP2 (3R): {sig['tp2']}",
        f"Swept level: {sig['swept_level']:.5f} | MSS level: {sig['broken_level']:.5f}",
        "Why:",
    ]
    lines += [f"  • {r}" for r in sig["reasons"]]
    if not sig["price_in_zone"]:
        lines.append("  • NOTE: price not inside FVG yet — use a LIMIT order at the zone.")
    lines.append("Signal only — place/manage the trade manually in MT5.")
    lines.append("══════════════════════════════════════════")
    return "\n".join(lines)


class SignalSink:
    """De-duplicates signals (per symbol+direction+setup bar) and writes outputs."""

    def __init__(self, cfg: Dict) -> None:
        a = cfg.get("alerts", {})
        self.console = a.get("console", True)
        self.log_file = a.get("log_file", "signals.log")
        self.json_file = a.get("json_file", "signals.json")
        self.csv_file = a.get("csv_file", "signals.csv")
        self.cooldown_bars = int(cfg.get("strategy", {}).get("cooldown_bars", 3))
        self.telegram = bool(a.get("telegram_enabled", False))
        self._seen = {}  # (symbol, direction) -> setup_bar_time string
        self._history: List[Dict] = []

    def _key(self, sig: Dict):
        return (sig["broker_symbol"], sig["direction"])

    def should_emit(self, sig: Dict) -> bool:
        # Always emit a *new* setup bar; suppress repeats of the same setup.
        key = self._key(sig)
        if self._seen.get(key) == sig["setup_bar_time"]:
            return False
        return True

    def emit(self, sig: Dict, stamps: Dict[str, str]) -> Optional[str]:
        if not self.should_emit(sig):
            return None
        self._seen[self._key(sig)] = sig["setup_bar_time"]
        text = format_signal(sig, stamps)
        if self.console:
            print(text, flush=True)
        record = {**sig, "stamps": stamps}
        record.pop("reasons", None)
        record["reasons_text"] = " | ".join(sig["reasons"])
        self._append_log(text)
        self._append_json(record)
        self._append_csv(record)
        if self.telegram:
            self._send_telegram(text)
        return text

    # ── writers ─────────────────────────────────────────────
    def _append_log(self, text: str) -> None:
        if not self.log_file:
            return
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def _append_json(self, record: Dict) -> None:
        if not self.json_file:
            return
        path = Path(self.json_file)
        data = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = []
        data.append(record)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _append_csv(self, record: Dict) -> None:
        if not self.csv_file:
            return
        path = Path(self.csv_file)
        fieldnames = ["server_time", "cat_time", "symbol", "broker_symbol", "direction",
                      "bias_htf", "entry", "sl", "tp1", "tp2", "risk_distance",
                      "confluence", "killzone", "swept_level", "broken_level",
                      "fvg_bottom", "fvg_top", "setup_bar_time"]
        row = {"server_time": record["stamps"]["server"], "cat_time": record["stamps"]["cat"],
               **{k: record.get(k, "") for k in fieldnames if k not in ("server_time", "cat_time")}}
        write_header = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                w.writeheader()
            w.writerow(row)

    def _send_telegram(self, text: str) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            log.warning("Telegram enabled but TELEGRAM_BOT_TOKEN/CHAT_ID missing in .env")
            return
        try:
            import requests
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=10)
        except Exception as exc:  # never crash the bot on alert failure
            log.warning("Telegram send failed: %s", exc)
