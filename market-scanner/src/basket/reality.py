FIELD_TYPES = {
    "ballot": "Ballot election",
    "coalition": "Chosen by a body after the vote",
    "buckets": "Exhaustive numeric buckets",
    "roster": "Fixed roster or field",
    "discretionary": "Somebody decides, whenever they like",
    "awards": "Award with nominees not yet set",
}

VERDICTS = {
    "field-safe": "Field is closed. Nobody new can appear.",
    "watch": "Field closes on a known date. Safe only after it passes.",
    "field-open": "Field is open. A name that is not on the board can still win.",
}

GENERIC = {
    "coalition": dict(
        type="coalition", closure="open", verdict="field-open", evidence="rules",
        who="Any person the winning coalition agrees on, including someone not on this board "
            "at all. And nobody at all, if the talks deadlock past the backstop date.",
        detail="Nobody votes for this job directly. The public elects an assembly, then the "
               "parties negotiate and the assembly elects whoever the deal produces. The "
               "candidate list on a prediction market is a guess at that deal, not a ballot. "
               "There are two separate ways this pays you nothing, and the rules spell out "
               "both. First, the deal lands on somebody who is not on the board. Second, and "
               "easier to miss, the rules say an interim or caretaker office-holder does not "
               "count, and if nobody is formally elected by the backstop date the market "
               "resolves to Other. So a deadlock wrecks the basket just as thoroughly as a "
               "surprise winner, and it does so no matter who the candidates are.",
    ),
    "discretionary": dict(
        type="discretionary", closure="open", verdict="field-open", evidence="structural",
        who="Anyone the decision-maker picks. There is no ballot and no shortlist.",
        detail="One person or a small group decides this, on their own timetable, from a pool "
               "with no formal limit. A matchmaker can book any fighter on the roster; an "
               "appointment can go to any person alive. No amount of cheapness makes a "
               "complete basket possible when the set of outcomes has no edge.",
    ),
    "awards": dict(
        type="awards", closure="open", verdict="field-open", evidence="structural",
        who="Any eligible work or person, including ones not yet nominated or released.",
        detail="The nominee list does not exist yet, or is still growing. Until nominations "
               "close, the outcome space is open and the placeholder slots on this market are "
               "exactly what they look like: room to add names later.",
    ),
    "roster": dict(
        type="roster", closure="closed", verdict="field-safe", evidence="structural",
        who="Nobody new. The field is the set of teams or players already competing.",
        detail="The field for this is fixed by the season. No new entrant can appear, so the "
               "only question is whether every competitor still mathematically alive is one "
               "you can buy. Check the outcome list below against the ones still in it.",
    ),
    "ballot": dict(
        type="ballot", closure="unverified", verdict="watch", evidence="structural",
        who="Any candidate who can still file nomination papers. Whether that window is shut "
            "has not been checked for this market.",
        detail="This is decided by a public vote on a printed ballot, so the field does close "
               "at some point and after that nobody new can appear. That is the good news. "
               "The catch is that this particular market has not been checked against its "
               "electoral authority, so the nomination deadline is unknown here. Find that "
               "date, confirm it has passed, then compare the certified ballot against the "
               "names you can buy. Until then treat the outcome list as possibly incomplete.",
    ),
}

