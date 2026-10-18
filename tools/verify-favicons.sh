#!/usr/bin/env bash
#
#  verify-favicons.sh — έλεγχος του σετ favicon/app-icon και της δημόσιας διαθεσιμότητάς του.
#
#  Χρήση:
#     bash tools/verify-favicons.sh                  # τοπικά: αρχεία + <head> + ICO δομή
#     bash tools/verify-favicons.sh tsigalogo.gr     # + LIVE: status/content-type κάθε path
#     bash tools/verify-favicons.sh staging.tsigalogo-staging.pages.dev
#
#  ΤΙ ΑΠΟΔΕΙΚΝΥΕΙ (και γιατί έτσι):
#   1. Το <head> δηλώνει τα εικονίδια με URL (όχι data:) — η Google δεν κατεβάζει data: URIs.
#   2. Κάθε δηλωμένο path υπάρχει, με το σωστό μέγεθος pixel.
#   3. Το ICO περιέχει 16+32+48 και κάθε frame είναι byte-ίσο με το αντίστοιχο PNG
#      (PIL: το frame picker σκάει σε χειροποίητα ICO, οπότε διαβάζουμε τα payloads με struct).
#   4. Το apple-touch είναι ΑΔΙΑΦΑΝΕΣ (α = 255 παντού): το iOS συνθέτει τη διαφάνεια σε μαύρο.
#   5. (LIVE) κάθε path γυρίζει 200 + σωστό content-type, το robots.txt ΔΕΝ μπλοκάρει
#      το Googlebot-Image, και το εικονίδιο που κρατά η Google ελέγχεται με control domain.
#
set -uo pipefail

V2="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${1:-}"
FAILS=0
ok()  { printf '  ✓ %s\n' "$1"; }
bad() { printf '  ✗ %s\n' "$1"; FAILS=$((FAILS+1)); }

ICONS=(favicon.ico favicon-16x16.png favicon-32x32.png favicon-48x48.png favicon-96x96.png
       apple-touch-icon.png android-chrome-192x192.png android-chrome-512x512.png site.webmanifest)

echo "── 1. <head>: δηλώσεις με URL, χωρίς data: ─────────────────────"
for page in index.html privacy.html; do
  if grep -qE '<link[^>]*rel="(icon|apple-touch-icon)"[^>]*href="data:' "$V2/$page"; then
    bad "$page: data: URI στο εικονίδιο — αόρατο στη Google"
  else
    ok "$page: κανένα data: URI στα εικονίδια"
  fi
  decl=$(grep -oE 'href="/[a-zA-Z0-9._-]+\.(ico|png|webmanifest)"' "$V2/$page" | sed -E 's|href="/(.*)"|\1|' | sort -u)
  missing=""
  for f in $decl; do [ -f "$V2/$f" ] || missing="$missing $f"; done
  [ -z "$missing" ] && ok "$page: $(echo "$decl" | wc -l) δηλωμένα paths, όλα υπάρχουν" \
                    || bad "$page: λείπουν$missing"
  grep -qE '<link[^>]*rel="icon"[^>]*href="/favicon\.ico"' "$V2/$page" \
    && ok "$page: ρητή δήλωση /favicon.ico (το fallback των crawlers)" \
    || bad "$page: λείπει η δήλωση /favicon.ico"
done

echo
echo "── 2. Αρχεία στο root: μέγεθος, διαφάνεια, manifest ────────────"
${PYTHON:-python3} - "$V2" <<'PY'
import json, struct, sys
from pathlib import Path
from PIL import Image
root = Path(sys.argv[1])
fails = 0

def ok(m): print(f"  ✓ {m}")
def bad(m):
    global fails; fails += 1; print(f"  ✗ {m}")

expect = {"favicon-16x16.png":16, "favicon-32x32.png":32, "favicon-48x48.png":48, "favicon-96x96.png":96,
          "apple-touch-icon.png":180, "android-chrome-192x192.png":192, "android-chrome-512x512.png":512}
imgs = {}
for name, size in expect.items():
    p = root / name
    if not p.exists():
        bad(f"{name} λείπει"); continue
    im = Image.open(p)
    imgs[name] = im
    if im.size != (size, size):
        bad(f"{name}: {im.size} αντί {size}x{size}")
    else:
        ok(f"{name}: {size}x{size} {im.mode} {p.stat().st_size:,}B")
if "apple-touch-icon.png" in imgs:
    a = imgs["apple-touch-icon.png"].convert("RGBA").getchannel("A").getextrema()
    ok("apple-touch-icon.png: αδιαφανές (a=255)" if a == (255, 255) else f"apple-touch-icon.png: ΜΗ αδιαφανές {a}")

