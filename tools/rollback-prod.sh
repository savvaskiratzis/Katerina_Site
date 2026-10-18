#!/usr/bin/env bash
#
#  rollback-prod.sh — επαναφορά του tsigalogo.gr στην προηγούμενη έκδοση.
#
#  Χρήση:
#     bash tools/rollback-prod.sh              # δείχνει τις production εκδόσεις
#     bash tools/rollback-prod.sh <id_prefix> # rollback σε συγκεκριμένη έκδοση (π.χ. 8cbf5b4b)
#     bash tools/rollback-prod.sh --latest-1   # rollback στην αμέσως προηγούμενη
#
#  Δύο ανεξάρτητοι δρόμοι επιστροφής (και οι δύο εδώ):
#    Α. Pages rollback API — ακαριαίο, δεν ανεβάζει αρχεία, γυρίζει σε ήδη δημοσιευμένη έκδοση.
#    Β. snapshot tarball από ~/tsiga-backups/ — αν χρειαστεί redeploy από αρχεία:
#       tar xzf <snap>.tgz -C /tmp/dist && npx wrangler pages deploy /tmp/dist --project-name tsigalogo
#
set -euo pipefail

ACC=8e5b456a91684ad83edd9fd82b5cbf56
PROJ=tsigalogo
TOKEN_FILE="$HOME/.hermes/scripts/tsiga-verify/.cf-token"
CF="${CLOUDFLARE_API_TOKEN:-$(cat "$TOKEN_FILE")}"
API="https://api.cloudflare.com/client/v4/accounts/$ACC/pages/projects/$PROJ"

list() {
  curl -s -H "Authorization: Bearer $CF" "$API/deployments?per_page=15" -o /tmp/tsiga-deps.json
  python3 - <<'PY'
import json
d = json.load(open("/tmp/tsiga-deps.json"))["result"]
prod = [r for r in d if r.get("environment") == "production"]
print(f"production deployments ({len(prod)}):")
for i, r in enumerate(prod):
    print(f"  [{i}] {r['id'][:8]}  {r['created_on'][:19]}  {r['url']}")
PY
}

case "${1:-list}" in
  list) list; exit 0 ;;
  --latest-1)
    list
    ID=$(python3 -c "
import json
d=json.load(open('/tmp/tsiga-deps.json'))['result']
prod=[r for r in d if r.get('environment')=='production']
print(prod[1]['id'] if len(prod)>1 else '')")
    [ -n "$ID" ] || { echo '✗ δεν βρέθηκε προηγούμενη production έκδοση'; exit 1; }
    ;;
  *) ID="$1" ;;
esac

# το API δέχεται και prefix? Όχι — ανάκτησε το πλήρες id
FULL=$(python3 -c "
import json,sys
d=json.load(open('/tmp/tsiga-deps.json'))['result'] if __import__('os').path.exists('/tmp/tsiga-deps.json') else []
m=[r['id'] for r in d if r['id'].startswith('$ID')]
print(m[0] if m else '')")
[ -n "$FULL" ] || { list; echo "✗ δεν βρέθηκε deployment με id $ID — διάλεξε από τη λίστα"; exit 1; }

echo "→ rollback στο $FULL"
curl -s -X POST -H "Authorization: Bearer $CF" "$API/deployments/$FULL/rollback" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('success:', d.get('success'), d.get('errors') or '')"
sleep 8
curl -s -o /dev/null -D - "https://tsigalogo.gr/?cb=$(date +%s)" | grep -iE "^(HTTP|x-robots)"
echo "Διαθέσιμα snapshots:"
ls -1t "$HOME/tsiga-backups" 2>/dev/null | head -5
