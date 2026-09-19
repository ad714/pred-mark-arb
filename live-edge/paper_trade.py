import argparse
import datetime
import json
import re
import sys
import threading
import time
from pathlib import Path

import requests

import dns_bypass
import watch
from record_cricket import extract_matches, HEADERS, LIVE_SCORES_URL
from record_commentary import decode_blob, extract_balls, commentary_url, ParseFailed as CommentaryParseFailed

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
CLOB_BOOK = "https://clob.polymarket.com/book"
WICKET_TOKENS = {"wicket"}
STOP_WORDS = {"the", "cricket", "match", "men", "mens", "team"}
QUAL_WORDS = {
    "women": "w", "womens": "w", "w": "w",
    "under": "u19", "u19": "u19", "19": "u19", "19s": "u19", "u19s": "u19",
    "a": "second", "b": "second", "ii": "second", "2nd": "second",
    "emerging": "emerging", "legends": "legends", "masters": "legends",
}
MIN_NAME_SCORE = 0.5
MAX_DATE_DRIFT_DAYS = 1
LIVE_STATES = ("In Progress", "Innings Break")
SLUG_DATE = re.compile(r"-(\d{4}-\d{2}-\d{2})$")
PAIR_MIN_PRICE = 0.02
PAIR_MAX_PRICE = 0.98


def split_name(name):
    base, quals = [], set()
    for word in re.findall(r"[a-z0-9]+", (name or "").lower()):
        if word in QUAL_WORDS:
            quals.add(QUAL_WORDS[word])
        elif word not in STOP_WORDS:
            base.append(word)
    return set(base), quals


def name_score(left, right):
    left_base, left_quals = split_name(left)
    right_base, right_quals = split_name(right)
    if left_quals != right_quals or not left_base or not right_base:
        return 0.0
    shared = left_base & right_base
    if not shared:
        return 0.0
    return len(shared) / len(left_base | right_base)


def slug_date(slug):
    found = SLUG_DATE.search(slug or "")
    if not found:
        return None
    try:
        return datetime.date.fromisoformat(found.group(1))
    except ValueError:
        return None


def match_date(cb_match):
    raw = (cb_match.get("matchInfo") or {}).get("startDate")
    if not raw:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            int(raw) / 1000, datetime.timezone.utc).date()
    except (ValueError, OSError):
        return None


def dates_agree(day, cb_day):
    if day is None or cb_day is None:
        return True
    return abs((day - cb_day).days) <= MAX_DATE_DRIFT_DAYS


def resolve_tokens(session, slug):
    try:
        response = session.get(GAMMA_EVENTS, params={"slug": slug}, timeout=20)
        response.raise_for_status()
        events = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not events:
        return None
    for market in events[0].get("markets", []):
        if market.get("slug") == slug:
            try:
                token_ids = json.loads(market["clobTokenIds"])
                outcomes = json.loads(market["outcomes"])
            except (KeyError, ValueError, json.JSONDecodeError):
                return None
            return {
                "question": market.get("question"),
                "outcomes": dict(zip(outcomes, token_ids)),
            }
    return None


def short_to_full(cb_match):
    info = cb_match["matchInfo"]
    mapping = {}
    for key in ("team1", "team2"):
        team = info.get(key) or {}
        short = team.get("teamSName")
        full = team.get("teamName")
        if short and full:
            mapping[short] = full
    return mapping


def team_full_names(cb_match):
    info = cb_match["matchInfo"]
    return [
        (info.get("team1") or {}).get("teamName"),
        (info.get("team2") or {}).get("teamName"),
    ]


def best_outcome(team_name, outcomes):
    best, score = None, 0.0
    for outcome in outcomes:
        current = name_score(team_name, outcome)
        if current > score:
            best, score = outcome, current
    return best if score >= MIN_NAME_SCORE else None