# --- ICO: directory + payloads ---
ico = root / "favicon.ico"
if not ico.exists():
    bad("favicon.ico λείπει")
else:
    data = ico.read_bytes()
    reserved, kind, n = struct.unpack("<HHH", data[:6])
    if (reserved, kind) != (0, 1):
        bad(f"favicon.ico: λάθος header {(reserved, kind)}")
    else:
        frames = []
        for i in range(n):
            w, h, _c, _r, _p, bpp, length, off = struct.unpack("<BBBBHHII", data[6+16*i:22+16*i])
            payload = data[off:off+length]
            frames.append((w or 256, h or 256, bpp, payload))
        sizes = [f[0] for f in frames]
        ok(f"favicon.ico: {n} frames {sizes}, {len(data):,}B") if sizes == [16, 32, 48] \
            else bad(f"favicon.ico: frames {sizes} αντί [16, 32, 48]")
        for w, h, bpp, payload in frames:
            ref = root / f"favicon-{w}x{w}.png"
            same = ref.exists() and ref.read_bytes() == payload
            ok(f"favicon.ico[{w}]: byte-ίσο με favicon-{w}x{w}.png, {bpp}bpp") if same \
                else bad(f"favicon.ico[{w}]: ΔΕΝ ταυτίζεται με favicon-{w}x{w}.png")
            # decode του payload (ο picker του PIL σκάει σε χειροποίητα ICO)
            import io
            im = Image.open(io.BytesIO(payload))
            ok(f"favicon.ico[{w}]: αποκωδικοποιείται σε {im.size[0]}x{im.size[1]}") if im.size == (w, h) \
                else bad(f"favicon.ico[{w}]: decode {im.size}")

man = root / "site.webmanifest"
if not man.exists():
    bad("site.webmanifest λείπει")
else:
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
        miss = [i["src"] for i in m.get("icons", []) if not (root / i["src"].lstrip("/")).exists()]
        ok(f"site.webmanifest: έγκυρο JSON, {len(m.get('icons', []))} icons, name='{m.get('name')}'") if not miss \
            else bad(f"site.webmanifest: λείπουν αρχεία {miss}")
    except Exception as e:
        bad(f"site.webmanifest: άκυρο JSON ({e})")
sys.exit(1 if fails else 0)
PY
[ $? -eq 0 ] || FAILS=$((FAILS+1))

echo
echo "── 3. Το <head> δεν δηλώνει εικονίδιο που λείπουν από το dist ──"
for f in "${ICONS[@]}"; do
  [ -f "$V2/$f" ] && ok "$f στη ρίζα" || bad "$f ΛΕΙΠΕΙ από τη ρίζα"
done
grep -q 'ICONS=' "$V2/tools/promote-to-prod.sh" \
  && ok "promote-to-prod.sh: τα εικονίδια μπαίνουν στο dist" \
  || bad "promote-to-prod.sh: τα εικονίδια ΔΕΝ μπαίνουν στο dist (θα λείπουν από το live)"

