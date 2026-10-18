#!/usr/bin/env node
/*
 * verify-nav.js — έλεγχος του οριζόντιου μενού (ετικέτες + διάταξη) σε ΕΛ/ΕΝ.
 *
 * ΓΙΑΤΙ ΥΠΑΡΧΕΙ. Το nav είναι ΔΕΞΙΑ-ΑΓΚΥΡΩΜΕΝΟ flex. Όταν οι ετικέτες μεγάλωσαν
 * («Σχετικά» -> «Σχετικά με εμένα», «Ερωτήσεις» -> «Συχνές Ερωτήσεις», 18/10/2026) το flex
 * άρχισε να ΣΜΙΚΡΥΝΕΙ τα <li> κάτω από το πλάτος του κειμένου σε viewport ≤1080px. Το <a> είναι
 * inline, οπότε το κουτί του έσπαγε σε δύο γραμμές και το chevron — absolute μέσα σε αυτό —
 * έπεφτε ΑΡΙΣΤΕΡΑ, κάτω από το κείμενο. Διορθώθηκε με `.nav-menu > li { flex: 0 0 auto }` +
 * `nowrap`, και αυτό το script κλειδώνει τη διόρθωση: κάθε μελλοντική αλλαγή ετικέτας το
 * ξανατρέχει πριν το promote.
 *
 * ΧΡΗΣΗ
 *   node tools/verify-nav.js [url]          # default https://tsigalogo.gr/
 *
 * ΑΠΑΙΤΕΙ node + playwright-core και τον chromium του playwright. Το python playwright ΔΕΝ
 * είναι διαθέσιμο σε αυτό το host (το venv ~/.venvs/fortinet δεν υπάρχει), γι' αυτό το script
 * είναι node — τα υπόλοιπα harness (verify-about.sh, verify-redesign.sh) περιμένουν το venv.
 * Overrides: PW_MODULE=<path σε playwright-core>  PW_CHROME=<path σε chrome binary>
 *
 * Οι ΑΝΑΜΕΝΟΜΕΝΕΣ ετικέτες ΔΕΝ είναι καρφωμένες εδώ — διαβάζονται από το index.html, γιατί τα
 * κείμενα είναι του ιδιοκτήτη και αλλάζουν. Έτσι ο έλεγχος δεν ζητά ενημέρωση όταν αλλάξει το
 * copy, αλλά πιάνει πάντα τη ΔΙΑΤΑΞΗ (συμπίεση, σπάσιμο γραμμής, chevron, υπερχείλιση).
 */
const fs = require('fs');
const path = require('path');

const URL = process.argv[2] || 'https://tsigalogo.gr/';
const ROOT = path.resolve(__dirname, '..');
const PW = process.env.PW_MODULE || '/home/ubuntu/psi/node_modules/playwright-core';
const CHROME = process.env.PW_CHROME ||
  '/home/ubuntu/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome';
const { chromium } = require(PW);

// ── 1. Αναμενόμενες ετικέτες από το source (όχι από τη μνήμη) ────────────────
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const navBlock = html.match(/<ul class="nav-menu"[^>]*>[\s\S]*?<\/nav>/);
if (!navBlock) { console.error('FATAL: δεν βρέθηκε το <ul class="nav-menu"> στο index.html'); process.exit(2); }
// Χωρίς τα υπο-κουμπιά του «Σχετικά»: αυτά είναι σύνδεσμοι μέσα στο dropdown, όχι items του nav.
const navOnly = navBlock[0].replace(/<ul class="nav-sub">[\s\S]*?<\/ul>/, '');
const expected = { el: [], en: [] };
for (const m of navOnly.matchAll(/<span class="lang-el">([^<]+)<\/span><span class="lang-en">([^<]+)<\/span>/g)) {
  expected.el.push(m[1].replace(/&amp;/g, '&').trim());
  expected.en.push(m[2].replace(/&amp;/g, '&').trim());
}
const strip = s => s.replace(/\s+/g, ' ').trim();

