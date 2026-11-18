"""Fetch resolved Polymarket markets and price history from the public APIs.

Read-only: no keys, no wallet, no trading endpoints.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
USER_AGENT = "vwapbot-research/0.1"

log = logging.getLogger(__name__)


def _ssl_context() -> ssl.SSLContext:
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    return ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()


def get_json(url: str, params: Optional[dict] = None, retries: int = 4, pause: float = 0.2) -> Any:
    """GET + parse JSON with exponential backoff on 429/5xx/network errors."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
                data = json.load(resp)
            time.sleep(pause)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def _iso_to_ts(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def parse_market(raw: dict, category: str) -> Optional[dict]:
    """Normalise a Gamma market; None unless it cleanly resolved to 1/0.

    The first outcome is treated as "YES" (this covers Yes/No and Up/Down).
    """
    if not raw.get("closed") or raw.get("umaResolutionStatus") != "resolved":
        return None
    try:
        prices = [float(p) for p in json.loads(raw["outcomePrices"])]
        tokens = json.loads(raw["clobTokenIds"])
        outcomes = json.loads(raw["outcomes"])
        end_ts = _iso_to_ts(raw["endDate"])
    except (KeyError, TypeError, ValueError):
        return None
    if len(prices) != 2 or len(tokens) != 2 or len(outcomes) != 2:
        return None
    if sorted(prices) != [0.0, 1.0]:
        return None
    return {
        "id": str(raw["id"]),
        "category": category,
        "question": raw.get("question", ""),
        "end_ts": end_ts,
        "yes_won": prices[0] == 1.0,
        "yes_token": tokens[0],
    }


def iter_closed_events(tag_slug: str, max_events: int, page: int = 20) -> Iterator[dict]:
    """Newest-first closed events for a Gamma tag.

    Pages are kept small on purpose: each event embeds all its markets, and a
    100-event page exceeds the egress proxy's response limit (HTTP 406).
    """
    offset = 0
    while offset < max_events:
        batch = get_json(
            f"{GAMMA}/events",
            {
                "tag_slug": tag_slug,
                "closed": "true",
                "limit": min(page, max_events - offset),
                "offset": offset,
                "order": "endDate",
                "ascending": "false",
            },
        )
        if not batch:
            return
        yield from batch
        offset += len(batch)


def fetch_history(token: str, fidelity: int) -> list[list[float]]:
    data = get_json(f"{CLOB}/prices-history", {"market": token, "interval": "max", "fidelity": fidelity})
    return [[int(pt["t"]), float(pt["p"])] for pt in data.get("history", [])]


def _history_or_none(rec: dict, fidelity: int) -> Optional[list]:
    try:
        history = fetch_history(rec["yes_token"], fidelity)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log.warning("history failed for %s: %s", rec["id"], exc)
        return None
    return history if len(history) >= 2 else None


def collect(
    category: str,
    tag_slug: str,
    out_path: Path,
    max_markets: int,
    fidelity: int,
    max_events: int = 1000,
    event_stride: int = 1,
    workers: int = 6,
) -> int:
    """Append resolved markets with history to a JSONL file; returns count saved.

    `event_stride` keeps every k-th event so a fixed market budget spans more
    calendar days. Histories for one event's markets are fetched concurrently.
    """
    if event_stride < 1 or workers < 1:
        raise ValueError("event_stride and workers must be >= 1")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if out_path.exists():
        seen = {json.loads(line)["id"] for line in out_path.read_text().splitlines() if line}
    saved = 0
    with out_path.open("a") as fh, ThreadPoolExecutor(max_workers=workers) as pool:
        for i, event in enumerate(iter_closed_events(tag_slug, max_events)):
            if i % event_stride:
                continue
            recs, ids = [], set()
            for raw in event.get("markets", []):
                rec = parse_market(raw, category)
                if rec is not None and rec["id"] not in seen and rec["id"] not in ids:
                    recs.append(rec)
                    ids.add(rec["id"])
            for rec, history in zip(recs, pool.map(lambda r: _history_or_none(r, fidelity), recs)):
                if history is None:
                    continue
                fh.write(json.dumps({**rec, "history": history}) + "\n")
                seen.add(rec["id"])
                saved += 1
                if saved >= max_markets:
                    return saved
    return saved
