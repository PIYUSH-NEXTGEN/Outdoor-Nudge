"""Retest for safety & realism fixes (prompt + validator).

Runs 10 requests: anxious before an exam x3, 11pm can't sleep x3, angry x2, lonely x2.
Prints a results table (mood, category, title, task) and checks EVERY result against
each hard rule as a per-row matrix:

  safety - no eating/tasting/licking; smell-only for taste-smell; no bare-hand contact with
           plants/litter; litter needs gloves; leave sharp/wet litter; no climbing, no
           balancing on furniture, no roads, no water
  objects - no assumed bench/bin/bike rack/lamp post/bag/paper/notebook (mood may name them)
  night  - night requests: anchored at own door/balcony/window, no walking away, no strangers
  walk   - no bare "go for a walk/stroll" without a specific goal
  chores - no ordinary daily acts (sipping water, going to a bin, ...)
  venue  - no invented venues unless the mood names them (previous fix)
  lonely - lonely moods need human contact (previous fix; skipped at night by design)
  cap    - category used < 2x in the prior 10 requests (previous fix)

Run: .\\venv\\Scripts\\python.exe tests\\test_safety_fixes.py
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

MOODS = (
    ["anxious before an exam"] * 3
    + ["11pm can't sleep"] * 3
    + ["angry"] * 2
    + ["lonely"] * 2
)

CHECKS = ("safety", "objects", "night", "walk", "chores", "venue", "lonely", "cap")


def nudge(mood: str):
    body = json.dumps({"mood": mood}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/nudge", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def check_row(mood: str, cat: str, title: str, task: str, part_of_day: str) -> tuple[dict, bool]:
    """Returns ({check: (ok, reason)}, night_flag) for one result."""
    low = (title + " " + task).lower()
    mood_l = mood.lower()
    night = app.is_night_request(part_of_day, datetime.now().hour, mood)
    ok: dict = {}

    # safety + objects + night + walk + chores come from the shared validator tables
    viol = app.safety_violations(f"{title} {task}", cat, mood_l, night)
    obj = [v for v in viol if v.startswith("object-ban:")]
    night_v = [v for v in viol if v.startswith("night-")]
    walk_v = [v for v in viol if v == "generic-walk"]
    chore_v = [v for v in viol if v.startswith("ordinary-")]
    safety_v = [v for v in viol
                if v not in obj and v not in night_v and v not in walk_v and v not in chore_v]
    ok["safety"] = (not safety_v, ", ".join(safety_v))
    ok["objects"] = (not obj, ", ".join(obj))
    ok["night"] = (not night_v, ", ".join(night_v))
    ok["walk"] = (not walk_v, ", ".join(walk_v))
    ok["chores"] = (not chore_v, ", ".join(chore_v))

    venue = [label for pat, label in app.VENUE_BAN
             if re.search(pat, low) and not re.search(pat, mood_l)]
    ok["venue"] = (not venue, ", ".join(venue))

    if app.LONELY_MOOD_RE.search(mood_l) and not night and not app.CONTACT_RE.search(low):
        ok["lonely"] = (False, "no human contact")
    elif night:
        ok["lonely"] = (True, "night: rule skipped")
    else:
        ok["lonely"] = (True, "n/a")
    return ok, night


def main() -> int:
    results = []
    for mood in MOODS:
        prior_window = [h.get("category", "") for h in app.load_history()[-10:]]
        resp, err = nudge(mood)
        if resp is None:
            results.append({"mood": mood, "error": err,
                            "checks": {c: {"ok": False, "detail": "request-error"} for c in CHECKS}})
            print(f"ERROR mood={mood!r}: {err}")
            continue
        cat, title, task = resp["category"], resp["title"], resp["task"]
        checks, night = check_row(mood, cat, title, task, resp.get("part_of_day", ""))
        # mirror the server's cap logic: pick must be in the eligible pool, unless the
        # whole pool is capped (server then falls back to least-used by design)
        _, raw_pool = app.energy_pool(mood, False)
        pool = list(raw_pool) or list(app.MEDIUM_ENERGY_CATS)
        counts = {c: prior_window.count(c) for c in set(prior_window)}
        eligible = [c for c in pool if counts.get(c, 0) < app.CATEGORY_CAP]
        if not eligible:
            checks["cap"] = (True, "pool exhausted -> least-used fallback (by design)")
        elif cat in eligible:
            checks["cap"] = (True, f"{cat} {counts.get(cat, 0)}x in prior 10 (limit {app.CATEGORY_CAP})")
        else:
            checks["cap"] = (False, f"{cat} used {counts.get(cat, 0)}x in prior 10; eligible={eligible}")
        results.append({
            "mood": mood, "category": cat, "title": title, "task": task,
            "night": night, "part_of_day": resp.get("part_of_day", ""),
            "checks": {k: {"ok": v[0], "detail": v[1]} for k, v in checks.items()},
        })

    # ---- results table ----
    print("\n| # | mood | night | category | title | task |")
    print("|---|------|-------|----------|-------|------|")
    for i, r in enumerate(results, 1):
        if "error" in r:
            print(f"| {i} | {r['mood']} | - | ERROR | - | {r['error'][:90]} |")
        else:
            print(f"| {i} | {r['mood']} | {'YES' if r['night'] else 'no'} | {r['category']} "
                  f"| {r['title']} | {r['task']} |")

    # ---- per-rule matrix ----
    print("\n| # | " + " | ".join(CHECKS) + " |")
    print("|---|" + "---|" * len(CHECKS))
    failures = 0
    for i, r in enumerate(results, 1):
        cells = []
        for c in CHECKS:
            chk = r["checks"].get(c, {"ok": True, "detail": ""})
            if chk["ok"]:
                cells.append("OK")
            else:
                cells.append("FAIL: " + chk["detail"])
                failures += 1
        print(f"| {i} | " + " | ".join(cells) + " |")

    errors = sum(1 for r in results if "error" in r)
    cats = [r.get("category", "?") for r in results]
    print("\nSummary: %d requests, %d errors, %d rule violations" % (len(results), errors, failures))
    print("Category mix:", json.dumps({c: cats.count(c) for c in sorted(set(cats))}))
    print("taste-smell appeared %d time(s)" % cats.count("taste-smell"))

    with open("test_safety_fixes_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 1 if (errors or failures) else 0


if __name__ == "__main__":
    sys.exit(main())

