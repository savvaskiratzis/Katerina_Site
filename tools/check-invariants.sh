#!/usr/bin/env bash
#
#  check-invariants.sh — «τι ΔΕΝ επιτρέπεται να σπάσει» πριν πάει το v2 στο live.
#
#  Τρέχει ΠΑΝΤΑ πριν από promote-to-prod.sh. Ελέγχει δύο κατηγορίες:
#    Α. ΑΡΧΕΙΑ ΥΠΟΔΟΜΗΣ: πρέπει να είναι byte-ίδα με του production. Αν ο σχεδιασμός
#       (εικόνες/κείμενα/background) άγγιξε κατά λάθος κάποιο από αυτά, σταματάμε.
#    Β. ΠΕΡΙΕΧΟΜΕΝΟ: SEO (canonical, JSON-LD, NAP), ασφάλεια (_headers),
#       φόρμα (endpoint), και ΔΙΑΡΡΟΗ STAGING (noindex / pages.dev μέσα στο source).
#
set -uo pipefail

V2="$(cd "$(dirname "$0")/.." && pwd)"
PROD="${PROD_TREE:-$HOME/tsiga-speech-therapy}"
FAILS=0

ok()   { printf '  ✓ %s\n' "$1"; }
bad()  { printf '  ✗ %s\n' "$1"; FAILS=$((FAILS+1)); }
warn() { printf '  ! %s\n' "$1"; }

echo "── Α. αρχεία υποδομής: v2 vs production ──────────────────────────"
for f in _headers _redirects functions/api/contact.js 404.html; do
  if [ ! -f "$V2/$f" ]; then bad "$f ΛΕΙΠΕΙ από το v2"; continue; fi
  if [ ! -f "$PROD/$f" ]; then warn "$f δεν υπάρχει στο prod tree — παράλειψη σύγκρισης"; continue; fi
  if diff -q "$PROD/$f" "$V2/$f" >/dev/null; then
    ok "$f ταυτίζεται με το production"
  else
    # ΚΑΤΑΓΕΓΡΑΜΜΕΝΕΣ ΑΠΟΚΛΙΣΕΙΣ — γιατί αλλιώς ο φρουρός μπλοκάρει το promote για κάτι που
    # έγινε ΕΠΙΤΗΔΕΣ. Ο κανόνας: απόκλιση επιτρέπεται μόνο αν υπάρχει ο δείκτης της αλλαγής
    # ΜΕΣΑ στο αρχείο (όχι «το είπαμε»), και τυπώνεται ως ≈ απόκλιση ώστε να φαίνεται.
    case "$f" in
      functions/api/contact.js)
        if grep -q 'ΔΥΟ ΔΙΟΡΘΩΣΕΙΣ ΑΣΦΑΛΕΙΑΣ' "$V2/$f"; then
          ok "$f: ≈ ΑΠΟΔΕΚΤΗ ΑΠΟΚΛΙΣΗ (19/9/2026) — διορθώσεις ασφάλειας status/origin·"
          echo "        ο συγχρονισμός με το production γίνεται στο promote (το promote αντιγράφει functions/)"
        else
          bad "$f ΔΙΑΦΕΡΕΙ από το production ΧΩΡΙΣ καταγεγραμμένο λόγο (λείπει ο δείκτης της διόρθωσης)"
        fi ;;
      *) bad "$f ΔΙΑΦΕΡΕΙ από το production (δες: diff $PROD/$f $V2/$f)" ;;
    esac
  fi
done

echo
echo "── Β1. SEO / στοιχεία που κρατούν το ranking ────────────────────"
for page in index.html privacy.html; do
  [ -f "$V2/$page" ] || { bad "$page λείπει"; continue; }
  grep -q 'rel="canonical" href="https://tsigalogo.gr' "$V2/$page" \
    && ok "$page: canonical → https://tsigalogo.gr" \
    || bad "$page: ΧΑΘΗΚΕ το canonical (duplicate content κίνδυνος)"
  n=$(grep -c 'application/ld+json' "$V2/$page")
  [ "$n" -ge 1 ] && ok "$page: $n μπλοκ JSON-LD" || warn "$page: κανένα JSON-LD"
