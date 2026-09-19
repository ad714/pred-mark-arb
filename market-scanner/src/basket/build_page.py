import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LIVE_EDGE = Path(__file__).resolve().parents[3] / "live-edge"
if LIVE_EDGE.is_dir():
    sys.path.insert(0, str(LIVE_EDGE))
    import dns_bypass

    dns_bypass.install()

import requests

from src.basket.basket import PLACEHOLDER, event_legs, yes_mark
from src.basket.baserates import base_rate
from src.basket.rules import parse as parse_rules
from src.basket.reality import (CATCHALL_NOTE, COMPLETE_NOTE, COVERAGE_NOTE, FIELD_TYPES,
                                VERDICTS, classify, coverage_verdict)
from src.fetch.clob_book import fetch_books

SCAN = Path("data/derived/basket.json")
RAW = Path("data/raw/poly_events_raw.json")
OUT = Path("data/derived/basket_page.json")
SHELL = Path("data/page_shell.html")
PAGE = Path("../basket-board.html")

DATE = re.compile(
    r"by\s+((?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4})", re.I)


def history(jobs):
    session = requests.Session()

    def one(job):
        for _ in range(2):
            try:
                r = session.get("https://clob.polymarket.com/prices-history",
                                params={"market": job[1], "interval": "max", "fidelity": 720},
                                timeout=25)
                if r.status_code == 200:
                    return job, r.json().get("history", [])
            except requests.RequestException:
                time.sleep(0.4)
        return job, []

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for job, h in pool.map(one, jobs):
            out[job] = h
    return out


def basket_history(series):
    series = [s for s in series if s]
    if len(series) < 2:
        return [], None
    grid = sorted(set().union(*[set(s) for s in series]))
    last, rows = {}, []
    for t in grid:
        for i, s in enumerate(series):
            if t in s:
                last[i] = s[t]
        if len(last) < len(series):
            continue
        rows.append([t, round(sum(last.values()), 4)])
    if not rows:
        return [], None
    under = round(100.0 * sum(1 for _, v in rows if v < 1.0) / len(rows), 1)
    if len(rows) > 190:
        step = len(rows) / 190.0
        rows = [rows[int(i * step)] for i in range(190)] + [rows[-1]]
    return rows, under


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    scan = json.load(open(SCAN, encoding="utf-8"))
    raw = {e["id"]: e for e in json.load(open(RAW, encoding="utf-8"))}

    jobs, legmap, marks = [], {}, {}
    for row in scan["events"]:
        src = raw[row["event_id"]]
        legmap[row["event_id"]] = event_legs(src)
        marks[row["event_id"]] = {
            (m.get("groupItemTitle") or m.get("question") or ""): yes_mark(m)[0]
            for m in src.get("markets") or []}
        jobs += [(row["event_id"], l["token"]) for l in legmap[row["event_id"]]]

    print(f"reading {len(jobs)} books and price histories...")
    books = fetch_books([t for _, t in jobs])
    hist = history(jobs)

    out = {"generated_at": scan["generated_at"], "scanned": scan["events_scanned"],
           "walked": scan["candidates_walked"], "field_types": FIELD_TYPES,
           "verdicts": VERDICTS, "events": []}

    for row in scan["events"]:
        eid = row["event_id"]
        src = raw[eid]
        buy, dark, series = [], [], []
        for leg in legmap[eid]:
            book = books.get(leg["token"])
            mark = marks[eid].get(leg["name"], 0.0) or 0.0
            if leg["tradeable"] and book and book["asks"]:
                buy.append({"n": leg["name"], "r": leg["fee_rate"], "a": leg["best_ask"],
                            "b": book["bids"][0][0] if book["bids"] else None,
                            "m": round(mark, 4),
                            "k": [[round(p, 4), round(s, 2)] for p, s in book["asks"][:45]]})
                h = hist.get((eid, leg["token"])) or []
                series.append({int(x["t"]) // 43200 * 43200: x["p"] for x in h})
            else:
                dark.append({"n": leg["name"], "m": round(leg["mark"] or 0, 4),
                             "known": bool(leg["mark_known"]),
                             "ph": bool(PLACEHOLDER.match((leg["name"] or "").strip()))})

        rows, under = basket_history(series)
        drift = None
        if len(rows) > 3:
            cut = rows[-1][0] - 7 * 86400
            past = [v for t, v in rows if t <= cut]
            if past:
                drift = round(rows[-1][1] - past[-1], 4)

        coverage = sum(l["m"] for l in buy)
        has_other = any(d["n"].strip().lower().startswith("other") for d in dark)
        dark_max = max([d["m"] for d in dark] or [0.0])
        breakeven = row["peak_net"] / row["peak_size"] if row["peak_size"] else 0.0
        r = coverage_verdict(classify(row["title"]), coverage, breakeven,
                             has_other, len(dark), dark_max)

        notes = []
        if not dark:
            notes.append(COMPLETE_NOTE)
        else:
            if has_other:
                notes.append(CATCHALL_NOTE)
            if (1 - coverage) > breakeven:
                notes.append(COVERAGE_NOTE.format(cov=coverage * 100,
                                                  gap=(1 - coverage) * 100,
                                                  be=breakeven * 100))
        rules = parse_rules(src.get("description") or "", [d["n"] for d in dark])
        backstop = DATE.search(src.get("description") or "")
        top = max(buy, key=lambda b: b["m"]) if buy else None

        out["events"].append({
            "id": eid, "title": row["title"], "url": row["url"], "tags": row["tags"],
            "days": row["days_left"], "end": src.get("endDate"), "vol": row["volume_24h"],
            "vol_total": round(float(src.get("volume") or 0)),
            "vol_1wk": round(float(src.get("volume1wk") or 0)),
            "desc": (src.get("description") or "")[:2600],
            "backstop": backstop.group(1) if backstop else None,
            "resolver": src.get("resolutionSource") or "",
            "complete": row["complete_basket"], "trap": row["full_cost_per_share"] >= 1.0,
            "nlegs": row["legs_buyable"], "dark": row["legs_dark"], "unk": row["legs_unknown"],
            "real": row["legs_unknown_named"], "darkmax": row["dark_mark_max"],
            "darksum": row["dark_mark_sum"], "fullshare": row["full_cost_per_share"],
            "share": row["cost_per_share_peak"], "linchpin": row["linchpin"],
            "fav": top["n"] if top else "", "fav_p": top["m"] if top else 0,
            "hist": rows, "under_pct": under, "first_under": None, "drift": drift,
            "legs": buy, "darklegs": dark, "rules": rules,
            "reality": {"type": r["type"], "type_label": FIELD_TYPES[r["type"]],
                        "closure": r["closure"], "verdict": r["verdict"],
                        "verdict_label": VERDICTS[r["verdict"]], "evidence": r["evidence"],
                        "who": r["who"], "detail": r["detail"], "closes": r.get("closes"),
                        "sources": r.get("sources", []), "coverage": round(coverage, 4),
                        "has_other": has_other, "notes": notes,
                        "base": base_rate(row["title"], r["type"])},
        })

    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"payload {os.path.getsize(OUT)} bytes, {len(out['events'])} events")

    shell = open(SHELL, encoding="utf-8").read()
    payload = open(OUT, encoding="utf-8").read()
    page = shell.replace("__PAYLOAD__", payload)
    open(PAGE, "w", encoding="utf-8", newline="\n").write(page)
    print(f"page written -> {PAGE.resolve()} ({len(page.encode('utf-8'))} bytes)")

    from collections import Counter
    print(Counter(e["reality"]["verdict"] for e in out["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
