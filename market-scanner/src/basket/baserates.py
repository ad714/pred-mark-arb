BASE_RATES = {
    "coalition": dict(
        headline="All three of Sweden's largest regions changed hands last time",
        detail="This is not a rare event, it is the normal one. At the 2022 Swedish regional "
               "elections the right lost all three of the largest regions: Stockholm after "
               "sixteen straight years in power, plus Vastra Gotaland and Skane. In Stockholm "
               "the chair went to Aida Hadzialic of the Social Democrats, a change of both "
               "bloc and person, settled in negotiation after the votes were counted. A market "
               "pricing a named person to take one of these jobs is pricing the outcome of a "
               "negotiation that has not started yet.",
        rules="The public elects the council or assembly. That body then elects the office "
              "holder from among its own members as part of the coalition deal. There is no "
              "public vote for the job and no nomination deadline, so the pool of possible "
              "winners is every member of the incoming body. Two clauses matter more than the "
              "candidate list: an interim or caretaker holder explicitly does not count for "
              "resolution, and if nobody is formally elected by the stated backstop date the "
              "market resolves to Other. Every one of the nine coalition markets on this board "
              "carries both clauses.",
        sources=[["The Local, who controls Sweden's regions and municipalities",
                  "https://www.thelocal.se/20220830/in-data-who-controls-swedens-regions-and-municipalities"],
                 ["Region Stockholm", "https://en.wikipedia.org/wiki/Region_Stockholm"]],
    ),
    "discretionary": dict(
        headline="No deadline and no shortlist, so there is no base rate to quote",
        detail="There is nothing to measure a frequency against. A booking or an appointment "
               "is made when the decision-maker feels like it, from a pool with no formal "
               "boundary, and it can change again the next day. Injuries, negotiations and "
               "politics all reopen the field after it looks settled. The only honest base "
               "rate is that announced names change often enough that the people involved "
               "treat them as provisional until something is signed.",
        rules="One person or a small group decides. No filing window, no certified list, and "
              "nothing that closes the outcome space before the market resolves.",
    ),
    "awards": dict(
        headline="The candidate set can only grow between now and resolution",
        detail="New songs chart every week, new films release, and nominee lists get published "
               "months after a market opens. The field never shrinks. Every placeholder slot "
               "sitting on the board is reserved space for a name that has not appeared yet, "
               "and those slots do get filled.",
        rules="An eligibility window plus a voting or measurement body. Until nominations "
              "close or the measurement period ends, entries keep arriving.",
    ),
    "ballot": dict(
        headline="Once nominations close the field cannot grow at all",
        detail="This is the one structure where the wildcard genuinely falls to zero, and it "
               "does so on a known date. Before it, anyone eligible can file. After it, the "
               "certified ballot is the complete and final list of people who can win. The "
               "failure mode is not a surprise entrant, it is a prediction market whose "
               "outcome list was written before the ballot was certified and then never "
               "updated to match it.",
        rules="A statutory nomination window run by an electoral commission, which publishes "
              "the certified candidate list when it closes. That list is the entire outcome "
              "space.",
    ),
    "roster": dict(
        headline="The field closed when the season started",
        detail="Nobody joins a competition already in progress, so the wildcard is not a new "
               "entrant. It is a competitor already in the field who is missing from the "
               "market's outcome list, which is a different and far more checkable problem: "
               "put the standings next to the buyable names and the answer is immediate.",
        rules="Entry closed at the start of the season. Resolution follows the official "
              "standings or statistics on a fixed date.",
    ),
    "buckets": dict(
        headline="Every possible number is covered, so nothing new can appear",
        detail="Numeric buckets partition the whole line by construction, so there is no "
               "wildcard entrant at all. The entire risk is whether you can buy every bucket. "
               "If one has no offers, your exposure is simply the probability the number lands "
               "in it, and official forecasters publish exactly that.",
        rules="A named statistical agency publishes the figure on a scheduled date and the "
              "bucket containing it pays. The buckets are mutually exclusive and exhaustive.",
    ),
}