done
n=$(grep -c 'googletagmanager\|AW-\|gtag(' "$V2/index.html")
[ "$n" -ge 1 ] && ok "index.html: το tag των Google Ads υπάρχει ($n αναφορές)" \
              || bad "index.html: ΧΑΘΗΚΕ το Google Ads tag (σπάει το conversion tracking)"
[ -f "$V2/sitemap.xml" ] && ok "sitemap.xml υπάρχει" || bad "sitemap.xml λείπει"
[ -f "$V2/robots.txt" ] && ok "robots.txt υπάρχει" || bad "robots.txt λείπει"
if [ -f "$V2/robots.txt" ] && grep -qi 'disallow: */*' "$V2/robots.txt"; then
  bad "robots.txt του v2 έχει Disallow: / — μοιάζει με STAGING αρχείο, θα αποκλείσει το live site!"
fi
if [ -f "$V2/sitemap.xml" ]; then
  grep -q 'https://tsigalogo.gr/' "$V2/sitemap.xml" \
    && ok "sitemap.xml: δείχνει στο tsigalogo.gr" \
    || bad "sitemap.xml: δεν περιέχει tsigalogo.gr"
fi

echo
echo "── Β2. Ασφάλεια (security headers) ──────────────────────────────"
for h in "Strict-Transport-Security" "X-Frame-Options" "Permissions-Policy"; do
  grep -q "$h" "$V2/_headers" && ok "_headers: $h" || bad "_headers: ΧΑΘΗΚΕ το $h"
done
# ΠΑΓΙΔΑ ΠΟΥ ΑΠΟΔΕΙΧΘΗΚΕ ΣΤΟ STAGING: το Pages κρατά ΜΟΝΟ το τελευταίο μπλοκ για το ίδιο path.
# Το staging έχει 2 μπλοκ /* (το κανονικό + το noindex injection) και γι' αυτό ΔΕΝ στέλνει
# Strict-Transport-Security / X-Frame-Options / Permissions-Policy, ενώ το production (1 μπλοκ)
# τα στέλνει όλα. Δηλαδή: αν ποτέ προστεθεί δεύτερο μπλοκ /* στο _headers, το LIVE χάνει
# σιωπηλά τα security headers του — γι' αυτό ελέγχεται ΕΔΩ, με νούμερο.
blocks=$(grep -c '^/\*' "$V2/_headers")
if [ "$blocks" -eq 1 ]; then
  ok "_headers: ένα μόνο μπλοκ /* (κανένα override των security headers)"
else
  bad "_headers: $blocks μπλοκ /* — το Pages κρατά μόνο το τελευταίο -> χάνονται HSTS/X-Frame-Options/Permissions-Policy"
fi

echo
echo "── Β3. Φόρμα επικοινωνίας ───────────────────────────────────────"
grep -q '/api/contact' "$V2/index.html" \
  && ok "index.html: στοιχείο/JS φόρμας δείχνει στο /api/contact" \
  || bad "index.html: ΧΑΘΗΚΕ η αναφορά στο /api/contact"
grep -q 'X-Contact-Endpoint' "$V2/functions/api/contact.js" \
  && ok "Pages Function: δηλώνει X-Contact-Endpoint (Pages fallback)" \
  || warn "Pages Function: δεν δηλώνει X-Contact-Endpoint"
grep -q 'tsiga.kat@gmail.com' "$V2/functions/api/contact.js" \
  && ok "Pages Function: παραλήπτης το email της Κατερίνας" \
  || bad "Pages Function: άλλαξε ο παραλήπτης!"

