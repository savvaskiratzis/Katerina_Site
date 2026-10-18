#!/usr/bin/env python3
"""Σμικρύνει τα ΛΑΤΙΝΙΚΑ Literata subsets στα σύμβολα που πραγματικά χρησιμοποιούνται.

ΓΙΑΤΙ. Το PageSpeed/Lighthouse έδειξε FCP κινητού 3,0s στο staging vs 2,5s στο live, και η αιτία
είναι τα βάρη: live 96KB γραμματοσειρές, staging 203KB. Το +108KB είναι η νέα Literata. Τα
ελληνικά αρχεία είναι ήδη λιτά (14,6KB το καθένα — όλη η ελληνική περιοχή), αλλά τα ΛΑΤΙΝΙΚΑ
είναι 39,8 + 38,6KB επειδή το Google subset καλύπτει ΟΛΟ το U+0000-00FF + latin-ext. Η σελίδα
όμως χρησιμοποιεί ASCII + λίγα τυπογραφικά.

ΤΙ ΚΑΝΕΙ
  1. μαζεύει τους χαρακτήρες ΠΟΥ ΧΡΗΣΙΜΟΠΟΙΟΥΝΤΑΙ (και στις δύο γλώσσες, και στις δύο σελίδες)
     από το rendered DOM — όχι από τα source, γιατί μετράει ό,τι πράγματι βλέπει ο χρήστης·
  2. προσθέτει ένα «δίχτυ ασφαλείας» (όλο το ASCII + συνηθισμένα τυπογραφικά) ώστε μια μικρή
     αλλαγή κειμένου να μη βγάλει tofu·
  3. subset-άρει τα 2 λατινικά, ΚΡΑΤΩΝΤΑΣ τα layout features (kerning/ligatures — αλλιώς
     αλλάζει η οπτική πυκνότητα των τίτλων);
  4. ΕΛΕΓΧΕΙ ότι κάθε χρησιμοποιούμενος χαρακτήρας υπάρχει στο subset (αλλιώς fallback = λάθος
     γραμματοσειρά, το χειρότερο σενάριο);
  5. γράφει και το ΝΕΟ unicode-range στο CSS, βγαλμένο από το cmap του subset — ώστε το range
     να ΜΗΝ ξεφύγει ποτέ από το περιεχόμενο (αν έλεγε U+0000-00FF ενώ λείπει γλύφος, ο browser
     θα κατέβαζε το αρχείο και θα έβρισκε κενό)

Χρήση: ~/.venvs/img/bin/python tools/build-font-subsets.py [--dry-run]
"""
import os
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
DRY = "--dry-run" in sys.argv

# Χαρακτήρες που ΧΡΗΣΙΜΟΠΟΙΕΙ η σελίδα (θα γεμίσουν από τη μέτρηση). Προς το παρόν, γνωστοί.
EXTRA = "«»“”‘’–—…·•€™°→←±×÷≥≤§¶†‡‰′″№"


