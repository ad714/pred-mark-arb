"""Ladder maths shared by the cross-venue scanner and the hourly watcher.

Both legs of a cross-venue lock are buys. Long YES on one venue and long NO on the
other pays exactly $1 whichever way the event lands, so capital per share is the sum
of the two leg prices and the profit is 1 minus that. Nothing here shorts anything.

Both venues charge the taker `size * price * (1 - price) * rate`, and both rates have
to be charged: Pascal's is 2% and Polymarket's `feeSchedule` is 4%, which at even
money is a full cent a share and larger than any edge seen so far.
"""


def ladder(levels, ascending):
    """Normalize a venue's book side to a sorted [(price, size)] list."""
    out = []
    for level in levels or []:
        if isinstance(level, dict):
            out.append((float(level["price"]), float(level["size"])))
        else:
            out.append((float(level[0]), float(level[1])))
    return sorted(out, key=lambda level: level[0], reverse=not ascending)


def fee_per_share(price, rate, exponent=1):
    if not rate:
        return 0.0
    return rate * (price ** exponent) * ((1 - price) ** exponent)


def walk(buy_side, sell_side, buy_fee, sell_fee, capital_cap=None, exponent=1):
    """Cross a buy ladder against a sell ladder, stopping at capital_cap.

    `sell_side` is the other venue's bid ladder; buying its complement costs
    1 - bid, so a pair fills while bid > ask. buy_fee and sell_fee are the taker
    rates of the venue each leg trades on. Returns the best fill, or None if the
    books never cross or the cap admits nothing.
    """
    buys, sells = list(buy_side), list(sell_side)
    filled = profit = capital = fees = 0.0
    best = None
    buy_index = sell_index = 0

    while buy_index < len(buys) and sell_index < len(sells):
        buy_price, buy_size = buys[buy_index]
        sell_price, sell_size = sells[sell_index]
        if sell_price <= buy_price:
            break

        size = min(buy_size, sell_size)
        per_share = buy_price + 1 - sell_price
        if capital_cap is not None:
            room = capital_cap - capital
            if room <= 1e-9:
                break
            if per_share > 0:
                size = min(size, room / per_share)
        if size <= 1e-9:
            break

        fee = size * (fee_per_share(buy_price, buy_fee, exponent)
                      + fee_per_share(sell_price, sell_fee, exponent))
        filled += size
        capital += size * per_share
        fees += fee
        profit += size * (sell_price - buy_price) - fee

        if best is None or profit > best["profit"]:
            best = {"profit": profit, "shares": filled, "capital": capital,
                    "fees": fees, "edge": profit / filled,
                    "buy": buy_price, "sell": sell_price}

        buys[buy_index] = (buy_price, buy_size - size)
        sells[sell_index] = (sell_price, sell_size - size)
        if buys[buy_index][1] <= 1e-9:
            buy_index += 1
        if sells[sell_index][1] <= 1e-9:
            sell_index += 1

    return best
