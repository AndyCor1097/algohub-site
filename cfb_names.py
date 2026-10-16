"""Matches Novig college team names (and their abbreviations) to your CFB algo's names."""
import difflib
import re
import unicodedata

# Novig name -> your algo's name (only the ones normalizing can't figure out)
ALIAS = {
    "byu": "brigham young", "lsu": "louisiana state", "tcu": "texas christian", "smu": "southern methodist",
    "unlv": "nevada las vegas", "ole miss": "mississippi", "miami florida": "miami", "miami fl": "miami",
    "miami (fl)": "miami", "miami (oh)": "miami ohio", "miami oh": "miami ohio", "sam houston state": "sam houston",
    "southern mississippi": "southern miss", "ul monroe": "louisiana monroe", "uab": "alabama birmingham",
    "fiu": "florida international", "umass": "massachusetts", "app state": "appalachian state",
    "usc": "southern california", "pitt": "pittsburgh", "nc state": "north carolina state",
    "uconn": "connecticut", "ul lafayette": "louisiana", "louisiana lafayette": "louisiana",
    "texas a&m commerce": "east texas a&m", "central florida": "ucf", "western kentucky": "western kentucky",
    "southern utah": "southern utah", "hawaii": "hawaii", "san jose state": "san jose state",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.lower().replace("'", "").replace(".", "").replace("`", "")
    s = re.sub(r"\s+", " ", s).strip()
    return ALIAS.get(s, s)


class Matcher:
    def __init__(self, algo_names):
        self.by_norm = {norm(n): n for n in algo_names}
        self.keys = list(self.by_norm)

    def find(self, novig_name):
        k = norm(novig_name)
        if k in self.by_norm:
            return self.by_norm[k]
        close = difflib.get_close_matches(k, self.keys, n=1, cutoff=0.88)
        return self.by_norm[close[0]] if close else None


def _fits(abbr, name):
    """How well an abbreviation like 'MRSH' fits a name like 'Marshall' (letters appear in order)."""
    a = re.sub(r"[^A-Z]", "", abbr.upper())
    words = re.sub(r"[^A-Za-z ]", "", name).upper().split()
    letters = "".join(words)
    it, ok = iter(letters), True
    for ch in a:
        if ch not in it:
            ok = False
            break
    initials = "".join(w[0] for w in words)
    score = (2 if ok else 0) + (1 if a and letters.startswith(a[0]) else 0) + (2 if a == initials else 0)
    score += 3 if a == letters[:len(a)] else 0
    return score


def home_away_abbr(abbrs, away_name, home_name):
    """Given Novig's two abbreviations for a game, return (away_abbr, home_abbr)."""
    x, y = abbrs
    keep = _fits(x, away_name) + _fits(y, home_name)
    swap = _fits(x, home_name) + _fits(y, away_name)
    if keep > swap:
        return x, y
    if swap > keep:
        return y, x
    return y, x            # tie: Novig lists the home team first