MARKETS = {
    "Republican Presidential Nominee 2028": dict(
        type="ballot", closure="open", verdict="field-open", evidence="structural",
        who="Any Republican who declares between now and the 2028 primaries. The field does "
            "not exist yet.",
        detail="Nominations for 2028 are more than two years away and not a single primary "
               "ballot has been drawn. Every serious contender for this is a person who has "
               "not declared. Robert F. Kennedy Jr. already sits in the outcome list with no "
               "offers against him, which is the mechanism in miniature: a name gets added, "
               "and if it wins, a basket bought before it appeared pays nothing. Capital is "
               "also locked for over two years.",
    ),
    "U.K. Annual Inflation 2026": dict(
        type="buckets", closure="closed", verdict="field-open", evidence="researched",
        who="Nothing new can appear, but the single bucket you cannot buy is 3.0-3.4%, and "
            "that is where the official forecast sits.",
        detail="The buckets cover every possible number, so the field is closed by "
               "construction. That is not the problem. The problem is that one bucket has no "
               "offers, and it is the one the Bank of England's own central projection lands "
               "in: the July 2026 Monetary Policy Report puts CPI at about 3.2% in 2026 Q4. "
               "You would be buying every outcome except the single most likely one. This is "
               "the clearest losing basket on the board and the price does not show it.",
        sources=[["Bank of England Monetary Policy Report, July 2026",
                  "https://www.bankofengland.co.uk/monetary-policy-report/2026/july-2026"],
                 ["ONS Consumer Price Inflation releases",
                  "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/previousreleases"]],
    ),
    "WNBA: Three Point Percentage Leader": dict(
        type="roster", closure="closed", verdict="field-open", evidence="researched",
        who="Any qualified player in the league. Only 15 are listed and the ones actually "
            "leading the stat are not among them.",
        detail="No new player can join mid-season, so the field is closed in the trivial "
               "sense. That is not the test. The test is whether the names you can buy cover "
               "the players who can actually win it, and here they do not come close. On the "
               "2026 season leaderboard the top thirteen by three point percentage are Serah "
               "Williams at 50.0%, Kelsey Mitchell at 45.5%, Sophie Cunningham, Leonie "
               "Fiebich, Julie Allemand, Kayla McBride, Aliyah Boston, Napheesa Collier, Han "
               "Xu, Carla Leite, Kaitlyn Chen, Maddy Siegrist and Michaela Onyenwere. Not one "
               "of them is buyable. The only listed name anywhere near the top is A'ja Wilson "
               "at 39.8%, ranked fourteenth. The board is stocked with famous shooters, "
               "Bueckers, Clark, Ionescu, Plum, who are not leading this particular stat. "
               "Buy the whole set and you are betting the leaderboard inverts in its final "
               "days. It resolves to Other, which nobody will sell you.",
        sources=[["WNBA 2026 three point percentage leaders",
                  "https://www.statpick.ai/stats/wnba/leaders/fg3_pct"],
                 ["ESPN WNBA player stat leaders, 2026",
                  "https://www.espn.com/wnba/stats"]],
    ),
"F1 Drivers' Champion": dict(
        type="roster", closure="closed", verdict="field-safe", evidence="researched",
        who="Nobody. Every driver with any mathematical chance is buyable, and the ones who "
            "are not are out of contention on points.",
        detail="This is the one big market where the field check actually passes. The 2026 "
               "standings run Antonelli 267, Russell 201, Hamilton 191, Norris 171, Leclerc "
               "155, Verstappen 127, Piastri 116, Hadjar 71, Lawson 51, Gasly 41. Every one of "
               "those ten is buyable. The outcomes with no offers are Alonso, Stroll, Ocon, "
               "Hulkenberg, Albon, Sainz, Bottas and Perez, all far enough back that they "
               "cannot win it. No new driver can join a season in progress. So the Other "
               "outcome, while unbuyable, is effectively dead: there is no path to it. The "
               "residual gap between mid prices and a dollar here is spread, not wildcard risk.",
        sources=[["Formula 1 official 2026 drivers standings",
                  "https://www.formula1.com/en/results/2026/drivers"]],
    ),
    "MLB: 2026 NL East Champion": dict(
        type="roster", closure="closed", verdict="field-open", evidence="researched",
        who="The New York Mets and the Washington Nationals. Both are in this division and "
            "neither can be bought.",
        detail="The NL East has five teams and you can only buy three of them: Atlanta at 86%, "
               "Philadelphia at 9%, Miami at about 0%. The Mets and the Nationals are the other "
               "two, they are unbuyable, and a division title going to either wrecks the whole "
               "basket. No new team can appear, so the field is closed, but closed is not the "
               "same as covered. With a month of baseball left the market puts roughly 6% on "
               "the two teams you cannot own, against a profit that absorbs 1.4%. That is not "
               "an arbitrage, it is a bet that the Mets do not get hot.",
        sources=[["MLB standings",
                  "https://www.mlb.com/standings"]],
    ),
    "OK-02 House Election Winner": dict(
        type="ballot", closure="closed", verdict="field-open", evidence="researched",
        who="Erik Terwey and William Webb. Both are on the certified November ballot and "
            "neither is buyable.",
        detail="The field is closed, the primary is long past, and the general election ballot "
               "for 3 November 2026 carries Josh Brecheen, Erik Terwey and William Webb. Only "
               "Brecheen is buyable. Worse, the market lists a buyable outcome called Brandon "
               "Wade (D) who does not appear on that ballot at all, so the outcome list and "
               "the real ballot have drifted apart. Brecheen is a heavy favourite in a "
               "safe Republican seat, which is why this looks cheap, but you would be buying a "
               "set that does not match the actual ballot and paying $739 to do it.",
        sources=[["Ballotpedia, Oklahoma's 2nd Congressional District election 2026",
                  "https://ballotpedia.org/Oklahoma's_2nd_Congressional_District_election,_2026"]],
    ),
    "MI-13 House Election Winner": dict(
        type="ballot", closure="closed", verdict="field-open", evidence="researched",
        who="Shelby Campbell, Simone Coleman, Christopher Dardzinski and Maurice Morton, all "
            "on the ballot, none of them buyable.",
        detail="The November ballot here runs Donavan McKinney as the Democratic nominee "
               "against a Republican plus four others: Shelby Campbell as an independent, "
               "Simone Coleman for the Working Class Party, Christopher Dardzinski for the "
               "U.S. Taxpayers Party and Maurice Morton as an independent. You can buy two "
               "names, and one of them, T.P. Nykoriak (R), does not match the Republican who "
               "actually won the August primary. Six or more candidates on the ballot, two "
               "buyable, and $1,059 of capital to earn $8. The seat is safely Democratic so "
               "the favourite will almost certainly hold, but the basket is not a basket.",
        sources=[["Ballotpedia, Michigan's 13th Congressional District election 2026",
                  "https://ballotpedia.org/Michigan's_13th_Congressional_District_election,_2026"],
                 ["Michigan Advance 2026 voter guide, 13th District",
                  "https://michiganadvance.com/voter-guides/contests/13th-district-representative-in-congress/"]],
    ),
    "Central Coast Mayoral Election Winner": dict(
        type="ballot", closure="closing", verdict="watch", evidence="researched",
        closes="21 September 2026",
        who="Any resident who files before nominations close. Right now the window is open.",
        detail="This is Central Coast Council in Tasmania, not the New South Wales one of the "
               "same name. Nominations for the 27 October local elections opened on 7 "
               "September 2026 and close on 21 September 2026, so as things stand a third "
               "candidate can still file and the board holds only two names. The two buyable "
               "names are the real ones so far: Cheryl Fuller, the sitting mayor who took "
               "54.5% in 2022, against Garry Carpenter, who took 45.5%. Once nominations shut "
               "the Tasmanian Electoral Commission publishes the final list. Check it against "
               "those two names then, not now.",
        sources=[["Tasmanian Electoral Commission, 2026 local government elections",
                  "https://www.tec.tas.gov.au/local-government/elections-2026/index.html"],
                 ["Central Coast Council, meet the candidates",
                  "https://www.centralcoast.tas.gov.au/events/meet-the-candidates/"]],
    ),
    "Which movie has biggest opening weekend in 2026?": dict(
        type="roster", closure="closed", verdict="field-open", evidence="researched",
        who="Toy Story 5, Star Wars: The Mandalorian and Grogu, The Odyssey, Super Mario "
            "Galaxy, Project Hail Mary, Scream 7, Michael and Wuthering Heights. All real "
            "2026 releases, none of them buyable.",
        detail="The slate for 2026 is fixed enough to call the field closed, but the buyable "
               "list is only four titles: Avengers: Doomsday at 47%, Spider-Man: Brand New Day "
               "at 46%, and Dune: Messiah and Hunger Games at roughly nothing. Every other "
               "major 2026 release sits in the outcome list with no offers against it, "
               "including Toy Story 5 and the Mandalorian film, either of which can post a "
               "very large opening. The two Marvel titles are genuinely the favourites, which "
               "is why the basket looks almost complete on price, but you are leaving eight "
               "named tentpoles uncovered to earn $5.",
    ),
    "#2 US Spotify Song 2026": dict(
        type="awards", closure="open", verdict="field-open", evidence="researched",
        who="Any song released between now and the end of the year, plus the twenty-seven "
            "unnamed song slots already sitting on the board.",
        detail="A year-end streaming chart is not a closed field in September. New releases "
               "enter the chart every week and the market already carries twenty-seven empty "
               "slots named Song A through Song T, which exist precisely so tracks can be "
               "added later. Two songs carry almost all the price, Earrings by Malcom Todd at "
               "66% and Man I Need by Olivia Dean at 23%, and the rest of the buyable list is "
               "catalogue material at zero. There is no version of this that is a complete "
               "basket.",
    ),
    "MLB: NL Manager of the Year": dict(
        type="awards", closure="closed", verdict="watch", evidence="researched",
        who="Nobody new. Every National League manager is already in the outcome list, but "
            "this is a vote, and votes are not a closed field in the way standings are.",
        detail="The buyable list covers the real National League bench: Pat Murphy at 46%, "
               "Walt Weiss at 25%, plus Counsell, Lovullo, Mendoza, Francona, Roberts, "
               "Thomson and the rest. The unbuyable outcomes are placeholders named Manager A "
               "through Manager E, not real people, so the coverage here is genuinely better "
               "than most of this board. The residual risk is that this is decided by writers "
               "voting after the season, not by a table, and the gap between mid prices and a "
               "dollar is wider than the profit absorbs.",
    ),
    "#3 AI Lab end of September? (Style Control On)": dict(
        type="roster", closure="closed", verdict="watch", evidence="researched",
        who="Only a lab already on the leaderboard. Twenty-one are buyable, which covers every "
            "lab with a realistic model at the top.",
        detail="This resolves off a public leaderboard position on a fixed date, and the "
               "buyable list is long: Google at 51%, Meta 16%, OpenAI 9%, Alibaba, Moonshot, "
               "Anthropic, DeepSeek, ByteDance, Mistral, Tencent and more. The unbuyable "
               "outcomes are Company A through Company K, placeholders rather than real labs. "
               "So the field is well covered. What makes this unsafe is not a wildcard, it is "
               "that a third place ranking moves whenever anyone ships a model, and the whole "
               "thing settles in under three weeks for $1.37.",
    ),
    "Next President of Kosovo?": dict(
        type="coalition", closure="open", verdict="field-open", evidence="researched",
        who="Anyone the Assembly can find two thirds for, and realistically nobody at all, "
            "because that is what has happened for nearly two years.",
        detail="Kosovo has had no permanent president since Vjosa Osmani's term ended on 4 "
               "April 2026. Albulena Haxhiu has been acting president since, and the market "
               "rules say an acting or caretaker holder does not count for resolution. The "
               "Assembly needs a two thirds majority to elect a president and has repeatedly "
               "failed to find one; the parties missed a March deadline, a snap election "
               "followed on 7 June, and Albin Kurti's Vetevendosje won it without the two "
               "thirds required. In late August VV and the opposition LDK agreed to back "
               "Bekim Sejdiu, a law professor and former ambassador to Turkey, and he is the "
               "buyable favourite here at 34%. So there is a deal, but there has been a deal "
               "before. Under the constitution, failing to elect a head of state triggers yet "
               "another parliamentary election, and if no president takes a full term by 30 "
               "April 2027 this market resolves to Other, which nobody will sell you.",
        sources=[["Reuters via Internazionale, Kosovo parties strike deal to elect president",
                  "https://www.internazionale.it/ultime-notizie-reuters/2026/08/31/kosovo-parties-strike-deal-to-elect-president-breaking-deadlock"],
                 ["Balkan Insight, opposition snubs acting president amid parliamentary crisis",
                  "https://balkaninsight.com/2026/08/18/kosovo-opposition-snubs-acting-presidents-meeting-amid-parliamentary-crisis/bi/"],
                 ["Al Jazeera, Kosovo votes again amid political deadlock",
                  "https://www.aljazeera.com/news/2026/6/7/kosovo-votes-again-amid-political-deadlock-seeking-eu-and-nato-progress"]],
    ),
    "West Vancouver, BC Mayoral Election Winner": dict(
        type="ballot", closure="closing", verdict="watch", evidence="researched",
        closes="11 September 2026, 4pm Pacific",
        who="Any candidate who files nomination papers before the deadline. After it passes, "
            "nobody.",
        detail="British Columbia runs a fixed nomination window for the 17 October local "
               "elections: it opened on 1 September 2026 and closes at 4pm Pacific on 11 "
               "September 2026. Until that clock runs out a third candidate can still file "
               "and the board here only has two names you can buy. Once it passes, Elections "
               "BC publishes the final list and this becomes a genuinely closed field. The "
               "honest play is to wait for the certified list and check it against the two "
               "buyable names before committing a cent.",
        sources=[["Elections BC, 2026 General Local Elections",
                  "https://elections.bc.ca/local-elections/2026-general-local-elections/"],
                 ["District of West Vancouver election office",
                  "https://election.westvancouver.ca/"]],
    ),
    "Morocco Legislative Elections: Party Winner": dict(
        type="ballot", closure="closed", verdict="field-safe", evidence="researched",
        who="Only a party already contesting the 23 September vote. 27 parties are running "
            "and the 8 you can buy are the only ones with a realistic path to most seats.",
        detail="The ballot is set and campaigning opened on 10 September. Morocco elects 305 "
               "of 395 seats across 92 local constituencies on a quotient computed from "
               "registered voters, with no threshold, which spreads seats widely but makes it "
               "near impossible for a minor party to take the largest bloc. The eight listed "
               "parties took 385 of 395 seats in 2021. The real exposure is not a surprise "
               "party, it is the rules clause: if results are not definitively known by 31 "
               "July 2027 the market resolves to Other, which you cannot buy.",
        sources=[["Morocco World News, campaign opens with 27 parties",
                  "https://www.moroccoworldnews.com/2026/09/337838/moroccos-13-day-election-campaign-opens-with-27-parties-chasing-395-seats/"],
                 ["2026 Moroccan general election",
                  "https://en.wikipedia.org/wiki/2026_Moroccan_general_election"]],
    ),
    "World Cup 2030: Location of Final": dict(
        type="roster", closure="closed", verdict="field-safe", evidence="rules",
        who="Nobody. Every outcome including the catch-all is buyable.",
        detail="This is the rare complete basket. The outcome list carries an explicit "
               "Other / Unconfirmed bucket and that bucket has offers against it, so every "
               "branch of the future is covered by something you can own. There is no "
               "unbuyable outcome to get wrecked by. What is left is execution risk and fees, "
               "not wildcard risk.",
    ),
}