echo
echo "── Β4. Διαρροή staging (noindex / pages.dev) ────────────────────"
if grep -qi 'x-robots-tag' "$V2/_headers"; then
  bad "_headers του v2 περιέχει X-Robots-Tag — το LIVE site θα γίνει noindex!"
else
  ok "_headers: καθαρό από X-Robots-Tag (δεν θα κρύψει το live από τη Google)"
fi
hits=$(grep -rl 'pages\.dev' "$V2" --include='*.html' --include='*.css' --include='*.js' --include='*.xml' --include='*.txt' --include='_headers' --include='_redirects' 2>/dev/null | grep -v '^'$V2'/\.dist' || true)
if [ -n "$hits" ]; then bad "βρέθηκε 'pages.dev' μέσα σε site αρχεία: $hits"; else ok "κανένα pages.dev URL μέσα στο site"; fi
if grep -qi 'noindex' "$V2/robots.txt" 2>/dev/null; then
  bad "robots.txt: περιέχει noindex/Disallow — staging κατάλοιπο"
else
  ok "robots.txt: εντάξει για production"
fi

echo
echo "── Β5. IndexNow (εύρεση από Bing/Yandex/Copilot) ────────────────"
# Το κλειδί αποδεικνύεται από το ΙΔΙΟ το αρχείο <key>.txt στο root. Αν αλλάξει το ένα χωρίς το
# άλλο, το ping γίνεται 403 και μένει σιωπηλά αναποτελεσματικό — γι' αυτό ελέγχεται εδώ.
INDEXNOW_KEY="$(cat "$V2/tools/indexnow.key" 2>/dev/null || true)"
if [ -z "$INDEXNOW_KEY" ]; then
  warn "λείπει το tools/indexnow.key — το IndexNow ping δεν θα έχει κλειδί"
elif [ ! -f "$V2/$INDEXNOW_KEY.txt" ]; then
  bad "λείπει το $INDEXNOW_KEY.txt από το site root — το Bing δεν θα επαληθεύσει το ping"
elif [ "$(cat "$V2/$INDEXNOW_KEY.txt")" != "$INDEXNOW_KEY" ]; then
  bad "$INDEXNOW_KEY.txt δεν περιέχει το κλειδί του tools/indexnow.key (mismatch → 403)"
else
  ok "IndexNow: $INDEXNOW_KEY.txt στο root, περιεχόμενο συμφωνεί"
fi

echo
echo "── Β6. Favicon / SERP εικονίδιο ────────────────────────────────"
# ΓΙΑΤΙ ΕΔΩ: το <head> είχε το εικονίδιο ως inline `data:image/svg+xml` με emoji. Ο browser
# το δείχνει στο tab, οπότε ένα meta-audit περνάει — αλλά η Google δεν κατεβάζει ποτέ
# data: URIs (θέλει URL) και δεν υποστηρίζει SVG στο SERP, άρα το αποτέλεσμα έπαιρνε την
# προεπιλεγμένη υδρόγειο (επιβεβαιώθηκε 24/9/2026). Τώρα ο έλεγχος είναι μόνιμος.
for page in index.html privacy.html; do
  [ -f "$V2/$page" ] || continue
  if grep -qE '<link[^>]*rel="(icon|apple-touch-icon)"[^>]*href="data:' "$V2/$page"; then
    bad "$page: το εικονίδιο είναι πάλι data: URI — αόρατο στη Google (υδρόγειος στο SERP)"
  elif ! grep -qE '<link[^>]*rel="icon"[^>]*href="/favicon' "$V2/$page"; then
    bad "$page: λείπει το <link rel=\"icon\" href=\"/favicon.ico\">"
  else
    n=$(grep -cE '<link[^>]*rel="(icon|apple-touch-icon|manifest)"' "$V2/$page")
    # Ένα URL που δεν υπάρχει στο dist είναι εξίσου άχρηστο με το data: URI (404 στο live).
    miss=""
    for f in $(grep -oE 'href="/[a-zA-Z0-9._-]+\.(ico|png|webmanifest)"' "$V2/$page" | sed -E 's|href="/(.*)"|\1|'); do
      [ -f "$V2/$f" ] || miss="$miss $f"
    done
    if [ -n "$miss" ]; then
      bad "$page: δηλώνονται εικονίδια που ΔΕΝ υπάρχουν στο root:$miss"
    else
      ok "$page: $n δηλώσεις εικονιδίων, όλες με URL και όλα τα αρχεία παρόντα"
    fi
  fi
