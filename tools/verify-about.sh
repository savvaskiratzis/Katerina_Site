#!/usr/bin/env bash
# verify-about.sh — ad-hoc verification για το «Σχετικά με Εμένα» + το hero της κεντρικής.
#
# ΜΟΝΙΜΟ (όχι /tmp): περιέχει τις παγίδες μέτρησης που κόστισαν επαναλήψεις, ώστε η επόμενη
# αλλαγή κειμένου/εικόνας να μην τις ξανα-ανακαλύψει:
#   * η παράγραφος-στόχος βρίσκεται ΑΠΟ ΤΟ ΠΕΡΙΕΧΟΜΕΝΟ, όχι από σταθερό δείκτη (το κείμενο
#     αλλάζει και οι δείκτες μετακινούνται — ένας σταθερός δείκτης «περνά» με λάθος ζεύγος);
#   * η ορατότητα ελέγχεται με `offsetParent`, ΟΧΙ με getComputedStyle().display
#     (δεν κληρονομείται: παιδί μέσα σε display:none αναφέρει το δικό του display);
#   * τα `.fade-in` χρειάζονται ΠΡΑΓΜΑΤΙΚΟ scroll: γι' αυτό γίνεται wait_for_function στην
#     κλάση `visible` αντί για σταθερό sleep μετά από programmatic scrollIntoView (race με το
#     smooth scroll του pop-up — έδωσε ψευδές FAIL δύο φορές);
#   * πριν μετρηθεί το CSS, επιβεβαιώνεται με curl ότι το deployment το σερβίρει ήδη
#     (edge propagation lag έδωσε ψευδές FAIL: μετρήθηκε η προηγούμενη έκδοση).
#
# Χρήση: bash tools/verify-about.sh [url]
set -uo pipefail
V2="$(cd "$(dirname "$0")/.." && pwd)"
S="${1:-https://staging.tsigalogo-staging.pages.dev}"
PY_PW="$HOME/.venvs/fortinet/bin/python"
TMP=$(mktemp -d /tmp/hermes-verify-XXXXXX)
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
no() { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
chk() { if [ "$2" = "$3" ]; then ok "$1 ($3)"; else no "$1 (got '$2', want '$3')"; fi; }

echo "── A. to μόνιμο harness ──"
bash "$V2/tools/verify-redesign.sh" >"$TMP/main.log" 2>&1
chk "tools/verify-redesign.sh exit" "$?" "0"

echo "── B. το deployed φέρει τις νέες τιμές (πριν μετρηθεί το DOM) ──"
curl -s "$S/css/style.css" >"$TMP/css"; curl -s -H 'Cache-Control: no-cache' "$S/" >"$TMP/html"
# Το ύψος της φωτογραφίας και το όνομα των assets ΔΕΝ είναι καρφωμένα: αλλάζουν με κάθε αλλαγή
# κειμένου/γραμματοσειράς (702 -> 604 -> 651 σε μία μέρα). Διαβάζονται από το deployed CSS, και
# μετά ελέγχεται ότι HTML/DOM συμφωνούν μαζί του. Έτσι ο έλεγχος δεν χρειάζεται ενημέρωση.
PH=$(grep -oE "aspect-ratio: 550 / [0-9]+" "$TMP/css" | grep -oE "[0-9]+\$")
[ -n "$PH" ] && ok "CSS: aspect-ratio 550/$PH" || no "CSS: λείπει το aspect-ratio 550/N"
grep -q "katerina-tsiga-p${PH}-550.avif" "$TMP/html" && ok "HTML: assets p$PH" || no "HTML: λείπει το p$PH asset"
grep -q 'class="v-badge"' "$TMP/html" && ok "HTML: v-badge (εικονίδιο χειλιών)" || no "HTML: λείπει το v-badge"
grep -q "fa-brain" "$TMP/html" && no "HTML: μένει fa-brain" || ok "HTML: κανένα fa-brain"
STALE=$(grep -oE "katerina-tsiga-p[0-9]+" "$TMP/html" | sort -u | grep -v "p${PH}\$")
[ -z "$STALE" ] && ok "HTML: κανένα asset άλλου ύψους" || no "HTML: μένει παλιό ύψος: $STALE"

echo "── C. DOM (ΕΛ + ΕΝ) ──"
"$PY_PW" - "$S" "$PH" >"$TMP/dom.log" 2>&1 <<'PY'
import sys
from playwright.sync_api import sync_playwright
URL = sys.argv[1]
PH = int(sys.argv[2])          # ύψος φωτογραφίας = ύψος κειμένου, από το CSS
JS = """() => {
  const vis = el => el && el.offsetParent !== null;
  const tx = sel => Array.from(document.querySelectorAll(sel)).filter(vis)
      .map(e => e.innerText.replace(/\\s+/g,' ').trim());
  const box = document.querySelector('.about-image').getBoundingClientRect();
  const ps = Array.from(document.querySelectorAll('.about-text p')).filter(vis);
  const target = ps.find(p => p.innerText.includes('επικοινωνίας.'));   // από το περιεχόμενο
  const lips = document.querySelector('.v-badge img'); const lic = document.querySelector('.about-license');
  return {
    lead: tx('.about-lead')[0], h3: tx('#about h3'), h4: tx('#about h4'),
    lists: Array.from(document.querySelectorAll('.about-list')).filter(vis).map(u => u.querySelectorAll('li').length),
    target_ok: !!target && target.innerText.includes('Από το 2013'),
    d_bottom: target ? Math.round(target.getBoundingClientRect().bottom - box.bottom) : null,
    photo: [Math.round(box.width), Math.round(box.height)], ratio: +(box.width/box.height).toFixed(4),
    src: document.querySelector('.about-photo').currentSrc.split('/').pop(),
    lips: lips ? [Math.round(lips.getBoundingClientRect().width), Math.round(lips.getBoundingClientRect().height)] : null,
    lip_nat: lips ? lips.naturalWidth : null,
    badge: lips ? Math.round(lips.closest('i').getBoundingClientRect().width) : null,
    brain: !!document.querySelector('.welcome-values .fa-brain'),
    // >= 0.99 και όχι === '1': μέτρηση στα 400ms μιας μετάβασης 0.6s δίνει 0.9x και
    // φαίνεται «αόρατο», ενώ απλώς δεν είχε τελειώσει η κίνηση.
    lic_vis: !!(lic && vis(lic) && lic.classList.contains('visible')
                && parseFloat(getComputedStyle(lic).opacity) >= 0.99),
    // 30 χάρηκες ήταν πολύ λίγοι: το «2360» ζει μετά το 30ό στοιχείο και ο έλεγχος
    // απέτυχε ενώ η κάρτα ήταν μια χαρά. Κόβουμε πιο μετά.
    lic_text: lic ? lic.innerText.replace(/\\s+/g,' ').trim().slice(0, 90) : '',
  };
}"""
bad = 0
def check(n, c, d=""):
    global bad
    print(f"  {'PASS' if c else 'FAIL'}  {n} {d}"); bad += 0 if c else 1
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 1000},
                        extra_http_headers={"Cache-Control": "no-cache"})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle"); pg.reload(wait_until="networkidle")
    pg.evaluate("() => { const o=document.getElementById('welcomeOverlay'); const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
    pg.wait_for_timeout(1200)
    # (α) ΣΤΑΣΗ στο About ώστε να σταθεροποιηθούν ΤΑ ΔΥΟ .fade-in (εικόνα + κείμενο). Τα .fade-in
    #     έχουν `transform: translateY(30px)` μέχρι να πάρουν την κλάση `visible` — μέτρηση πριν
    #     από αυτό δίνει Δκάτω = -30 και μοιάζει με λάθος ευθυγράμμιση, ενώ είναι animation.
    #     Προσοχή: ένα JUMP (instant scrollTo) πάνω από ένα στοιχείο δεν αρκεί — ο IO αξιολογεί
    #     σε frame boundaries και το προσπερνά. Χρειάζεται στάση ΜΕΣΑ στο viewport.
    pg.evaluate("""() => { const g = document.querySelector('.about-grid');
        window.scrollTo({ top: g.getBoundingClientRect().top + window.scrollY - 120, behavior: 'instant' }); }""")
    for sel in (".about-image", ".about-text"):
        try:
            pg.wait_for_function(
                f"() => document.querySelector('{sel}').classList.contains('visible')", timeout=6000)
        except Exception as exc:
            print(f"  (το {sel} δεν πήρε visible: {type(exc).__name__})")
    pg.wait_for_timeout(700)          # να ολοκληρωθεί και το transition (0.6s)

    # (β) μετά στην κάρτα άδειας — πάλι με στάση, και μετά η μέτρηση
    pg.evaluate("""() => { const el = document.querySelector('.about-license');
        window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 400, behavior: 'instant' }); }""")
    try:
        pg.wait_for_function(
            "() => document.querySelector('.about-license').classList.contains('visible')", timeout=6000)
        pg.wait_for_function(
            "() => parseFloat(getComputedStyle(document.querySelector('.about-license')).opacity) >= 0.99",
            timeout=4000)
    except Exception as exc:
        print(f"  (η κάρτα δεν ολοκλήρωσε τη μετάβαση: {type(exc).__name__})")
    pg.wait_for_timeout(200)
    d = pg.evaluate(JS)
    check("ΕΛ lead", d["lead"] == "Η λογοθεραπεία για μένα ξεκινά από τη σύνδεση", d["lead"])
    check("ΕΛ 3 h3 σωστή σειρά",
          d["h3"] == ["Η δική μου προσέγγιση", "Σπουδές & Επαγγελματική Εμπειρία", "Πώς δουλεύω"], d["h3"])
    check("ΕΛ h4", d["h4"] == ["Εξατομικευμένα θεραπευτικά πλάνα"], d["h4"])
    check("ΕΛ 2 λίστες (6+2)", d["lists"] == [6, 2], d["lists"])
    check("παράγραφος-στόχος = «Από το 2013…επικοινωνίας.»", d["target_ok"])
    check(f"φωτογραφία 550x{PH} + Δκάτω=0",
          d["photo"] == [550, PH] and d["d_bottom"] == 0, (d["photo"], d["d_bottom"], PH))
    check(f"αναλογία 550:{PH} (χωρίς stretch)", abs(d["ratio"] - 550/PH) < 0.002, d["ratio"])
    check(f"σερβίρεται p{PH} asset", d["src"] == f"katerina-tsiga-p{PH}-550.avif", d["src"])
    check("χείλη: εικόνα 30x17 native, badge 52px, χωρίς fa-brain",
          d["lips"] == [30, 17] and d["lip_nat"] == 30 and d["badge"] == 52 and not d["brain"],
          (d["lips"], d["lip_nat"], d["badge"]))
    check("κάρτα άδειας: visible + opacity 1", d["lic_vis"] and "2360" in d["lic_text"], d["lic_text"])
    pg.evaluate("() => { try { switchLang('en') } catch(e) {} }")
    pg.wait_for_timeout(600)
    en = pg.evaluate(JS)
    check("ΕΝ lead", en["lead"] == "For me, speech therapy starts with connection", en["lead"])
    check("ΕΝ 3 h3", en["h3"] == ["My approach", "Education & Professional Experience", "How I work"], en["h3"])
    check("ΕΝ h4 + λίστες", en["h4"] == ["Personalised therapy plans"] and en["lists"] == [6, 2])
    ctx.close(); b.close()
print("OK" if not bad else "BAD")
PY
grep -E '^  (PASS|FAIL) ' "$TMP/dom.log" | sed 's/^/      /'
chk "DOM έλεγχοι" "$(grep -c '^OK$' "$TMP/dom.log")" "1"

echo "── D. εικονίδιο χειλιών (αντιγραφή από artwork), γραμματοσειρά h3, υπο-κουμπιά «Σχετικά» ──"
grep -q "icon-lips-30.webp" "$TMP/html" && ok "HTML: αναφέρει το εικονίδιο χειλιών" || no "HTML: λείπει το εικονίδιο"
grep -q "w-lips" "$TMP/html" && no "HTML: μένει το παλιό SVG w-lips" || ok "HTML: κανένα παλιό SVG"
grep -q "fa-chevron-down" "$TMP/html" && ok "HTML: chevron" || no "HTML: λείπει το chevron"

"$PY_PW" - "$S" >"$TMP/new.log" 2>&1 <<'PY'
import sys
from playwright.sync_api import sync_playwright
URL = sys.argv[1]
JS = """() => {
  const vis = el => el && el.offsetParent !== null;
  const img = document.querySelector('.v-badge img');
  const badge = img && img.closest('i');
  const h3 = Array.from(document.querySelectorAll('.about-text h3')).filter(vis);
  const sub = document.querySelector('.nav-sub');
  const links = sub ? Array.from(sub.querySelectorAll('a')).map(a => a.innerText.replace(/\\s+/g,' ').trim()) : [];
  const anchors = ['about-intro','approach','studies','how-i-work']
      .map(id => { const el = document.getElementById(id); return el ? el.tagName + '#' + id : null; });
  return {
    lips: img ? {w: Math.round(img.getBoundingClientRect().width), h: Math.round(img.getBoundingClientRect().height),
                 nat: img.naturalWidth, ok: img.complete,
                 src: img.currentSrc.split('/').pop(), old_svg: !!document.querySelector('.w-lips')} : null,
    badge_w: badge ? Math.round(badge.getBoundingClientRect().width) : null,
    h3: h3.map(e => { const cs = getComputedStyle(e);
        return {fam: cs.fontFamily.split(',')[0].replace(/["']/g,''), it: cs.fontStyle, color: cs.color}; }),
    nav: {exists: !!sub, items: links,
          hidden_desktop: sub ? getComputedStyle(sub).opacity === '0' : null,
          chevron: (() => { const c = document.querySelector('.sub-parent i');
              const v = c ? getComputedStyle(c,'::before').content : null; return !!v && v !== 'none'; })()},
    anchors,
  };
}"""
bad = 0
def check(n, c, d=""):
    global bad
    print(f"  {'PASS' if c else 'FAIL'}  {n} {d}"); bad += 0 if c else 1
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width":1400,"height":1000}, extra_http_headers={"Cache-Control":"no-cache"})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle"); pg.reload(wait_until="networkidle")
    pg.evaluate("() => { const o=document.getElementById('welcomeOverlay'); const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
    pg.wait_for_timeout(1200)
    d0 = pg.evaluate(JS)                     # ΚΛΕΙΣΤΟ dropdown
    check("desktop: κλειστό χωρίς hover", d0["nav"]["hidden_desktop"])
    pg.hover(".nav-menu > li.has-sub > a"); pg.wait_for_timeout(500)
    d = pg.evaluate(JS)                      # ΑΝΟΙΧΤΟ: οι ετικέτες διαβάζονται μόνο έτσι
    check("εικονίδιο: 30x17, native, φορτωμένο, χωρίς παλιό SVG",
          d["lips"] and d["lips"]["w"] == 30 and d["lips"]["h"] == 17 and d["lips"]["nat"] == 30
          and d["lips"]["ok"] and not d["lips"]["old_svg"], d["lips"])
    check("badge ίδιο μέγεθος με τα FA (52px)", d["badge_w"] == 52, d["badge_w"])
    check("και τα 3 h3: Literata + italic + sage",
          len(d["h3"]) == 3 and all(x["fam"] == "Literata" and x["it"] == "italic"
                                    and x["color"] == "rgb(95, 102, 86)" for x in d["h3"]),
          [(x["fam"], x["it"]) for x in d["h3"]])
    check("υπο-κουμπιά: 4, σωστή σειρά",
          d["nav"]["items"] == ["Η λογοθεραπεία για μένα ξεκινά από τη σύνδεση", "Η δική μου προσέγγιση",
                                "Σπουδές & Επαγγελματική Εμπειρία", "Πώς δουλεύω"], d["nav"]["items"])
    check("chevron glyph υπάρχει", d["nav"]["chevron"])
    check("4 anchors (περιλαμβανομένου του #about-intro)",
          d["anchors"] == ["DIV#about-intro", "SPAN#approach", "SPAN#studies", "SPAN#how-i-work"], d["anchors"])
    # κλικ σε κάθε υπο-κουμπί: σωστό hash ΚΑΙ προσγείωση κάτω από το sticky header
    for i, aid in ((1, "approach"), (2, "studies"), (3, "how-i-work")):
        pg.evaluate("() => window.scrollTo(0,0)"); pg.wait_for_timeout(350)
        pg.hover(".nav-menu > li.has-sub > a"); pg.wait_for_timeout(400)
        pg.hover(f".nav-sub li:nth-child({i+1}) a"); pg.wait_for_timeout(200)
        pg.click(f".nav-sub li:nth-child({i+1}) a"); pg.wait_for_timeout(1300)
        r = pg.evaluate("""(id) => { const h = document.querySelector('header').getBoundingClientRect();
            const a = document.getElementById(id).getBoundingClientRect();
            return {hash: location.hash, hb: Math.round(h.bottom), top: Math.round(a.top)}; }""", aid)
        check(f"κλικ «{aid}»: hash + κάτω από το header",
              r["hash"] == "#" + aid and r["top"] >= r["hb"], (r["hash"], r["top"], r["hb"]))
    ctx.close()
    m = b.new_context(viewport={"width":390,"height":844}, extra_http_headers={"Cache-Control":"no-cache"})
    pg2 = m.new_page()
    pg2.goto(URL, wait_until="networkidle"); pg2.reload(wait_until="networkidle")
    pg2.evaluate("() => { const o=document.getElementById('welcomeOverlay'); const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
    pg2.wait_for_timeout(1000)
    pg2.evaluate("() => toggleMenu()"); pg2.wait_for_timeout(600)
    mm = pg2.evaluate("""() => { const sub = document.querySelector('.nav-sub'); const cs = getComputedStyle(sub);
        const menu = document.getElementById('navMenu');
        return {vis: sub.offsetParent !== null && cs.visibility === 'visible' && cs.opacity === '1',
                static: cs.position === 'static',
                items: Array.from(sub.querySelectorAll('a')).filter(a => a.offsetParent !== null).length,
                chev_hidden: getComputedStyle(document.querySelector('.sub-parent i')).display === 'none',
                fits: menu.getBoundingClientRect().height <= window.innerHeight}; }""")
    check("κινητό: ένθετη λίστα ορατή/στατική/4 στοιχεία",
          mm["vis"] and mm["static"] and mm["items"] == 4 and mm["chev_hidden"], mm)
    check("κινητό: το μενού χωράει στην οθόνη", mm["fits"])
    m.close(); b.close()
print("OK" if not bad else "BAD")
PY
grep -E '^  (PASS|FAIL) ' "$TMP/new.log" | sed 's/^/      /'
chk "νέοι έλεγχοι (D)" "$(grep -c '^OK$' "$TMP/new.log")" "1"

echo "── E. λογότυπο, ευθυγράμμιση nav vs production, bold lead ──"
grep -q 'images/logo-kt-50.webp' "$TMP/html" && ok "index: λογότυπο (picture)" || no "index: λείπει το λογότυπο"
grep -q '>ΚΤ<' "$TMP/html" && no "index: μένει το παλιό κείμενο ΚΤ" || ok "index: κανένα παλιό ΚΤ"
curl -s -H 'Cache-Control: no-cache' "$S/privacy" >"$TMP/priv.html"
grep -q 'images/logo-kt-50.webp' "$TMP/priv.html" && ok "privacy: ίδιο λογότυπο" || no "privacy: λείπει το λογότυπο"

"$PY_PW" - "$S" >"$TMP/e.log" 2>&1 <<'PY'
import sys
from playwright.sync_api import sync_playwright
URL = sys.argv[1]
PROD = "https://tsigalogo.gr/"
NAVJS = """() => Array.from(document.querySelectorAll('.nav-menu > li')).map(li => {
  const a = li.querySelector('a'); const r = a.getBoundingClientRect();
  const sp = Array.from(a.querySelectorAll('span')).find(s => s.offsetParent !== null);
  const sr = sp.getBoundingClientRect();
  return {label: sp.innerText.trim(), text_x: Math.round(sr.x), box_x: Math.round(r.x),
          box_w: Math.round(r.width)}; })"""
bad = 0
def check(n, c, d=""):
    global bad
    print(f"  {'PASS' if c else 'FAIL'}  {n} {d}"); bad += 0 if c else 1
with sync_playwright() as p:
    b = p.chromium.launch()
    def nav(url):
        ctx = b.new_context(viewport={"width": 1400, "height": 900},
                            extra_http_headers={"Cache-Control": "no-cache"})
        pg = ctx.new_page(); pg.goto(url, wait_until="networkidle")
        pg.evaluate("() => { const o=document.getElementById('welcomeOverlay');"
                    " const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
        pg.wait_for_timeout(900)
        out = pg.evaluate(NAVJS); ctx.close(); return out
    prod, v2 = nav(PROD), nav(URL)
    pm = {d["label"]: d for d in prod}
    diffs = []
    for d in v2:
        a = pm.get(d["label"])
        if a and (d["text_x"] != a["text_x"] or d["box_x"] != a["box_x"] or d["box_w"] != a["box_w"]):
            diffs.append((d["label"], a["text_x"], d["text_x"], a["box_w"], d["box_w"]))
    check("nav: ΚΑΘΕ item στην ίδια θέση με production (Δ=0)", not diffs, diffs)
    check("nav: 6 items", len(v2) == 6, [d["label"] for d in v2])

    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, extra_http_headers={"Cache-Control": "no-cache"})
    pg = ctx.new_page(); pg.goto(URL, wait_until="networkidle"); pg.reload(wait_until="networkidle")
    pg.evaluate("() => { const o=document.getElementById('welcomeOverlay'); const a=o&&o.querySelector('.welcome-enter'); if(a) a.click(); }")
    pg.wait_for_timeout(1100)
    lg = pg.evaluate("""() => { const img=document.querySelector('.logo-icon img'); const box=document.querySelector('.logo-icon');
      const r=box.getBoundingClientRect();
      return {w: img ? Math.round(img.getBoundingClientRect().width) : null, nat: img ? img.naturalWidth : null,
              ok: img ? img.complete : false, text: box.innerText.trim(),
              box: [Math.round(r.width), Math.round(r.height)]}; }""")
    check("λογότυπο: εικόνα 50x50 φορτωμένη, χωρίς κείμενο ΚΤ, κουτί 50x50",
          lg["w"] == 50 and lg["nat"] == 50 and lg["ok"] and lg["text"] == "" and lg["box"] == [50, 50], lg)
    ch = pg.evaluate("""() => { const i=document.querySelector('.sub-parent i'); const a=document.querySelector('.sub-parent');
      const sp=Array.from(a.querySelectorAll('span')).find(s=>s.offsetParent!==null);
      const ri=i.getBoundingClientRect(), ra=a.getBoundingClientRect(), rs=sp.getBoundingClientRect();
      return {inset: Math.round(ra.right - ri.right), gap: Math.round(ri.left - rs.right)}; }""")
    check("nav chevron: μέσα στο δεξί padding (όχι στη ροή)", 0 <= ch["inset"] <= 16 and ch["gap"] >= 0, ch)
    pg.evaluate("() => { const el=document.querySelector('.about-grid'); window.scrollTo({top: el.getBoundingClientRect().top+window.scrollY-150, behavior:'instant'}); }")
    pg.wait_for_timeout(1000)
    wt = pg.evaluate("""() => { const lead=getComputedStyle(document.querySelector('.about-lead'));
      const h3=Array.from(document.querySelectorAll('.about-text h3')).filter(e=>e.offsetParent)[0];
      return {lead: lead.fontWeight, h3: getComputedStyle(h3).fontWeight,
              fam_l: lead.fontFamily.split(',')[0], fam_h: getComputedStyle(h3).fontFamily.split(',')[0]}; }""")
    check("lead: ίδιο βάρος ΚΑΙ ίδια γραμματοσειρά με τα h3",
          wt["lead"] == wt["h3"] and wt["fam_l"] == wt["fam_h"] and wt["lead"] != "400", wt)
    # privacy: το λογότυπο υπάρχει και εκεί.
    # ΣΗΜΕΙΩΣΗ: μια αστοχία εδώ (π.χ. timeout στο networkidle μετά από πολλές πλοηγήσεις) ΔΕΝ
    # πρέπει να σκοτώνει το block πριν τυπώσει «OK» — αυτό δίνει ακατανόητο aggregate FAIL χωρίς
    # καμία γραμμή εξήγησης. Τυπώνουμε το σφάλμα και συνεχίζουμε.
    try:
        # Ο $S ΔΕΝ έχει κάθετο στο τέλος: `URL + "privacy"` έδινε «…devprivacy» και
        # ERR_NAME_NOT_RESOLVED. Πάντα rstrip + "/".
        pg.goto(URL.rstrip("/") + "/privacy", wait_until="load", timeout=20000)
        pg.wait_for_timeout(900)
        pr = pg.evaluate("""() => { const img=document.querySelector('.logo-icon img');
          return {present: !!img, ok: img ? img.complete : false}; }""")
        check("privacy: λογότυπο φορτωμένο", pr["present"] and pr["ok"], pr)
    except Exception as exc:
        check("privacy: λογότυπο φορτωμένο", False, f"{type(exc).__name__}: {str(exc)[:120]}")
    ctx.close(); b.close()
print("OK" if not bad else "BAD")
PY
grep -E '^  (PASS|FAIL) ' "$TMP/e.log" | sed 's/^/      /'
chk "νέοι έλεγχοι (E)" "$(grep -c '^OK$' "$TMP/e.log")" "1"

echo
echo "ad-hoc verification: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
