#!/usr/bin/env bash
#
#  promote-to-prod.sh — περνάει το v2 στο LIVE (tsigalogo.gr), με δικτυωμένη ασφάλεια.
#
#  Χρήση:
#     bash tools/promote-to-prod.sh            # dry-run: ελέγχει και σταματά (ΔΕΝ κάνει deploy)
#     bash tools/promote-to-prod.sh --go       # πραγματικό πέρασμα στο production
#
#  Σειρά ενεργειών (καμία δεν παραλείπεται):
#    1. check-invariants.sh — αν σπάσει κάτι (SEO/ασφάλεια/φόρμα) σταματάει ΕΔΩ.
#    2. snapshot του τρέχοντος production σε ~/tsiga-backups/  (rollback σε δευτερόλεπτα)
#    3. αντίγραφο των site αρχείων στο prod tree (source of truth = repo) + dist με ρητή λίστα
#    4. deploy στο project `tsigalogo` (production branch main)
#    5. poll στο live μέχρι να εμφανιστεί η αλλαγή (τα PoP αργούν λίγα δευτερόλεπτα)
#    6. τυπώνει την εντολή rollback και υπενθυμίζει το git commit/push (χειροκίνητα, επιλεκτικά)
#
set -euo pipefail

V2="$(cd "$(dirname "$0")/.." && pwd)"
PROD="${PROD_TREE:-$HOME/tsiga-speech-therapy}"
BACKUPS="$HOME/tsiga-backups"
PROJ=tsigalogo
ACC=8e5b456a91684ad83edd9fd82b5cbf56
# Το <key>.txt του IndexNow πρέπει να κάθεται στο root του dist: το ΟΝΟΜΑ του αρχείου ΕΙΝΑΙ το
# κλειδί με το οποίο το Bing/Yandex επιβεβαιώνουν ότι ο αποστολέας ελέγχει το site. Αν λείψει από
# το dist, το ping γίνεται 403 (βλ. tools/indexnow-ping.sh).
INDEXNOW_KEY="$(cat "$V2/tools/indexnow.key" 2>/dev/null || true)"
# Τα favicon/app-icon του root ΠΡΕΠΕΙ να είναι στη ρητή λίστα: το promote χτίζει το dist
# από αυτήν, και χωρίς αυτά το /favicon.ico γυρίζει 404 στο live -> η Google κρατά την
# προεπιλεγμένη υδρόγειο δίπλα στο domain. Πηγή/παραγωγή: tools/build-favicons.py.
ICONS=(favicon.ico favicon-16x16.png favicon-32x32.png favicon-48x48.png favicon-96x96.png
       apple-touch-icon.png android-chrome-192x192.png android-chrome-512x512.png site.webmanifest)
FILES=(index.html privacy.html 404.html robots.txt sitemap.xml _headers _redirects "${ICONS[@]}" ${INDEXNOW_KEY:+"$INDEXNOW_KEY.txt"})

cd "$V2"

echo "── 1. invariants ────────────────────────────────────────────────"
bash tools/check-invariants.sh || { echo "✗ Σταματώ — δεν γίνεται promote με σπασμένο invariant."; exit 1; }

echo
echo "── 2. snapshot του production ───────────────────────────────────"
mkdir -p "$BACKUPS"
TS=$(date +%Y-%m-%d_%H%M%S)
SNAP="$BACKUPS/tsigalogo-prod-$TS.tgz"
tar czf "$SNAP" -C "$PROD" --exclude=.git --exclude=.wrangler --exclude=worker/.wrangler .
echo "  ✓ $SNAP"

if [ "${1:-}" != "--go" ]; then
  echo
  echo "── DRY-RUN: όλα εντάξει. Δεν έγινε deploy."
  echo "   Για να περάσει στο live:  bash tools/promote-to-prod.sh --go"
  exit 0
fi

echo
echo "── 3. αντίγραφο site αρχείων στο prod tree ──────────────────────"
for f in "${FILES[@]}"; do cp "$V2/$f" "$PROD/$f"; done
for d in css fonts images vendor functions; do rm -rf "$PROD/$d"; cp -a "$V2/$d" "$PROD/$d"; done
echo "  ✓ ενημερώθηκε το $PROD (δεν έγινε commit — δικό σου το git βήμα)"
echo "    έλεγξε πρώτα:  cd $PROD && git status --short && git diff --stat"

echo
echo "── 4. deploy στο production ─────────────────────────────────────"
DIST="$V2/.dist-prod"
rm -rf "$DIST"; mkdir -p "$DIST"
for f in "${FILES[@]}"; do cp "$PROD/$f" "$DIST/$f"; done
cp -a "$PROD"/css "$PROD"/fonts "$PROD"/images "$PROD"/vendor "$PROD"/functions "$DIST/"
grep -qi 'x-robots-tag' "$DIST/_headers" && { echo "✗ Το dist περιέχει X-Robots-Tag — abort."; exit 1; }
# Τα security headers πρέπει να ΕΠΙΒΙΩΣΟΥΝ στο dist. Αποδείχθηκε στο staging ότι ένα δεύτερο
# μπλοκ `/*` στο _headers κάνει το Pages να κρατήσει ΜΟΝΟ το τελευταίο: το staging έχει 2 μπλοκ
# και γι' αυτό δεν στέλνει HSTS/X-Frame-Options/Permissions-Policy. Εδώ σταματάμε πριν το live.
for h in "Strict-Transport-Security" "X-Frame-Options" "Permissions-Policy"; do
  grep -q "$h" "$DIST/_headers" || { echo "✗ Το dist έχασε το $h — abort."; exit 1; }
