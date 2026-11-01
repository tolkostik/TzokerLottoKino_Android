"""
Τζόκερ, Λόττο, ΚΙΝΟ: λήψη προηγούμενων κληρώσεων από τις δημόσιες υπηρεσίες του ΟΠΑΠ,
στατιστικά και παραγωγή αριθμών.

ΣΗΜΑΝΤΙΚΟ: κάθε κλήρωση είναι τυχαία και ανεξάρτητη. Τα στατιστικά δεν προβλέπουν
την επόμενη κλήρωση. Η «αποφυγή δημοφιλών συνδυασμών» δεν αυξάνει την πιθανότητα
κέρδους, μειώνει όμως την πιθανότητα να μοιραστείς το έπαθλο.
"""
import datetime
import json
import math
import random
import ssl
import urllib.request
from pathlib import Path

API = "https://api.opap.gr/draws/v3.0"
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"

GAMES = {
    "joker": {"name": "ΤΖΟΚΕΡ", "id": 5104, "pick": 5, "max": 45, "bonus_max": 20, "draw": 5, "days": 30},
    "lotto": {"name": "ΛΟΤΤΟ", "id": 5103, "pick": 6, "max": 49, "bonus_max": 0, "draw": 6, "days": 30},
    "kino": {"name": "ΚΙΝΟ", "id": 1100, "pick": 6, "max": 80, "bonus_max": 0, "draw": 20, "days": 1},
}
METHODS = ["Ισορροπημένη", "Συχνοί (ζεστοί)", "Καθυστερημένοι (κρύοι)", "Εντελώς τυχαία"]

DATA_DIR = Path.home() / ".tyxeroi"


def set_dir(path):
    global DATA_DIR
    DATA_DIR = Path(path)


# ------------------------------------------------------------------ λήψη από ΟΠΑΠ
def _get(url, timeout=20):
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_draw(d):
    """Μετατρέπει μια κλήρωση του ΟΠΑΠ σε {id, time, numbers, bonus}."""
    if not isinstance(d, dict):
        return None
    wn = d.get("winningNumbers") or {}
    nums = wn.get("list") if isinstance(wn, dict) else None
    if nums is None:
        nums = d.get("results") or d.get("numbers")
    if not nums:
        return None
    bonus = wn.get("bonus") if isinstance(wn, dict) else None
    did = d.get("drawId") or d.get("drawNo") or d.get("id")
    t = d.get("drawTime") or d.get("drawDate")
    if isinstance(t, (int, float)) and t > 10 ** 11:
        t = datetime.datetime.fromtimestamp(t / 1000).strftime("%d/%m/%Y %H:%M")
    return {"id": int(did) if did is not None else 0, "time": str(t or ""),
            "numbers": [int(x) for x in nums], "bonus": [int(x) for x in (bonus or [])]}


def _content(js):
    if isinstance(js, list):
        return js
    if isinstance(js, dict):
        for k in ("content", "draws", "items"):
            if isinstance(js.get(k), list):
                return js[k]
    return []


def fetch_history(game, wanted=200, log=lambda s: None):
    """Κατεβάζει τις τελευταίες «wanted» κληρώσεις, από τη νεότερη στην παλαιότερη."""
    g = GAMES[game]
    gid = g["id"]
    draws = {}
    errors = []

    # 1) τελευταία κλήρωση
    last_id = None
    try:
        js = _get(f"{API}/{gid}/last-result-and-active")
        last = parse_draw(js.get("last") if isinstance(js, dict) else None)
        if last:
            draws[last["id"]] = last
            last_id = last["id"]
    except Exception as e:  # noqa: BLE001
        errors.append(f"τελευταία κλήρωση: {e}")

    # 2) κληρώσεις ανά διάστημα ημερομηνιών, προς τα πίσω
    end = datetime.date.today()
    span = g["days"]
    requests_left = 40
    empty_in_row = 0
    while len(draws) < wanted and requests_left > 0 and empty_in_row < 4:
        start = end - datetime.timedelta(days=span - 1)
        got = 0
        for page in range(0, 6):
            requests_left -= 1
            try:
                js = _get(f"{API}/{gid}/draw-date/{start.isoformat()}/{end.isoformat()}?limit=100&page={page}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{start}–{end}: {e}")
                break
            items = [parse_draw(x) for x in _content(js)]
            items = [x for x in items if x]
            for it in items:
                draws[it["id"]] = it
            got += len(items)
            log(f"{g['name']}: {len(draws)} κληρώσεις…")
            total_pages = js.get("totalPages") if isinstance(js, dict) else None
            if not items or (total_pages is not None and page + 1 >= total_pages) or len(items) < 100:
                break
            if len(draws) >= wanted or requests_left <= 0:
                break
        empty_in_row = empty_in_row + 1 if got == 0 else 0
        end = start - datetime.timedelta(days=1)

    # 3) εναλλακτικά: μία-μία με αριθμό κλήρωσης
    if len(draws) < min(wanted, 30) and last_id:
        for did in range(last_id - 1, max(0, last_id - 60), -1):
            if did in draws:
                continue
            try:
                d = parse_draw(_get(f"{API}/{gid}/{did}"))
                if d:
                    draws[d["id"]] = d
            except Exception as e:  # noqa: BLE001
                errors.append(f"κλήρωση {did}: {e}")
                break
            if len(draws) >= wanted:
                break

    out = sorted(draws.values(), key=lambda d: d["id"], reverse=True)[:wanted]
    if not out:
        raise RuntimeError("Δεν ήρθαν κληρώσεις από τον ΟΠΑΠ. " + (errors[0][:150] if errors else ""))
    return out


