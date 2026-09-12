"""Take the thirteen walkthrough screenshots by driving the real builder.

    python tools/take_walkthrough_shots.py

Drives a real Chromium through every step of the wizard against
ConvoConnect-Mini -- the example study the builder generates -- and writes the
PNGs `docs/tutorial.md` expects into `docs/images/walkthrough/`. The contract
for what belongs in each shot is `docs/images/walkthrough/SHOTS.md`, which is
generated from the page's own capture notes; this script is how those states
are reached.

The shots live in the documentation tree because the documentation is published
per release: re-taking them changes what the *next* version's tutorial shows,
and leaves every published version showing the wizard it actually shipped.

Two things it does deliberately:

* **A cold chance-level cache.** `08-compute.png` has to be taken mid-run, and
  DIMS caches the cross-wavelet null in ~/.cache/dims -- so a second run of the
  same pairs finishes in seconds and there is nothing to photograph. This points
  DIMS_WCT_CACHE_DIR at a scratch directory, which makes step 6 take about nine
  minutes and gives the shot something real to show.
* **The step bar on every wizard shot**, stitched above the crops that are
  details inside a step. A reader meeting a screenshot in the middle of a long
  page needs to see which step it belongs to.

Needs playwright with Chromium (`pip install playwright && playwright install
chromium`) and Pillow. The study it builds goes to /tmp, deliberately outside
both repositories and free of any real username.
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright

# Relative to this file, so the script works from any checkout rather than from
# one machine. It used to name two absolute paths and a scratch directory that
# had since been deleted.
ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(ROOT, "apps", "builder")
OUTDIR  = os.path.join(ROOT, "docs", "images", "walkthrough")
SCRATCH = tempfile.mkdtemp(prefix="dims-walkthrough-")
STUDY   = "/tmp/convoconnect-mini"
log = lambda *a: print(*a, flush=True)

STITCH = """
import sys
from PIL import Image
bar, body, out = sys.argv[1], sys.argv[2], sys.argv[3]
a, b = Image.open(bar), Image.open(body)
w = max(a.width, b.width)
canvas = Image.new("RGB", (w, a.height + b.height), (13, 15, 20))
canvas.paste(a, (0, 0)); canvas.paste(b, (0, a.height))
canvas.save(out)
"""


PAIRS = [("personLeftLeftHandSpeed", "personRightLeftHandSpeed"),
         ("personLeftRightHandSpeed", "personRightRightHandSpeed")]
HANDS = [(0, "lefthand", "personLeftLeftHandSpeed"), (0, "righthand", "personLeftRightHandSpeed"),
         (1, "lefthand", "personRightLeftHandSpeed"), (1, "righthand", "personRightRightHandSpeed")]

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

DOC_BOX = """el => { const r = el.getBoundingClientRect();
    return {x: r.x + window.scrollX, y: r.y + window.scrollY,
            width: r.width, height: r.height}; }"""


def box(page, selector, nth=0):
    """An element's rectangle in *document* coordinates.

    Playwright's bounding_box() is relative to the viewport, and a full-page
    screenshot's clip is relative to the document. Mixing the two silently
    clipped the wrong band -- a shot of step 4 that began with a second copy of
    the page header stitched above it.
    """
    return page.locator(selector).nth(nth).evaluate(DOC_BOX)


def shot(page, name, panel=None, top_sel="#stepnav"):
    """The step bar, and everything down to the end of `panel`.

    The bar is the point: a reader meeting a screenshot in the middle of a long
    page needs to see which step it belongs to.
    """
    if not panel:
        page.screenshot(path=os.path.join(OUTDIR, name))
        log("  shot", name)
        return
    b = box(page, panel)
    if not b or not b["height"]:
        page.screenshot(path=os.path.join(OUTDIR, name)); log("  shot", name, "(viewport)")
        return
    t = box(page, top_sel)
    top = max(0, (t["y"] if t else b["y"]) - 10)
    page.screenshot(path=os.path.join(OUTDIR, name), full_page=True,
                    clip={"x": 0, "y": top, "width": 1280,
                          "height": b["y"] + b["height"] + 20 - top})
    log("  shot", name)


def crop_with_bar(page, name, top, height):
    """A detail inside a step, with the step bar stitched above it."""
    nav = box(page, "#stepnav")
    bar = os.path.join(SCRATCH, "_bar.png")
    page.screenshot(path=bar, full_page=True,
                    clip={"x": 0, "y": max(0, nav["y"] - 10), "width": 1280,
                          "height": nav["height"] + 20})
    body = os.path.join(SCRATCH, "_body.png")
    page.screenshot(path=body, full_page=True,
                    clip={"x": 0, "y": max(0, top), "width": 1280, "height": height})
    subprocess.run([sys.executable, "-c", STITCH, bar, body,
                    os.path.join(OUTDIR, name)], check=True)
    log("  shot", name)


TABS_ONLY = "--tabs-only" in sys.argv

if TABS_ONLY:
    # The dashboard shots, against a study that is already built and computed.
    # Worth having: the tabs are the fiddly half, and re-taking them should not
    # cost another nine minutes of cross-wavelet.
    # The study's own serve.py, not http.server: the dashboard's video needs
    # Range requests, and without them the page never reaches networkidle.
    server = subprocess.Popen([sys.executable, "serve.py", "8000"], cwd=STUDY,
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
                break
        except OSError:
            time.sleep(0.2)
    log(f"serving {STUDY} on :8000")
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        dash = br.new_context(viewport={"width": 1280, "height": 800},
                              device_scale_factor=2).new_page()
        errs = []
        dash.on("pageerror", lambda e: errs.append(str(e)))
        dash.goto("http://localhost:8000/index.html", wait_until="networkidle")
        dash.wait_for_timeout(6000)
        dash.evaluate("""() => {
            const s = document.querySelector('#timeSlider input[type=range]');
            s.value = 76; s.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        dash.wait_for_timeout(3000)

        def dash_shot(name):
            # The status line is not a reliable "done" signal — the network tab
            # leaves it reading "Loading cross-effector network…" after it has
            # drawn — so a stuck status is not worth failing a shot over.
            try:
                dash.wait_for_function(
                    "() => !(document.getElementById('status')||{}).textContent"
                    ".match(/^Loading/)", timeout=8000)
            except Exception:
                pass
            bar = dash.locator("#tabContainer").evaluate(DOC_BOX)
            top = max(0, bar["y"] - 12)
            bottom = 0
            for sel in ("#plotContainer", ".chart-section", "#tabContainer"):
                try:
                    b = dash.locator(sel).first.evaluate(DOC_BOX)
                    bottom = max(bottom, b["y"] + b["height"])
                except Exception:
                    pass
            dash.screenshot(path=os.path.join(OUTDIR, name), full_page=True,
                            clip={"x": 0, "y": top, "width": 1280,
                                  "height": min(1500, max(700, bottom - top + 20))})
            log("  shot", name)

        dash_shot("10-dashboard-timeseries.png")
        for name, label in (("10b-dashboard-elan.png", "ELAN Annotations"),
                            ("opt-rqa-tab.png", "RQA Plots"),
                            ("opt-crqa-tab.png", "Cross-RQA"),
                            ("opt-cw-tab.png", "Cross-Wavelet"),
                            ("opt-network-tab.png", "Cross-effector network")):
            try:
                dash.click(f'#tabContainer .tab-button:text-is("{label}")')
                dash.wait_for_timeout(6000)
                dash_shot(name)
            except Exception as exc:
                log("  FAILED", name, exc)
        log("page errors:", "; ".join(errs[:3]) or "none")
        br.close()
    server.terminate()
    raise SystemExit(0)

shutil.rmtree(STUDY, ignore_errors=True)
shutil.rmtree(f"{SCRATCH}/wct_shots", ignore_errors=True)
port = free_port()
env = dict(os.environ, BUILDER_PORT=str(port), DIMS_BUILDER_NO_BROWSER="1",
           DIMS_BUILDER_CACHE=f"{SCRATCH}/wc5", DIMS_WCT_CACHE_DIR=f"{SCRATCH}/wct_shots")
env.pop("WERKZEUG_RUN_MAIN", None)
proc = subprocess.Popen([sys.executable, "-m", "dims_builder"], cwd=BUILDER, env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
for _ in range(100):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2): break
    except OSError: time.sleep(0.2)

notes = []
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")

        shot(pg, "01-wizard-opens.png")

        pg.fill("#output_dir", STUDY)
        pg.fill("#title", "ConvoConnect-Mini")
        pg.fill("#authors", "DIMS tutorial")
        shot(pg, "02-your-study.png", '.panel[data-panel="1"]')
        pg.click("#btn-create")
        pg.wait_for_selector('.panel[data-panel="2"]:not([hidden])', timeout=30000)

        log("step 2: generating the example study")
        pg.click("#btn-samples")
        pg.wait_for_function("() => document.querySelectorAll('#filelist .filerow').length >= 16",
                             timeout=240000)
        pg.wait_for_timeout(800)
        rows = pg.locator("#filelist .filerow").count()
        notes.append(f"step 2 staged {rows} rows")
        shot(pg, "03-sessions-files.png", '.panel[data-panel="2"]')

        pg.click("#next-2")
        pg.wait_for_selector('.panel[data-panel="3"]:not([hidden])')
        pg.wait_for_timeout(1500)
        # dyad02 is the card with something to fix; capture the overhang, then fix it.
        card = pg.locator(".align-card", has_text="dyad02").first
        card.locator("button.d-trim").click()          # reveal the trim tool
        pg.wait_for_timeout(400)
        b = card.bounding_box()
        pg.screenshot(path=os.path.join(OUTDIR, "04-align.png"), full_page=True,
                      clip={"x": 0, "y": max(0, b["y"]-16), "width": 1280,
                            "height": b["height"]+32})
        log("  shot 04-align.png")   # a detail of one card; no step bar wanted
        card.locator("button.t-apply").click()
        pg.wait_for_timeout(4000)                       # ffmpeg writes the trimmed copy
        pg.click("#next-3")
        pg.wait_for_selector('.panel[data-panel="4"]:not([hidden])')

        # ---- phase A: the core path ---------------------------------------
        # ELAN and recurrence on one measure, and nothing else. This is what the
        # tutorial's core actually tells a reader to do.
        log("step 4: the core (ELAN + recurrence on rtpjSync)")
        pg.check("#t_elan")
        pg.check("#t_rqa")

        def keep_only(box_id, wanted):
            """Narrow a chip row to `wanted`, re-querying every time: each click
            re-renders the row, so a list of handles goes stale after the first."""
            for _ in range(40):
                on = pg.eval_on_selector_all(f"#{box_id} .chip.on",
                                             "els => els.map(e => e.textContent.trim())")
                extra = [l for l in on if l not in wanted]
                if not extra:
                    return
                pg.click(f'#{box_id} .chip:text-is("{extra[0]}")')
                pg.wait_for_timeout(80)
            raise AssertionError(f"could not narrow {box_id}")

        keep_only("rqa_types", {"rtpjSync"})
        # All five analysis blocks, not just recurrence: the instruction is
        # "switch on two things", and the shot has to show the other three left
        # alone or it illustrates something the text did not say.
        rq = box(pg, ".analysis", 0)
        el = box(pg, '.analysis:has(#t_elan)')
        crop_with_bar(pg, "05-analyses.png", rq["y"] - 16,
                      el["y"] + el["height"] - rq["y"] + 32)

        pg.click("#next-4")
        pg.wait_for_selector('.panel[data-panel="5"]:not([hidden])', timeout=20000)
        pg.click("#btn-build")
        pg.wait_for_function("() => document.querySelector('#msg-5').className.includes('ok')",
                             timeout=180000)
        pg.wait_for_timeout(500)
        pg.click('.step[data-step="5"]')          # a build jumps to step 6 at once
        pg.wait_for_selector('.panel[data-panel="5"]:not([hidden])')
        pg.wait_for_timeout(400)
        shot(pg, "07-build.png", '.panel[data-panel="5"]')
        pg.click('.step[data-step="6"]')

        log("step 6: the core run (recurrence only)")
        t0 = time.time()
        pg.click("#btn-precompute")
        pg.wait_for_function(
            "() => (document.querySelector('#precompute-log').textContent||'')"
            ".includes('Processing video')", timeout=300000)
        pg.wait_for_timeout(900)
        shot(pg, "08-compute.png", '.panel[data-panel="6"]')
        pg.wait_for_selector('.panel[data-panel="7"]:not([hidden])', timeout=1800000)
        notes.append(f"core step 6 took {time.time()-t0:.0f}s")
        log(f"  core step 6 done in {time.time()-t0:.0f}s")
        pg.wait_for_timeout(600)
        shot(pg, "09-open-it.png", '.panel[data-panel="7"]')

        pg.click("#btn-preview")
        pg.wait_for_timeout(4000)
        dash = ctx.new_page()
        dash.on("pageerror", lambda e: errs.append("dashboard: " + str(e)))

        def open_dash():
            dash.goto("http://localhost:8000/index.html", wait_until="networkidle")
            dash.wait_for_timeout(6000)
            dash.evaluate("""() => {
                const s = document.querySelector('#timeSlider input[type=range]');
                s.value = 76; s.dispatchEvent(new Event('input', {bubbles: true}));
            }""")
            dash.wait_for_timeout(3000)

        def dash_shot(name):
            """The tab bar and the whole of what the tab drew — a viewport shot
            cuts the picture off below the fold."""
            # The status line is not a reliable "done" signal — the network tab
            # leaves it reading "Loading cross-effector network…" after it has
            # drawn — so a stuck status is not worth failing a shot over.
            try:
                dash.wait_for_function(
                    "() => !(document.getElementById('status')||{}).textContent"
                    ".match(/^Loading/)", timeout=8000)
            except Exception:
                pass
            bar = dash.locator("#tabContainer").evaluate(DOC_BOX)
            top = max(0, bar["y"] - 12)
            # Not every tab draws into #plotContainer -- ELAN and recurrence put
            # their content elsewhere, and measuring the wrong box gives a clip
            # of height zero, which is a screenshot that never happens.
            bottom = 0
            for sel in ("#plotContainer", ".chart-section", "#tabContainer"):
                try:
                    b = dash.locator(sel).first.evaluate(DOC_BOX)
                    bottom = max(bottom, b["y"] + b["height"])
                except Exception:
                    pass
            height = min(1500, max(700, bottom - top + 20))
            dash.screenshot(path=os.path.join(OUTDIR, name), full_page=True,
                            clip={"x": 0, "y": top, "width": 1280, "height": height})
            log("  shot", name)

        def dash_tab(name, label):
            try:
                dash.click(f'#tabContainer .tab-button:text-is("{label}")')
                dash.wait_for_timeout(6000)
                dash_shot(name)
            except Exception as exc:
                notes.append(f"{name}: {type(exc).__name__} {exc}")
                log("  FAILED", name, exc)

        open_dash()
        dash_shot("10-dashboard-timeseries.png")
        dash_tab("10b-dashboard-elan.png", "ELAN Annotations")
        dash_tab("opt-rqa-tab.png", "RQA Plots")

        # ---- phase B: the optional analyses --------------------------------
        # Back to step 4, switch on what the expandable sections describe, and
        # rebuild -- which is exactly the instruction each of them gives.
        log("phase B: cross-recurrence, cross-wavelet, the network")
        pg.bring_to_front()
        pg.click('.step[data-step="4"]')
        pg.wait_for_selector('.panel[data-panel="4"]:not([hidden])')
        pg.check("#t_crqa")
        keep_only("crqa_types", {"personLeftRightHandSpeed × personRightRightHandSpeed"})
        pg.check("#t_cw")
        for a, b_ in PAIRS:
            pg.click(f'#cw_types .chip:text-is("{a} × {b_}")')
        cw = box(pg, '.analysis:has(#cw_types)')
        crop_with_bar(pg, "opt-cw-step4.png", cw["y"] - 16, cw["height"] + 32)

        pg.check("#t_network")
        for who in ("Left partner", "Right partner"):
            pg.click("#add-person")
            pg.locator(".people-strip input[type=text]").last.fill(who)
        for idx, part, measure in HANDS:
            pg.locator(f"#network-diagram [data-person][data-spot={part}]").nth(idx).click()
            pg.click(f"#spot-menu button[data-pick='{measure}']")
        pg.wait_for_timeout(300)
        nb = box(pg, '.analysis:has(#network-diagram)')
        crop_with_bar(pg, "opt-network-step4.png", nb["y"] - 16, nb["height"] + 32)

        pg.click("#next-4")
        pg.wait_for_selector('.panel[data-panel="5"]:not([hidden])', timeout=20000)
        pg.click("#btn-build")
        pg.wait_for_function("() => document.querySelector('#msg-5').className.includes('ok')",
                             timeout=180000)
        pg.wait_for_selector('.panel[data-panel="6"]:not([hidden])')
        log("step 6 again: cross-wavelet on a cold chance-level cache")
        t0 = time.time()
        pg.click("#btn-precompute")
        pg.wait_for_selector('.panel[data-panel="7"]:not([hidden])', timeout=2400000)
        notes.append(f"phase B step 6 took {time.time()-t0:.0f}s")
        log(f"  done in {time.time()-t0:.0f}s")

        pg.click("#btn-preview")
        pg.wait_for_timeout(4000)
        open_dash()
        dash_tab("opt-crqa-tab.png", "Cross-RQA")
        dash_tab("opt-cw-tab.png", "Cross-Wavelet")
        dash_tab("opt-network-tab.png", "Cross-effector network")

        notes.append("page errors: " + ("; ".join(errs[:4]) or "none"))
        br.close()
finally:
    proc.terminate()

log("\n".join(notes))
json.dump(notes, open("/tmp/shots_notes.json", "w"))