CATEGORY_HINTS = [
    ("Regional Board Chair", "coalition"),
    ("Next Prime Minister", "coalition"),
    ("Next President of", "coalition"),
    ("Governing Mayor", "coalition"),
    ("Press Secretary", "discretionary"),
    ("fight next", "discretionary"),
    ("Trump endorse", "discretionary"),
    ("AI Lab", "discretionary"),
    ("Spotify", "awards"),
    ("Grammys", "awards"),
    ("Manager of the Year", "awards"),
    ("biggest opening weekend", "awards"),
    ("Champion", "roster"),
    ("Percentage Leader", "roster"),
    ("Election Winner", "ballot"),
    ("Election:", "ballot"),
    ("Elections", "ballot"),
    ("Senate and Governor", "ballot"),
    ("state elec", "buckets"),
    ("Inflation", "buckets"),
]


def classify(title):
    if title in MARKETS:
        base = dict(GENERIC.get(MARKETS[title].get("type"), {}))
        base.update(MARKETS[title])
        return base
    for needle, kind in CATEGORY_HINTS:
        if needle.lower() in title.lower():
            return dict(GENERIC[kind])
    return dict(GENERIC["ballot"], evidence="structural", closure="open",
                verdict="watch",
                who="Not established. Treat the outcome list as possibly incomplete.",
                detail="This market has not been checked against a primary source. Read its "
                       "rules below and satisfy yourself that the outcomes you can buy cover "
                       "every way it can resolve before risking anything.")

