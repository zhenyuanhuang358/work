#!/usr/bin/env node
/**
 * 归藏 Page — export a rendered page to PDF and/or a full-page long image.
 * Export is a model-run step (the page itself has no export buttons).
 *
 *   node scripts/export.mjs <page.html> [--pdf out.pdf] [--png out.png]
 *        [--width 1440] [--scale 2] [--color <index|name>] [--font <index|name>] [--format A4]
 *
 * - PDF uses the page's print CSS (@media print, A4, blank-space budget) with backgrounds.
 * - PNG is a full-page screenshot at --width CSS px (default 1440) × --scale DPR (default 2).
 * - Before capturing: lazy images are made eager and scrolled into view, all <img> are awaited,
 *   document.fonts.ready is awaited, UI chrome (settings button, TOC) is hidden.
 * - --color / --font pick a colour theme / font from the page's own settings panel
 *   (0-based index, or a case-insensitive substring of the theme id such as forest-ink,
 *   the swatch name or the font name).
 * Needs Chrome/Chromium + puppeteer or puppeteer-core (npm i puppeteer-core in the skill dir,
 * or anywhere on NODE_PATH). Chrome path: $CHROME_PATH or common install locations.
 */
import { existsSync } from 'fs';
import { resolve } from 'path';
import { createRequire } from 'module';
import { pathToFileURL } from 'url';

const argv = process.argv.slice(2);
const opt = { width: 1440, scale: 2, format: 'A4' };
const files = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) { const k = a.slice(2); const v = argv[i + 1]; if (v === undefined || v.startsWith('--')) opt[k] = true; else { opt[k] = v; i++; } }
  else files.push(a);
}
if (!files[0] || (!opt.pdf && !opt.png)) {
  console.error('Usage: node scripts/export.mjs <page.html> [--pdf out.pdf] [--png out.png] [--width 1440] [--scale 2] [--color i|name] [--font i|name]');
  process.exit(1);
}

async function loadPuppeteer() {
  const req = createRequire(import.meta.url);
  const roots = [process.cwd(), resolve(import.meta.dirname || '.', '..'), ...(process.env.NODE_PATH || '').split(':').filter(Boolean)];
  for (const name of ['puppeteer', 'puppeteer-core']) {
    for (const root of roots) {
      try { const p = req.resolve(name, { paths: [root] }); const m = await import(pathToFileURL(p).href); return { mod: m.default || m, name }; } catch (_) {}
    }
  }
  throw new Error('puppeteer / puppeteer-core not found — run `npm install` in the skill folder');
}
function chromePath() {
  const c = [process.env.CHROME_PATH, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].filter(Boolean);
  return c.find(p => existsSync(p));
}

const { mod: puppeteer, name } = await loadPuppeteer();
const exe = chromePath();
const browser = await puppeteer.launch({
  ...(exe || name === 'puppeteer-core' ? { executablePath: exe } : {}),
  args: ['--no-sandbox', '--allow-file-access-from-files', '--font-render-hinting=none'],
});
const page = await browser.newPage();
const width = parseInt(opt.width, 10) || 1440;
await page.setViewport({ width, height: 900, deviceScaleFactor: parseFloat(opt.scale) || 2 });
const url = /^https?:/.test(files[0]) ? files[0] : pathToFileURL(resolve(files[0])).href;
await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });

// Optional theme colour / font via the page's own controls (keeps ui.js logic in one place)
async function pick(selector, val) {
  if (val === undefined || val === true) return;
  const ok = await page.evaluate((sel, v) => {
    const els = [...document.querySelectorAll(sel)];
    const el = /^\d+$/.test(v) ? els[+v] : els.find(e => ((e.dataset.themeId || '') + ' ' + (e.title || '') + ' ' + e.textContent).toLowerCase().includes(String(v).toLowerCase()));
    if (!el) return false; el.click(); return true;
  }, selector, String(val));
  if (!ok) console.warn(`! no match for ${selector} = ${val}`);
}
await pick('.hf-swatch', opt.color);
await pick('.hf-font-option', opt.font);

// Make every image load: eager + scroll through the page, then wait for decode + fonts
await page.evaluate(async () => {
  document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; });
  for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }
  window.scrollTo(0, 0);
  await Promise.all([...document.images].map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; })));
  await document.fonts.ready;
});
await page.waitForNetworkIdle({ idleTime: 500, timeout: 60000 }).catch(() => {});
const broken = await page.evaluate(() => [...document.images].filter(i => !i.naturalWidth).map(i => i.getAttribute('src')));
if (broken.length) console.warn('! images failed to load:', broken.join(', '));

// PDF first: the long-image capture resizes the viewport and hides UI, which the print layout would inherit
if (opt.pdf) {
  await page.emulateMediaType('print');
  await page.pdf({ path: resolve(opt.pdf), format: opt.format, printBackground: true, preferCSSPageSize: true });
  await page.emulateMediaType('screen');
  console.log('✓ PDF →', resolve(opt.pdf));
}
if (opt.png) {
  await page.addStyleTag({ content: '.hf-fab,.toc,.toc-scrim{display:none!important}' });
  await page.evaluate(() => document.documentElement.classList.remove('toc-is-open'));
  // Chrome can't capture more than 16384 device pixels in one go: past that the bottom of the image
  // repeats the top of the page. Lower the pixel ratio so the whole page fits.
  const MAX = 16000;
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  let dpr = parseFloat(opt.scale) || 2;
  if (height * dpr > MAX) {
    const fit = Math.floor((MAX / height) * 100) / 100;
    if (fit < 0.5) console.warn(`! 页面高 ${height}px，长图会很糊；建议只导 PDF，或把文章拆成几页`);
    console.warn(`! 页面高 ${height}px，${dpr}x 超过长图上限，改用 ${fit}x`);
    dpr = fit;
    await page.setViewport({ width, height: 900, deviceScaleFactor: dpr });
  }
  await page.screenshot({ path: resolve(opt.png), fullPage: true, captureBeyondViewport: true });
  console.log('✓ PNG →', resolve(opt.png));
}
await browser.close();
