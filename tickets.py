"""
Έλεγχος δελτίων με τις επίσημες κληρώσεις του ΟΠΑΠ (api.opap.gr).

Κάθε κλήρωση περιέχει «prizeCategories»: ανά κατηγορία επιτυχιών το ποσό ανά νικητή (divident)
και τον αριθμό των νικητών. Έτσι υπολογίζεται ακριβώς το κέρδος κάθε στήλης.
"""
import datetime
import json
import time

import lottery as L

# Κατηγορίες κερδών (αρίθμηση κατηγοριών του ΟΠΑΠ: I = 1, II = 2, …)
JOKER_TIERS = {(5, 1): 1, (5, 0): 2, (4, 1): 3, (4, 0): 4, (3, 1): 5, (3, 0): 6, (2, 1): 7, (1, 1): 8}
LOTTO_TIERS = {6: 1, 5: 2, 4: 3, 3: 4}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}
OPAP_CHECK_URL = "https://www.opap.gr/"


# ------------------------------------------------------------------ κληρώσεις
def _draw_full(js):
    if not isinstance(js, dict):
        return None
    d = L.parse_draw(js)
    if not d:
        return None
    d["prizes"] = {}
    for c in js.get("prizeCategories") or []:
        try:
            d["prizes"][int(c.get("id"))] = {"amount": float(c.get("divident") or 0),
                                             "winners": int(c.get("winners") or 0),
                                             "jackpot": float(c.get("jackpot") or 0)}
        except (TypeError, ValueError):
            continue
    d["status"] = js.get("status", "")
    return d


_CACHE = {}


def fetch_draw(game, draw_id=None):
    """Μια κλήρωση με τα κέρδη της. Χωρίς αριθμό: η τελευταία."""
    gid = L.GAMES[game]["id"]
    key = (game, draw_id)
    hit = _CACHE.get(key)
    if hit and (draw_id is not None or time.time() - hit[0] < 300):
        return hit[1]
    if draw_id is None:
        js = L._get(f"{L.API}/{gid}/last-result-and-active")
        d = _draw_full(js.get("last") if isinstance(js, dict) else None)
        active = (js.get("active") or {}) if isinstance(js, dict) else {}
        if d is not None:
            d["next_id"] = active.get("drawId")
            t = active.get("drawTime")
            if isinstance(t, (int, float)):
                d["next_time"] = datetime.datetime.fromtimestamp(t / 1000).strftime("%d/%m %H:%M")
            jp = 0.0
            for c in active.get("prizeCategories") or []:
                if int(c.get("id", 0)) == 1:
                    jp = float(c.get("jackpot") or c.get("minimumDistributed") or 0)
            d["next_jackpot"] = jp
    else:
        d = _draw_full(L._get(f"{L.API}/{gid}/{int(draw_id)}"))
    if d is not None:
        _CACHE[key] = (time.time(), d)
    return d


def latest_all():
    out = {}
    for g in L.GAMES:
        try:
            out[g] = fetch_draw(g)
        except Exception as e:  # noqa: BLE001
            out[g] = {"error": str(e)[:80]}
    return out


# ------------------------------------------------------------------ έλεγχος στήλης
def check_column(game, numbers, bonus, draw):
    """Επιστρέφει {hits, bonus_hit, tier, amount, text}."""
    drawn = set(draw["numbers"][: L.GAMES[game]["draw"]])
    hits = len(set(numbers) & drawn)
    res = {"hits": hits, "bonus_hit": False, "tier": None, "amount": None}
    if game == "joker":
        bh = bool(draw.get("bonus")) and bonus is not None and bonus == draw["bonus"][0]
        res["bonus_hit"] = bh
        tier = JOKER_TIERS.get((hits, 1 if bh else 0))
        res["text"] = f"{hits} αριθμοί" + (" + Τζόκερ" if bh else "")
    elif game == "lotto":
        tier = LOTTO_TIERS.get(hits)
        res["text"] = f"{hits} αριθμοί"
    else:
        tier = None
        res["text"] = f"{hits} από {len(numbers)} αριθμούς"
    if tier:
        res["tier"] = tier
        pr = draw.get("prizes", {}).get(tier)
        if pr is not None:
            res["amount"] = pr["amount"]
    return res


def check_ticket_now(game, columns, draw):
    results = [check_column(game, c["numbers"], c.get("bonus"), draw) for c in columns]
    total = sum(r["amount"] or 0 for r in results)
    return results, total


# ------------------------------------------------------------------ τα δελτία μου
def load_tickets():
    try:
        return json.loads((L.DATA_DIR / "tickets.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def save_tickets(ts):
    import os
    L.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = L.DATA_DIR / "tickets.json.tmp"
    tmp.write_text(json.dumps(ts, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, L.DATA_DIR / "tickets.json")


def add_ticket(game, columns, draw_id, code=""):
    ts = load_tickets()
    t = {"id": int(time.time() * 1000), "game": game, "columns": columns, "draw_id": draw_id, "code": code,
         "created": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "status": "εκκρεμεί", "results": None,
         "total": None}
    ts.insert(0, t)
    save_tickets(ts[:100])
    return t


def delete_ticket(tid):
    save_tickets([t for t in load_tickets() if t["id"] != tid])


def settle_tickets():
    """Ελέγχει όσα δελτία έχουν πλέον κλήρωση. Επιστρέφει λίστα (δελτίο, σύνολο) για όσα κέρδισαν τώρα."""
    ts = load_tickets()
    new_wins = []
    changed = False
    for t in ts:
        if t["status"] != "εκκρεμεί" or not t.get("draw_id"):
            continue
        try:
            d = fetch_draw(t["game"], t["draw_id"])
        except Exception:  # noqa: BLE001
            continue
        if not d or not d.get("numbers") or (t["game"] != "kino" and not d.get("prizes")):
            continue
        results, total = check_ticket_now(t["game"], t["columns"], d)
        t["results"] = results
        t["total"] = total
        t["drawn"] = {"numbers": d["numbers"], "bonus": d.get("bonus", []), "time": d.get("time")}
        if t["game"] == "kino":
            t["status"] = "ελέγχθηκε"
        else:
            t["status"] = "κερδίζει" if total > 0 else "δεν κερδίζει"
        changed = True
        if total > 0:
            new_wins.append((t, total))
    if changed:
        save_tickets(ts)
    return new_wins


def euro(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