done
grep -q 'ICONS=' "$V2/tools/promote-to-prod.sh" \
  && ok "promote-to-prod.sh: τα εικονίδια είναι στη ρητή λίστα αρχείων του dist" \
  || bad "promote-to-prod.sh: τα favicon δεν μπαίνουν στο dist — θα λείπουν από το live"
n=$(grep -c 'katerina-tsiga.jpg' "$V2/tools/build-favicons.py" 2>/dev/null || echo 0)
[ "$n" -ge 1 ] && ok "build-favicons.py: πηγή η φωτογραφία του site (χωρίς crop)" \
              || warn "build-favicons.py: δεν βρέθηκε η αναμενόμενη πηγή"

echo
echo "── Β7. Sitemap lastmod (φρεσκάδα δήλωσης) ───────────────────────"
# ΓΙΑΤΙ ΕΔΩ: το <lastmod> δηλώνει στη Google ΠΟΤΕ άλλαξε το περιεχόμενο. Ένα ξεχασμένο lastmod
# είναι λάθος δήλωση και χαραμισμένο re-indexing (ζητήθηκε χειροκίνητα 24/9/2026). Το κλειδώνουμε
# στην ΗΜΕΡΟΜΗΝΙΑ mtime του ίδιου του αρχείου — μετράει η πραγματική αλλαγή, όχι η μνήμη μας.
# (Μετά από fresh clone/checkout τα mtime γίνονται «τώρα»: τότε ενημερώνεις το lastmod, μία γραμμή.)
mtime_date() { date -r "$1" +%F 2>/dev/null || stat -c %y "$1" 2>/dev/null | cut -d' ' -f1; }
loc_lastmod() {  # $1 = το ακριβές <loc>
  python3 - "$V2/sitemap.xml" "$1" <<'PY' 2>/dev/null || true
import re,sys
p,loc=sys.argv[1],sys.argv[2]
try: x=open(p,encoding="utf-8").read()
except OSError: raise SystemExit
m=re.search(r"<loc>"+re.escape(loc)+r"</loc>\s*<lastmod>([0-9]{4}-[0-9]{2}-[0-9]{2})</lastmod>",x)
print(m.group(1) if m else "")
PY
}
for pair in "index.html|https://tsigalogo.gr/" "privacy.html|https://tsigalogo.gr/privacy"; do
  page="${pair%%|*}"; loc="${pair##*|}"
  [ -f "$V2/$page" ] || continue
  lm="$(loc_lastmod "$loc")"; mt="$(mtime_date "$V2/$page")"
  if [ -z "$lm" ]; then
    bad "sitemap.xml: δεν βρέθηκε lastmod για $loc"
  elif [ -n "$mt" ] && [[ "$mt" > "$lm" ]]; then
    bad "sitemap.xml: lastmod $loc = $lm, αλλά το $page άλλαξε $mt — ανέβασέ το πριν το promote"
  else
    ok "sitemap.xml: lastmod $loc = $lm ≥ τελευταία αλλαγή $page ($mt)"
  fi
done

echo
if [ "$FAILS" -gt 0 ]; then
  echo "❌ $FAILS έλεγχος/-οι ΑΠΕΤΥΧΑΝ — ΜΗΝ κάνεις promote."
  exit 1
fi
echo "✅ Όλοι οι invariants πέρασαν. Ασφαλές για promote-to-prod.sh --go"
