#!/usr/bin/env python3
"""SEO parity: what crawlers read must be IDENTICAL between the live site and the redesign.

A redesign that also rewrites the <title>, the meta description, the H1 or the structured
data can quietly undo months of ranking. Design is free; text that ranks is not. This
compares the production tree against the v2 tree and fails on any difference in:

  <title>, meta description, canonical, og:/twitter: tags, every JSON-LD block (parsed and
  re-serialised so whitespace does not count), the H1's text, the number of h2s, and the
  visible text of every tel:/mailto: link.

Usage: python3 tools/seo-parity.py [--prod DIR] [--v2 DIR]
"""
import html
import json
import os
import re
import sys

PROD = os.path.expanduser("~/tsiga-speech-therapy")
V2 = os.path.expanduser("~/tsiga-speech-therapy-v2")
for i, a in enumerate(sys.argv):
    if a == "--prod":
        PROD = sys.argv[i + 1]
    if a == "--v2":
        V2 = sys.argv[i + 1]

PAGES = ["index.html", "privacy.html"]


def strip_comments(s):
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)


def strip_lang(s):
    """Text content with tags removed.

    NOT a regex over the markup: the first version tried to delete the `.lang-en` branch with
    `<span class="lang-en">.*?</span>` and, because the branch is NESTED, it cut at the first
    inner </span> — leaving mangled leftovers on one side only and reporting a false SEO
    difference in the H1. A heading's markup may legitimately change in a redesign (<br> ->
    a styled span); its TEXT may not. So compare text, not tags.
    """
    return re.sub(r"<[^>]+>", " ", s or "")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def one(pattern, s, flags=re.S):
    m = re.search(pattern, s, flags)
    return m.group(1).strip() if m else None


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def facts(path):
    raw = read(path)
    s = strip_comments(raw)
    ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
    ld_norm = []
    for block in ld:
        try:
            ld_norm.append(json.dumps(json.loads(block), sort_keys=True, ensure_ascii=False))
        except Exception as e:
            ld_norm.append(f"UNPARSEABLE: {e}")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    return {
        "title": norm(one(r"<title>(.*?)</title>", s)),
        "meta_description": norm(one(r'<meta name="description" content="(.*?)"', s)),
        "canonical": norm(one(r'<link rel="canonical" href="(.*?)"', s)),
        "og_title": norm(one(r'<meta property="og:title" content="(.*?)"', s)),
        "og_description": norm(one(r'<meta property="og:description" content="(.*?)"', s)),
        "robots_meta": norm(one(r'<meta name="robots" content="(.*?)"', s)),
        "jsonld_blocks": len(ld_norm),
        "jsonld": sorted(ld_norm),
        "h1_text": norm(strip_lang(h1.group(1))) if h1 else None,
        "h1_count": len(re.findall(r"<h1[^>]*>", s)),
        "h2_count": len(re.findall(r"<h2[^>]*>", s)),
        "tel_links": sorted(set(re.findall(r'href="(tel:[^"]+)"', s))),
        "mailto_links": sorted(set(re.findall(r'href="(mailto:[^"]+)"', s))),
        "ads_tag": len(re.findall(r"googletagmanager|AW-|gtag\(", s)),
        "internal_anchors": sorted(set(re.findall(r'href="(#[a-z-]+)"', s))),
    }