def build_pairings(session, min_price, max_price, diagnostics=None, states=None):
    html = session.get(LIVE_SCORES_URL, headers=HEADERS, timeout=20).text
    matches = extract_matches(html)
    wanted = states or LIVE_STATES
    live = {
        mid: m
        for mid, m in matches.items()
        if m["matchInfo"].get("state") in wanted
    }
    live_days = {match_date(m) for m in live.values()} - {None}

    candidates = watch.discover(min_price, max_price)
    markets = {}
    for slug, cand in candidates.items():
        if not cand["competitive"] or cand["closed"]:
            continue
        day = slug_date(slug)
        if live_days and day and not any(dates_agree(day, d) for d in live_days):
            continue
        resolved = resolve_tokens(session, slug)
        if not resolved or len(resolved["outcomes"]) != 2:
            continue
        markets[slug] = resolved

    scored, closest = [], {}
    for mid, cb_match in live.items():
        cb_day = match_date(cb_match)
        full1, full2 = team_full_names(cb_match)
        for slug, resolved in markets.items():
            outcomes = resolved["outcomes"]
            pick1 = max(outcomes, key=lambda o: name_score(full1, o))
            pick2 = max(outcomes, key=lambda o: name_score(full2, o))
            raw = min(name_score(full1, pick1), name_score(full2, pick2))
            if raw > closest.get(mid, (0.0, None))[0]:
                closest[mid] = (raw, slug)
            if not dates_agree(slug_date(slug), cb_day):
                continue
            one = best_outcome(full1, outcomes)
            two = best_outcome(full2, outcomes)
            if not one or not two or one == two:
                continue
            scored.append((raw, mid, slug, resolved, one, two, full1, full2))

    scored.sort(key=lambda row: -row[0])
    pairings, taken_matches, taken_slugs = {}, set(), set()
    for raw, mid, slug, resolved, one, two, full1, full2 in scored:
        if mid in taken_matches or slug in taken_slugs:
            continue
        taken_matches.add(mid)
        taken_slugs.add(slug)
        pairings[slug] = {
            "cb_id": mid,
            "slug": slug,
            "question": resolved["question"],
            "outcomes": resolved["outcomes"],
            "full_to_outcome": {full1: one, full2: two},
            "short_to_full": short_to_full(matches[mid]),
            "score": round(raw, 3),
        }

    if diagnostics is not None:
        for mid, cb_match in live.items():
            if mid in taken_matches:
                continue
            best_raw, best_slug = closest.get(mid, (0.0, None))
            info = cb_match["matchInfo"]
            full1, full2 = team_full_names(cb_match)
            if best_slug is None:
                why = "no open two outcome cricket market to compare against"
            elif best_raw < MIN_NAME_SCORE:
                why = f"closest market {best_slug} only scored {best_raw:.2f} on team names"
            else:
                why = f"{best_slug} matched on names but its date does not fit this fixture"
            diagnostics.append({
                "cb_id": mid,
                "teams": f"{full1} v {full2}",
                "series": info.get("seriesName"),
                "state": info.get("state"),
                "date": str(match_date(cb_match) or ""),
                "reason": why,
            })

    return pairings


def fetch_book(session, token_id, timeout=6, retries=2):
    last = None
    for _ in range(retries + 1):
        try:
            return _fetch_book_once(session, token_id, timeout)
        except (requests.RequestException, ValueError, KeyError) as exc:
            last = exc
    raise last


def _fetch_book_once(session, token_id, timeout):
    response = session.get(CLOB_BOOK, params={"token_id": token_id}, timeout=timeout)
    response.raise_for_status()
    book = response.json()
    bids = sorted(
        ((float(b["price"]), float(b["size"])) for b in book.get("bids") or []),
        key=lambda x: -x[0],
    )
    asks = sorted(
        ((float(a["price"]), float(a["size"])) for a in book.get("asks") or []),
        key=lambda x: x[0],
    )
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None
    return {"bids": bids, "asks": asks, "best_bid": best_bid, "best_ask": best_ask, "mid": mid}


def buy_vwap(asks, dollars):
    spent, shares, used = 0.0, 0.0, []
    for price, size in asks:
        room = dollars - spent
        if room <= 1e-9:
            break
        level_cost = price * size
        if level_cost <= room:
            spent += level_cost
            shares += size
            used.append([price, size])
        else:
            take = room / price
            spent += take * price
            shares += take
            used.append([price, round(take, 4)])
            break
    vwap = spent / shares if shares > 0 else None
    return shares, spent, vwap, used


def sell_vwap(bids, shares, fallback_mid):
    proceeds, filled, used = 0.0, 0.0, []
    for price, size in bids:
        need = shares - filled
        if need <= 1e-9:
            break
        take = min(size, need)
        proceeds += take * price
        filled += take
        used.append([price, round(take, 4)])
    remainder = shares - filled
    partial = remainder > 1e-6
    if partial:
        mark = bids[-1][0] if bids else (fallback_mid if fallback_mid is not None else 0.0)
        proceeds += remainder * mark
    vwap = proceeds / shares if shares > 0 else None
    return proceeds, filled, vwap, used, partial


