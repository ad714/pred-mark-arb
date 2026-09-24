import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "live-edge"))

import requests
import dns_bypass
import paper_trade
from record_cricket import extract_matches, HEADERS, LIVE_SCORES_URL
from record_commentary import decode_blob, extract_balls, commentary_url

dns_bypass.install()

DATA = ROOT / "docs" / "data"
API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "ad714/pred-mark-arb")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gh(path, params=None):
    if not TOKEN:
        return None
    try:
        r = requests.get(f"{API}/{path}", params=params, timeout=20,
                         headers={"Authorization": f"Bearer {TOKEN}",
                                  "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def trader_state():
    runs = gh(f"repos/{REPO}/actions/workflows/football-scan.yml/runs",
              {"per_page": 10})
    if not runs or not runs.get("workflow_runs"):
        return {"state": "unknown", "runs_total": 0}
    items = runs["workflow_runs"]
    active = next((r for r in items if r["status"] in ("in_progress", "queued")), None)
    target = active or items[0]
    started = target.get("run_started_at") or target.get("created_at")
    anchor = started if active else (target.get("updated_at") or started)
    elapsed = None
    if anchor:
        began = datetime.strptime(anchor, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        elapsed = int((datetime.now(timezone.utc) - began).total_seconds())
    return {
        "state": target["status"] if active else "idle",
        "conclusion": target.get("conclusion"),
        "run_number": target.get("run_number"),
        "url": target.get("html_url"),
        "started_at": started,
        "elapsed_s": elapsed,
        "elapsed_means": "running for" if active else "idle for",
        "runs_total": runs.get("total_count", len(items)),
    }


def registry_update(matches, pairings, diagnostics, wicket_counts):
    path = DATA / "matches.json"
    book = {}
    if path.exists():
        try:
            book = json.loads(path.read_text(encoding="utf-8")).get("matches", {})
        except ValueError:
            book = {}

    stamp = now_iso()
    paired_by_id = {p["cb_id"]: p for p in pairings}
    reason_by_id = {d["cb_id"]: d["reason"] for d in diagnostics}

    for entry in matches:
        key = str(entry["cb_id"])
        row = book.get(key) or {
            "cb_id": entry["cb_id"],
            "first_seen": stamp,
            "states": [],
        }
        row.update({
            "teams": entry["teams"],
            "teams_full": entry.get("teams_full"),
            "series": entry.get("series"),
            "format": entry.get("format"),
            "date": entry.get("date"),
            "last_seen": stamp,
            "last_state": entry.get("state"),
        })
        if entry.get("state") and entry["state"] not in row["states"]:
            row["states"].append(entry["state"])
        hit = paired_by_id.get(entry["cb_id"])
        if hit:
            row["paired_slug"] = hit["slug"]
            row["paired_score"] = hit.get("score")
            row["paired_question"] = hit.get("question")
            row.pop("unpaired_reason", None)
        elif entry["cb_id"] in reason_by_id and "paired_slug" not in row:
            row["unpaired_reason"] = reason_by_id[entry["cb_id"]]
        row["wickets_timed"] = wicket_counts.get(entry["cb_id"], row.get("wickets_timed", 0))
        book[key] = row

    path.write_text(json.dumps({"generated_at": stamp, "matches": book}, indent=1),
                    encoding="utf-8")
    return book


STALE_BALL_MINUTES = 25


def minutes_since_last_ball(session, cb_id):
    try:
        html = session.get(commentary_url(cb_id), headers=HEADERS, timeout=15).text
        stamps = [b.get("timestamp") for b in extract_balls(decode_blob(html)) if b.get("timestamp")]
        if not stamps:
            return None
        return round((time.time() * 1000 - max(stamps)) / 60000, 1)
    except Exception:
        return None


def live_view(wicket_counts):
    session = requests.Session()
    matches = []
    try:
        html = session.get(LIVE_SCORES_URL, headers=HEADERS, timeout=25).text
        for cb_id, match in extract_matches(html).items():
            info = match["matchInfo"]
            team1 = (info.get("team1") or {}).get("teamSName")
            team2 = (info.get("team2") or {}).get("teamSName")
            full1, full2 = paper_trade.team_full_names(match)
            matches.append({
                "cb_id": cb_id,
                "teams": f"{team1} v {team2}",
                "teams_full": f"{full1} v {full2}",
                "state": info.get("state"),
                "status": info.get("status"),
                "series": info.get("seriesName"),
                "format": info.get("matchFormat"),
                "date": str(paper_trade.match_date(match) or ""),
                "start_ms": int(info["startDate"]) if info.get("startDate") else None,
            })

        for row in matches:
            if row["state"] in paper_trade.LIVE_STATES:
                row["last_ball_min"] = minutes_since_last_ball(session, row["cb_id"])
                row["balls_flowing"] = (row["last_ball_min"] is not None
                                        and row["last_ball_min"] <= STALE_BALL_MINUTES)
    except Exception as exc:
        print(f"cricbuzz live view failed: {type(exc).__name__}: {exc}")

    states_by_id = {m["cb_id"]: m["state"] for m in matches}
    pairings, diagnostics = [], []
    try:
        found = paper_trade.build_pairings(
            session, paper_trade.PAIR_MIN_PRICE, paper_trade.PAIR_MAX_PRICE,
            diagnostics=diagnostics,
            states=("In Progress", "Innings Break", "Toss", "Stumps", "Preview"))
        for slug, pairing in found.items():
            prices = {}
            for outcome, token in pairing["outcomes"].items():
                try:
                    book = paper_trade.fetch_book(session, token, timeout=10, retries=1)
                    prices[outcome] = {"bid": book["best_bid"], "ask": book["best_ask"],
                                       "mid": book["mid"]}
                except Exception:
                    prices[outcome] = {"bid": None, "ask": None, "mid": None}
            pairings.append({
                "slug": slug,
                "cb_id": pairing["cb_id"],
                "question": pairing["question"],
                "score": pairing.get("score"),
                "state": states_by_id.get(pairing["cb_id"]),
                "prices": prices,
            })
    except Exception as exc:
        print(f"pairing failed: {type(exc).__name__}: {exc}")

    book = registry_update(matches, pairings, diagnostics, wicket_counts)
    tracked = [r for r in book.values() if r.get("paired_slug")]

    paired_ids = {p["cb_id"] for p in pairings}
    upcoming = sorted(
        (m for m in matches
         if m.get("start_ms") and m["cb_id"] in paired_ids
         and m["start_ms"] > time.time() * 1000),
        key=lambda m: m["start_ms"])

    return {
        "generated_at": now_iso(),
        "matches": [m for m in matches if m["state"] != "Complete"],
        "pairings": pairings,
        "unpaired": diagnostics,
        "next_fixture": upcoming[0] if upcoming else None,
        "coverage": {
            "seen_total": len(book),
            "ever_paired": len(tracked),
            "balls_flowing": sum(1 for m in matches if m.get("balls_flowing")),
            "state_says_live": sum(1 for m in matches
                                   if m["state"] in paper_trade.LIVE_STATES),
        },
        "trader": trader_state(),
    }


def merge_trades(artifact_dir):
    cumulative = DATA / "trades.jsonl"
    seen = set()
    rows = []

    def take(line):
        line = line.strip()
        if not line:
            return
        try:
            row = json.loads(line)
        except ValueError:
            return
        key = (row.get("type"), row.get("recv_ms"), row.get("slug"), row.get("over_ball"))
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    if cumulative.exists():
        for line in cumulative.read_text(encoding="utf-8").splitlines():
            take(line)
    if artifact_dir.is_dir():
        for path in sorted(artifact_dir.rglob("paper_trades.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                take(line)

    rows.sort(key=lambda r: r.get("recv_ms") or 0)
    cumulative.parent.mkdir(parents=True, exist_ok=True)
    cumulative.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
                          encoding="utf-8")
    return rows


def results_view(rows):
    wickets = []
    for row in rows:
        if row["type"] not in ("open", "skip"):
            continue
        cb_ms, recv_ms = row.get("cb_ms"), row.get("recv_ms")
        if not cb_ms or not recv_ms:
            continue
        wickets.append({
            "t": recv_ms,
            "iso": row.get("iso"),
            "slug": row.get("slug"),
            "over_ball": row.get("over_ball"),
            "lag_s": round((recv_ms - cb_ms) / 1000.0, 1),
            "action": row["type"],
            "reason": row.get("reason"),
        })

    lags = sorted(w["lag_s"] for w in wickets)
    lag = {"n": len(lags)}
    if lags:
        def pct(p):
            return lags[min(len(lags) - 1, int(len(lags) * p))]
        lag.update({"min": lags[0], "median": round(statistics.median(lags), 1),
                    "p90": pct(0.9), "max": lags[-1], "values": lags})

    closes = [r for r in rows if r["type"] == "close"]
    moves = [r["exit_buy_mid"] - r["entry_buy_mid"] for r in closes
             if r.get("exit_buy_mid") is not None and r.get("entry_buy_mid") is not None]
    trades = {
        "n": len(closes),
        "wins": sum(1 for c in closes if c["pnl"] > 0),
        "realized": round(sum(c["pnl"] for c in closes), 4),
        "median_mid_move": round(statistics.median(moves), 4) if moves else None,
        "recent": [{
            "iso": c.get("iso"), "slug": c.get("slug"), "over_ball": c.get("over_ball"),
            "outcome": c.get("buy_outcome"), "entry": c.get("entry_vwap"),
            "exit": c.get("exit_vwap"), "pnl": c.get("pnl"),
            "mid_move": round(c["exit_buy_mid"] - c["entry_buy_mid"], 4)
            if c.get("exit_buy_mid") is not None and c.get("entry_buy_mid") is not None else None,
        } for c in closes[-25:]][::-1],
    }

    return {"generated_at": now_iso(), "lag": lag, "trades": trades,
            "wickets": wickets[-200:][::-1]}


def basket_view(artifact_dir):
    out = DATA / "basket.json"
    history = []
    if out.exists():
        try:
            history = json.loads(out.read_text(encoding="utf-8")).get("history", [])
        except ValueError:
            history = []
    seen = {h["t"] for h in history}

    latest = None
    sources = sorted(artifact_dir.rglob("basket_*.json")) if artifact_dir.is_dir() else []
    for path in sources:
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        stamp = blob.get("generated_at")
        events = blob.get("events") or []
        complete = [e for e in events if e.get("complete_basket")]
        entry = {
            "t": stamp,
            "events_scanned": blob.get("events_scanned"),
            "candidates": blob.get("candidates_walked"),
            "rows": len(events),
            "complete_n": len(complete),
            "best_net": round(max((e["peak_net"] for e in events), default=0.0), 2),
            "best_complete_net": round(max((e["peak_net"] for e in complete), default=0.0), 2),
        }
        latest = {**entry, "top": [{
            "event": e.get("title") or e.get("slug"),
            "url": e.get("url"),
            "net": round(e.get("peak_net", 0.0), 2),
            "capital": round(e.get("peak_capital", 0.0), 2),
            "return_pct": e.get("peak_return_pct"),
            "per_share": e.get("cost_per_share_peak"),
            "buyable": e.get("legs_buyable"),
            "dark": e.get("legs_dark"),
            "dark_named": e.get("legs_unknown_named"),
            "complete": bool(e.get("complete_basket")),
            "days": e.get("days_left"),
            "vol24": e.get("volume_24h"),
        } for e in events[:12]]}
        if stamp and stamp not in seen:
            history.append(entry)
            seen.add(stamp)

    if latest is None and out.exists():
        try:
            latest = json.loads(out.read_text(encoding="utf-8")).get("latest")
        except ValueError:
            latest = None

    history.sort(key=lambda h: h["t"] or "")
    return {"generated_at": now_iso(), "latest": latest, "history": history[-240:]}


EDGE_LOW, EDGE_HIGH, BREAKEVEN = 0.65, 0.85, 0.029


def football_view():
    raw = DATA / "football.jsonl"
    if not raw.exists():
        return {"generated_at": now_iso(), "latest": None, "history": [], "leagues": {}}

    rows = []
    for line in raw.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if not rows:
        return {"generated_at": now_iso(), "latest": None, "history": [], "leagues": {}}

    by_sample = {}
    for row in rows:
        by_sample.setdefault(row.get("t"), []).append(row)

    flagged = [r.get("t") for r in rows if r.get("snapshot")]
    if flagged:
        cutover = min(flagged)
        stamps = sorted(s for s in by_sample
                        if s < cutover or any(r.get("snapshot") for r in by_sample[s]))
    else:
        stamps = sorted(by_sample)

    history = []
    for stamp in stamps:
        batch = by_sample[stamp]
        band = [r for r in batch if r.get("in_edge_band")]
        good = [r for r in band if r.get("tradeable")]
        spreads = sorted(r["spread"] for r in band if r.get("spread") is not None)
        history.append({
            "t": stamp,
            "markets": len(batch),
            "fixtures": len({r.get("fixture") for r in batch}),
            "in_band": len(band),
            "tradeable": len(good),
            "median_band_spread": (round(statistics.median(spreads), 4) if spreads else None),
        })

    newest = stamps[-1]
    batch = by_sample[newest]
    band = [r for r in batch if r.get("in_edge_band")]
    good = sorted((r for r in band if r.get("tradeable")),
                  key=lambda r: (r.get("spread") if r.get("spread") is not None else 9, r.get("match_date") or ""))
    latest = {
        "t": newest,
        "markets": len(batch),
        "fixtures": len({r.get("fixture") for r in batch}),
        "in_band": len(band),
        "tradeable": len(good),
        "rows": [{
            "market": r.get("market"), "league": r.get("league"),
            "question": r.get("question"), "match_date": r.get("match_date"),
            "quoted": r.get("quoted"), "bid": r.get("bid"), "ask": r.get("ask"),
            "spread": r.get("spread"), "ask_size": r.get("ask_size"),
            "liquidity": r.get("liquidity"),
        } for r in good[:40]],
    }

    leagues = {}
    complete = set(stamps)
    for row in rows:
        if row.get("t") not in complete:
            continue
        key = row.get("league") or "?"
        slot = leagues.setdefault(key, {"seen": 0, "in_band": 0, "tradeable": 0})
        slot["seen"] += 1
        if row.get("in_edge_band"):
            slot["in_band"] += 1
        if row.get("tradeable"):
            slot["tradeable"] += 1
    leagues = dict(sorted(leagues.items(), key=lambda kv: -kv[1]["tradeable"])[:14])

    return {"generated_at": now_iso(), "breakeven": BREAKEVEN,
            "edge_band": [EDGE_LOW, EDGE_HIGH],
            "latest": latest, "history": history[-400:], "leagues": leagues}


def main():
    artifacts = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts"
    DATA.mkdir(parents=True, exist_ok=True)

    rows = merge_trades(artifacts)

    wicket_counts = {}
    for row in rows:
        if row["type"] in ("open", "skip") and row.get("cb_id"):
            wicket_counts[row["cb_id"]] = wicket_counts.get(row["cb_id"], 0) + 1

    (DATA / "results.json").write_text(json.dumps(results_view(rows), indent=1), encoding="utf-8")
    (DATA / "basket.json").write_text(json.dumps(basket_view(artifacts), indent=1), encoding="utf-8")
    (DATA / "football.json").write_text(json.dumps(football_view(), indent=1), encoding="utf-8")
    (DATA / "live.json").write_text(json.dumps(live_view(wicket_counts), indent=1), encoding="utf-8")

    print(f"trade records: {len(rows)}")
    for name in ("results.json", "basket.json", "live.json", "matches.json", "football.json"):
        print(f"  {name:<14} {(DATA / name).stat().st_size:>8} bytes")


if __name__ == "__main__":
    main()
