"""Step 4 writes the pairs that were picked on screen — in both ways of picking.

A pair can be chosen twice over: as a chip under the cross-wavelet switch, or as
a line on the network diagram. They are one list behind the glass. What matters
to the study is neither of those: it is `include_crosswavelet` in config.json,
which is what decides whether the analysis runs at all. So that is what this
asserts, from the outside, after a real click-through.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest

pytest.importorskip("playwright", reason="pip install playwright && playwright install chromium")
from playwright.sync_api import sync_playwright  # noqa: E402

BUILDER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PAIR_CHIP = ("personLeftLeftHandSpeed", "personRightLeftHandSpeed")
PAIR_LINE = ("personLeftRightHandSpeed", "personRightRightHandSpeed")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def builder():
    """The wizard, on its own port, with its own example-study cache."""
    port = _free_port()
    env = dict(os.environ, BUILDER_PORT=str(port), DIMS_BUILDER_NO_BROWSER="1",
               DIMS_BUILDER_CACHE=tempfile.mkdtemp(prefix="e2e-cache-"))
    env.pop("WERKZEUG_RUN_MAIN", None)
    proc = subprocess.Popen([sys.executable, "-m", "dims_builder"], cwd=BUILDER, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if proc.poll() is not None:
            pytest.skip(f"the builder would not start:\n{proc.stdout.read()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.skip("the builder did not come up in 20s")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _chip(page, a, b):
    return page.locator("#cw_types .chip", has_text=f"{a} × {b}").first


def test_step4_writes_both_ways_of_picking_a_pair(builder, tmp_path):
    out = str(tmp_path / "study")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # dyad02's video is deliberately longer than its data, so the build asks
        # whether to go ahead. Playwright dismisses dialogs unless told.
        page.on("dialog", lambda d: d.accept())
        page.goto(builder, wait_until="networkidle")

        # 1 · the study
        page.fill("#output_dir", out)
        page.fill("#title", "e2e")
        page.click("#btn-create")
        page.wait_for_selector('.panel[data-panel="2"]:not([hidden])', timeout=30_000)

        # 2 · the example study, generated on first use
        page.click("#btn-samples")
        page.wait_for_function("() => document.querySelectorAll('#filelist .filerow').length >= 16",
                               timeout=180_000)
        page.click("#next-2")
        page.wait_for_selector('.panel[data-panel="3"]:not([hidden])')
        page.click("#next-3")
        page.wait_for_selector('.panel[data-panel="4"]:not([hidden])')

        # 4 · cross-wavelet starts empty; pick one pair as a chip
        page.check("#t_cw")
        assert page.locator("#cw_types .chip.on").count() == 0, \
            "the expensive analysis pre-selected pairs nobody asked for"
        _chip(page, *PAIR_CHIP).click()

        # ...and one as a line on the diagram, which is the same list. Driven
        # by clicking, because the point is that a person can reach this state.
        page.check("#t_network")
        for who in ("Left partner", "Right partner"):
            page.click("#add-person")
            page.locator(".people-strip input[type=text]").last.fill(who)
        for i, measure in enumerate(PAIR_LINE):
            spot = page.locator(f"#network-diagram [data-person][data-spot=righthand]").nth(i)
            spot.click()
            page.click(f"#spot-menu button[data-pick='{measure}']")
        # Dragged, not clicked: the gesture the diagram implies, and the one
        # jsdom can only approximate. Press on one node, release on the other.
        boxes = [page.locator(f"#network-diagram [data-dt='{m}'] circle").first.bounding_box()
                 for m in PAIR_LINE]
        page.mouse.move(boxes[0]["x"] + boxes[0]["width"] / 2,
                        boxes[0]["y"] + boxes[0]["height"] / 2)
        page.mouse.down()
        page.mouse.move(boxes[0]["x"] + 40, boxes[0]["y"] + 10, steps=4)
        assert page.locator("#rubber-band").count() == 1, \
            "nothing followed the pointer, so the drag gives no sign it started"
        page.mouse.move(boxes[1]["x"] + boxes[1]["width"] / 2,
                        boxes[1]["y"] + boxes[1]["height"] / 2, steps=8)
        page.mouse.up()
        assert _chip(page, *PAIR_LINE).evaluate("el => el.classList.contains('on')"), \
            "a line on the diagram did not show up as a selected pair"

        page.click("#next-4")
        page.wait_for_selector('.panel[data-panel="5"]:not([hidden])', timeout=15_000)
        page.click("#btn-build")
        page.wait_for_function(
            "() => document.querySelector('#msg-5') && "
            "document.querySelector('#msg-5').className.includes('ok')", timeout=120_000)
        browser.close()

    assert not errors, f"the page threw: {errors}"

    cfg = json.load(open(os.path.join(out, "config.json")))
    written = {tuple(sorted(p)) for p in cfg.get("include_crosswavelet", [])}
    assert written == {tuple(sorted(PAIR_CHIP)), tuple(sorted(PAIR_LINE))}, (
        "the study was built without the pairs that were picked on screen; the "
        "analysis will not run and the network tab will report no cross-wavelet "
        f"output. config.json says: {cfg.get('include_crosswavelet')}")
    assert cfg.get("include_network"), "the network was switched on and did not survive"
    assert cfg["analysis"]["crosswavelet"]["mcCount"] == 100, \
        "the network needs a chance level and the study does not record one"


def _to_step4(page, builder, out):
    """The wizard, clicked through to the cross-effector network step."""
    page.goto(builder, wait_until="networkidle")
    page.fill("#output_dir", out)
    page.fill("#title", "e2e")
    page.click("#btn-create")
    page.wait_for_selector('.panel[data-panel="2"]:not([hidden])', timeout=30_000)
    page.click("#btn-samples")
    page.wait_for_function("() => document.querySelectorAll('#filelist .filerow').length >= 16",
                           timeout=180_000)
    page.click("#next-2")
    page.wait_for_selector('.panel[data-panel="3"]:not([hidden])')
    page.click("#next-3")
    page.wait_for_selector('.panel[data-panel="4"]:not([hidden])')
    page.check("#t_network")


def _labels(page):
    return page.locator(".people-strip input[type=text]").evaluate_all(
        "els => els.map(e => e.value)")


def test_a_person_added_after_a_removal_does_not_reuse_a_name(builder, tmp_path):
    """Reported from this exact click-through, and it cost a measure.

    `addPerson` numbered by how many people there were, and a measure named its
    person by *label*, so removing one of three and adding another produced two
    people with the same name whose nodes were drawn on top of each other --
    and removing either stripped both of their measures.

    Driven through the real UI because the report was: I added three, removed
    one, and got something weird.
    """
    out = str(tmp_path / "study")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())
        _to_step4(page, builder, out)

        for _ in range(3):
            page.click("#add-person")
        assert _labels(page) == ["Person 1", "Person 2", "Person 3"]
        assert page.locator("#network-diagram .dims-figure").count() == 3

        # Put a measure on the third, so there is something to lose.
        third = page.locator("#network-diagram [data-person][data-spot=head]").nth(2)
        third.click()
        measure = page.locator("#spot-menu button[data-pick]").first
        kept = measure.get_attribute("data-pick")
        measure.click()
        assert page.locator(f"#network-diagram [data-dt='{kept}']").count() == 1

        # Remove the middle one and add a replacement: the reported sequence.
        page.locator(".people-strip [data-person-remove]").nth(1).click()
        assert _labels(page) == ["Person 1", "Person 3"]
        page.click("#add-person")

        names = _labels(page)
        assert len(set(names)) == len(names), \
            f"two people share a name, so a measure cannot say which it is on: {names}"
        assert names == ["Person 1", "Person 3", "Person 2"], names

        # And the measure is still where it was put, on its own person.
        assert page.locator(f"#network-diagram [data-dt='{kept}']").count() == 1, \
            "the measure came off the diagram when an unrelated person was added"

        # Removing the newcomer must not take the namesake's measure with it.
        page.locator(".people-strip [data-person-remove]").last.click()
        assert page.locator(f"#network-diagram [data-dt='{kept}']").count() == 1, \
            "removing one person removed another person's measure"

        browser.close()

    assert not errors, f"the page threw: {errors}"


def test_two_people_with_one_name_is_refused(builder, tmp_path):
    """The wizard's own names cannot collide now, but a typed one can, and the
    config identifies a measure's group by name -- so the dashboard would
    collapse the two and one person's measures would go with it. Said plainly,
    with the name in the message, rather than renaming anybody's person."""
    out = str(tmp_path / "study2")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        page.on("dialog", lambda d: d.accept())
        _to_step4(page, builder, out)

        page.check("#t_cw")
        _chip(page, *PAIR_CHIP).click()
        for _ in range(2):
            page.click("#add-person")
        for i in range(2):
            page.locator(".people-strip input[type=text]").nth(i).fill("Twin")

        page.click("#next-4")
        page.wait_for_function(
            "() => document.querySelector('#msg-4') && "
            "document.querySelector('#msg-4').textContent.includes('Twin')",
            timeout=10_000)
        assert page.locator('.panel[data-panel="4"]:not([hidden])').count() == 1, \
            "the wizard moved on and wrote a config naming two groups the same"
        browser.close()
