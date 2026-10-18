#!/usr/bin/env python3
"""Μετράει το ύψος του εισαγωγικού κειμένου του «Σχετικά με Εμένα».

ΓΙΑΤΙ ΥΠΑΡΧΕΙ. Η φωτογραφία του About πρέπει να «κλείνει» ακριβώς με το κείμενο από τη
γραμμή-εισαγωγή ως το «…λόγου, ομιλίας και επικοινωνίας.». Κάθε αλλαγή κειμένου Ή γραμματοσειράς
αλλάζει αυτό το ύψος — και τότε η φωτογραφία περισσεύει ή λείπει. Αυτό το εργαλείο δίνει το
ΝΟΥΜΕΡΟ· το build-about-portrait.py το μετατρέπει σε αναλογία, νέα assets και patch σε CSS/HTML.

Έχει ήδη συμβεί δύο φορές: 702px (αρχικό κείμενο) → 604px (β' έκδοση) → 651px (γραμμή-εισαγωγή
στα 28px). Γι' αυτό δεν το αφήνουμε στο χέρι.

ΠΑΓΙΔΕΣ ΠΟΥ ΣΕΒΕΤΑΙ (κόστισαν επαναλήψεις):
  * η παράγραφος-στόχος βρίσκεται ΑΠΟ ΤΟ ΠΕΡΙΕΧΟΜΕΝΟ, όχι από σταθερό δείκτη (οι δείκτες
    μετακινούνται με κάθε αλλαγή κειμένου και ένας σταθερός δείκτης «περνά» με λάθος ζεύγος)·
  * τα `.fade-in` φοράνε `transform: translateY(30px)` μέχρι να μπουν στο viewport — χρειάζεται
    ΣΤΑΣΗ στο στοιχείο και αναμονή της κλάσης `visible`, αλλιώς η μέτρηση βγαίνει 30px λάθος.

Χρήση: ~/.venvs/fortinet/bin/python tools/measure-about.py [url] [--json]
"""
import json
import sys

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://staging.tsigalogo-staging.pages.dev/"
COLUMN_W = 550          # μετρημένο πλάτος στήλης σε desktop (1280–1920)

JS = """() => {
  const vis = el => el && el.offsetParent !== null;
  const ps = Array.from(document.querySelectorAll('.about-text p')).filter(vis);
  const first = ps[0];
  const target = ps.find(p => p.innerText.includes('επικοινωνίας.'));
  const box = document.querySelector('.about-image').getBoundingClientRect();
  const col = document.querySelector('.about-text').getBoundingClientRect();
  return {
    first_text: first.innerText.replace(/\\s+/g,' ').trim().slice(0, 46),
    target_text: target ? target.innerText.replace(/\\s+/g,' ').trim().slice(-46) : null,
    text_h: target ? Math.round(target.getBoundingClientRect().bottom - first.getBoundingClientRect().top) : null,
    col_w: Math.round(col.width),
    photo: [Math.round(box.width), Math.round(box.height)],
    d_bottom: target ? Math.round(target.getBoundingClientRect().bottom - box.bottom) : null,
  };
}"""


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    url = args[0] if args else DEFAULT_URL
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1400, "height": 1000},
                            extra_http_headers={"Cache-Control": "no-cache"})
        pg = ctx.new_page()
        pg.goto(url, wait_until="networkidle")
        pg.reload(wait_until="networkidle")
        pg.evaluate("() => { const o=document.getElementById('welcomeOverlay');"
                    " const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
        pg.wait_for_timeout(1000)
        # ΣΤΑΣΗ στο About: και τα δύο .fade-in πρέπει να σταθεροποιηθούν πριν μετρηθεί το κουτί
        pg.evaluate("() => { const g=document.querySelector('.about-grid');"
                    " window.scrollTo({top: g.getBoundingClientRect().top + window.scrollY - 120,"
                    " behavior: 'instant'}); }")
        for sel in (".about-image", ".about-text"):
            try:
                pg.wait_for_function(
                    f"() => document.querySelector('{sel}').classList.contains('visible')", timeout=6000)
            except Exception:
                pass
        pg.wait_for_timeout(800)
        d = pg.evaluate(JS)
        b.close()

    H = d["text_h"]
    if H is None:
        sys.exit("δεν βρέθηκε η παράγραφος-στόχος («…επικοινωνίας.») — άλλαξε το κείμενο;")
    out = {
        "url": url,
        "text_h": H,
        "col_w": d["col_w"],
        "ratio": round(d["col_w"] / H, 4),
        "prefix": f"katerina-tsiga-p{H}",
        "photo_now": d["photo"],
        "d_bottom_now": d["d_bottom"],
        "first_text": d["first_text"],
        "target_tail": d["target_text"],
    }
    if "--json" in sys.argv:
        print(json.dumps(out))
        return
    print(f"πηγή: {url}")
    print(f"  1η παράγραφος : «{out['first_text']}…»")
    print(f"  στόχος (τέλος): «…{out['target_tail']}»")
    print(f"  ύψος κειμένου : {H}px  σε στήλη {out['col_w']}px  ->  αναλογία {out['ratio']}")
    print(f"  φωτογραφία τώρα: {d['photo'][0]}x{d['photo'][1]}  (Δκάτω {d['d_bottom']}px — θέλουμε 0)")
    print(f"  επόμενο: ~/.venvs/img/bin/python tools/build-about-portrait.py --text-h {H}")


if __name__ == "__main__":
    main()