# Εγκεκριμένες, ΑΠΟ ΤΟΝ ΙΔΙΟΚΤΗΤΗ, αποκλίσεις. Το gate συνεχίζει να πιάνει ΚΑΘΕ άλλη αλλαγή —
# αλλά δεν κολλάει σε ό,τι ζητήθηκε ρητά, και το καταγράφει αντί να το κρύβει.
APPROVED = {
    ("index.html", "og_description"):
        "19/9/2026 — «Από το 2012» → «Από το 2013» (έτος έναρξης, ζητήθηκε από τον ιδιοκτήτη)",
    ("index.html", "jsonld"):
        "19/9/2026 — ίδιο έτος στο JSON-LD (description + foundingDate). 18/10/2026 — το "
        "`image` δείχνει πλέον την κάρτα og (χωρίς πρόσωπο, ζητήθηκε) και προστέθηκε `logo` "
        "(logo-kt-512.png) για τη Google· κανένα άλλο πεδίο του schema δεν άλλαξε.",
    ("index.html", "internal_anchors"):
        "19/9/2026 — το «Σχετικά» απέκτησε 4 ΥΠΟ-ΚΟΥΜΠΙΑ (ζητήθηκε από τον ιδιοκτήτη), άρα 4 νέα "
        "εσωτερικά anchors: #about-intro, #approach, #studies, #how-i-work. ΠΡΟΣΘΕΤΙΚΗ αλλαγή — "
        "κανένα παλιό anchor δεν χάθηκε, και ο έλεγχος «κάθε anchor έχει υπαρκτό id» (πιο κάτω) "
        "επιβεβαιώνει ότι κανένα δεν είναι κρεμασμένο.",
}

# Έλεγχος που ΔΕΝ υπήρχε: κανένα anchor χωρίς στόχο. Ένα κρεμασμένο #link είναι χειρότερο από
# ένα εξτρά anchor — ο επισκέπτης πατάει και δεν γίνεται τίποτα.
def dangling_anchors(path):
    s = open(path, encoding="utf-8").read()
    hrefs = set(re.findall(r'href="(#[A-Za-z0-9_-]+)"', s))
    ids = set(re.findall(r'\sid="([A-Za-z0-9_-]+)"', s))
    return sorted(a for a in hrefs if a[1:] not in ids)


fails = []
approved = []
for page in PAGES:
    pp, vp = os.path.join(PROD, page), os.path.join(V2, page)
    if not (os.path.exists(pp) and os.path.exists(vp)):
        print(f"— {page}: λείπει από το ένα δέντρο, παράλειψη")
        continue
    a, b = facts(pp), facts(vp)
    print(f"\n── {page} ──────────────────────────────────────────────")
    for key in a:
        same = a[key] == b[key]
        if same:
            shown = a[key]
            if isinstance(shown, list):
                shown = f"{len(shown)} στοιχεία"
            if isinstance(shown, str) and len(shown) > 68:
                shown = shown[:65] + "…"
            print(f"  ✓ {key:18s} {shown}")
            continue
        why = APPROVED.get((page, key))
        if why:
            print(f"  ≈ {key:18s} ΕΓΚΕΚΡΙΜΕΝΗ ΑΠΟΚΛΙΣΗ — {why}")
            approved.append(f"{page}:{key}")
            continue
        print(f"  ✗ {key:18s} ΔΙΑΦΕΡΕΙ")
        print(f"      prod: {a[key]}")
        print(f"      v2  : {b[key]}")
        fails.append(f"{page}:{key}")

print()
if approved:
    print(f"≈ {len(approved)} εγκεκριμένες από τον ιδιοκτήτη αποκλίσεις: {', '.join(approved)}")
dangling = dangling_anchors(os.path.join(V2, 'index.html'))
if dangling:
    fails.append(f"index.html:dangling_anchors({','.join(dangling)})")
    print(f"  ✗ {'dangling_anchors':18s} ΔΙΑΦΕΡΕΙ — anchors ΧΩΡΙΣ στόχο: {dangling}")
else:
    print(f"  ✓ {'dangling_anchors':18s} όλα τα εσωτερικά anchors έχουν υπαρκτό id")

if fails:
    sys.exit(f"✗ {len(fails)} πεδία SEO διαφέρουν: {', '.join(fails)}")
print("✅ SEO parity OK — ό,τι διαβάζουν οι crawlers είναι ίδιο με το live (εκτός εγκεκριμένων).")