done
BH=$(grep -c '^/\*' "$DIST/_headers")
[ "$BH" -eq 1 ] || { echo "✗ Το dist έχει $BH μπλοκ /* — το Pages θα κρατήσει μόνο το τελευταίο. Abort."; exit 1; }
echo "  ✓ dist: 1 μπλοκ /*, security headers παρόντα"

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  CLOUDFLARE_API_TOKEN="$(cat "$HOME/.hermes/scripts/tsiga-verify/.cf-token")"
fi
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID="$ACC"
npx --yes wrangler@latest pages deploy "$DIST" --project-name "$PROJ" --branch main

echo
echo "── 5. αναμονή διάδοσης στο live ─────────────────────────────────"
# (α) ΤΟ CLOUDFLARE ΞΑΝΑΓΡΑΦΕΙ ΤΟ HTML: το Scrape Shield αντικαθιστά κάθε mailto: με
#     /cdn-cgi/l/email-protection + ένα email-decode.min.js. Άρα το live HTML δεν είναι ΠΟΤΕ
#     byte-ίσο με το τοπικό αρχείο — ένα σκέτο sha256 συγκρίνει άκυρα πράγματα κι ο έλεγχος θα
#     «αποτύχει» ακόμα κι όταν το deploy πέτυχε. Κανονικοποιούμε ΚΑΙ ΤΙΣ ΔΥΟ πλευρές.
# (β) ΚΑΘΕ curl ΕΔΩ ΕΙΝΑΙ ΑΝΕΚΤΙΚΟ ΣΤΟ ΣΦΑΛΜΑ: με `set -euo pipefail` ένα παροδικό connection
#     reset σε αυτό το σημείο ΣΚΟΤΩΝΕΙ το script — και μαζί του τα βήματα 5β/6, δηλαδή το IndexNow
#     ping δεν στέλνεται ποτέ ενώ το site είναι ήδη live. Αυτό συνέβη στις 21/9/2026.
norm_html() {
  sed -E 's|/cdn-cgi/l/email-protection#[0-9a-fA-F]*|MAILTO|g;
          s|<span class="__cf_email__"[^>]*>\[email&#160;protected\]</span>|EMAILTEXT|g;
          s|mailto:[^" ]*|MAILTO|g;
          s|tsiga\.kat@gmail\.com|EMAILTEXT|g;
          s|<script data-cfasync="false" src="/cdn-cgi/scripts/[^"]*"></script>||g'
}
fetch_live() { curl -sS --max-time 25 --retry 2 "$1" || true; }

BASELINE=$(fetch_live "https://tsigalogo.gr/?cb=$TS" | norm_html | sha256sum | cut -c1-12)
NEW=$(norm_html < "$V2/index.html" | sha256sum | cut -c1-12)
for i in $(seq 1 20); do
  LIVE=$(fetch_live "https://tsigalogo.gr/?cb=$TS-$i" | norm_html | sha256sum | cut -c1-12)
  if [ "$LIVE" = "$NEW" ]; then echo "  ✓ το live σερβίρει το νέο index.html (προσπάθεια $i)"; break; fi
  if [ "$LIVE" != "$BASELINE" ]; then echo "  ✓ άλλαξε το live (προσπάθεια $i)"; break; fi
  sleep 5
done
[ "${LIVE:-}" = "$NEW" ] || echo "  ! προσοχή: το live δεν ταυτίστηκε με το τοπικό index.html — έλεγξέ το"
curl -sS --max-time 25 -o /dev/null -D - https://tsigalogo.gr/ | grep -iE "^(HTTP|x-robots|cache-control)" || true

echo
echo "── 5b. IndexNow: ειδοποίηση Bing / Yandex / Seznam ──────────────"
# Δεν μπλοκάρει το deploy: το site είναι ΗΔΗ live σε αυτό το σημείο, και ένα 429/δικτυακό
# σφάλμα δεν είναι λόγος για rollback. Αν αποτύχει, ξανατρέχει χειροκίνητα μόνο του.
bash tools/indexnow-ping.sh \
  || echo "  ! IndexNow ping απέτυχε — το deploy ισχύει· ξανά: bash tools/indexnow-ping.sh"

echo
echo "── 6. επόμενα βήματα ────────────────────────────────────────────"
echo "  rollback (μία γραμμή):  bash $V2/tools/rollback-prod.sh"
echo "  πλήρης έλεγχος:         bash $HOME/.hermes/scripts/tsiga-verify/run-verification.sh"
echo "  git (επιλεκτικά, ΧΩΡΙΣ 'git add -A'):  cd $PROD && git add ${FILES[*]} css images fonts vendor functions && git commit -m 'v2 redesign' && git push"
