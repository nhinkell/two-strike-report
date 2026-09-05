#!/usr/bin/env python3
"""Rebuild the Dynasty Yr 1 front-office dashboard from live data.

Fetches the Sleeper league (rosters, auction results, traded picks,
transactions), FantasyCalc dynasty market values (1QB / PPR / 10-team)
and the DynastyProcess consensus overlay, then injects the combined
dataset into the dashboard template's <script id="ff-data"> block.

Usage:
  python3 tools/refresh_dashboard.py \
      --template dashboard/front-office.html \
      --out /tmp/front-office.html [--data-dir data/sleeper]

Exits non-zero (and writes nothing) if any required fetch fails, so a
half-empty page can never be published.
"""
import argparse, csv, datetime, io, json, sys, urllib.request
from collections import defaultdict

LEAGUE_ID = "1354143142760169472"
SLEEPER = "https://api.sleeper.app/v1"
FC_URL = ("https://api.fantasycalc.com/values/current"
          "?isDynasty=true&numQbs=1&numTeams=10&ppr=1")
DP_VALUES = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
DP_IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"


def fetch(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": "dynasty-yr1-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return json.loads(body) if as_json else body.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-dir", default=None,
                    help="optional: also write raw fetched JSON here")
    args = ap.parse_args()

    league = fetch(f"{SLEEPER}/league/{LEAGUE_ID}")
    users = fetch(f"{SLEEPER}/league/{LEAGUE_ID}/users")
    rosters = fetch(f"{SLEEPER}/league/{LEAGUE_ID}/rosters")
    drafts = fetch(f"{SLEEPER}/league/{LEAGUE_ID}/drafts")
    traded = fetch(f"{SLEEPER}/league/{LEAGUE_ID}/traded_picks")
    state = fetch(f"{SLEEPER}/state/nfl")
    draft = next(d for d in drafts if d.get("type") == "auction")
    picks = fetch(f"{SLEEPER}/draft/{draft['draft_id']}/picks")

    legs = sorted({1, max(1, state.get("leg") or 1)})
    txraw, seen = [], set()
    for leg in legs:
        for t in fetch(f"{SLEEPER}/league/{LEAGUE_ID}/transactions/{leg}"):
            if t["transaction_id"] not in seen:
                seen.add(t["transaction_id"])
                txraw.append(t)

    nfl = fetch(f"{SLEEPER}/players/nfl")
    fc = fetch(FC_URL)
    dp_vals = list(csv.DictReader(io.StringIO(fetch(DP_VALUES, as_json=False))))
    dp_ids = list(csv.DictReader(io.StringIO(fetch(DP_IDS, as_json=False))))

    umap = {u["user_id"]: u for u in users}
    owner_rid = {r["owner_id"]: r["roster_id"] for r in rosters}
    price = {p["player_id"]: int(p["metadata"].get("amount") or 0) for p in picks}
    drafter_rid = {p["player_id"]: owner_rid[p["picked_by"]] for p in picks}

    teams = []
    for r in sorted(rosters, key=lambda x: x["roster_id"]):
        u = umap.get(r["owner_id"], {})
        tn = (u.get("metadata") or {}).get("team_name") or u.get("display_name")
        st = r.get("starters") or []
        tx = r.get("taxi") or []
        rv = r.get("reserve") or []
        allp = r.get("players") or []
        bench = [p for p in allp if p not in st and p not in tx and p not in rv]
        teams.append({"rid": r["roster_id"], "h": u.get("display_name", "?"), "tn": tn,
                      "faab": r["settings"].get("waiver_budget_used", 0),
                      "w": r["settings"].get("wins", 0), "l": r["settings"].get("losses", 0),
                      "st": st, "bn": bench, "tx": tx, "ir": rv})

    fcmap = {}
    for e in fc:
        p = e["player"]
        sid = p.get("sleeperId")
        if p["position"] == "PICK" or not sid:
            continue
        fcmap[sid] = {"v": e["value"], "rv": e.get("redraftValue", 0),
                      "tr": e.get("trend30Day", 0), "or": e.get("overallRank", 0),
                      "pr": e.get("positionRank", 0), "age": p.get("maybeAge")}
    fp2sl = {row["fantasypros_id"]: row["sleeper_id"] for row in dp_ids
             if row["fantasypros_id"] not in ("", "NA") and row["sleeper_id"] not in ("", "NA")}
    for row in dp_vals:
        sid = fp2sl.get(row["fp_id"])
        if sid and sid in fcmap:
            try:
                fcmap[sid]["ecr"] = float(row["ecr_1qb"])
                fcmap[sid]["dpv"] = int(row["value_1qb"])
            except ValueError:
                pass

    txns = []
    for t in sorted(txraw, key=lambda x: -x["created"]):
        ty, ts, ok = t["type"], t["created"], t["status"] == "complete"
        adds, drops = t.get("adds") or {}, t.get("drops") or {}
        if ty == "trade" and ok:
            pks = [[d["season"], d["round"], d["roster_id"], d["owner_id"]]
                   for d in (t.get("draft_picks") or [])]
            faab = [[b["sender"], b["receiver"], b["amount"]]
                    for b in (t.get("waiver_budget") or [])]
            txns.append(["t", ts, t.get("roster_ids") or [], adds, pks, faab])
        elif ty == "waiver":
            rid = (t.get("roster_ids") or [0])[0]
            addp = next(iter(adds), None)
            txns.append(["w", ts, rid, addp, list(drops),
                        (t.get("settings") or {}).get("waiver_bid", 0), ok])
        elif ty == "free_agent" and ok:
            rid = (t.get("roster_ids") or [0])[0]
            txns.append(["f", ts, rid, next(iter(adds), None), list(drops)])
        elif ty == "commissioner" and ok:
            txns.append(["c", ts, adds, drops])

    need = set(fcmap) | set(price)
    for tm in teams:
        need |= set(tm["st"] + tm["bn"] + tm["tx"] + tm["ir"])
    for t in txns:
        if t[0] == "t":
            need |= set(t[3])
        elif t[0] in ("w", "f"):
            need |= {t[3]} | set(t[4]) if t[3] else set(t[4])
        elif t[0] == "c":
            need |= set(t[2]) | set(t[3])
    need.discard(None)
    players = {}
    for sid in need:
        n = nfl.get(sid)
        if n:
            players[sid] = {"n": (n.get("full_name") or
                                  (n.get("first_name", "") + " " + n.get("last_name", "")).strip()),
                            "p": n.get("position") or "?", "t": n.get("team") or "FA"}

    pickfc = {e["player"]["name"]: e["value"] for e in fc if e["player"]["position"] == "PICK"}
    pick_vals = {}
    for season in ("2027", "2028", "2029"):
        for rnd in (1, 2, 3, 4):
            v = pickfc.get(f"{season} {['1st','2nd','3rd','4th'][rnd-1]}") or \
                pickfc.get(f"{season} {['1st','2nd','3rd','4th'][rnd-1]} (Mid)")
            if v is None:
                prior_yr = pick_vals.get(f"{int(season)-1}-{rnd}")
                prior_rd = pick_vals.get(f"{season}-{rnd-1}")
                v = int(prior_yr * 0.88) if prior_yr else (
                    int(prior_rd * 0.45) if prior_rd else 150)
            pick_vals[f"{season}-{rnd}"] = v

    own = {}
    for season in ("2027", "2028", "2029"):
        for rnd in (1, 2, 3, 4):
            for r in rosters:
                own[(season, rnd, r["roster_id"])] = r["roster_id"]
    for e in traded:
        own[(e["season"], e["round"], e["roster_id"])] = e["owner_id"]
    team_picks = defaultdict(list)
    for (season, rnd, orig), holder in own.items():
        team_picks[holder].append([season, rnd, orig])
    for k in team_picks:
        team_picks[k].sort()

    now_on = {}
    for r in rosters:
        for pid in (r["players"] or []):
            now_on[pid] = r["roster_id"]
    moved, cuts, waivers = [], [], []
    for pid, frm in drafter_rid.items():
        if pid in now_on:
            if now_on[pid] != frm:
                moved.append([pid, frm, now_on[pid], price[pid]])
        else:
            cuts.append([pid, frm, price[pid]])
    for pid, rid in now_on.items():
        if pid not in drafter_rid:
            waivers.append([pid, rid])
    moved.sort(key=lambda x: -x[3])
    cuts.sort(key=lambda x: -x[2])

    pick_rows = [[p["player_id"], int(p["metadata"].get("amount") or 0),
                  owner_rid[p["picked_by"]], p.get("pick_no", 0)] for p in picks]
    now = datetime.datetime.now(datetime.timezone.utc)
    vals = {sid: [m["v"], m.get("rv", 0), m.get("tr", 0), m.get("or", 0), m.get("pr", 0),
                  round(m["age"], 1) if m.get("age") else 0, m.get("ecr", 0), m.get("dpv", 0)]
            for sid, m in fcmap.items()}
    data = {"meta": {"name": "Dynasty Yr 1", "season": league["season"],
                     "snapshot": now.strftime("%Y-%m-%d %H:%M UTC"),
                     "snapshotISO": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "valuesAsOf": now.strftime("%b %d, %Y"),
                     "budget": 500, "faab": 50, "nTeams": 10, "playoffTeams": 8,
                     "playoffStart": 15, "deadline": 12, "taxi": 3, "ir": 3,
                     "caps": {"QB": 3, "RB": 8, "WR": 8, "TE": 5, "K": 3},
                     "lineup": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K"],
                     "benchSlots": 13, "scoring": "Full PPR · 4-pt pass TD",
                     "draftDate": "Aug 23, 2026"},
            "teams": teams, "players": players, "picks": pick_rows,
            "traded": moved, "cuts": cuts, "waivers": waivers,
            "values": vals, "pickVals": pick_vals, "teamPicks": dict(team_picks),
            "txns": txns}
    payload = json.dumps(data, separators=(",", ":"))
    if "</" in payload:
        sys.exit("refusing to embed JSON containing '</'")

    html = open(args.template, encoding="utf-8").read()
    marker = '<script id="ff-data" type="application/json">'
    i = html.index(marker) + len(marker)
    j = html.index("</script>", i)
    open(args.out, "w", encoding="utf-8").write(html[:i] + payload + html[j:])

    if args.data_dir:
        import os
        os.makedirs(args.data_dir, exist_ok=True)
        for name, obj in [("league", league), ("users", users), ("rosters", rosters),
                          ("drafts", drafts), ("traded_picks", traded), ("state", state),
                          (f"picks_{draft['draft_id']}", picks), ("transactions", txraw),
                          ("players_lookup", players)]:
            json.dump(obj, open(f"{args.data_dir}/{name}.json", "w"), separators=(",", ":"))

    print(f"DONE teams={len(teams)} picks={len(pick_rows)} txns={len(txns)} "
          f"valued={len(vals)} players={len(players)} -> {args.out}")


if __name__ == "__main__":
    main()
