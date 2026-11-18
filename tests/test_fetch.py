import json

from vwapbot.fetch import parse_market


def raw_market(**over):
    base = {
        "id": "42",
        "question": "Will the highest temperature in Tokyo be 14°C or below on November 18?",
        "closed": True,
        "umaResolutionStatus": "resolved",
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps(["1", "0"]),
        "clobTokenIds": json.dumps(["111", "222"]),
        "endDate": "2026-11-18T12:00:00Z",
    }
    base.update(over)
    return base


def test_parse_market_yes_won():
    rec = parse_market(raw_market(), category="weather")
    assert rec == {
        "id": "42",
        "category": "weather",
        "question": raw_market()["question"],
        "end_ts": 1795003200,
        "yes_won": True,
        "yes_token": "111",
    }


def test_parse_market_no_won():
    rec = parse_market(raw_market(outcomePrices=json.dumps(["0", "1"])), category="crypto")
    assert rec["yes_won"] is False


def test_parse_market_skips_unresolved_or_ambiguous():
    assert parse_market(raw_market(closed=False), "weather") is None
    assert parse_market(raw_market(umaResolutionStatus="proposed"), "weather") is None
    assert parse_market(raw_market(outcomePrices=json.dumps(["0.5", "0.5"])), "weather") is None
    assert parse_market(raw_market(clobTokenIds=None), "weather") is None
    assert parse_market(raw_market(endDate="not-a-date"), "weather") is None


def test_parse_market_treats_first_outcome_as_yes_for_up_down():
    raw = raw_market(outcomes=json.dumps(["Up", "Down"]), outcomePrices=json.dumps(["1", "0"]))
    assert parse_market(raw, "crypto")["yes_won"] is True
    raw = raw_market(outcomes=json.dumps(["Up", "Down"]), outcomePrices=json.dumps(["0", "1"]))
    assert parse_market(raw, "crypto")["yes_won"] is False


def test_collect_writes_resolved_markets_and_skips_duplicates(tmp_path, monkeypatch):
    from vwapbot import fetch

    events = [{"markets": [raw_market(id="1"), raw_market(id="2", closed=False), raw_market(id="1")]}]
    monkeypatch.setattr(fetch, "iter_closed_events", lambda tag, n: iter(events))
    monkeypatch.setattr(fetch, "fetch_history", lambda token, fidelity: [[1, 0.5], [2, 0.6]])

    out = tmp_path / "w.jsonl"
    assert fetch.collect("weather", "daily-temperature", out, max_markets=10, fidelity=60) == 1
    # a second run appends nothing: the market is already stored
    assert fetch.collect("weather", "daily-temperature", out, max_markets=10, fidelity=60) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["id"] for r in rows] == ["1"]
    assert rows[0]["history"] == [[1, 0.5], [2, 0.6]]


def test_collect_skips_markets_with_too_little_history(tmp_path, monkeypatch):
    from vwapbot import fetch

    monkeypatch.setattr(fetch, "iter_closed_events", lambda tag, n: iter([{"markets": [raw_market()]}]))
    monkeypatch.setattr(fetch, "fetch_history", lambda token, fidelity: [[1, 0.5]])
    assert fetch.collect("weather", "t", tmp_path / "x.jsonl", max_markets=5, fidelity=60) == 0


def test_get_json_retries_on_429_then_succeeds(monkeypatch):
    import io
    import urllib.error

    from vwapbot import fetch

    calls = {"n": 0}

    def fake_urlopen(req, timeout, context):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down", {}, None)
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    assert fetch.get_json("https://example.test/x", pause=0) == {"ok": True}
    assert calls["n"] == 2


def test_iter_closed_events_paginates_in_small_pages_and_stops(monkeypatch):
    from vwapbot import fetch

    calls = []

    def fake_get_json(url, params=None, **kw):
        calls.append(params["offset"])
        assert params["limit"] <= 20
        return [{"slug": f"e{params['offset'] + i}"} for i in range(params["limit"])] if params["offset"] < 40 else []

    monkeypatch.setattr(fetch, "get_json", fake_get_json)
    got = list(fetch.iter_closed_events("daily-temperature", max_events=100))
    assert len(got) == 40
    assert calls == [0, 20, 40]
