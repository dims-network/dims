"""Build hooks for the MkDocs site.

`docs/analyses/demo/analyses-plots.js` fetches its payloads by bare name --
`fetch("demo_rqa.json")` -- because the website's renderer copies the script and
the JSON it needs next to each generated page. MkDocs keeps the source layout
instead, so a relative fetch from `/analyses/rqa/` would look for
`/analyses/rqa/demo_rqa.json` and find nothing.

Rather than fork the script (it is shared with tools/render_docs.py and checked
by CI), put the payloads where each page already looks for them. They are 312 KB
in total, so the duplication is cheap; if that stops being true, give the script
a base path and delete this file.
"""
from __future__ import annotations

import os
import re
import shutil
import tomllib

from mkdocs.structure.files import File

PAYLOADS = ("demo_signals.json", "demo_crosswavelet.json",
            "demo_rqa.json", "demo_crqa.json")


def on_post_build(config, **kwargs) -> None:
    site = config["site_dir"]
    src = os.path.join(site, "analyses", "demo")
    if not os.path.isdir(src):
        return

    # Every directory holding a rendered analyses page: `analyses/` itself for
    # the overview, plus one per page under directory URLs.
    targets = [os.path.join(site, "analyses")]
    for name in sorted(os.listdir(os.path.join(site, "analyses"))):
        d = os.path.join(site, "analyses", name)
        if name != "demo" and os.path.isfile(os.path.join(d, "index.html")):
            targets.append(d)

    for payload in PAYLOADS:
        origin = os.path.join(src, payload)
        if not os.path.isfile(origin):
            continue
        for target in targets:
            shutil.copy2(origin, os.path.join(target, payload))


# --- links that leave docs/ ------------------------------------------------
#
# The markdown is written to be read on GitHub as well as on a site, so pages
# link into the source tree: `../../packages/dims-tabs/rqa.js`. MkDocs has no
# page to point those at and warns about every one of them.
#
# tools/render_docs.py on the website already answers this the same way -- send
# the reader to the file in the core, at the released ref, rather than to a 404
# -- so do exactly that here. Keeping the two renderers' answers identical is
# the point: a link that works on one site should work on the other.

HERE = os.path.dirname(os.path.abspath(__file__))
LINK = re.compile(r'(?<=]\()([^)\s]+)(?=[)\s])')


def _ref() -> str:
    """The released tag to link at, so a link is stable once published."""
    try:
        with open(os.path.join(HERE, "pyproject.toml"), "rb") as fh:
            return "v" + tomllib.load(fh)["project"]["version"]
    except Exception:
        return "main"


def on_page_markdown(markdown, page, config, files, **kwargs):
    repo = config.get("repo_url", "").rstrip("/")
    if not repo:
        return markdown
    src_dir = os.path.dirname(page.file.src_path)

    def rewrite(match):
        url = match.group(1)
        if url.startswith(("http://", "https://", "#", "mailto:", "/")):
            return url
        clean, _, anchor = url.partition("#")
        anchor = ("#" + anchor) if anchor else ""
        target = os.path.normpath(os.path.join(src_dir, clean))
        # Inside docs/ -- MkDocs resolves it itself.
        if not target.startswith(".."):
            return url
        # Outside: repository-relative, at the released ref.
        repo_path = os.path.normpath(os.path.join("docs", src_dir, clean))
        return f"{repo}/blob/{_ref()}/{repo_path.lstrip('/')}" + anchor

    return LINK.sub(rewrite, markdown)


# --- the mark ---------------------------------------------------------------
#
# The header wordmark and the favicon are the project's own, and they live with
# the code that draws them into every dashboard
# (packages/dims-core/branding/) rather than in docs/. Publishing them from
# there keeps one copy: a second one in docs/ is a second thing to update when
# the branding changes, and the dashboards would keep the old one.
#
# dims-logo-light.png is the variant for a light background -- the same one
# dims-core.js loads for the light theme -- and this site is light only.

BRANDING = os.path.join("packages", "dims-core", "branding")
MARKS = {
    "images/dims-logo-light.png": "dims-logo-light.png",   # header
    "images/dims-mark.png": "dims-mark.png",               # favicon
}


def on_files(files, config, **kwargs):
    for uri, name in MARKS.items():
        src = os.path.join(HERE, BRANDING, name)
        if not os.path.isfile(src):
            raise FileNotFoundError(
                f"{os.path.join(BRANDING, name)} is missing; mkdocs.yml points "
                f"the logo or favicon at it")
        try:
            asset = File.generated(config, uri, abs_src_path=src)
        except AttributeError:          # MkDocs < 1.6
            asset = File(name, os.path.join(HERE, BRANDING),
                         config["site_dir"], config["use_directory_urls"])
        files.append(asset)
    return files
