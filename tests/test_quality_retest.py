"""Quality retest: day AND night via now_override, checked against every hard rule.
Run: .\\venv\\Scripts\\python.exe tests\\test_quality_retest.py
24 requests: at 10:00, 15:00 and 23:00 -> lonely x2, angry x2, anxious-exam x2, excited x2.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app

BASE = "http://127.0.0.1:8000"

TIMES = (("2026-01-01T10:00", "10:00 day"), ("2026-01-01T15:00", "15:00 day"),
         ("2026-01-01T23:00", "23:00 night"))

MOODS_PER_TIME = (["lonely"] * 2 + ["angry"] * 2
                  + ["anxious before an exam"] * 2 + ["excited"] * 2)

CHECKS = ("safety", "objects", "night", "walk", "chores", "venue", "lonely",
          "in-head", "scavenger", "quiet", "short", "cap")


def nudge(mood, now_override):
    # weather_override keeps the retest deterministic (no dependency on the live
    # Open-Meteo API, which can fail with transient DNS errors).
    body = json.dumps({"mood": mood, "now_override": now_override,
                       "weather_override": "clear sky, 12C, wind 5 kph"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/api/nudge", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def check_row(mood, cat, title, task, part_of_day):
    low = (title + " " + task).lower()
    mood_l = mood.lower()
    night = app.is_night_request(part_of_day, datetime.now().hour, mood)
    viol = app.safety_violations(f"{title} {task}", cat, mood_l, night)

    def only(prefix):
        return [v for v in viol if v == prefix or v.startswith(prefix)]

    obj = only("object-ban:")
    night_v = only("night-")
    walk_v = only("generic-walk")
    chore_v = only("ordinary-")
    lonely_v = only("lonely-")
    inhead_v = only("sketch-in-your-head")
    scav_v = only("scavenger-")
    quiet_v = only("night-loud-movement")
    short_v = only("too-short-duration")
    grouped = (obj + night_v + walk_v + chore_v + lonely_v + inhead_v + scav_v
               + quiet_v + short_v)
    safety_v = [v for v in viol if v not in grouped]
    venue = [lbl for pat, lbl in app.VENUE_BAN
             if re.search(pat, low) and not re.search(pat, mood_l)]
    ok = {"safety": (not safety_v, ", ".join(safety_v)),
          "objects": (not obj, ", ".join(obj)),
          "night": (not night_v, ", ".join(night_v)),
          "walk": (not walk_v, ", ".join(walk_v)),
          "chores": (not chore_v, ", ".join(chore_v)),
          "lonely": (not lonely_v, ", ".join(lonely_v)),
          "in-head": (not inhead_v, ", ".join(inhead_v)),
          "scavenger": (not scav_v, ", ".join(scav_v)),
          "quiet": (not quiet_v, ", ".join(quiet_v)),
          "short": (not short_v, ", ".join(short_v)),
          "venue": (not venue, ", ".join(venue))}
    return ok, night

def main():
    results = []
    n = 0
    for now_override, tlabel in TIMES:
        for mood in MOODS_PER_TIME:
            n += 1
            prior = [h.get("category", "") for h in app.load_history()[-10:]]
            resp, err = nudge(mood, now_override)
            if resp is None:
                results.append({"n": n, "time": tlabel, "mood": mood, "error": err,
                                "checks": {c: {"ok": False, "detail": "request-error"}
                                           for c in CHECKS}})
                print(f"ERROR [{tlabel}] mood={mood!r}: {err}")
                continue
            cat, title, task = resp["category"], resp["title"], resp["task"]
            checks, night = check_row(mood, cat, title, task, resp.get("part_of_day", ""))
            _, pool = app.energy_pool(mood, False)
            pool = list(pool) or list(app.MEDIUM_ENERGY_CATS)
            counts = {c: prior.count(c) for c in set(prior)}
            elig = [c for c in pool if counts.get(c, 0) < app.CATEGORY_CAP]
            if not elig:
                checks["cap"] = (True, "pool exhausted (by design)")
            elif cat in elig:
                checks["cap"] = (True, f"{cat} {counts.get(cat, 0)}x in prior 10")
            else:
                checks["cap"] = (False, f"{cat} used {counts.get(cat, 0)}x; eligible={elig}")
            results.append({"n": n, "time": tlabel, "mood": mood, "category": cat,
                            "energy": resp.get("energy"), "night": night,
                            "part_of_day": resp.get("part_of_day", ""),
                            "title": title, "task": task,
                            "checks": {k: {"ok": a, "detail": b}
                                       for k, (a, b) in checks.items()}})

    print("\n## Results table\n")
    print("| # | time | mood | night | energy | category | title | task |")
    print("|---|------|------|-------|--------|----------|-------|------|")
    for r in results:
        if "error" in r:
            print(f"| {r['n']} | {r['time']} | {r['mood']} | - | - | ERROR | - | {r['error'][:80]} |")
        else:
            print(f"| {r['n']} | {r['time']} | {r['mood']} | {'Y' if r['night'] else 'n'} "
                  f"| {r['energy']} | {r['category']} | {r['title']} | {r['task']} |")

    print("\n## Per-rule matrix\n")
    print("| # | " + " | ".join(CHECKS) + " |")
    print("|---|" + "---|" * len(CHECKS))
    fails = 0
    for r in results:
        cells = []
        for c in CHECKS:
            chk = r.get("checks", {}).get(c, {"ok": True})
            cells.append("OK" if chk["ok"] else "FAIL:" + chk.get("detail", ""))
            fails += 0 if chk["ok"] else 1
        print(f"| {r['n']} | " + " | ".join(cells) + " |")

    errs = sum(1 for r in results if "error" in r)
    cats = [r.get("category", "?") for r in results]
    print(f"\nSummary: {len(results)} reqs, {errs} errors, {fails} violations")
    print("Category mix:", json.dumps({c: cats.count(c) for c in sorted(set(cats))}))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "test_quality_retest_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 1 if (errs or fails) else 0


if __name__ == "__main__":
    sys.exit(main())
