import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market-scanner"))

from src.crossvenue.book import fee_per_share, ladder, walk

PASCAL_FEE = 0.02
POLY_FEE = 0.04


def close(left, right, tolerance=1e-6):
    return abs(left - right) <= tolerance


def main():
    failures = []

    # Books that do not cross are not an arb, in either orientation.
    if walk([(0.40, 100)], [(0.38, 100)], PASCAL_FEE, POLY_FEE) is not None:
        failures.append("a buy above the other venue's bid must not report a fill")
    if walk([], [(0.90, 100)], PASCAL_FEE, POLY_FEE) is not None:
        failures.append("an empty ladder must not report a fill")

    # Buy 0.30 against a 0.35 bid. BOTH venues take a fee, each on its own leg's
    # price: 0.30*0.70*2% on the buy and 0.35*0.65*4% on the sell.
    buy_fee = 100 * 0.30 * 0.70 * PASCAL_FEE
    sell_fee = 100 * 0.35 * 0.65 * POLY_FEE
    uncapped = walk([(0.30, 100)], [(0.35, 100)], PASCAL_FEE, POLY_FEE)
    if uncapped is None:
        failures.append("crossed books must report a fill")
    else:
        if not close(uncapped["shares"], 100):
            failures.append(f"uncapped fill took {uncapped['shares']} of 100 shares")
        if not close(uncapped["fees"], buy_fee + sell_fee):
            failures.append(f"fees {uncapped['fees']} do not charge both venues")
        if not close(uncapped["profit"], 100 * 0.05 - buy_fee - sell_fee):
            failures.append(f"uncapped profit {uncapped['profit']} is wrong")
        # Both legs are buys: 0.30 here plus 1 - 0.35 there.
        if not close(uncapped["capital"], 100 * 0.95):
            failures.append(f"uncapped capital {uncapped['capital']} is not 95.00")

    # Forgetting the second venue's fee is the bug this guard exists for.
    one_sided = walk([(0.30, 100)], [(0.35, 100)], PASCAL_FEE, 0.0)
    if one_sided is None or one_sided["profit"] <= uncapped["profit"]:
        failures.append("charging only one venue must look more profitable")

    # The cap is on capital across both legs, not on the notional of one.
    capped = walk([(0.30, 100)], [(0.35, 100)], PASCAL_FEE, POLY_FEE, capital_cap=25.0)
    if capped is None:
        failures.append("capped walk must still report a fill")
    else:
        if capped["capital"] > 25.0 + 1e-6:
            failures.append(f"capped walk tied up {capped['capital']}, over the $25 cap")
        if not close(capped["shares"], 25.0 / 0.95):
            failures.append(f"capped fill took {capped['shares']} shares, not 26.32")
        if capped["profit"] >= uncapped["profit"]:
            failures.append("capping capital must not increase profit")

    # A cap smaller than one share's capital must not fabricate a fill.
    if walk([(0.30, 100)], [(0.35, 100)], PASCAL_FEE, POLY_FEE, capital_cap=0.0):
        failures.append("a zero cap must not report a fill")

    # Deeper levels are only worth taking while they still cross.
    deep = walk([(0.30, 10), (0.36, 100)], [(0.35, 200)], PASCAL_FEE, POLY_FEE)
    if deep is None or not close(deep["shares"], 10):
        failures.append("the walk must stop at the level where the books stop crossing")

    # Fees are symmetric in p, so buying the complement costs the same to trade.
    if not close(fee_per_share(0.35, POLY_FEE), fee_per_share(0.65, POLY_FEE)):
        failures.append("fee must be symmetric about 0.5")
    if not close(fee_per_share(0.5, 0.04), 0.01):
        failures.append("4% at even money must be a full cent a share")

    # Book sides arrive as dicts from Polymarket and as pairs from Pascal.
    if ladder([{"price": "0.4", "size": "5"}], True) != ladder([["0.4", "5"]], True):
        failures.append("dict and list book levels must normalize the same way")
    if ladder([["0.4", "5"], ["0.2", "7"]], True)[0][0] != 0.2:
        failures.append("ascending ladder must put the cheapest ask first")
    if ladder([["0.4", "5"], ["0.2", "7"]], False)[0][0] != 0.4:
        failures.append("descending ladder must put the best bid first")

    for line in failures:
        print("FAIL " + line)
    print(f"15 checks, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