def used_chars() -> str:
    """Ό,τι βλέπει ο χρήστης, και στις 2 γλώσσες και στις 2 σελίδες."""
    from playwright.sync_api import sync_playwright

    base = "https://staging.tsigalogo-staging.pages.dev/"
    seen = set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1400, "height": 1000})
        pg = ctx.new_page()
        for page in ("", "privacy"):
            pg.goto(base + page, wait_until="networkidle")
            pg.evaluate("() => { const o=document.getElementById('welcomeOverlay');"
                        " const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
            for i in range(12):
                pg.evaluate(f"() => window.scrollTo(0, document.body.scrollHeight * {i} / 12)")
                pg.wait_for_timeout(110)
            for lang in ("el", "en"):
                pg.evaluate(f"() => {{ try {{ switchLang('{lang}') }} catch(e) {{}} }}")
                pg.wait_for_timeout(400)
                seen |= set(pg.evaluate("() => document.body.innerText"))
                # και τα attributes που εμφανίζονται (placeholders, labels)
                seen |= set(pg.evaluate("""() => Array.from(document.querySelectorAll('[placeholder],[aria-label],[title]'))
                    .map(e => (e.placeholder || '') + (e.getAttribute('aria-label') || '') + (e.title || '')).join('')"""))
        b.close()
    return "".join(sorted(seen))


def codepoints(chars: str) -> list:
    return sorted({ord(c) for c in chars if ord(c) > 32 and not (0x7F <= ord(c) <= 0x9F)})


def ranges(cps: list) -> str:
    out, start, prev = [], None, None
    for c in cps:
        if start is None:
            start = prev = c
            continue
        if c == prev + 1:
            prev = c
            continue
        out.append((start, prev))
        start = prev = c
    if start is not None:
        out.append((start, prev))
    return ", ".join(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}" for a, b in out)


def main():
    live = used_chars()
    ascii_safe = "".join(chr(c) for c in range(33, 127))
    latin_used = set(live) | set(ascii_safe) | set(EXTRA) | set(" \u00a0")
    latin_used = {c for c in latin_used if ord(c) < 0x0370}      # τα ελληνικά έχουν το δικό τους
    cps = codepoints("".join(latin_used))
    print(f"χρησιμοποιούμενοι χαρακτήρες (σύνολο σελίδας): {len(live)}")
    print(f"λατινικό subset: {len(cps)} κωδικά σημεία")

    report = []
    for name in ("literata-latin", "literata-italic-latin"):
        # ΤΑ ΠΡΩΤΟΤΥΠΑ (Google subsets) ΔΕΝ μένουν στο fonts/ — δεν τα ζητά κανείς, αλλά το
        # εργαλείο τα χρειάζεται για να ξανατρέξει. Ζουν στο artwork-src/fonts-originals/
        # (εκτός deploy whitelist), ώστε το fonts/ να περιέχει ΜΟΝΟ ό,τι σερβίρεται.
        src = FONTS / f"{name}.woff2"
        if not src.exists():
            src = ROOT / "artwork-src" / "fonts-originals" / f"{name}.woff2"
        dst = FONTS / f"{name}-sub.woff2"
        if not src.exists():
            print(f"  ✗ λείπει το πρωτότυπο {name}.woff2 (ούτε στο fonts/ ούτε στο artwork-src/fonts-originals/)")
            continue
        before = src.stat().st_size
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]          # kerning/ligatures: αλλιώς αλλάζει η πυκνότητα
        opts.notdef_outline = True
        font = subset.load_font(str(src), opts)
        s = subset.Subsetter(options=opts)
        s.populate(unicodes=cps)
        s.subset(font)
        cmap = set(font.getBestCmap().keys())
        missing = [c for c in sorted(latin_used) if ord(c) > 32 and ord(c) not in cmap]
        if not DRY:
            subset.save_font(font, str(dst), opts)
        after = dst.stat().st_size if dst.exists() else 0
        report.append((name, before, after, ranges(sorted(cmap)), missing))
        print(f"  {name}: {before//1024}KB → {after//1024}KB   "
              f"λείπουν: {(''.join(missing) if missing else 'κανένα')}")

    if DRY:
        print("(dry-run: δεν γράφτηκε τίποτα)")
        return
    total_b = sum(b for _, b, _, _, _ in report)
    total_a = sum(a for _, _, a, _, _ in report)
    print(f"  ΣΥΝΟΛΟ: {total_b//1024}KB → {total_a//1024}KB  (κέρδος {(total_b-total_a)//1024}KB)")

    # ---- ενημέρωση CSS: νέο αρχείο + unicode-range από το πραγματικό cmap
    css_path = ROOT / "css" / "welcome.css"
    css = css_path.read_text(encoding="utf-8")
    for name, _, _, rng, _ in report:
        css = css.replace(f"url('../fonts/{name}.woff2')", f"url('../fonts/{name}-sub.woff2')")
        # το unicode-range της αντίστοιχης δήλωσης: μόλις μετά το src url
        pat = re.compile(r"(url\('\.\./fonts/" + re.escape(name) + r"-sub\.woff2'\) format\('woff2'\);\n(\s*)unicode-range: )([^;]+)(;)")
        css, n = pat.subn(lambda m: m.group(1) + rng + m.group(4), css, count=1)
        print(f"  CSS {name}: url + unicode-range ενημερώθηκαν ({n})")
    css_path.write_text(css, encoding="utf-8")


main()
