#!/usr/bin/env bash
# hermes-verify: ad-hoc verification of the four v2 tooling scripts.
# NOT a project test suite — there is none for these shell scripts. It asserts the
# BEHAVIOUR I claimed: syntax, dist whitelist, staging-override isolation, invariant
# gate (clean=pass / mutated=fail), promote dry-run safety, rollback listing,
# and that production stayed untouched throughout.
set -uo pipefail

V2="$HOME/tsiga-speech-therapy-v2"
PROD="$HOME/tsiga-speech-therapy"
TMP=$(mktemp -d /tmp/hermes-verify-XXXXXX)
trap 'rm -rf "$TMP"' EXIT          # never litter /tmp, even on failure (this harness failed loudly the first time)
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
no()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
chk() { if [ "$2" = "$3" ]; then ok "$1 ($3)"; else no "$1 (got '$2', want '$3')"; fi; }

ACC=8e5b456a91684ad83edd9fd82b5cbf56
CF=$(cat "$HOME/.hermes/scripts/tsiga-verify/.cf-token")
# NOTE: per_page max is 25 (30+ => success:false, result:null). Never count from a
# single page: compare the project's canonical deployment instead (pagination-free).
canon() { curl -s -H "Authorization: Bearer $CF" \
  "https://api.cloudflare.com/client/v4/accounts/$ACC/pages/projects/tsigalogo" \
  | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];c=r.get("canonical_deployment") or {};print(c.get("id") or "none")'; }
# populate the stub dir NOW so the dry-run cannot possibly reach wrangler
mkdir -p "$TMP/fakebin"
printf '#!/bin/sh\necho "stub: refusing to reach the network" >&2\nexit 9\n' > "$TMP/fakebin/npx"
chmod +x "$TMP/fakebin/npx"

echo "── 1. syntax ───────────────────────────────────────────────"
for s in deploy-staging check-invariants promote-to-prod rollback-prod; do
  if bash -n "$V2/tools/$s.sh" 2>"$TMP/err"; then ok "bash -n tools/$s.sh"; else no "bash -n tools/$s.sh: $(cat "$TMP/err")"; fi
done

echo "── 2. deploy-staging builds the right dist (npx stubbed to abort) ──"
PATH="$TMP/fakebin:$PATH" bash "$V2/tools/deploy-staging.sh" >"$TMP/staging.log" 2>&1
rc=$?
chk "script aborts when wrangler is unavailable (set -e)" "$([ $rc -ne 0 ] && echo yes || echo no)" "yes"
got=$(ls -A "$V2/.dist" | sort | tr '\n' ' ')
want=$(printf '_headers\n_redirects\n404.html\nandroid-chrome-192x192.png\nandroid-chrome-512x512.png\napple-touch-icon.png\ncss\nfavicon-16x16.png\nfavicon-32x32.png\nfavicon-48x48.png\nfavicon-96x96.png\nfavicon.ico\nfonts\nfunctions\nimages\nindex.html\nprivacy.html\nrobots.txt\nsite.webmanifest\nsitemap.xml\nvendor\n' | sort | tr '\n' ' ')
chk "dist = explicit whitelist only (no tools/ worker/ *.md)" "$got" "$want"
grep -qi 'x-robots-tag: noindex' "$V2/.dist/_headers" && ok "dist _headers carries the staging noindex" || no "dist _headers missing noindex"
grep -qi 'disallow: /' "$V2/.dist/robots.txt" && ok "dist robots.txt = Disallow: /" || no "dist robots.txt not blocking"
grep -qi 'x-robots-tag' "$V2/_headers" && no "SOURCE _headers polluted with X-Robots-Tag" || ok "source _headers stays clean (no staging leak)"
grep -qi 'disallow: /' "$V2/robots.txt" && no "SOURCE robots.txt polluted" || ok "source robots.txt stays production-safe"
grep -q 'pages.dev' "$V2/.dist/robots.txt" && no "dist robots.txt leaks a pages.dev URL" || ok "dist robots.txt has no pages.dev URL"

echo "── 3. invariant gate: clean tree passes ────────────────────"
bash "$V2/tools/check-invariants.sh" >"$TMP/clean.log" 2>&1
chk "check-invariants on untouched v2 exits 0" "$?" "0"
grep -q 'Όλοι οι invariants πέρασαν' "$TMP/clean.log" && ok "prints the all-clear line" || no "all-clear line missing"

