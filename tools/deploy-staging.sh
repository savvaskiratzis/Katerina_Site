#!/usr/bin/env bash
#
#  deploy-staging.sh — ρίχνει το v2 site στο ΑΠΟΜΟΝΩΜΕΝΟ staging project.
#
#  ΕΓΓΥΗΣΕΙΣ (γιατί αυτό το script δεν μπορεί να πειράξει το live site):
#    * Deploy target = project `tsigalogo-staging` (νέο, δικό του pages.dev subdomain).
#      Το project `tsigalogo` (tsigalogo.gr) και ο Worker `tsiga-contact` ΔΕΝ αναφέρονται
#      πουθενά εδώ μέσα — άρα δεν υπάρχει μονοπάτι που να τα αγγίξει.
#    * --branch staging = ΜΗ-production branch -> το Cloudflare βάζει μόνο του
#      `x-robots-tag: noindex` σε κάθε απάντηση (επιπλέον βάζουμε κι εμείς noindex/_headers
#      + robots.txt Disallow, ζώνη-και-τιράντες).
#    * Σταθερό URL για μοίρασμα: https://staging.tsigalogo-staging.pages.dev
#    * Καμία αλλαγή σε DNS, zone rules, custom domains, email routing, workers.
#
#  Το token διαβάζεται σε ΑΥΤΟ το command (τα env δεν επιβιώνουν μεταξύ terminal calls).
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

DIST=.dist
PROJ=tsigalogo-staging
BRANCH=staging
ACC=8e5b456a91684ad83edd9fd82b5cbf56

# ---------------------------------------------------------------------------
# 1. Χτίσε το dist με ΡΗΤΗ λίστα αρχείων (ποτέ `cp -a .` — το repo root περιέχει
#    google-ads-kit.md / local-seo-plan.md / tools/ / worker/ που ΔΕΝ δημοσιεύονται).
# ---------------------------------------------------------------------------
rm -rf "$DIST"
mkdir -p "$DIST"
# Favicon/app-icon του root: ρητά στη λίστα, αλλιώς μένουν στο source tree και το live
# γυρίζει 404 σε /favicon.ico -> η Google ξαναδείχνει την προεπιλεγμένη υδρόγειο.
# Παράγονται από tools/build-favicons.py (πηγή: images/katerina-tsiga.jpg, χωρίς crop).
ICONS=(favicon.ico favicon-16x16.png favicon-32x32.png favicon-48x48.png favicon-96x96.png
       apple-touch-icon.png android-chrome-192x192.png android-chrome-512x512.png site.webmanifest)
cp index.html privacy.html 404.html robots.txt sitemap.xml _headers _redirects "${ICONS[@]}" "$DIST/"
cp -a css fonts images vendor functions "$DIST/"

# ---------------------------------------------------------------------------
# 2. Staging-only overrides — ΜΟΝΟ στο dist, ποτέ στο source tree (ώστε το promote
#    προς production να είναι καθαρό copy χωρίς ξεχασμένα staging σκουπίδια).
# ---------------------------------------------------------------------------
cat >> "$DIST/_headers" <<'EOF'

# ---- STAGING ONLY — προστέθηκε από tools/deploy-staging.sh ----
# Το staging δεν πρέπει ΠΟΤΕ να μπει σε μηχανή αναζήτησης. Διπλή προστασία:
# αυτό εδώ + το αυτόματο x-robots-tag: noindex των Pages preview deployments.
/*
  X-Robots-Tag: noindex, nofollow, noarchive
EOF

printf '# STAGING — καμία μηχανή αναζήτησης.\nUser-agent: *\nDisallow: /\n' > "$DIST/robots.txt"

# ---------------------------------------------------------------------------
# 3. Deploy
# ---------------------------------------------------------------------------
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  TOKEN_FILE="$HOME/.hermes/scripts/tsiga-verify/.cf-token"
  [ -r "$TOKEN_FILE" ] || { echo "✗ Λείπει το API token (ούτε CLOUDFLARE_API_TOKEN ούτε $TOKEN_FILE)"; exit 1; }
  CLOUDFLARE_API_TOKEN="$(cat "$TOKEN_FILE")"
fi
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID="$ACC"

if ! npx --yes wrangler@latest pages project list 2>/dev/null | grep -q "$PROJ"; then
  echo "→ δημιουργία project $PROJ"
  npx --yes wrangler@latest pages project create "$PROJ" --production-branch main
fi

echo "→ deploy στο $PROJ (branch=$BRANCH → preview env, noindex)"
npx --yes wrangler@latest pages deploy "$DIST" --project-name "$PROJ" --branch "$BRANCH"

echo
echo "✓ staging: https://$BRANCH.$PROJ.pages.dev"
echo "  (production tsigalogo.gr ΔΕΝ άλλαξε — επιβεβαίωσε: curl -sI https://tsigalogo.gr/ | head -1)"
