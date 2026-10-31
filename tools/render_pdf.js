#!/usr/bin/env node
// HTML 报告 → PDF（profile 1.1zb：用户在手机上看文件，HTML 必须同时给 PDF）
// 用法：node tools/render_pdf.js [--print] reports/xxx.html [更多.html ...]
//   --print：按页面的 print CSS 渲染（guizang-page-skill 的页面需要，否则浮动目录与设置按钮会印进 PDF）
// 产物与 HTML 同名同目录（reports/*.pdf 被 .gitignore 忽略，HTML 才是入库源文件）。
// 用 Node 版 playwright：容器预装的是它，Python 版不在（2026-10-28 实测）。
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const args = process.argv.slice(2);
  const media = args.includes('--print') ? 'print' : 'screen';
  const files = args.filter(a => a !== '--print');
  if (!files.length) { console.error('用法: node tools/render_pdf.js <file.html> ...'); process.exit(2); }
  const browser = await chromium.launch();
  let failed = 0;
  for (const f of files) {
    const src = path.resolve(f);
    if (!fs.existsSync(src)) { console.error(`✗ 不存在: ${f}`); failed++; continue; }
    const out = src.replace(/\.html?$/i, '.pdf');
    const page = await browser.newPage();
    await page.goto('file://' + src, { waitUntil: 'networkidle' });
    await page.emulateMedia({ media });
    await page.pdf({ path: out, format: 'A4', printBackground: true,
                     margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' } });
    await page.close();
    const kb = Math.round(fs.statSync(out).size / 1024);
    // 小于 20KB 基本是空白页或渲染失败，不能当成功交付
    if (kb < 20) { console.error(`✗ ${path.relative(process.cwd(), out)} 仅 ${kb}KB，疑似空白`); failed++; }
    else console.log(`✓ ${path.relative(process.cwd(), out)}  ${kb}KB`);
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
