"""Keep one GitHub issue in sync with the cross-venue watcher.

One open issue at a time, edited in place each run, so an hourly schedule does not
turn into an hourly inbox. A comment is only posted when the set of live pairs
actually changes, and the issue closes itself once the books stop crossing.
"""

import json
import subprocess
import sys
from pathlib import Path

LABEL = "crossvenue"
TITLE = "Cross-venue lock open"
ALERT = Path("alert.json")


def gh(*args, check=False):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
    return result


LOOKUP_FAILED = object()


def open_issue():
    """The open alert issue, None if there is none, LOOKUP_FAILED if gh broke.

    Treating a failed lookup as "no issue" would open a duplicate every time the
    API hiccups, so the caller has to be able to tell the two apart.
    """
    result = gh("issue", "list", "--label", LABEL, "--state", "open",
                "--limit", "1", "--json", "number,body")
    if result.returncode != 0:
        return LOOKUP_FAILED
    try:
        rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return LOOKUP_FAILED
    return rows[0] if rows else None


def when(hit):
    return f"{hit['days'] * 24:.1f}h" if hit["days"] < 1 else f"{hit['days']:.1f}d"


def body(alert):
    lines = [
        f"Checked {alert['checked_at']}. Every pair below is an exact join on "
        "Polymarket's own outcome token id, so both legs settle the same event.",
        "",
        "Both legs are buys. The pair pays $1 whichever way it lands, so `capital` "
        "is the whole position and `profit` is locked at fill.",
        "",
        "| resolves in | profit | capital | edge/share | pair | how |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for hit in alert["hits"]:
        lines.append(
            f"| {when(hit)} | ${hit['profit']:.2f} | ${hit['capital']:.2f} | "
            f"{hit['edge']:.4f} | {hit['event']} - {hit['outcome']} | "
            f"{hit['side']} at {hit['buy']:.3f} against {hit['sell']:.3f} |"
        )
    lines += [
        "",
        f"Pascal symbols: {', '.join(h['symbol'] for h in alert['hits'])}",
        "",
        "Books move. Re-price before sending anything.",
    ]
    return "\n".join(lines)


def main():
    if not ALERT.exists():
        print("no alert.json, nothing to do")
        return 0
    try:
        alert = json.loads(ALERT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"could not read alert.json ({exc}); leaving the alert state untouched")
        return 1
    # The title is driven by hits[0], so do not rely on another file's sort order.
    hits = sorted(alert.get("hits") or [], key=lambda hit: hit.get("days", 0))
    issue = open_issue()

    if issue is LOOKUP_FAILED:
        print("could not list issues; leaving the alert state untouched")
        return 1

    if not hits:
        if issue:
            gh("issue", "comment", str(issue["number"]),
               "--body", f"Books no longer cross as of {alert['checked_at']}. Closing.")
            gh("issue", "close", str(issue["number"]), check=True)
            print(f"closed #{issue['number']}")
        else:
            print("no hits, no open issue")
        return 0

    soonest = hits[0]
    title = f"{TITLE}: {soonest['event']} in {when(soonest)}"
    text = body(alert)

    if not issue:
        gh("label", "create", LABEL, "--color", "0E8A16",
           "--description", "Cross-venue arbitrage watcher")
        result = gh("issue", "create", "--title", title, "--label", LABEL,
                    "--body", text, check=True)
        print(result.stdout.strip() or "issue created")
        return 0

    number = str(issue["number"])
    gh("issue", "edit", number, "--title", title, "--body", text, check=True)
    before = {line for line in (issue.get("body") or "").splitlines()
              if line.startswith("Pascal symbols:")}
    after = {line for line in text.splitlines() if line.startswith("Pascal symbols:")}
    if before != after:
        gh("issue", "comment", number,
           "--body", f"Live pairs changed as of {alert['checked_at']}:\n\n{text}")
        print(f"updated and commented on #{number}")
    else:
        print(f"updated #{number}, same pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
