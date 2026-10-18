#!/usr/bin/env bash
#
#  indexnow-ping.sh — λέει στο Bing (και σε Yandex/Seznam/Naver) «άλλαξαν αυτές οι σελίδες».
#
#  Γιατί έτσι και όχι με λογαριασμό:
#    Το IndexNow δεν θέλει signup, API key, ούτε dashboard. Η απόδειξη ιδιοκτησίας είναι το
#    ίδιο το αρχείο  https://tsigalogo.gr/<key>.txt  που σερβίρει το site — το όνομα ΤΟΥ αρχείου
#    ΕΙΝΑΙ το κλειδί. Γι' αυτό:
#      * το κλειδί ζει στο tools/indexnow.key  (local-only, ΔΕΝ ανεβαίνει)
#      * και υπάρχει αντίγραφο στο site root ως <key>.txt (αυτό ΑΝΕΒΑΙΝΕΙ, μέσω promote-to-prod.sh)
#
#  Χρήση:  bash tools/indexnow-ping.sh            (χρησιμοποιεί το URL list του sitemap.xml)
#          bash tools/indexnow-ping.sh --test     (δεν στέλνει, δείχνει τι θα στείλει)
#
#  Κωδικοί απάντησης: 200/202 = ΟΚ (202 = το κλειδί εκκρεμεί validation, φυσιολογικό στην αρχή)
#                      403 = το κλειδί δεν επαληθεύεται  →  τρέξε πρώτα το promote (το <key>.txt
#                            πρέπει να είναι LIVE, όχι μόνο τοπικά)
#                      422 = URL εκτός host
#
set -uo pipefail

V2="$(cd "$(dirname "$0")/.." && pwd)"
HOST="tsigalogo.gr"
ENDPOINT="https://api.indexnow.org/indexnow"
TEST=0
[ "${1:-}" = "--test" ] && TEST=1

KEYFILE="$V2/tools/indexnow.key"
[ -f "$KEYFILE" ] || { echo "✗ λείπει το tools/indexnow.key"; exit 1; }
KEY="$(cat "$KEYFILE")"
[ -n "$KEY" ] || { echo "✗ το tools/indexnow.key είναι κενό"; exit 1; }

# Το αρχείο που σερβίρει το site ΠΡΕΠΕΙ να λέγεται <key>.txt με το ίδιο περιεχόμενο —
# αλλιώς το IndexNow απορρίπτει το ping (403). Έλεγχος ΠΡΙΝ το δικτυακό κάλεσμα.
if [ ! -f "$V2/$KEY.txt" ]; then
  echo "✗ λείπει το $V2/$KEY.txt — το IndexNow δεν θα επαληθεύσει το κλειδί."
  exit 1
fi
if [ "$(cat "$V2/$KEY.txt")" != "$KEY" ]; then
  echo "✗ το $KEY.txt δεν περιέχει το κλειδί — mismatch."
  exit 1
fi

# URL list: από το sitemap.xml (μία πηγή αλήθειας — αν μπει σελίδα στο sitemap, μπαίνει κι εδώ).
URLS=$(grep -o '<loc>[^<]*</loc>' "$V2/sitemap.xml" | sed 's|</\?loc>||g')
[ -n "$URLS" ] || { echo "✗ δεν βρέθηκαν URLs στο sitemap.xml"; exit 1; }
JSON_URLS=$(printf '%s\n' "$URLS" | sed 's/.*/"&"/' | paste -sd, -)

PAYLOAD="{\"host\":\"$HOST\",\"key\":\"$KEY\",\"keyLocation\":\"https://$HOST/$KEY.txt\",\"urlList\":[$JSON_URLS]}"

echo "── IndexNow ─────────────────────────────────────────────────────"
echo "  host    : $HOST"
echo "  key     : $KEY"
echo "  urls    : $(printf '%s\n' "$URLS" | grep -c .)"
printf '%s\n' "$URLS" | sed 's/^/            /'

if [ "$TEST" -eq 1 ]; then
  echo
  echo "  DRY-RUN — δεν στάλθηκε τίποτα. Payload:"
  echo "$PAYLOAD" | sed 's/^/    /'
  exit 0
fi

# Το key file ΠΡΕΠΕΙ να είναι live πριν το ping, αλλιώς 403.
LIVEKEY=$(curl -sS --max-time 20 "https://$HOST/$KEY.txt" || true)
if [ "$LIVEKEY" != "$KEY" ]; then
  echo "  ! το https://$HOST/$KEY.txt δεν σερβίρει ακόμα το κλειδί (πήρα: '${LIVEKEY:0:20}')"
  echo "    → τρέξε πρώτα:  bash tools/promote-to-prod.sh --go"
  exit 1
fi
echo "  ✓ το key file είναι live"

CODE=$(curl -sS --max-time 30 -o /tmp/indexnow.out -w '%{http_code}' \
  -X POST "$ENDPOINT" \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data "$PAYLOAD" || echo '000')

echo "  → HTTP $CODE"
cat /tmp/indexnow.out 2>/dev/null | sed 's/^/    /'
case "$CODE" in
  200) echo "  ✓ 200 — τα URLs παραδόθηκαν" ;;
  202) echo "  ✓ 202 — αποδεκτό, το κλειδί εκκρεμεί validation (φυσιολογικό στην πρώτη αποστολή)" ;;
  400) echo "  ✗ 400 — κακό payload" ;;
  403) echo "  ✗ 403 — το κλειδί δεν επαληθεύεται (δεν είναι live το <key>.txt;)"; exit 1 ;;
  422) echo "  ✗ 422 — URLs που δεν ανήκουν στον host" ;;
  429) echo "  ! 429 — rate limit, ξαναδοκίμασε αργότερα" ;;
  000) echo "  ! κανένα δικτυακό αποτέλεσμα (timeout/DNS)" ;;
  *)   echo "  ! απροσδόκητος κωδικός" ;;
esac
