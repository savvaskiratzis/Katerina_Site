#!/usr/bin/env python3
"""Re-stamp every versioned asset reference from the file's CONTENT hash.

The site serves /css/* and /images/* with `Cache-Control: immutable, max-age=31536000`
(see _headers), so a changed file that keeps its URL is frozen in returning visitors'
browsers for a year. The old scheme used a date token (?v=20260917) and it failed exactly
as predicted: a second CSS change the same day kept serving the old stylesheet.

This tool is the replacement. It hashes css/style.css and css/welcome.css and rewrites the
?v= token in every HTML page, and it also keeps the favicon's inline fill colour in step
with the theme. Run it from the deploy script so a token can never go stale.

Usage: python3 tools/version-assets.py [--check]
       --check exits 1 if anything is stale (used as a deploy gate).
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "privacy.html"]
SHEETS = ["css/style.css", "css/welcome.css", "vendor/font-awesome/6.5.1/subset/fa-subset.css"]
TARGET_FILL = "%236b7363"          # --sage, as a URL-encoded '#'

# /vendor/* is cached immutable for a year (see _headers), on the assumption that a future
# Font Awesome update would land in a NEW version directory. That assumption breaks the moment
# we rebuild the subset in place: adding an icon changes fa-subset.css AND fa-solid-900.woff2
# under the same path, so returning visitors would keep the old glyph set for a year and see a
# blank square. The fonts are referenced from the subset CSS, so they are stamped together with
# it — same rule as /fonts/* and css/style.css.
FA_SUBSET = "vendor/font-awesome/6.5.1/subset/fa-subset.css"
FA_FONT_PAT = re.compile(r"(url\((fa-[a-z0-9-]+\.woff2))(\?v=[0-9a-f]{8})?(\))")


def stamp_fa_fonts():
    """Bust each subset font with its own content hash, inside the subset CSS."""
    p = os.path.join(ROOT, FA_SUBSET)
    if not os.path.exists(p):
        return
    css = open(p, encoding="utf-8").read()
    orig = css

    def repl(m):
        font = m.group(2)
        path = os.path.join("vendor/font-awesome/6.5.1/subset", font)
        if not os.path.exists(os.path.join(ROOT, path)):
            return m.group(0)
        return f"{m.group(1)}?v={h8(path)}{m.group(4)}"

    css = FA_FONT_PAT.sub(repl, css)
    if css != orig:
        changes.append(f"{FA_SUBSET}: ?v= στα woff2 ενημερώθηκαν")
        if "--check" not in sys.argv:
            open(p, "w", encoding="utf-8").write(css)


def h8(path):
    return hashlib.sha256(open(os.path.join(ROOT, path), "rb").read()).hexdigest()[:8]

changes = []
stamp_fa_fonts()
for page in PAGES:
    p = os.path.join(ROOT, page)
    if not os.path.exists(p):
        continue
    html = open(p, encoding="utf-8").read()
    orig = html
    for sheet in SHEETS:
        digest = h8(sheet)
        pat = re.compile(r"(" + re.escape(sheet) + r"\?v=)([0-9a-f]{8})")
        for m in pat.finditer(html):
            if m.group(2) != digest:
                changes.append(f"{page}: {sheet} {m.group(2)} -> {digest}")
        html = pat.sub(lambda m: m.group(1) + digest, html)
    # Subset CSS may be referenced without a token yet (privacy.html): add one. Without it the
    # immutable /vendor/ cache would hide a rebuilt subset (new icons) from returning visitors.
    for sheet in SHEETS:
        if "?v=" in sheet or not sheet.endswith(".css"):
            continue
        digest = h8(sheet)
        bare = re.compile(r"(" + re.escape(sheet) + r")(?!\?v=)(?=[\"'])")
        if bare.search(html):
            html = bare.sub(lambda m: m.group(1) + "?v=" + digest, html)
            changes.append(f"{page}: {sheet} χωρίς ?v= -> {digest}")
    # favicon: an inline SVG in a data: URL, still carrying the OLD rose fill
    if "fill='%23DF6C73'" in html:
        html = html.replace("fill='%23DF6C73'", f"fill='{TARGET_FILL}'")
        changes.append(f"{page}: favicon fill %23DF6C73 -> {TARGET_FILL}")
    if html != orig:
        if "--check" in sys.argv:
            continue
        open(p, "w", encoding="utf-8").write(html)

for c in changes:
    print("  " + c)
if not changes:
    print("  (όλα τα ?v= tokens είναι ενημερωμένα)")
if "--check" in sys.argv and changes:
    sys.exit("✗ stale asset versions — τρέξε tools/version-assets.py")