# ------------------------------------------------------------------ αποθήκευση
def _file(game):
    return DATA_DIR / f"{game}.json"


def load(game):
    try:
        return json.loads(_file(game).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"draws": [], "updated": None}


def save(game, draws):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {"draws": draws, "updated": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}
    _file(game).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


# ------------------------------------------------------------------ στατιστικά
def stats(game, draws):
    g = GAMES[game]
    n = len(draws)
    freq = {k: 0 for k in range(1, g["max"] + 1)}
    gap = {k: n for k in range(1, g["max"] + 1)}  # κληρώσεις από την τελευταία εμφάνιση
    bfreq = {k: 0 for k in range(1, g["bonus_max"] + 1)}
    bgap = {k: n for k in range(1, g["bonus_max"] + 1)}
    sums = []
    for i, d in enumerate(draws):  # η 0 είναι η νεότερη
        main = d["numbers"][: g["draw"]]
        sums.append(sum(main))
        for x in main:
            if x in freq:
                freq[x] += 1
                gap[x] = min(gap[x], i)
        for x in d.get("bonus", [])[:1]:
            if x in bfreq:
                bfreq[x] += 1
                bgap[x] = min(bgap[x], i)
    hot = sorted(freq, key=lambda k: (-freq[k], k))
    cold = sorted(gap, key=lambda k: (-gap[k], k))
    return {"n": n, "freq": freq, "gap": gap, "bfreq": bfreq, "bgap": bgap,
            "hot": hot, "cold": cold, "sums": sorted(sums)}


# ------------------------------------------------------------------ παραγωγή
def _weights(method, freq, gap, size):
    keys = list(range(1, size + 1))
    if method == "Συχνοί (ζεστοί)":
        return keys, [freq.get(k, 0) + 1.0 for k in keys]
    if method == "Καθυστερημένοι (κρύοι)":
        return keys, [gap.get(k, 0) + 1.0 for k in keys]
    if method == "Ισορροπημένη":
        return keys, [math.sqrt((freq.get(k, 0) + 1.0) * (gap.get(k, 0) + 1.0)) for k in keys]
    return keys, [1.0] * len(keys)


def _sample(rng, keys, weights, k):
    keys, weights = list(keys), list(weights)
    out = []
    for _ in range(k):
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if acc >= r:
                out.append(keys.pop(i))
                weights.pop(i)
                break
    return sorted(out)


def _popular(nums, maxn):
    """Συνδυασμοί που παίζουν πολλοί (γενέθλια, σειρές, ίδια λήξη)."""
    if maxn > 31 and all(x <= 31 for x in nums):
        return True
    run = 1
    for a, b in zip(nums, nums[1:]):
        run = run + 1 if b == a + 1 else 1
        if run >= 3:
            return True
    if len(nums) >= 4 and len({x % 10 for x in nums}) <= 2:
        return True
    if len(nums) >= 4 and len(set(b - a for a, b in zip(nums, nums[1:]))) == 1:
        return True  # αριθμητική πρόοδος, π.χ. 5-10-15-20-25
    return False


def _balanced(nums, st, game):
    k = len(nums)
    if k >= 4:
        odd = sum(x % 2 for x in nums)
        if odd == 0 or odd == k:
            return False
    sums = st["sums"]
    if game in ("joker", "lotto") and len(sums) >= 30 and k == GAMES[game]["draw"]:
        lo, hi = sums[int(len(sums) * 0.1)], sums[int(len(sums) * 0.9) - 1]
        if not lo <= sum(nums) <= hi:
            return False
    return True


def generate(game, draws, method, columns=3, pick=None, avoid_popular=True, seed=None):
    g = GAMES[game]
    k = pick or g["pick"]
    st = stats(game, draws)
    rng = random.Random(seed)
    keys, w = _weights(method, st["freq"], st["gap"], g["max"])
    out, seen = [], set()
    for _ in range(columns):
        nums = None
        for _try in range(800):
            cand = _sample(rng, keys, w, k)
            if tuple(cand) in seen:
                continue
            if avoid_popular and _popular(cand, g["max"]):
                continue
            if method == "Ισορροπημένη" and not _balanced(cand, st, game):
                continue
            nums = cand
            break
        nums = nums or _sample(rng, keys, w, k)
        seen.add(tuple(nums))
        bonus = None
        if g["bonus_max"]:
            bk, bw = _weights(method, st["bfreq"], st["bgap"], g["bonus_max"])
            bonus = _sample(rng, bk, bw, 1)[0]
        out.append({"numbers": nums, "bonus": bonus})
    return out


# ------------------------------------------------------------------ πιθανότητες
def _gr(n):
    return f"{n:,}".replace(",", ".")


def odds_text(game, pick=None):
    g = GAMES[game]
    if game == "joker":
        return f"Πιθανότητα 5+1 (τζάκποτ): 1 στις {_gr(math.comb(45, 5) * 20)}"
    if game == "lotto":
        return f"Πιθανότητα 6 στα 6: 1 στις {_gr(math.comb(49, 6))}"
    k = pick or g["pick"]
    p = math.comb(20, k) / math.comb(80, k)
    return f"ΚΙΝΟ με {k} αριθμούς, πιθανότητα να πιάσεις και τους {k}: 1 στις {_gr(round(1 / p))}"