echo "── 4. invariant gate: mutated tree must FAIL (prove it can) ─"
MUT="$TMP/mutant"
cp -a "$V2" "$MUT"; rm -rf "$MUT/.dist" "$MUT/.dist-prod"
printf '\n/*\n  X-Robots-Tag: noindex\n' >> "$MUT/_headers"
sed -i 's#href="https://tsigalogo.gr/"#href="https://tsigalogo-staging.pages.dev/"#' "$MUT/index.html"
sed -i '/X-Frame-Options/d' "$MUT/_headers"
bash "$MUT/tools/check-invariants.sh" >"$TMP/mut.log" 2>&1
chk "check-invariants on mutated tree exits 1" "$?" "1"
for needle in "ΧΑΘΗΚΕ το canonical" "ΧΑΘΗΚΕ το X-Frame-Options" "X-Robots-Tag" "pages.dev" "_headers ΔΙΑΦΕΡΕΙ"; do
  grep -q "$needle" "$TMP/mut.log" && ok "caught: $needle" || no "missed: $needle"
done
grep -q 'Traceback' "$TMP/mut.log" && no "checker crashed instead of reporting" || ok "no crash/traceback (clean report)"

echo "── 5. promote-to-prod dry-run must NOT deploy ──────────────"
BEFORE=$(canon)
PATH="$TMP/fakebin:$PATH" bash "$V2/tools/promote-to-prod.sh" >"$TMP/dry.log" 2>&1
chk "dry-run exits 0" "$?" "0"
grep -q 'DRY-RUN' "$TMP/dry.log" && ok "prints DRY-RUN banner" || no "no DRY-RUN banner"
grep -qE 'Deployment complete|Uploading|stub: refusing' "$TMP/dry.log" && no "dry-run tried to reach wrangler!" || ok "no wrangler call in dry-run (npx stub untouched)"
AFTER=$(canon)
chk "canonical production deployment unchanged" "$AFTER" "$BEFORE"
[ "$AFTER" != "none" ] && ok "canonical deployment id read back ($AFTER)" || no "could not read canonical deployment"
SNAP=$(ls -1t "$HOME/tsiga-backups" | head -1)
case "$SNAP" in tsigalogo-prod-*) ok "snapshot tarball created ($SNAP)";; *) no "no snapshot tarball";; esac
tar tzf "$HOME/tsiga-backups/$SNAP" >"$TMP/snap.list" 2>"$TMP/snap.err"
chk "snapshot tarball readable" "$?" "0"
n=$(grep -c '^\./index\.html$' "$TMP/snap.list")
chk "snapshot contains ./index.html" "$n" "1"
n=$(grep -c '^\./functions/api/contact\.js$' "$TMP/snap.list")
chk "snapshot contains the contact function" "$n" "1"

echo "── 6. rollback-prod lists real production deployments ──────"
bash "$V2/tools/rollback-prod.sh" >"$TMP/rb.log" 2>&1
chk "rollback listing exits 0" "$?" "0"
n=$(grep -cE '^  \[[0-9]+\] [0-9a-f]{8} ' "$TMP/rb.log")
[ "$n" -ge 2 ] && ok "lists $n production deployments with id prefixes" || no "listing only $n rows"
bash "$V2/tools/rollback-prod.sh" >/dev/null 2>&1 || no "rollback ls unexpectedly failed"

echo "── 7. production untouched (live, not noindexed, no new deploy) ─"
hdr=$(curl -s -o /dev/null -D - https://tsigalogo.gr/ | tr -d '\r')
echo "$hdr" | grep -q '^HTTP/2 200' && ok "tsigalogo.gr → 200" || no "tsigalogo.gr not 200"
echo "$hdr" | grep -qi 'x-robots-tag' && no "production is now noindexed!" || ok "production has no x-robots-tag"
echo "$hdr" | grep -qi '^strict-transport-security' && ok "HSTS still served" || no "HSTS missing"
chk "canonical deployment still unchanged after all tests" "$(canon)" "$BEFORE"
curl -s -o /dev/null -w '%{http_code}' https://staging.tsigalogo-staging.pages.dev/ >"$TMP/st"
chk "staging still responds 200" "$(cat "$TMP/st")" "200"
curl -s -o /dev/null -D - https://staging.tsigalogo-staging.pages.dev/ | tr -d '\r' | grep -qi '^x-robots-tag: noindex' \
  && ok "staging still noindexed" || no "staging lost its noindex"

echo
echo "ad-hoc verification: $PASS passed, $FAIL failed   (tmp: $TMP)"
[ "$FAIL" -eq 0 ] || exit 1