class PaperTrader:
    def __init__(self, out_dir, bankroll, stake, hold_s, min_price, max_price, max_detect_lag):
        self.out_dir = out_dir
        self.bankroll = bankroll
        self.start_bankroll = bankroll
        self.stake = stake
        self.hold_s = hold_s
        self.min_price = min_price
        self.max_price = max_price
        self.max_detect_lag = max_detect_lag
        self.open_positions = []
        self.realized = 0.0
        self.n_trades = 0
        self.wins = 0
        self.trades_path = out_dir / "paper_trades.jsonl"
        self.state_path = out_dir / "paper_state.json"
        out_dir.mkdir(parents=True, exist_ok=True)

    def log(self, record):
        with open(self.trades_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def save_state(self):
        state = {
            "bankroll": round(self.bankroll, 4),
            "start_bankroll": self.start_bankroll,
            "realized_pnl": round(self.realized, 4),
            "open_positions": len(self.open_positions),
            "n_trades": self.n_trades,
            "wins": self.wins,
            "updated_ms": int(time.time() * 1000),
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def try_enter(self, session, pairing, ball, recv_ms):
        cb_ms = ball.get("timestamp")
        detect_lag = (recv_ms - cb_ms) / 1000.0 if cb_ms else None
        if detect_lag is not None and detect_lag > self.max_detect_lag:
            self._skip(ball, pairing, f"detected too late ({detect_lag:.0f}s after ball)", recv_ms)
            return

        batting_short = ball.get("teamName")
        batting_full = pairing["short_to_full"].get(batting_short, batting_short)
        batting_outcome = best_outcome(batting_full, pairing["outcomes"])
        if not batting_outcome:
            self._skip(ball, pairing, "cannot map batting team to outcome", recv_ms)
            return
        opposing_outcome = next(
            o for o in pairing["outcomes"] if o != batting_outcome
        )
        buy_token = pairing["outcomes"][opposing_outcome]
        bat_token = pairing["outcomes"][batting_outcome]

        try:
            buy_book = fetch_book(session, buy_token)
        except (requests.RequestException, ValueError, KeyError) as exc:
            self._skip(ball, pairing, f"buy book fetch failed: {type(exc).__name__}", recv_ms)
            return
        try:
            bat_book = fetch_book(session, bat_token)
        except (requests.RequestException, ValueError, KeyError):
            bat_book = {"mid": None}

        mid = buy_book["mid"]
        if mid is None or not (self.min_price <= mid <= self.max_price):
            self._skip(ball, pairing, f"non-competitive mid {mid}", recv_ms, buy_book, opposing_outcome)
            return
        if self.bankroll < 0.10:
            self._skip(ball, pairing, "bankroll exhausted", recv_ms)
            return

        stake = min(self.stake, self.bankroll)
        shares, spent, vwap, used = buy_vwap(buy_book["asks"], stake)
        if shares <= 0 or vwap is None:
            self._skip(ball, pairing, "no ask liquidity", recv_ms, buy_book, opposing_outcome)
            return

        self.bankroll -= spent
        position = {
            "slug": pairing["slug"],
            "cb_id": pairing["cb_id"],
            "over_ball": ball.get("ballMetric"),
            "batsman": (ball.get("batsmanDetails") or {}).get("playerName"),
            "batting_team": batting_full,
            "buy_outcome": opposing_outcome,
            "buy_token": buy_token,
            "bat_token": bat_token,
            "cb_ms": cb_ms,
            "detect_lag_s": round(detect_lag, 1) if detect_lag is not None else None,
            "entry_recv_ms": recv_ms,
            "exit_due_ms": recv_ms + self.hold_s * 1000,
            "shares": shares,
            "spent": spent,
            "entry_vwap": vwap,
            "entry_buy_mid": mid,
            "entry_bat_mid": bat_book["mid"],
            "entry_levels": used,
        }
        self.open_positions.append(position)
        self.log(
            {
                "type": "open",
                "recv_ms": recv_ms,
                "iso": time.strftime("%H:%M:%S", time.gmtime(recv_ms / 1000)),
                **{k: position[k] for k in (
                    "slug", "cb_id", "over_ball", "batsman", "batting_team",
                    "buy_outcome", "shares", "spent", "entry_vwap",
                    "entry_buy_mid", "entry_bat_mid", "entry_levels", "cb_ms",
                    "detect_lag_s",
                )},
                "buy_book_top": {"bid": buy_book["best_bid"], "ask": buy_book["best_ask"]},
            }
        )
        lag_s = f"{detect_lag:.0f}s late" if detect_lag is not None else "lag n/a"
        print(
            f"  [{time.strftime('%H:%M:%S')}] OPEN  {pairing['slug']}  wkt {position['over_ball']} "
            f"({batting_full} lost {position['batsman']}) -> BUY {opposing_outcome} "
            f"{shares:.2f}sh @ {vwap:.3f}  cost ${spent:.2f}  [{lag_s}]  bankroll ${self.bankroll:.2f}"
        )
        self.save_state()

    def _skip(self, ball, pairing, reason, recv_ms, book=None, outcome=None):
        self.log(
            {
                "type": "skip",
                "recv_ms": recv_ms,
                "iso": time.strftime("%H:%M:%S", time.gmtime(recv_ms / 1000)),
                "slug": pairing["slug"],
                "cb_id": pairing["cb_id"],
                "over_ball": ball.get("ballMetric"),
                "cb_ms": ball.get("timestamp"),
                "reason": reason,
                "outcome": outcome,
                "mid": book["mid"] if book else None,
            }
        )
        print(f"  [{time.strftime('%H:%M:%S')}] skip  {pairing['slug']} wkt {ball.get('ballMetric')}: {reason}")

    def process_exits(self, session, now_ms):
        still_open = []
        for pos in self.open_positions:
            if now_ms < pos["exit_due_ms"]:
                still_open.append(pos)
                continue
            try:
                book = fetch_book(session, pos["buy_token"])
                bat_book = fetch_book(session, pos["bat_token"])
            except (requests.RequestException, ValueError, KeyError):
                still_open.append(pos)
                continue

            proceeds, filled, vwap, used, partial = sell_vwap(
                book["bids"], pos["shares"], book["mid"]
            )
            self.bankroll += proceeds
            pnl = proceeds - pos["spent"]
            self.realized += pnl
            self.n_trades += 1
            if pnl > 0:
                self.wins += 1

            record = {
                "type": "close",
                "recv_ms": now_ms,
                "iso": time.strftime("%H:%M:%S", time.gmtime(now_ms / 1000)),
                "slug": pos["slug"],
                "cb_id": pos["cb_id"],
                "over_ball": pos["over_ball"],
                "batting_team": pos["batting_team"],
                "buy_outcome": pos["buy_outcome"],
                "shares": round(pos["shares"], 4),
                "hold_s": round((now_ms - pos["entry_recv_ms"]) / 1000, 1),
                "entry_vwap": round(pos["entry_vwap"], 4),
                "exit_vwap": round(vwap, 4) if vwap else None,
                "entry_buy_mid": pos["entry_buy_mid"],
                "exit_buy_mid": book["mid"],
                "entry_bat_mid": pos["entry_bat_mid"],
                "exit_bat_mid": bat_book["mid"],
                "spent": round(pos["spent"], 4),
                "proceeds": round(proceeds, 4),
                "pnl": round(pnl, 4),
                "partial_exit": partial,
                "exit_levels": used,
                "bankroll": round(self.bankroll, 4),
                "realized_pnl": round(self.realized, 4),
            }
            self.log(record)
            move = book["mid"] - pos["entry_buy_mid"] if book["mid"] is not None else None
            move_s = f"{move:+.3f}" if move is not None else "  n/a"
            print(
                f"  [{time.strftime('%H:%M:%S')}] CLOSE {pos['slug']}  {pos['buy_outcome']} "
                f"{pos['entry_vwap']:.3f}->{(vwap or 0):.3f}  mid move {move_s}  "
                f"PnL ${pnl:+.3f}  bankroll ${self.bankroll:.2f}  "
                f"({self.wins}/{self.n_trades} win, realized ${self.realized:+.3f})"
            )
            self.save_state()
        self.open_positions = still_open


def discovery_thread(holder, discover_s):
    disc_session = requests.Session()
    while not holder["stop"]:
        try:
            new_pairings = build_pairings(disc_session, PAIR_MIN_PRICE, PAIR_MAX_PRICE)
            with holder["lock"]:
                old = holder["pairings"]
                for slug, p in new_pairings.items():
                    if slug not in old:
                        print(f"[{time.strftime('%H:%M:%S')}] PAIR {slug} <-> cb {p['cb_id']}  {p['question']}")
                for slug in list(old):
                    if slug not in new_pairings:
                        print(f"[{time.strftime('%H:%M:%S')}] UNPAIR {slug} (match ended or market closed)")
                holder["pairings"] = new_pairings
        except Exception as exc:
            print(f"[{time.strftime('%H:%M:%S')}] discover failed: {type(exc).__name__}: {exc}")
        for _ in range(int(discover_s)):
            if holder["stop"]:
                return
            time.sleep(1)


def run(args):
    dns_bypass.install()
    session = requests.Session()
    trader = PaperTrader(
        args.out, args.bankroll, args.stake, args.hold,
        args.min_price, args.max_price, args.max_detect_lag,
    )
    print(f"paper trader: ${args.bankroll:.2f} bankroll, ${args.stake:.2f}/trade, {args.hold}s hold")
    print(f"entry band {args.min_price}-{args.max_price}, max detect lag {args.max_detect_lag}s")
    print(f"pairing band {PAIR_MIN_PRICE}-{PAIR_MAX_PRICE}, logging -> {trader.trades_path}\n")

    holder = {"pairings": {}, "lock": threading.Lock(), "stop": False}
    worker = threading.Thread(target=discovery_thread, args=(holder, args.discover), daemon=True)
    worker.start()

    seen_balls = {}
    primed = set()

    while True:
        loop_start = time.perf_counter()

        with holder["lock"]:
            pairings = dict(holder["pairings"])

        for slug, pairing in pairings.items():
            try:
                html = session.get(commentary_url(pairing["cb_id"]), headers=HEADERS, timeout=15).text
                balls = extract_balls(decode_blob(html))
                recv_ms = int(time.time() * 1000)
            except (requests.RequestException, ValueError, CommentaryParseFailed):
                continue

            match_seen = seen_balls.setdefault(pairing["cb_id"], set())
            fresh = []
            for ball in balls:
                key = (ball.get("inningsId"), ball.get("ballMetric"), ball.get("timestamp"))
                if key in match_seen:
                    continue
                match_seen.add(key)
                fresh.append(ball)

            if pairing["cb_id"] not in primed:
                primed.add(pairing["cb_id"])
                continue

            for ball in sorted(fresh, key=lambda b: b.get("timestamp", 0)):
                flags = {str(e).lower() for e in (ball.get("event") or [])}
                if flags & WICKET_TOKENS:
                    trader.try_enter(session, pairing, ball, recv_ms)

        trader.process_exits(session, int(time.time() * 1000))

        if int(loop_start) % 60 < args.poll:
            print(
                f"[{time.strftime('%H:%M:%S')}] {len(pairings)} paired, "
                f"{len(trader.open_positions)} open, bankroll ${trader.bankroll:.2f}, "
                f"realized ${trader.realized:+.3f} ({trader.wins}/{trader.n_trades})"
            )

        time.sleep(max(0.0, args.poll - (time.perf_counter() - loop_start)))


def selftest(args):
    dns_bypass.install()
    session = requests.Session()
    resolved = resolve_tokens(session, args.selftest)
    if not resolved:
        raise SystemExit(f"could not resolve slug {args.selftest}")
    outcomes = resolved["outcomes"]
    name = list(outcomes)[0]
    token = outcomes[name]
    print(f"selftest market: {resolved['question']}")
    print(f"simulating: buy {name} with ${args.stake:.2f}, hold {args.hold}s, then exit\n")
    book = fetch_book(session, token)
    print(f"book: bid {book['best_bid']} / ask {book['best_ask']} mid {book['mid']}")
    print(f"  asks top: {book['asks'][:3]}")
    print(f"  bids top: {book['bids'][:3]}")
    shares, spent, vwap, used = buy_vwap(book["asks"], args.stake)
    print(f"\nENTRY: {shares:.3f} shares @ vwap {vwap} for ${spent:.3f}  levels {used}")
    print(f"waiting {args.hold}s...")
    time.sleep(args.hold)
    book2 = fetch_book(session, token)
    proceeds, filled, evwap, eused, partial = sell_vwap(book2["bids"], shares, book2["mid"])
    print(f"EXIT : {filled:.3f} shares @ vwap {evwap} for ${proceeds:.3f}  partial={partial}")
    print(f"mid {book['mid']} -> {book2['mid']}   PnL ${proceeds - spent:+.4f}")


def main():
    parser = argparse.ArgumentParser(description="Paper-trade cricket wickets against the real Polymarket book.")
    parser.add_argument("--out", type=Path, default=Path("data/paper"))
    parser.add_argument("--bankroll", type=float, default=5.0)
    parser.add_argument("--stake", type=float, default=1.0)
    parser.add_argument("--hold", type=float, default=60.0)
    parser.add_argument("--min-price", type=float, default=0.25)
    parser.add_argument("--max-price", type=float, default=0.75)
    parser.add_argument("--max-detect-lag", type=float, default=60.0)
    parser.add_argument("--poll", type=float, default=3.0)
    parser.add_argument("--discover", type=float, default=120.0)
    parser.add_argument("--selftest", default=None, help="slug to run a one-shot fill/exit mechanics test")
    args = parser.parse_args()

    if args.selftest:
        selftest(args)
        return
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    sys.exit(main())
