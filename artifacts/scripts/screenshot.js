#!/usr/bin/env node
/**
 * screenshot.js  —  HTML → PNG via Playwright
 *
 * Usage:
 *   node screenshot.js <html-file-or-url> [output.png] [--width=1440] [--height=900] [--full]
 *
 * Examples:
 *   node screenshot.js ../research/2026-05-14/AAPL-Q2-2026-DataViz/index.html
 *   node screenshot.js ../research/2026-05-14/AAPL-Q2-2026-DataViz/index.html preview.png --width=1920
 *   node screenshot.js http://localhost:8000 out.png --full
 */

const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
const fs   = require('fs');

async function main() {
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error('Usage: node screenshot.js <html-file> [output.png] [--width=N] [--height=N] [--full]');
    process.exit(1);
  }

  let inputPath  = args[0];
  let outputPath = args[1] && !args[1].startsWith('--') ? args[1] : null;
  const fullPage = args.includes('--full');
  const widthArg  = args.find(a => a.startsWith('--width='));
  const heightArg = args.find(a => a.startsWith('--height='));
  const width  = widthArg  ? parseInt(widthArg.split('=')[1])  : 1440;
  const height = heightArg ? parseInt(heightArg.split('=')[1]) : 900;

  // Resolve URL
  let url = inputPath;
  if (!inputPath.startsWith('http')) {
    const abs = path.resolve(inputPath);
    if (!fs.existsSync(abs)) { console.error(`File not found: ${abs}`); process.exit(1); }
    url = `file://${abs}`;
  }

  // Default output path next to input
  if (!outputPath) {
    const base = inputPath.startsWith('http') ? 'screenshot' : path.basename(path.dirname(inputPath)) || 'screenshot';
    outputPath = path.join(path.dirname(path.resolve(inputPath)), 'preview.png');
    if (inputPath.startsWith('http')) outputPath = path.resolve('screenshot.png');
  }

  console.log(`📸 Capturing: ${url}`);
  console.log(`   Viewport:  ${width}×${height}${fullPage ? ' (full page)' : ''}`);
  console.log(`   Output:    ${outputPath}`);

  const browser = await chromium.launch();
  const page    = await browser.newPage();
  await page.setViewportSize({ width, height });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

  // Wait for fonts/animations to settle
  await page.waitForTimeout(800);

  await page.screenshot({ path: outputPath, fullPage });
  await browser.close();

  const stat = fs.statSync(outputPath);
  console.log(`✓ Saved: ${outputPath} (${(stat.size/1024).toFixed(1)} KB)`);
}

main().catch(e => { console.error(e); process.exit(1); });