let fails = 0;
const check = (name, cond, detail) => {
  if (!cond) fails++;
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${detail === undefined ? '' : '  ' + JSON.stringify(detail)}`);
};

const DESKTOP = `(() => {
  const ul = document.getElementById('navMenu');
  const items = Array.from(ul.querySelectorAll(':scope > li > a')).map(a => {
    const sp = Array.from(a.querySelectorAll('span')).find(s => s.offsetParent !== null) || a;
    const r = a.getBoundingClientRect();
    return {label: sp.innerText.trim(), w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x)};
  });
  const a = document.querySelector('.sub-parent'), i = a.querySelector('i');
  const sp = Array.from(a.querySelectorAll('span')).find(s => s.offsetParent !== null);
  const ur = ul.getBoundingClientRect();
  const logo = document.querySelector('.logo-icon').getBoundingClientRect();
  const lt = document.querySelector('.lang-toggle').getBoundingClientRect();
  const ri = i.getBoundingClientRect(), rs = sp.getBoundingClientRect();
  return {items,
          heights: Array.from(new Set(items.map(x => x.h))),
          logo_gap: Math.round(ur.x - logo.right),
          toggle_gap: Math.round(lt.x - ur.right),
          chevron_inset: Math.round(a.getBoundingClientRect().right - ri.right),
          chevron_after_text: ri.x >= rs.right - 0.5,
          doc_overflow: document.documentElement.scrollWidth - window.innerWidth};
})()`;

const MOBILE = `(() => {
  const ul = document.getElementById('navMenu');
  const sub = document.querySelector('.nav-sub');
  const visible = Array.from(ul.querySelectorAll('a')).filter(a => a.offsetParent !== null);
  return {menu_h: Math.round(ul.getBoundingClientRect().height), vh: window.innerHeight,
          sub_static: getComputedStyle(sub).position === 'static',
          sub_links: Array.from(sub.querySelectorAll('a')).filter(a => a.offsetParent !== null).length,
          overflow_links: visible.filter(a => a.getBoundingClientRect().right > window.innerWidth + 1).length,
          doc_overflow: document.documentElement.scrollWidth - window.innerWidth};
})()`;

(async () => {
  const b = await chromium.launch({ executablePath: CHROME });
  for (const lang of ['el', 'en']) {
    for (const width of [1400, 1200, 1100, 1080, 1024, 992]) {
      const ctx = await b.newContext({ viewport: { width, height: 900 } });
      const pg = await ctx.newPage();
      await pg.goto(URL, { waitUntil: 'load' });
      await pg.evaluate(() => { const o = document.getElementById('welcomeOverlay');
        const a = o && o.querySelector('.welcome-enter'); if (a) a.click(); });
      await pg.waitForTimeout(1400);                      // το overlay σβήνει — αλλιώς το hover «χάνεται»
      if (lang === 'en') { await pg.evaluate(() => switchLang('en')); await pg.waitForTimeout(500); }
      const r = await pg.evaluate(DESKTOP);
      const tag = `desktop ${width}px ${lang}`;
      check(`${tag}: ${expected[lang].length} ετικέτες, σωστή σειρά`,
            JSON.stringify(r.items.map(i => i.label)) === JSON.stringify(expected[lang]), r.items.map(i => i.label));
      check(`${tag}: όλα σε ΜΙΑ γραμμή (ίδιο ύψος)`, r.heights.length === 1, r.heights);
      check(`${tag}: chevron μέσα στο δεξί padding (0..16px), μετά το κείμενο`,
            r.chevron_after_text && r.chevron_inset >= 0 && r.chevron_inset <= 16, [r.chevron_inset]);
      check(`${tag}: δεν πατάει το λογότυπο / το lang toggle`,
            r.logo_gap >= 40 && r.toggle_gap >= 4 && r.toggle_gap <= 24, [r.logo_gap, r.toggle_gap]);
      check(`${tag}: καμία οριζόντια υπερχείλιση`, r.doc_overflow <= 1, r.doc_overflow);
      await ctx.close();
    }
  }
  for (const lang of ['el', 'en']) {
    for (const width of [390, 360, 320]) {
      const ctx = await b.newContext({ viewport: { width, height: 844 } });
      const pg = await ctx.newPage();
      await pg.goto(URL, { waitUntil: 'load' });
      await pg.evaluate(() => { const o = document.getElementById('welcomeOverlay');
        const a = o && o.querySelector('.welcome-enter'); if (a) a.click(); });
      await pg.waitForTimeout(1400);
      if (lang === 'en') { await pg.evaluate(() => switchLang('en')); await pg.waitForTimeout(500); }
      await pg.evaluate(() => toggleMenu());
      await pg.waitForTimeout(500);
      const r = await pg.evaluate(MOBILE);
      const tag = `mobile ${width}px ${lang}`;
      check(`${tag}: μενού ανοίγει, χωράει, υπο-λίστα ένθετη με 4 συνδέσμους`,
            r.menu_h > 0 && r.menu_h <= r.vh && r.sub_static && r.sub_links === 4, r);
      check(`${tag}: κανένας σύνδεσμος εκτός οθόνης / υπερχείλιση`,
            r.overflow_links === 0 && r.doc_overflow <= 1, [r.overflow_links, r.doc_overflow]);
      await ctx.close();
    }
  }
  await b.close();
  console.log(fails ? `\n❌ ${fails} έλεγχοι απέτυχαν` : '\n✅ Το nav είναι εντάξει σε όλα τα πλάτη (ΕΛ+ΕΝ)');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('FATAL', e.message); process.exit(2); });
