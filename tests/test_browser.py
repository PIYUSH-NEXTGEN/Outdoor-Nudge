"""Browser tests for index.html (Playwright). Run: .\\venv\\Scripts\\python.exe tests\\test_browser.py"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

# Windows console (cp1252) cannot encode symbols like ✓ — force UTF-8 output.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = "http://127.0.0.1:8000"
SHOT_DIR = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)
results = []

def record(name, ok, info=""):
    results.append({"test": name, "ok": bool(ok), "info": str(info)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (" :: " + str(info)[:160] if info else ""))

def shot(page, name):
    page.screenshot(path=os.path.join(SHOT_DIR, name), full_page=True)

nudge_bodies = []  # every POST /api/nudge body, for request-contract assertions

def get_nudge(page, mood="restless and stuck at my desk", model=None):
    page.fill("#mood", mood)
    if model:
        page.select_option("#model", model)
    nudge_bodies.clear()
    page.click("#nudgeBtn")
    try:
        page.wait_for_selector("#result h3", timeout=120000)
        return True, ""
    except Exception:
        return False, "no result: " + page.inner_text("#nudgeStatus")[:150]

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))
    def on_req(req):
        if req.url.endswith("/api/nudge") and req.method == "POST":
            try: nudge_bodies.append(json.loads(req.post_data or "{}"))
            except Exception: nudge_bodies.append({})
    page.on("request", on_req)

    # 1. page loads, no console errors
    page.goto(BASE, wait_until="networkidle")
    record("1 page loads without console errors",
           len([e for e in console_errors if "favicon" not in e]) == 0, console_errors[:3])

    # 2. weather strip: live data or fallback input
    wx = page.inner_text("#weather")
    has_live = bool(re.search(r"\d+(\.\d+)?\s*(?:°|\s)?\s*C", wx, re.I))
    has_fallback = "unavailable" in wx and page.locator("#wxManual").count() == 1
    record("2 weather strip shows live data or manual fallback", has_live or has_fallback, wx[:120])

    # 3. mood textarea + exactly 4 chips
    chips = page.locator(".chip")
    chip_texts = [chips.nth(i).inner_text() for i in range(chips.count())]
    record("3 mood textarea + 4 chips (Restless/Drained/Overwhelmed/Need a reset)",
           chips.count() == 4 and "Restless" in chip_texts and "Need a reset" in chip_texts, chip_texts)
    chips.nth(0).click()
    record("3b chip click writes mood into textarea", "Restless" in page.input_value("#mood"),
           page.input_value("#mood"))
    page.fill("#mood", "")

    # 4/5. nudge flow renders title/task/bring/minutes/model
    ok, why = get_nudge(page)
    record("4 Nudge me returns a rendered nudge", ok, why)
    if ok:
        h3 = page.inner_text("#result h3")
        task = page.inner_text("#result .task")
        meta = page.inner_text("#result .meta")
        has_bring = page.locator("#result .bring li").count() >= 1
        has_minutes = re.search(r"\d+\s*min", page.inner_text("#result .kicker"), re.I) is not None
        record("5 result shows task text, bring list, minutes, model",
               len(task) > 20 and has_bring and has_minutes and ("llama3" in meta or "gemma" in meta),
               "title=%r bring=%s min=%s" % (h3[:40], has_bring, has_minutes))
        shot(page, "3-result-desktop.png")
        req_mood = nudge_bodies[-1].get("mood", "") if nudge_bodies else ""
        record("5b request carried typed mood", "stuck at my desk" in req_mood, req_mood[:80])

    # 6. countdown start / stop / finish
    if ok:
        out = page.locator("#result output")
        t0 = out.inner_text()
        page.click('#result [data-t="start"]')
        page.wait_for_timeout(2200)
        t1 = out.inner_text()
        record("6 countdown Start ticks down (MM:SS)", t0 != t1 and t1 < t0, t0 + " -> " + t1)
        page.click('#result [data-t="stop"]')
        t2 = out.inner_text()
        page.wait_for_timeout(2200)
        t3 = out.inner_text()
        record("6b countdown Stop freezes clock", t2 == t3, t2 + " -> " + t3)
        page.evaluate("state.timerLeft = 2")
        page.click('#result [data-t="start"]')
        page.wait_for_timeout(3500)
        msg = page.inner_text("#result .tmsg")
        record("6c countdown reaches 0 with 'Time to head back'", msg == "Time to head back", msg)

    # 7. easier action sends easier:true + exclude
    if ok:
        first_title = page.inner_text("#result h3")
        nudge_bodies.clear()
        try:
            with page.expect_response(lambda r: "/api/nudge" in r.url, timeout=120000):
                page.click('#result [data-a="easier"]')
            page.wait_for_timeout(500)
        except Exception:
            pass
        body = nudge_bodies[-1] if nudge_bodies else {}
        record("7 easier sends easier:true + excludes previous title",
               body.get("easier") is True and first_title in (body.get("exclude") or []),
               json.dumps(body)[:180])

    # 8. another excludes previous, no easier
    if ok:
        prev_title = page.inner_text("#result h3")
        nudge_bodies.clear()
        try:
            with page.expect_response(lambda r: "/api/nudge" in r.url, timeout=120000):
                page.click('#result [data-a="another"]')
            page.wait_for_timeout(500)
        except Exception:
            pass
        body = nudge_bodies[-1] if nudge_bodies else {}
        record("8 another excludes previous title, no easier flag",
               prev_title in (body.get("exclude") or []) and not body.get("easier"),
               json.dumps(body)[:180])

    # 9. done action marks the entry done via POST /api/done (server-persisted)
    if ok:
        done_resp, status_code = {}, -1
        try:
            with page.expect_response(lambda r: r.url.endswith("/api/done"), timeout=15000) as ri:
                page.click('#result [data-a="done"]')
            resp = ri.value
            status_code = resp.status
            done_resp = json.loads(resp.body() or b"{}")
        except Exception as e:
            done_resp = {"error": str(e)[:120]}
        page.wait_for_timeout(300)
        btn = page.locator('#result [data-a="done"]')
        txt = btn.inner_text()
        status = page.inner_text("#result .status")
        entry = done_resp.get("entry") or {}
        record("9 done button marks entry done via POST /api/done",
               status_code == 200 and btn.is_disabled() and ("Done" in txt or "✓" in txt)
               and "done" in status.lower() and done_resp.get("ok") is True
               and entry.get("done") is True,
               "http=%s btn=%r status=%r entry.done=%s" % (status_code, txt, status[:70], entry.get("done")))
        # server state must persist: the history entry carries the done flag
        hist = json.loads(page.request.get(BASE + "/api/history").body() or b"{}")
        matching = [h for h in (hist.get("history") or []) if h.get("id") and h.get("id") == entry.get("id")]
        record("9b done flag persisted in history.json (not localStorage)",
               bool(matching) and matching[0].get("done") is True
               and page.evaluate("() => localStorage.getItem('nudgeDone')") is None,
               "matched=%s ls=%s" % (bool(matching), page.evaluate("() => localStorage.getItem('nudgeDone')")))
    # 10. model dropdown populated from /api/models (chat-capable, deduped)
    opts = page.locator("#model option").all_inner_texts()
    low_opts = [o.lower() for o in opts]
    clean = not any(("llamacpp" in o) or ("embed" in o) or ("blob" in o) for o in low_opts)
    deduped = len(opts) == len(set(opts))
    record("10 model dropdown lists chat models only, no llamacpp/embed, deduped",
           "llama3.2:3b" in opts and "gemma3:4b" in opts and len(opts) >= 2 and clean and deduped, opts)

    # 11. compare toggle -> two side-by-side results
    page.check("#compareToggle")
    b_visible = page.locator("#modelBWrap").is_visible()
    # default compare pair, before any manual selection
    sel_a = page.locator("#model").evaluate("el => el.value")
    sel_b = page.locator("#modelB").evaluate("el => el.value")
    record("11a compare defaults to llama3.2:3b vs gemma3:4b",
           sel_a == "llama3.2:3b" and sel_b == "gemma3:4b", "%s / %s" % (sel_a, sel_b))
    # pick two guaranteed-distinct models (Ollama may expose duplicates)
    avail = page.locator("#model option").all_inner_texts()
    distinct = sorted(set(avail))
    page.select_option("#model", distinct[0])
    page.select_option("#modelB", distinct[-1])
    nudge_bodies.clear()
    page.click("#nudgeBtn")
    try:
        # wait until BOTH cards have rendered their task, not just the first
        page.wait_for_function(
            "() => document.querySelectorAll('#compareGrid .result .task').length === 2",
            timeout=240000)
        cards = page.locator("#compareGrid .result").count()
        models_used = sorted(set(b.get("model", "") for b in nudge_bodies))
        record("11 compare shows two model results side by side",
               b_visible and cards == 2 and len(models_used) == 2,
               "cards=%s models=%s" % (cards, models_used))
        shot(page, "4-compare-two-models.png")
    except Exception as e:
        record("11 compare shows two model results side by side", False, str(e)[:200])
    page.uncheck("#compareToggle")

    # 12. history collapsible
    page.click("#histBox summary")
    page.wait_for_selector("#histList li", timeout=15000)
    n_hist = page.locator("#histList li").count()
    record("12 history opens and lists entries (newest first)",
           n_hist >= 1, "%d entries; first=%r" % (n_hist, page.inner_text("#histList li >> nth=0")[:90]))
    shot(page, "5-history-open.png")
    page.click("#histBox summary")  # close again

    # 13. weather fallback when endpoint fails
    page2 = ctx.new_page()
    page2.on("request", on_req)  # capture POST /api/nudge bodies on this page too
    page2.route("**/api/weather", lambda r: r.fulfill(status=500, content_type="application/json", body='{"error":"offline"}'))
    page2.goto(BASE, wait_until="networkidle")
    fb = page2.inner_text("#weather")
    record("13 weather failure shows manual describe-the-weather input",
           "unavailable" in fb and page2.locator("#wxManual").is_visible(), fb[:120])
    page2.fill("#wxManual", "light drizzle, 11C, evening")
    nudge_bodies.clear()
    page2.fill("#mood", "wet and bored")
    page2.click("#nudgeBtn")
    try:
        page2.wait_for_selector("#result h3", timeout=120000)
        body = nudge_bodies[-1] if nudge_bodies else {}
        record("13b manual weather text sent as weather_override",
               body.get("weather_override") == "light drizzle, 11C, evening", json.dumps(body)[:160])
        shot(page2, "6-weather-fallback.png")
    except Exception as e:
        record("13b manual weather text sent as weather_override", False, str(e)[:200])
    page2.close()

    # 14. mobile 390px
    mob = browser.new_context(viewport={"width": 390, "height": 844})
    mp = mob.new_page()
    mp.goto(BASE, wait_until="networkidle")
    ow = mp.evaluate("document.documentElement.scrollWidth")
    over = mp.evaluate("""() => [...document.querySelectorAll('body *')]
        .filter(e => e.getBoundingClientRect().right > 391 && e.offsetParent !== null)
        .map(e => e.tagName + '.' + (e.className || '')).slice(0, 5)""")
    record("14 mobile 390px: no horizontal overflow", ow <= 390 and not over,
           "scrollWidth=%s offenders=%s" % (ow, over))
    shot(mp, "7-mobile-390-top.png")
    mok, mwhy = get_nudge(mp)
    if mok:
        shot(mp, "8-mobile-390-result.png")
    record("14b mobile nudge flow works at 390px", mok, mwhy)
    mob.close()

    # screenshots: desktop light (already open page) + dark
    shot(page, "1-desktop-light-full.png")
    dk = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
    dp = dk.new_page()
    dp.goto(BASE, wait_until="networkidle")
    shot(dp, "2-desktop-dark-full.png")
    dk.close()
    browser.close()

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_browser_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
passed = sum(1 for r in results if r["ok"])
print("\n%d/%d checks passed" % (passed, len(results)))
for r in results:
    if not r["ok"]:
        print("  FAILED:", r["test"], "::", r["info"][:200])

