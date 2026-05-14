#!/usr/bin/env node
/**
 * pdf.js  —  HTML → PDF via Playwright
 *
 * Usage:
 *   node pdf.js <html-file-or-url> [output.pdf] [--format=A4|Letter] [--landscape]
 *
 * Examples:
 *   node pdf.js ../research/2026-05-14/AAPL-Q2-2026-DataViz/index.html
 *   node pdf.js ../research/2026-05-14/PLTR-Q1-2026-Editorial/index.html report.pdf --landscape
 */

const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
const fs   = require('fs');

async function main() {
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error('Usage: node pdf.js <html-file> [output.pdf] [--format=A4] [--landscape]');
    process.exit(1);
  }

  const inputPath  = args[0];
  let   outputPath = args[1] && !args[1].startsWith('--') ? args[1] : null;
  const landscape  = args.includes('--landscape');
  const formatArg  = args.find(a => a.startsWith('--format='));
  const format     = formatArg ? formatArg.split('=')[1] : 'A4';

  let url = inputPath;
  if (!inputPath.startsWith('http')) {
    const abs = path.resolve(inputPath);
    if (!fs.existsSync(abs)) { console.error(`File not found: ${abs}`); process.exit(1); }
    url = `file://${abs}`;
  }

  if (!outputPath) {
    const dir = inputPath.startsWith('http') ? '.' : path.dirname(path.resolve(inputPath));
    outputPath = path.join(dir, 'export.pdf');
  }

  console.log(`📄 Exporting PDF: ${url}`);
  console.log(`   Format:    ${format}${landscape ? ' landscape' : ''}`);
  console.log(`   Output:    ${outputPath}`);

  const browser = await chromium.launch();
  const page    = await browser.newPage();

  // Use wide viewport for landscape / slides
  const vw = landscape ? 1920 : 1440;
  const vh = landscape ? 1080 : 900;
  await page.setViewportSize({ width: vw, height: vh });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(800);

  await page.pdf({
    path: outputPath,
    format,
    landscape,
    printBackground: true,
    margin: { top: '0', right: '0', bottom: '0', left: '0' },
  });

  await browser.close();

  const stat = fs.statSync(outputPath);
  console.log(`✓ Saved: ${outputPath} (${(stat.size/1024).toFixed(1)} KB)`);
}

main().catch(e => { console.error(e); process.exit(1); });
