#!/usr/bin/env bash
# verify-redesign.sh — ad-hoc verification του welcome pop-up + του retint.
#
# ΔΕΝ είναι test suite του project (δεν υπάρχει test runner εδώ) και ΔΕΝ κρίνει αισθητική:
# το design το κρίνει ο ιδιοκτήτης. Ελέγχει ότι (α) ο ισχυρισμός «η εικόνα είναι ΑΥΤΟΥΣΙΑ»
# είναι αληθινός, (β) το αόρατο hit-area κάθεται πάνω στο ζωγραφισμένο κουμπί, (γ) το SEO
# gate πιάνει πραγματικά drift, (δ) το deployed == ο δίσκος, (ε) το production δεν άλλαξε.
#
# Χρήση: bash tools/verify-redesign.sh [url]
set -uo pipefail

V2="$(cd "$(dirname "$0")/.." && pwd)"
S="${1:-https://staging.tsigalogo-staging.pages.dev}"
PY_IMG="$HOME/.venvs/img/bin/python"
PY_PW="$HOME/.venvs/fortinet/bin/python"
SRCJPG="/home/azureadmin/.hermes/images/dashboard_20260919_130014_a2bfcca0_Gemini_Generated_Image_4qtahm4qtahm4qta.jpg"
TMP=$(mktemp -d /tmp/hermes-verify-XXXXXX)
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
no() { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
chk() { if [ "$2" = "$3" ]; then ok "$1 ($3)"; else no "$1 (got '$2', want '$3')"; fi; }

echo "── 1. τα gates περνούν ─────────────────────────────────────"
bash "$V2/tools/check-invariants.sh" >"$TMP/inv.log" 2>&1;     chk "check-invariants.sh" "$?" "0"
python3 "$V2/tools/seo-parity.py" >"$TMP/seo.log" 2>&1;         chk "seo-parity.py" "$?" "0"
python3 "$V2/tools/version-assets.py" --check >"$TMP/v.log" 2>&1; chk "version-assets --check" "$?" "0"
bash "$V2/tools/verify-tools.sh" >"$TMP/t.log" 2>&1;            chk "verify-tools.sh (37 assertions)" "$?" "0"

echo "── 2. το SEO gate μπορεί να ΑΠΟΤΥΧΕΙ (mutation test) ──────"
MUT="$TMP/mutant"; cp -a "$V2" "$MUT"; rm -rf "$MUT/.dist" "$MUT/.dist-prod" "$MUT/.git"
python3 - "$MUT/index.html" <<'PY'
import sys, re
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = s.replace("<title>Κατερίνα Τσίγα - Λογοθεραπεύτρια | Λογοθεραπεία κατ' οίκον, Γλυφάδα</title>",
              "<title>Κατερίνα Τσίγα</title>", 1)
s = s.replace('<link rel="canonical" href="https://tsigalogo.gr/">',
              '<link rel="canonical" href="https://tsigalogo-staging.pages.dev/">', 1)
open(p, "w", encoding="utf-8").write(s)
PY
python3 "$V2/tools/seo-parity.py" --v2 "$MUT" >"$TMP/seo_mut.log" 2>&1
chk "seo-parity σε πειραγμένο δέντρο → exit 1" "$?" "1"
for needle in title canonical; do
  grep -q "$needle" "$TMP/seo_mut.log" && ok "εντόπισε: $needle" || no "ΔΕΝ εντόπισε: $needle"
done
grep -q Traceback "$TMP/seo_mut.log" && no "crashed αντί να αναφέρει" || ok "καθαρή αναφορά, χωρίς crash"

echo "── 3. η εικόνα: ΑΥΤΟΥΣΙΑ, χωρίς καμία επέμβαση ──"
# Η 2η έκδοση artwork της Κατερίνας έχει το «Μάθετε» σωστό, οπότε δεν χρειάζεται patch:
# το deployed αρχείο πρέπει να είναι BYTE-IDENTICAL με το αρχικό.
"$PY_IMG" "$V2/tools/build-welcome-popup-image.py" >"$TMP/img.log" 2>&1
chk "build-welcome-popup-image.py exit" "$?" "0"
chk "deployed JPEG = το αρχικό αρχείο, byte-identical" \
    "$(grep -c 'byte-identical με το αρχείο που έστειλε' "$TMP/img.log")" "1"
chk "κανένα παράγωγο κάτω από το όριο PSNR" "$(grep -c 'ΑΠΟΡΡΙΨΗ' "$TMP/img.log")" "0"
grep -E 'deployed images|PSNR' "$TMP/img.log" | sed 's/^/        /'
# το πρωτότυπο φυλάσσεται εκτός deploy, με ίδιο sha256 με το deployed αρχείο
chk "sha256: πρωτότυπο στο artwork-src/ == deployed" \
    "$(sha256sum "$V2/artwork-src/katerina-welcome-original.jpg" | cut -c1-16)" \
    "$(sha256sum "$V2/images/katerina-welcome.jpg" | cut -c1-16)"
N=$(ls "$V2/images/" | grep -c 'welcome-art\|welcome-band' || true)
chk "δεν υπάρχουν τα παλιά (επεξεργασμένα) assets" "$N" "0"

echo "── 4. το hit-area πάνω στο ΖΩΓΡΑΦΙΣΜΕΝΟ κουμπί ─────────────"
"$PY_PW" "$V2/tools/check-cta-hitarea.py" "$S" >"$TMP/cta.log" 2>&1
chk "check-cta-hitarea.py" "$?" "0"
grep -E "^   [0-9]+px" "$TMP/cta.log" | sed 's/^/        /'

echo "── 5. deployed == δίσκος ───────────────────────────────────"
for f in css/style.css css/welcome.css images/katerina-welcome.jpg fonts/literata-greek.woff2; do
  a=$(sha256sum "$V2/$f" | cut -c1-16); b=$(curl -s "$S/$f" | sha256sum | cut -c1-16)
  chk "byte-identical: $f" "$b" "$a"
done

echo "── 6. production ΑΝΕΠΑΦΟ ───────────────────────────────────"
CODE=$(curl -s -o "$TMP/prod.html" -w '%{http_code}' https://tsigalogo.gr/)
SIZE=$(stat -c%s "$TMP/prod.html")
chk "production fetch 200" "$CODE" "200"
[ "$SIZE" -gt 40000 ] && ok "production HTML $SIZE bytes" || no "ύποπτα μικρό ($SIZE)"
grep -q hero-content "$TMP/prod.html" && ok "production: το παλιό hero markup" || no "ΑΛΛΑΞΕ το production markup!"
grep -q welcomeOverlay "$TMP/prod.html" && no "το pop-up είναι LIVE στο production!" || ok "καθόλου pop-up στο production"
curl -s -o /dev/null -D - https://tsigalogo.gr/ | tr -d '\r' | grep -qi '^x-robots-tag' \
  && no "production noindexed!" || ok "production χωρίς x-robots-tag"

echo "── 7. το pop-up δεν κρύβει το site: SEO + no-JS ────────────"
"$PY_PW" - "$V2" "$S" >"$TMP/dom.log" 2>&1 <<'PY'
import os, sys
from playwright.sync_api import sync_playwright
v2, url = sys.argv[1], sys.argv[2]
out = []
with sync_playwright() as p:
    b = p.chromium.launch()
    # 7a. κανονικός επισκέπτης: το pop-up εμφανίζεται, το κουμπί της εικόνας μπαίνει στο site
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    pg.goto(url, wait_until="networkidle"); pg.wait_for_timeout(500)
    out.append(("popup visible on first visit", pg.evaluate(
        "() => { const o=document.getElementById('welcomeOverlay'); return !!o && !o.hidden; }")))
    out.append(("dialog role/aria", pg.evaluate(
        "() => { const w=document.querySelector('.welcome-window');"
        "return w && w.getAttribute('role')==='dialog' && w.getAttribute('aria-modal')==='true'; }")))
    out.append(("exactly 1 h1", pg.evaluate("() => document.querySelectorAll('h1').length") == 1))
    pg.close()
    # 7b. ΧΩΡΙΣ JavaScript (και για crawlers): το pop-up ΔΕΝ πρέπει να φαίνεται
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, java_script_enabled=False)
    pg2 = ctx.new_page(); pg2.goto(url, wait_until="load")
    out.append(("no-JS: overlay not visible", pg2.evaluate(
        "() => { const o=document.getElementById('welcomeOverlay');"
        "return !o || o.hidden || getComputedStyle(o).display === 'none'; }")))
    out.append(("no-JS: h1 readable", "Κατερίνα" in pg2.inner_text("h1")))
    out.append(("no-JS: canonical present", pg2.evaluate(
        "() => !!document.querySelector('link[rel=canonical]')")))
    out.append(("no-JS: contact form present", pg2.evaluate(
        "() => !!document.getElementById('contactForm')")))
    ctx.close(); b.close()
bad = 0
for name, res in out:
    good = res is True
    print(f"  {'PASS' if good else 'FAIL'}  {name} = {res}")
    bad += 0 if good else 1
print("OK" if not bad else "BAD")
PY
grep -E "^  (PASS|FAIL) " "$TMP/dom.log" | sed 's/^/        /'
chk "SEO/no-JS checks" "$(grep -c '^OK$' "$TMP/dom.log")" "1"

echo
echo "ad-hoc verification: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
