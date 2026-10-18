#!/usr/bin/env bash
#
#  staging-vs-live.sh — «τι περιμένει στο staging;» Πριν αποφασίσεις promote.
#
#  Καλείται μετά από κάθε `deploy-staging.sh` και πριν από κάθε `promote-to-prod.sh --go`.
#  Δείχνει ΠΕΡΙΕΧΟΜΕΝΙΚΗ διαφορά (όχι μόνο «κάτι άλλαξε»): ποιες γραμμές του live HTML
#  λείπουν/περισσεύουν στο staging. Έτσι ο ιδιοκτήτης βλέπει τι θα πάει live πριν το πάει.
#
#  Έξοδος: 0 = staging ταυτίζεται με το live· 1 = υπάρχουν διαφορές (φυσιολογικό πριν promote).
#
#  Χρήση: bash tools/staging-vs-live.sh [-v]   (-v = όλες οι διαφορές, default 20)
set -uo pipefail

LIVE="https://tsigalogo.gr/"
STG="https://staging.tsigalogo-staging.pages.dev/"
LIMIT=20
[ "${1:-}" = "-v" ] && LIMIT=10000

TMP=$(mktemp -d /tmp/hermes-stgdiff-XXXXXX)
trap 'rm -rf "$TMP"' EXIT

# Cloudflare 403-άρει το default User-Agent της python/urllib· το curl περνάει. Χρησιμοποιούμε
# curl με Cache-Control: no-cache γιατί το HTML είναι max-age=0, must-revalidate.
fetch() { curl -s -H 'Cache-Control: no-cache' -H 'User-Agent: Mozilla/5.0 (staging-diff)' "$1"; }

for pair in "index.html|" "privacy.html|privacy"; do
  page="${pair%%|*}"; sub="${pair##*|}"
  fetch "$LIVE$sub"  > "$TMP/live-$page"
  fetch "$STG$sub"   > "$TMP/stg-$page"
done

echo "── Τι σερβίρει ο κάθε κόσμος ────────────────────────────────────"
for page in index.html privacy.html; do
  lv=$(grep -oE 'style\.css\?v=[0-9a-f]{8}' "$TMP/live-$page" | head -1)
  sv=$(grep -oE 'style\.css\?v=[0-9a-f]{8}' "$TMP/stg-$page"  | head -1)
  lb=$(stat -c%s "$TMP/live-$page"); sb=$(stat -c%s "$TMP/stg-$page")
  printf '  %-13s live: %s %6s bytes   staging: %s %6s bytes\n' "$page" "${lv:-—}" "$lb" "${sv:-—}" "$sb"
done
echo "  sitemap:  live $(fetch https://tsigalogo.gr/sitemap.xml | grep -o '<lastmod>[0-9-]*' | head -1 | tr -d '<lastmod>')· staging $(fetch https://staging.tsigalogo-staging.pages.dev/sitemap.xml | grep -o '<lastmod>[0-9-]*' | head -1 | tr -d '<lastmod>')"

# Κανονικοποίηση: HTML comments εκτός, κενά/indentation μαζεμένα ανά γραμμή, κενές γραμμές έξω —
# αλλιώς το diff γεμίζει θόρυβο από το formatting και δεν δείχνει την ΟΥΣΙΑ.
#
# ΚΑΙ: το production zone του tsigalogo.gr έχει «Email Address Obfuscation» του Cloudflare, που
# ξαναγράφει ΚΑΘΕ `mailto:` σε `/cdn-cgi/l/email-protection#hash` + `<span class="__cf_email__">`
# και προσθέτει το email-decode.min.js. Το staging (pages.dev, έξω από το zone) τα σερβίρει ως
# έχουν. Χωρίς αυτή την αφαίρεση, ΚΑΘΕ σύγκριση δείχνει 20+ «διαφορές» που δεν είναι διαφορές.
# Αφαιρούνται ΟΛΟΚΛΗΡΑ τα email anchors από τις δύο πλευρές (και το script), ώστε να μένει το
# κείμενο γύρω τους — που είναι αυτό που όντως μπορεί να άλλαξε.
obf() {
  perl -0777 -pe '
    s{<script data-cfasync="false" src="/cdn-cgi/scripts/[^"]*email-decode\.min\.js"></script>}{}g;
    s{<a href="mailto:[^"]*">.*?</a>}{}gs;
    s{<a href="/cdn-cgi/l/email-protection[^"]*">.*?</a>}{}gs;
    s{<span class="__cf_email__"[^>]*>.*?</span>}{}gs;
  ' "$1"
}
norm() { obf "$1" | sed -e 's/<!--.*-->//g' | sed -e 's/[[:space:]]\+/ /g' -e 's/^ //' -e 's/ $//' | grep -v '^$'; }

DIFFS=0
echo
for page in index.html privacy.html; do
  norm "$TMP/live-$page" > "$TMP/n-live-$page"
  norm "$TMP/stg-$page"  > "$TMP/n-stg-$page"
  n=$(diff "$TMP/n-live-$page" "$TMP/n-stg-$page" | grep -cE '^[<>]' || true)
  if [ "$n" -eq 0 ]; then
    printf '  ✓ %-13s ίδιο περιεχόμενο με το live\n' "$page"
  else
    DIFFS=$((DIFFS + n))
    printf '  ≠ %-13s %s γραμμές διαφέρουν (< live, > staging):\n' "$page" "$n"
    diff "$TMP/n-live-$page" "$TMP/n-stg-$page" | grep -E '^[<>]' | head -"$LIMIT" \
      | cut -c1-190 | sed 's/^/      /'
  fi
done

echo
if [ "$DIFFS" -eq 0 ]; then
  echo "✅ Το staging ταυτίζεται με το live — δεν υπάρχει εκκρεμής αλλαγή."
  exit 0
fi
echo "⚠  $DIFFS γραμμές περιμένουν απόφαση. Δες πρώτα https://staging.tsigalogo-staging.pages.dev"
echo "   Πέρασμα στο live ΜΟΝΟ μετά από ρητό ΟΚ:  bash tools/promote-to-prod.sh --go"
exit 1