CATCHALL_NOTE = (
    "This market carries an explicit Other outcome and nobody is selling it. Other is the "
    "catch-all: every winner that is not separately listed resolves there. So a complete "
    "basket is impossible here by construction, no matter how cheap the listed legs look. "
    "The only question left is how much probability really sits outside the names you can buy."
)

COMPLETE_NOTE = (
    "Every outcome on this market is buyable, including its catch-all. There is no unbuyable "
    "branch of the future, so there is no wildcard that can wreck you. Whatever gap you see "
    "between the mid prices and a dollar is the spread, not risk."
)

COVERAGE_NOTE = (
    "By this market's own mid prices, the outcomes you can buy account for only {cov:.0f}% of "
    "the probability. The other {gap:.0f}% sits on outcomes you cannot own, on the spread, or "
    "on both. Your profit can absorb {be:.0f}%. Part of that gap is just a wide book, but "
    "until somebody checks the real field against the list, assume the worse reading."
)


def coverage_verdict(base, coverage, breakeven, has_other, n_dark, dark_max=0.0):
    out = dict(base)
    if base.get("evidence") == "researched":
        return out
    if n_dark == 0:
        out["verdict"] = "field-safe"
        out["closure"] = "closed"
        return out
    if dark_max > breakeven:
        out["verdict"] = "field-open"
        out["closure"] = "open"
        return out
    if has_other and out["verdict"] == "field-safe":
        out["verdict"] = "watch"
    gap = max(0.0, 1.0 - coverage)
    if has_other and gap > breakeven:
        out["verdict"] = "field-open"
        out["closure"] = "open"
    elif gap > breakeven:
        out["verdict"] = "watch"
    return out