MARKET_BASE_RATES = {
    "F1 Drivers' Champion": dict(
        headline="Nobody outside the top five on points comes back this late",
        detail="The arithmetic does the work here. Antonelli leads Russell by 66 points with a "
               "handful of rounds to go, and the drivers with no offers against them, Alonso, "
               "Stroll, Ocon, Hulkenberg, Albon, Sainz, Bottas and Perez, are all far adrift. "
               "For one of them to take the title, every car ahead would have to fail "
               "repeatedly while they won repeatedly. This is the rare case where the "
               "unbuyable outcomes are not a risk at all, they are arithmetically dead.",
        rules="Points are awarded per race under the FIA sporting regulations and the title "
              "goes to the highest total after the final round. No new driver can enter a "
              "championship already under way.",
        sources=[["Formula 1 official 2026 drivers standings",
                  "https://www.formula1.com/en/results/2026/drivers"]],
    ),
    "MLB: 2026 NL East Champion": dict(
        headline="Leads this size usually hold, and the exceptions are famous",
        detail="Atlanta is priced at 86% with about a month to play, which is the market "
               "saying a collapse is unlikely rather than impossible. Baseball has produced "
               "some famous September collapses, which is why the Mets and Nationals still "
               "carry roughly 6% between them. That 6% is the number that matters, because "
               "both teams are unbuyable and your profit only absorbs 1.4%.",
        rules="The best regular season record in the division wins it, with tiebreakers set by "
              "MLB rule. The five teams were fixed before the season began.",
    ),
    "U.K. Annual Inflation 2026": dict(
        headline="The official central forecast lands inside the one bucket you cannot buy",
        detail="The Bank of England's July 2026 Monetary Policy Report puts CPI at about 3.2% "
               "in the fourth quarter of 2026. The unbuyable bucket is 3.0 to 3.4%. So the "
               "single most likely outcome, according to the institution that sets rates and "
               "publishes the forecast, is precisely the outcome with no offers against it. "
               "Their own milder scenario sits near 3.0%, which is still inside that bucket.",
        rules="The ONS publishes the December 2026 CPI figure on 20 January 2027 and whichever "
              "bucket contains the twelve month change pays out.",
        sources=[["Bank of England Monetary Policy Report, July 2026",
                  "https://www.bankofengland.co.uk/monetary-policy-report/2026/july-2026"]],
    ),
    "WNBA: Three Point Percentage Leader": dict(
        headline="The current top thirteen are all unbuyable, with days left to play",
        detail="This is not a probability, it is the present state of the table. Serah Williams "
               "leads on 50.0%, Kelsey Mitchell is second on 45.5% across forty games, and the "
               "next eleven are also unbuyable. The best buyable name is A'ja Wilson, "
               "fourteenth on 39.8%. For this basket to pay, the top of a season-long "
               "percentage table would have to invert in its final days, which percentage "
               "statistics measured over forty games do not do.",
        rules="The qualified player with the highest three point percentage at the end of the "
              "regular season wins. Ties break on games played, then alphabetically by "
              "surname. Qualification follows the official WNBA leaderboard minimum.",
        sources=[["WNBA 2026 three point percentage leaders",
                  "https://www.statpick.ai/stats/wnba/leaders/fg3_pct"]],
    ),
    "OK-02 House Election Winner": dict(
        headline="No third party has won a US House seat in decades, but the list is wrong",
        detail="On who wins, the base rate is strongly in your favour: every seat in the House "
               "is held by a Republican or a Democrat and Oklahoma's 2nd is among the safest "
               "Republican districts in the country. The problem is the list, not the winner. "
               "The certified ballot carries Brecheen, Terwey and Webb, while the market sells "
               "you Brecheen and a Brandon Wade who is not on that ballot at all.",
        rules="A single round plurality election on 3 November 2026. The certified ballot is "
              "final and, write-ins aside, nobody outside it can win.",
        sources=[["Ballotpedia, Oklahoma's 2nd Congressional District election 2026",
                  "https://ballotpedia.org/Oklahoma's_2nd_Congressional_District_election,_2026"]],
    ),
    "MI-13 House Election Winner": dict(
        headline="Four ballot-qualified candidates here have no market at all",
        detail="Michigan's 13th is a safe Democratic seat and McKinney is priced at 97%, so on "
               "the question of who wins the base rate is comfortable. What is not comfortable "
               "is that Shelby Campbell, Simone Coleman, Christopher Dardzinski and Maurice "
               "Morton are all on the November ballot with nobody selling them, and the "
               "Republican you can buy does not match the one who won the August primary. Six "
               "or more names on the ballot, two buyable, $1,059 at risk to earn $8.",
        rules="A single round plurality election on 3 November 2026, with major party, minor "
              "party and independent candidates all on the one ballot.",
        sources=[["Ballotpedia, Michigan's 13th Congressional District election 2026",
                  "https://ballotpedia.org/Michigan's_13th_Congressional_District_election,_2026"]],
    ),
    "Morocco Legislative Elections: Party Winner": dict(
        headline="The eight listed parties took 385 of 395 seats last time",
        detail="In 2021 the parties you can buy here won 385 of 395 seats between them, "
               "leaving ten for everybody else, and no unlisted party came near the largest "
               "bloc. The system reinforces that: 305 of the 395 seats are allocated across 92 "
               "local constituencies on a quotient computed from registered voters with no "
               "threshold, which spreads small parties thinly rather than concentrating them. "
               "The residual risk is not a surprise party at roughly 0.3%, it is the clause "
               "sending this to an unbuyable Other if no result exists by 31 July 2027.",
        rules="Voting on 23 September 2026 for the House of Representatives. The market pays "
              "the party with the most seats, and resolves to Other if no definitive result "
              "is known by 31 July 2027.",
        sources=[["2026 Moroccan general election",
                  "https://en.wikipedia.org/wiki/2026_Moroccan_general_election"]],
    ),
    "Next President of Kosovo?": dict(
        headline="Nearly two years of deadlock, and still no president",
        detail="This is the base rate, observed rather than estimated. Kosovo has failed to "
               "elect a president through repeated attempts since before Osmani's term expired "
               "on 4 April 2026. The parties blew a March deadline, the failure triggered a "
               "snap election on 7 June, and the winner still lacks the two thirds the "
               "constitution requires. An August deal between VV and LDK behind Bekim Sejdiu "
               "is the latest attempt, not the first. Meanwhile an acting president holds the "
               "office and the rules here say acting does not count. The single most likely "
               "way this market resolves may simply be the clock running out.",
        rules="The Assembly of Kosovo elects the president by a two thirds majority, and the "
              "winner must take the oath before the Assembly. Acting, interim and caretaker "
              "service does not count. Failure to elect triggers fresh parliamentary "
              "elections, and if nobody begins a full term by 30 April 2027 the market "
              "resolves to Other.",
        sources=[["2026 Kosovan presidential election",
                  "https://en.wikipedia.org/wiki/2026_Kosovan_presidential_election"],
                 ["European Western Balkans, another attempt to break the deadlock",
                  "https://europeanwesternbalkans.com/2026/08/06/another-attempt-to-break-a-long-standing-political-deadlock-in-pristina/"]],
    ),
    "West Vancouver, BC Mayoral Election Winner": dict(
        headline="Provisional until 4pm Pacific today, then fixed for good",
        detail="British Columbia runs one statutory nomination window for every local election "
               "in the province, 1 to 11 September 2026. Until it shuts, any eligible resident "
               "can file and the two names here are not the whole field. After it shuts, "
               "Elections BC publishes the certified list and the wildcard risk drops to zero, "
               "because a mayor can only be elected from that list. There is no version of "
               "this where a new candidate appears in October.",
        rules="Nominations close 11 September 2026 at 4pm Pacific. Election day is 17 October "
              "2026, decided by plurality from the certified list.",
        sources=[["Elections BC, 2026 General Local Elections",
                  "https://elections.bc.ca/local-elections/2026-general-local-elections/"]],
    ),
    "Central Coast Mayoral Election Winner": dict(
        headline="Nominations opened 7 September and do not close until the 21st",
        detail="The two buyable names are the two who contested it last time: Cheryl Fuller "
               "took the 2022 mayoral vote with 54.5% against Garry Carpenter on 45.5%, and "
               "Fuller is the sitting mayor. That is a reasonable field so far. But nominations "
               "for the 27 October poll are open as you read this and run until 21 September, "
               "so a third name can still appear and there is nothing bought to cover one. Ten "
               "days from now this becomes a checkable, closed field.",
        rules="The Tasmanian Electoral Commission runs nominations from 7 to 21 September 2026. "
              "The election is on 27 October 2026 and voters elect the mayor directly.",
        sources=[["Tasmanian Electoral Commission, 2026 local government elections",
                  "https://www.tec.tas.gov.au/local-government/elections-2026/index.html"]],
    ),
}


def base_rate(title, kind):
    if title in MARKET_BASE_RATES:
        return MARKET_BASE_RATES[title]
    return BASE_RATES.get(kind)
