"""Helper: pretty-print every successful task from a quality retest results JSON.
Usage: .\\venv\\Scripts\\python.exe tests\\show_tasks.py [results.json]
"""
import json
import os
import sys

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "test_quality_retest_results.json")
data = json.load(open(path, encoding="utf-8"))
for r in data:
    if "error" in r:
        print(f"#{r['n']} [{r['time']}] {r['mood']} :: ERROR {r['error'][:90]}")
        continue
    print(f"#{r['n']} [{r['time']}] {r['mood']} | night={r.get('night')} "
          f"| {r.get('category')}/{r.get('energy')}")
    print(f"   TITLE: {r.get('title')}")
    print(f"   TASK : {r.get('task')}")
    fails = [f"{k}={v['detail']}" for k, v in r["checks"].items() if not v["ok"]]
    print(f"   CHECKS: {'ALL OK' if not fails else 'FAIL -> ' + '; '.join(fails)}")
    print()
