import re

SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")

FALLBACK = re.compile(r"\bif\b[^.]*\bresolve(?:s|d)?\s+to\b", re.I)
FALLBACK_TARGET = re.compile(
    r"resolve(?:s|d)?\s+to\s+[“‘\"']?([A-Za-z][^.\"”’']{0,38})", re.I)
EXCLUDES = re.compile(r"\b(will not count|does not count|shall not count|"
                      r"not be considered|will not be considered)\b", re.I)
FORMAL = re.compile(r"\bformally (?:elected|appointed|assumes|sworn)\b|"
                    r"\bmust be formally\b|\bofficially assumes\b|\btakes? office\b", re.I)
TIEBREAK = re.compile(r"in the event of a tie|tie[- ]?break", re.I)
SOURCE = re.compile(r"(?:primary )?resolution source|consensus of credible reporting|"
                    r"according to official", re.I)
REVISION = re.compile(r"\b(revis\w+|restat\w+|corrected)\b", re.I)

LABELS = {
    "fallback": "What happens if the main condition is never met",
    "excludes": "What explicitly does NOT resolve this market",
    "formal": "The exact act that has to happen",
    "tiebreak": "How a tie is settled",
    "source": "Who decides the result",
    "revision": "Whether later corrections change the result",
}
ORDER = ["fallback", "excludes", "formal", "tiebreak", "source", "revision"]
PATTERNS = {"fallback": FALLBACK, "excludes": EXCLUDES, "formal": FORMAL,
            "tiebreak": TIEBREAK, "source": SOURCE, "revision": REVISION}

DATE = re.compile(
    r"\b((?:January|February|March|April|May|June|July|August|September|October|November|"
    r"December)\s+\d{1,2},\s+\d{4})", re.I)
INTERIM = re.compile(r"\b(interim|caretaker|acting|temporary|placeholder)\b", re.I)
THRESHOLD = re.compile(r"\b(two[- ]thirds|2/3|absolute majority|supermajority)\b", re.I)
TRAIL = re.compile(r"\s+(?:if|when|according|based|as|and|following)\b.*$", re.I)


def clean(text):
    return " ".join((text or "").split())


def sentences(text):
    text = clean(text)
    return [s.strip() for s in SENT.split(text) if s.strip()] if text else []


def parse(description, dark_names):
    out = {"clauses": [], "flags": [], "fallback": None, "fallback_date": None,
           "fallback_buyable": None, "excludes_interim": False, "threshold": None}
    if not clean(description):
        out["flags"].append(["no_rules",
                             "Polymarket published no resolution text for this market, so "
                             "none of these checks could run. Treat everything else on this "
                             "page as unverified."])
        return out

    dark = {(n or "").strip().lower() for n in dark_names}
    found = {}
    for sentence in sentences(description):
        for key in ORDER:
            if key not in found and PATTERNS[key].search(sentence):
                found[key] = sentence

    for key in ORDER:
        if key in found:
            out["clauses"].append({"key": key, "label": LABELS[key], "text": found[key]})

    fb = found.get("fallback")
    if fb:
        m = FALLBACK_TARGET.search(fb)
        if m:
            name = TRAIL.sub("", clean(m.group(1))).strip(" .,;:")
            out["fallback"] = name
            out["fallback_buyable"] = name.lower() not in dark
        d = DATE.search(fb)
        if d:
            out["fallback_date"] = d.group(1)

    if found.get("excludes") and INTERIM.search(found["excludes"]):
        out["excludes_interim"] = True

    th = THRESHOLD.search(clean(description))
    if th:
        out["threshold"] = th.group(1)

    if out["fallback"] and out["fallback_buyable"] is False:
        out["flags"].append([
            "fallback_unbuyable",
            "If the main condition is never met this pays " + out["fallback"] + ", and nobody "
            "is selling " + out["fallback"] + ". That loses you the whole stake without anyone "
            "having to pick a surprise winner."])
    if out["excludes_interim"]:
        out["flags"].append([
            "interim_excluded",
            "An interim, acting or caretaker holder explicitly does not resolve this market, "
            "so the clock keeps running until somebody is permanently in post."])
    if out["excludes_interim"] and out["fallback_buyable"] is False:
        out["flags"].append([
            "deadlock",
            "Those two clauses combine. No permanent appointment by " +
            (out["fallback_date"] or "the backstop date") + " and this pays " +
            (out["fallback"] or "the fallback") + ", which you cannot own. Every name you "
            "bought can be right and you still get nothing."])
    if out["threshold"]:
        out["flags"].append([
            "threshold",
            "This needs a " + out["threshold"] + " vote rather than a simple plurality, and "
            "thresholds are how these processes stall."])
    if "tiebreak" in found:
        out["flags"].append([
            "tiebreak",
            "There is a tie-break rule, so the winner is not always the obvious one."])
    if "revision" in found:
        out["flags"].append([
            "revision",
            "The rules deal with later revisions or corrections to the figure, so a "
            "restatement after the fact may still move this."])
    if not out["clauses"]:
        out["flags"].append([
            "unparsed",
            "None of the usual resolution clauses were found in this text. Read it yourself "
            "below before trusting anything else on this page."])
    return out