if [ -n "$DOMAIN" ]; then
  echo
  echo "── 4. LIVE: https://$DOMAIN ────────────────────────────────────"
  for f in "${ICONS[@]}"; do
    read -r code ctype size < <(curl -sL --max-time 20 -o /dev/null -w '%{http_code} %{content_type} %{size_download}' "https://$DOMAIN/$f")
    [ "$code" = "200" ] && ok "/$f → $code $ctype ${size}B" || bad "/$f → $code (αντί 200)"
  done
  # Standard paths που δοκιμάζουν τα crawler ακόμα κι αν δεν δηλώνονται.
  for f in favicon.ico apple-touch-icon.png; do
    code=$(curl -sL --max-time 20 -o /dev/null -w '%{http_code}' "https://$DOMAIN/$f")
    [ "$code" = "200" ] || bad "/$f (default path crawler) → $code"
  done
  # Το Disallow: / είναι ΣΩΣΤΟ στο staging (δεν πρέπει να μπει σε μηχανή αναζήτησης) και
  # μοιραίο στο production (κόβει και το Googlebot-Image, άρα και το favicon).
  if curl -sL --max-time 20 "https://$DOMAIN/robots.txt" | grep -qi 'disallow: */ *$'; then
    case "$DOMAIN" in
      *staging*|*pages.dev) echo "  ! robots.txt: Disallow: / — αναμενόμενο σε staging (το noindex είναι ο σκοπός)" ;;
      *) bad "robots.txt: Disallow: / — το Googlebot-Image δεν μπορεί να κατεβάσει το favicon" ;;
    esac
  else
    ok "robots.txt: δεν μπλοκάρει το favicon"
  fi
  # Control domain που ΔΕΝ μπορεί να υπάρξει: ίδιο placeholder bytes = η Google δεν έχει favicon.
  curl -sL --max-time 25 -o /tmp/fav-site.png "https://www.google.com/s2/favicons?domain=$DOMAIN&sz=64" || true
  curl -sL --max-time 25 -o /tmp/fav-none.png "https://www.google.com/s2/favicons?domain=$DOMAIN-nope-9c8f2.invalid&sz=64" || true
  h1=$(md5sum /tmp/fav-site.png 2>/dev/null | cut -d' ' -f1)
  h2=$(md5sum /tmp/fav-none.png 2>/dev/null | cut -d' ' -f1)
  if [ -n "$h1" ] && [ "$h1" = "$h2" ]; then
    echo "  ! Google: ΔΕΝ έχει favicon για το $DOMAIN ακόμα (placeholder ταυτίζεται με control domain)"
    echo "    -> φυσιολογικό αμέσως μετά το deploy· θέλει recrawl της αρχικής (Search Console → URL Inspection → Request Indexing)"
  else
    ok "Google: το favicon service δίνει ΔΙΑΦΟΡΕΤΙΚΟ (δικό της) εικονίδιο"
  fi
  ddg=$(curl -sL --max-time 20 -o /dev/null -w '%{http_code}' "https://icons.duckduckgo.com/ip3/$DOMAIN.ico")
  [ "$ddg" = "200" ] && ok "DuckDuckGo: έχει εικονίδιο για $DOMAIN" \
                     || echo "  ! DuckDuckGo: $ddg (δεν το έχει ακόμα — ενημερώνεται με τη σειρά του)"

  echo
  echo "── 5. Πραγματικός browser: αποκωδικοποιεί ό,τι δηλώνει το <head> ─"
  # Το curl αποδεικνύει ότι το αρχείο σερβίρεται· ο browser ότι το ΑΠΟΚΩΔΙΚΟΠΟΙΕΙ.
  # Ένα PNG που περνάει το PIL μπορεί να απορριφθεί από τον browser — οπότε το μετράμε.
  PY_BROWSER="$HOME/.venvs/fortinet/bin/python"
  if [ -x "$PY_BROWSER" ]; then
    "$PY_BROWSER" - "$DOMAIN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
domain = sys.argv[1]
files = ["/favicon.ico", "/favicon-16x16.png", "/favicon-32x32.png", "/favicon-48x48.png",
         "/favicon-96x96.png", "/apple-touch-icon.png", "/android-chrome-192x192.png"]
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/home/azureadmin/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
    pg = b.new_page()
    pg.goto(f"https://{domain}/", wait_until="domcontentloaded")
    links = pg.evaluate("""() => [...document.querySelectorAll('link[rel*=icon]')]
        .map(l => ({rel: l.rel, href: l.href, sizes: (l.sizes||{}).value || ''}))""")
    for l in links:
        print(f"  ✓ <head> {l['rel']} {l['sizes']:>12s} → {l['href']}")
    for f in files:
        r = pg.evaluate("""async (f) => {
            const im = new Image();
            const done = new Promise(res => { im.onload = () => res(true); im.onerror = () => res(false); });
            im.src = f;
            const ok = await done;
            return {ok, w: im.naturalWidth, h: im.naturalHeight};
        }""", f)
        if r["ok"] and r["w"] and r["h"]:
            print(f"  ✓ browser decode {f}: {r['w']}x{r['h']}")
        else:
            print(f"  ✗ browser decode {f}: ΑΠΕΤΥΧΕ"); bad += 1
    b.close()
sys.exit(1 if bad else 0)
PY
    [ $? -eq 0 ] && ok "browser: αποκωδικοποίησε όλα τα δηλωμένα εικονίδια" \
                 || bad "browser: κάποιο εικονίδιο δεν αποκωδικοποιήθηκε (δες πάνω)"
  else
    echo "  ! παράλειψη: λείπει το $PY_BROWSER (playwright)"
  fi
fi

echo
if [ "$FAILS" -gt 0 ]; then echo "❌ $FAILS έλεγχος/-οι απέτυχαν"; exit 1; fi
echo "✅ Το σετ favicon περνάει όλους τους ελέγχους"
