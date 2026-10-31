#!/usr/bin/env node
/**
 * 归藏 Page Renderer
 *
 * Reads a markdown file + annotations.json → outputs a single styled HTML file.
 * The markdown content flows through UNCHANGED except at annotated lines,
 * where standard prose is "upgraded" to richer visual components.
 *
 * Usage: node render.mjs <input.md> <annotations.json> <output.html> [--style swiss|magazine]
 *          [--theme <主题 id>] [--brand <#hex>] [--embed]
 *
 *   --theme  初始配色（themes.json 里的 id），也可写在 meta.theme；默认是该风格的默认主题
 *   --brand  用户的品牌色，也可写在 meta.brand；经 gz-theme.mjs 收进风格允许的范围后作为初始配色
 *   --embed  把页面用到的字体子集化内置进 HTML（离线可看、导出稳定）；默认用在线字体链接
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import { resolve, dirname } from 'path';
import { embedFonts, fontLinkTag } from './gz-fonts.mjs';

const args = process.argv.slice(2);
function takeFlag(name, withValue = true) {
  const i = args.indexOf(name);
  if (i === -1) return null;
  const v = withValue ? args[i + 1] : true;
  args.splice(i, withValue ? 2 : 1);
  return v;
}
const styleName = takeFlag('--style') || 'magazine';
const themeArg = takeFlag('--theme');
const brandArg = takeFlag('--brand');
const embed = takeFlag('--embed', false);
const [mdPath, annoPath, outPath] = args;
if (!mdPath || !annoPath || !outPath) {
  console.error('Usage: node render.mjs <input.md> <annotations.json> <output.html> [--style swiss|magazine] [--theme id] [--brand #hex] [--embed]');
  process.exit(1);
}

const mdRaw = readFileSync(resolve(mdPath), 'utf-8');
const anno = JSON.parse(readFileSync(resolve(annoPath), 'utf-8'));

// Document language for :lang(zh) rules and labels: meta.lang wins, else detect by Han ratio.
const hanCount = (mdRaw.match(/[\u3400-\u9fff]/g) || []).length;
const latinCount = (mdRaw.match(/[A-Za-z]/g) || []).length;
const docLang = anno.meta.lang === 'en' ? 'en'
  : anno.meta.lang === 'zh' ? 'zh-CN'
  : (hanCount > latinCount * 0.25 ? 'zh-CN' : 'en');
const TERM_LABEL = docLang === 'en' ? 'Term' : '术语';

// ── Parse markdown into lines, extract YAML frontmatter ──
let lines = mdRaw.split('\n');
let fmEnd = 0;
const frontmatter = {};
if (lines[0].trim() === '---') {
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') { fmEnd = i + 1; break; }
    const kv = lines[i].match(/^(\w+):\s*(.+)$/);
    if (kv) frontmatter[kv[1]] = kv[2].replace(/^["']|["']$/g, '');
  }
}
lines = lines.slice(fmEnd);
// Re-index: line numbers in annotations are 1-based from original file
// We need a mapping: original line number → content
const originalLines = mdRaw.split('\n');

// ── Build upgrade lookup: line number → upgrade instruction ──
const upgradeMap = new Map(); // lineNum → upgrade object
const INSERT_TYPES = new Set(['embed', 'figure', 'aside', 'summary-card']);
const insertMap = new Map();  // lineNum → explain-mode components to insert before that line
const dropLines = new Set();
const defCardLines = new Set();
const galleryRange = new Set();
const processRange = new Set();
const checklistRange = new Set();

for (const u of anno.upgrades) {
  if (u.type === 'drop') {
    dropLines.add(u.line);
  } else if (u.type === 'pullquote') {
    upgradeMap.set(u.line, u);
  } else if (u.type === 'highlight') {
    upgradeMap.set(u.line, u);
  } else if (u.type === 'def-card') {
    for (const ln of u.lines) {
      defCardLines.add(ln);
      upgradeMap.set(ln, { type: 'def-card' });
    }
  } else if (u.type === 'gallery') {
    upgradeMap.set(u.lines[0], u);
    for (const ln of u.lines) galleryRange.add(ln);
  } else if (u.type === 'process') {
    upgradeMap.set(u.lines[0], u);
    for (const ln of u.lines) processRange.add(ln);
  } else if (u.type === 'checklist') {
    upgradeMap.set(u.lines[0], u);
    for (const ln of u.lines) checklistRange.add(ln);
  } else if (INSERT_TYPES.has(u.type)) {
    // Explain-mode components are inserted before their line; the source line itself still renders
    if (!insertMap.has(u.line)) insertMap.set(u.line, []);
    insertMap.get(u.line).push(u);
  }
}

// ── Markdown footnotes: [^id] in text, [^id]: definition anywhere ──
const footnotes = new Map(); // id → { n, text }
for (const l of originalLines) {
  const m = l.trim().match(/^\[\^([^\]]+)\]:\s*(.*)$/);
  if (m && !footnotes.has(m[1])) footnotes.set(m[1], { n: footnotes.size + 1, text: m[2] });
}
const fnId = (id) => String(id).replace(/[^\w-]/g, '_');

// ── Annotation check: a wrong line number silently drops the upgrade or duplicates text ──
{
  const EXPECT = {
    pullquote: [/^\*\*/, '独立加粗句（**…**）'], highlight: [/^\*\*/, '独立加粗句（**…**）'],
    'def-card': [/^>\s*\*\*/, '引用里的术语行（> **术语**：…）'], checklist: [/^[-*]\s/, '无序列表项（- …）'],
    process: [/^\d+[.、)]\s*/, '有序列表项（1. …）'], gallery: [/\S/, '非空行'],
  };
  const problems = [];
  for (const u of anno.upgrades) {
    for (const ln of u.lines || [u.line]) {
      const text = (originalLines[ln - 1] ?? '').trim();
      if (!Number.isInteger(ln) || ln < 1 || ln > originalLines.length) problems.push(`${u.type} 行 ${ln}：超出文件范围（共 ${originalLines.length} 行）`);
      else if (!text && !INSERT_TYPES.has(u.type)) problems.push(`${u.type} 行 ${ln}：是空行，这条标注不会生效`);
      else if (EXPECT[u.type] && !EXPECT[u.type][0].test(text)) problems.push(`${u.type} 行 ${ln}：应该是${EXPECT[u.type][1]}，实际是「${text.slice(0, 30)}」`);
    }
  }
  const counts = anno.upgrades.reduce((m, u) => (m[u.type] = (m[u.type] || 0) + 1, m), {});
  console.log(`标注：${Object.entries(counts).map(([k, v]) => `${k} ×${v}`).join('，') || '无'}`);
  if (problems.length) console.warn(`⚠ 标注行号可能不对：\n  ${problems.join('\n  ')}`);
}

// ── Inline markdown helpers ──
// ── Bare URL → link. Scheme / www. / domain+path, or bare domain with a common TLD. ──
const URL_RE = /((?:https?:\/\/|www\.)[^\s<>"'，。；、）」』]+|(?<![\w@./-])(?:[a-z0-9-]+\.)+(?:com|org|net|dev|io|ai|se|wiki|app|co|cn|me|gg|xyz|so|sh|tv)(?:\/[^\s<>"'，。；、）」』]*)?)/i;
const EMAIL_RE = /([A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})/;
function mailLink(addr) {
  return `<a class="url" href="mailto:${addr}">${addr}</a>`;
}
function autoLink(raw) {
  if (/…|\.\.\.|[<>{}]/.test(raw)) return raw; // placeholder / templated string, not a real address
  let url = raw, tail = '';
  const m = url.match(/[.,;:!?)\]]+$/); if (m) { tail = m[0]; url = url.slice(0, -tail.length); }
  const href = /^https?:\/\//i.test(url) ? url : 'https://' + url;
  let disp = url.replace(/^https?:\/\//i, '').replace(/^www\./i, '').replace(/\/$/, '');
  if (disp.length > 42) disp = disp.slice(0, 40) + '…';
  const esc = (x) => x.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  return `<a class="url" href="${esc(href)}" title="${esc(href)}" target="_blank" rel="noopener">${esc(disp)}</a>${tail}`;
}

function inlineMd(text) {
  // Arrows & dashes typed in plain markdown — skipped inside `code` spans.
  const glyphs = (t) => {
  // Arrows & dashes typed in plain markdown (-> <- => -- …) → proper glyphs.
  // Done before HTML is produced, so only author text is touched (no tags yet).
  t = t.replace(/<->/g, '↔').replace(/(^|[^-<!])->/g, '$1→').replace(/<-(?!-)/g, '←').replace(/(^|[^=<>])=>/g, '$1⇒');
  // Paired ASCII double hyphen used as Chinese dash: "-- 插入语 --" / "--插入语--" → ——插入语——
  t = t.replace(/(^|[^-])\s?--(?!-)\s?([^-\n]+?)\s?--(?!-)\s?/g, '$1——$2——');
  t = t.replace(/(^|[^-])\s--\s/g, '$1——');
  // Dash-enclosed emphasis / interjection ——…—— : keep each "——" unbreakable and mark the span
  t = t.replace(/——([^—\n]{1,120}?)——/g, '<span class="dash-em"><span class="dash">——</span>$1<span class="dash">——</span></span>');
  t = t.replace(/——(?![^<]*<\/span>)/g, '<span class="dash">——</span>');
    return t;
  };
  // Split off `code`, existing [md](links) and bare URLs so glyph rewriting never touches them;
  // bare URLs become real <a> with shortened display text (domain/path…) — see autoLink().
  text = text.split(/(`[^`]+`)/).map((seg, k) => k % 2 ? seg
    : seg.split(/(\[[^\]]+\]\([^)]+\))/).map((s2, j) => j % 2 ? s2
      : s2.split(EMAIL_RE).map((s4, q) => q % 2 ? mailLink(s4)
        : s4.split(URL_RE).map((s3, i) => i % 2 ? autoLink(s3) : glyphs(s3)).join('')).join('')).join('')).join('');
  // Bold
  text = text.replace(/\*\*\[([^\]]+)\]\(([^)]+)\)\*\*/g, '<strong><a href="$2">$1</a></strong>');
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  // Latin-only emphasis is marked lang="en": it stays italic in zh docs instead of getting CJK emphasis dots
  text = text.replace(/\*([^*]+)\*/g, (_, t) => /[\u3400-\u9fff]/.test(t) ? `<em>${t}</em>` : `<em lang="en">${t}</em>`);
  // Links
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  // Inline code
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Footnote references
  text = text.replace(/\[\^([^\]]+)\]/g, (all, id) => footnotes.has(id)
    ? `<sup class="fn-ref"><a href="#fn-${fnId(id)}" id="fnref-${fnId(id)}">${footnotes.get(id).n}</a></sup>` : all);
  return text;
}

// ── Parse a def-card blockquote line ──
function parseDefCard(line) {
  // Format: > **Term**：Definition text
  const m = line.match(/^>\s*\*\*([^*]+)\*\*[：:]\s*(.+)$/);
  if (m) return { term: m[1], body: m[2] };
  return null;
}

// ── Blockquote renderer: nesting (> >, >>), multi-paragraph (blank ">"), attribution ──
// Attribution = last paragraph starting with —— / — / -- / ―, rendered as <footer><cite>.
function renderQuote(rawLines, depth = 0) {
  const lines = rawLines.map(l => l.replace(/^>\s?/, ''));
  const parts = []; let para = [];
  const flushPara = () => { if (para.length) { parts.push({ t: 'p', text: para.join(' ') }); para = []; } };
  for (let k = 0; k < lines.length; k++) {
    const l = lines[k].trim();
    if (/^>/.test(l)) {
      flushPara();
      const nested = [];
      while (k < lines.length && /^>/.test(lines[k].trim())) { nested.push(lines[k].trim()); k++; }
      k--;
      parts.push({ t: 'q', lines: nested });
    } else if (l === '') flushPara();
    else para.push(l);
  }
  flushPara();
  let cite = '';
  const last = parts[parts.length - 1];
  if (last && last.t === 'p' && /^(——|—|―|--)\s*\S/.test(last.text) && parts.length > 1) {
    cite = last.text.replace(/^(——|—|―|--)\s*/, '');
    parts.pop();
  }
  const inner = parts.map(pt => pt.t === 'q' ? renderQuote(pt.lines, depth + 1) : `<p>${inlineMd(pt.text)}</p>`).join('');
  const cls = depth ? ' class="bq-nested"' : '';
  return `<blockquote${cls}>${inner}${cite ? `<footer class="bq-cite"><span class="dash">——</span><cite>${inlineMd(cite)}</cite></footer>` : ''}</blockquote>`;
}

// ── Native bar chart (```chart fenced block) — pure HTML/CSS, no JS/canvas, so it survives
// PDF + long-image export and follows the theme colours.
//   title: 标题            unit: %            max: 100 (optional, default = max value)
//   series: A, B, C       (optional; enables grouped bars, one value per series per row)
//   highlight: 名称1, 名称2 (rows or series to draw in accent colour)
//   source: 数据来源       note: 说明
//   标签 | 58             (or  标签 | 59.1 | 54.3 | 49.9  for grouped)
// Values that are not numbers (e.g. "?" or "–") render as an empty bar marked "无数据".
function capHtml(t) {
  // 图注首句加粗当标题：只在括号外的第一个 。/：/—— 处切开，余下作说明
  let depth = 0;
  for (let i = 0; i < t.length && i < 60; i++) {
    const c = t[i];
    if (c === '（' || c === '(') depth++; else if (c === '）' || c === ')') depth = Math.max(0, depth - 1);
    else if (!depth && i >= 2 && (c === '。' || c === '：' || t.startsWith('——', i))) {
      const len = t.startsWith('——', i) ? 2 : 1; const rest = t.slice(i + len).trim();
      if (!rest) return t;
      return `<span class="cap-lead">${t.slice(0, i)}${c === '。' ? '。' : ''}</span>${rest}`;
    }
  }
  return t;
}
function renderChart(lines) {
  const meta = {}; const rows = [];
  for (const raw of lines) {
    const l = raw.trim(); if (!l) continue;
    const m = l.match(/^(title|unit|max|series|highlight|source|note)\s*[:：]\s*(.*)$/i);
    if (m && !l.includes('|')) { meta[m[1].toLowerCase()] = m[2].trim(); continue; }
    const parts = l.split('|').map(x => x.trim());
    rows.push({ label: parts[0], vals: parts.slice(1) });
  }
  const series = meta.series ? meta.series.split(/\s*[,，]\s*/) : null;
  const hi = new Set((meta.highlight || '').split(/\s*[,，]\s*/).filter(Boolean));
  const unit = meta.unit || '';
  const nums = rows.flatMap(r => r.vals.map(v => parseFloat(v))).filter(v => !isNaN(v));
  const max = parseFloat(meta.max) || Math.max(...nums, 0) || 1;
  const bar = (v, cls, label) => {
    const n = parseFloat(v); const ok = !isNaN(n);
    const w = ok ? Math.max(0.5, n / max * 100) : 0;
    return `<div class="hc-bar ${cls}${ok ? '' : ' hc-na'}"${label ? ` title="${escHtml(label)}"` : ''}><span class="hc-fill" style="width:${w.toFixed(2)}%"></span><span class="hc-val">${ok ? escHtml(v.replace(/[*]/g, '')) + (unit && !/%$/.test(v) ? unit : '') : '无数据'}</span></div>`;
  };
  let body = '';
  if (series) {
    body += `<div class="hc-legend">${series.map((s, k) => `<span class="hc-key hc-s${k}${hi.has(s) ? ' hc-hi' : ''}"><i></i>${escHtml(s)}</span>`).join('')}</div>`;
    for (const r of rows) {
      body += `<div class="hc-row hc-group"><div class="hc-label">${inlineMd(r.label)}</div><div class="hc-bars">${series.map((s, k) => bar(r.vals[k] ?? '', `hc-s${k}${hi.has(s) ? ' hc-hi' : ''}`, s)).join('')}</div></div>`;
    }
  } else {
    for (const r of rows) body += `<div class="hc-row${hi.has(r.label) ? ' hc-hi' : ''}"><div class="hc-label">${inlineMd(r.label)}</div><div class="hc-bars">${bar(r.vals[0] ?? '', hi.has(r.label) ? 'hc-hi' : '')}</div></div>`;
  }
  return `<figure class="hchart${series ? ' hchart-grouped' : ''}">${meta.title ? `<div class="hc-title">${inlineMd(meta.title)}</div>` : ''}<div class="hc-body">${body}</div>${meta.source || meta.note ? `<figcaption class="hc-cap">${meta.note ? inlineMd(meta.note) + ' ' : ''}${meta.source ? '来源：' + inlineMd(meta.source) : ''}</figcaption>` : ''}</figure>`;
}

function renderInsert(upgrade) {
  // Embed card — AI-generated SVG/UI preview
  if (upgrade.type === 'embed') {
    return (`<div class="embed-card"><div class="embed-label">${escHtml(upgrade.label || 'Preview')}</div><div class="embed-body">${upgrade.svg || upgrade.html || ''}</div>${upgrade.caption ? `<div class="embed-caption">${escHtml(upgrade.caption)}</div>` : ''}</div>`);
  }

  // Figure — Unsplash/external image with caption
  if (upgrade.type === 'figure') {
    return (`<figure class="figure-card"><img src="${upgrade.src}" alt="${escHtml(upgrade.alt || '')}" />${upgrade.caption ? `<figcaption>${capHtml(escHtml(upgrade.caption))}</figcaption>` : ''}</figure>`);
  }

  // Aside — side note / annotation that adds context
  if (upgrade.type === 'aside') {
    return (`<div class="aside-card"><div class="aside-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg></div><div class="aside-content"><div class="aside-title">${escHtml(upgrade.title || '补充')}</div><p>${inlineMd(upgrade.text)}</p></div></div>`);
  }

  // Summary card — key takeaway grid
  if (upgrade.type === 'summary-card') {
    let html = '<div class="summary-card"><div class="summary-label">' + escHtml(upgrade.label || 'Key Takeaways') + '</div><div class="summary-grid">';
    for (const item of (upgrade.items || [])) {
      html += `<div class="summary-item"><div class="summary-item-title">${escHtml(item.title)}</div><div class="summary-item-desc">${escHtml(item.desc)}</div></div>`;
    }
    html += '</div></div>';
    return html;
  }

  return '';
}

// ── Main render loop ──
const sections = [];
let currentSection = null;
let inSection = false;
let sectionCount = 0;
let skipUntil = 0;

function flushSection() {
  if (currentSection) {
    sections.push(currentSection);
    currentSection = null;
    inSection = false;
  }
}

function ensureSection() {
  if (!inSection) {
    currentSection = { num: null, title: null, blocks: [] };
    inSection = true;
  }
}

function addBlock(html) {
  ensureSection();
  currentSection.blocks.push(html);
}

for (let i = 0; i < originalLines.length; i++) {
  const lineNum = i + 1; // 1-based
  if (lineNum <= fmEnd) continue;
  // Explain-mode components go in before this line, even when the line is blank or consumed by a block above
  for (const u of insertMap.get(lineNum) || []) addBlock(renderInsert(u));
  if (lineNum < skipUntil) continue;

  const raw = originalLines[i];
  const trimmed = raw.trim();

  // Skip dropped lines
  if (dropLines.has(lineNum)) continue;

  // Skip empty lines
  if (trimmed === '') continue;

  // HTML comments (single or multi-line) are notes for the author, never page text
  if (trimmed.startsWith('<!--')) {
    let j = i;
    while (j < originalLines.length && !originalLines[j].includes('-->')) j++;
    skipUntil = j + 2;
    continue;
  }

  // Language filtering: if meta.lang is set, skip lines that are the "other" language
  // Works for bilingual docs where EN/ZH alternate line by line
  if (anno.meta.lang) {
    const lang = anno.meta.lang; // 'zh' or 'en'
    const isChinese = /[一-鿿]/.test(trimmed);
    const isEnglish = /^[A-Za-z\[*_>#\d]/.test(trimmed) && !isChinese;
    // Headings and special syntax always pass through
    const isStructural = /^#{1,6}\s|^>|^[-*]\s|^\d+\.\s|^<|^!\[|^\[/.test(trimmed);
    if (!isStructural && !upgradeMap.has(lineNum)) {
      if (lang === 'zh' && isEnglish && !isChinese) continue;
      if (lang === 'en' && isChinese && !isEnglish) continue;
    }
  }

  // Skip HTML-only lines (sub/sup references, video tags, svg blocks)
  if (/^<(sub|sup|svg|\/svg)/.test(trimmed)) continue;
  // Footnote definitions are collected up front and rendered as a list at the end
  if (/^\[\^[^\]]+\]:/.test(trimmed)) continue;

  // Image lines — one image = figure; 2–3 adjacent images (same line or consecutive lines)
  // = side-by-side group; 4+ = horizontally scrollable strip. All use the breakout width.
  const IMG_ONLY = /^(?:!\[[^\]]*\]\([^)]+\)\s*)+$/;
  if (IMG_ONLY.test(trimmed)) {
    const imgs = [];
    let j = i;
    while (j < originalLines.length && IMG_ONLY.test(originalLines[j].trim())) {
      for (const m of originalLines[j].trim().matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g)) imgs.push({ alt: m[1] || '', src: m[2] });
      j++;
    }
    skipUntil = j + 1;
    const radius = '0';
    const cap = alt => alt && !alt.startsWith('img_') ? `<figcaption>${capHtml(inlineMd(escHtml(alt)))}</figcaption>` : '';
    const one = (im, cls = '') => `<figure class="figure-card${cls}"><img src="${escHtml(im.src)}" alt="${escHtml(im.alt)}" loading="lazy" style="border-radius:${radius}" />${cap(im.alt)}</figure>`;
    if (imgs.length === 1) addBlock(one(imgs[0]));
    else if (imgs.length <= 3) addBlock(`<div class="img-row img-row-${imgs.length}">${imgs.map(im => one(im)).join('')}</div>`);
    else addBlock(`<div class="img-strip-wrap"><div class="img-strip">${imgs.map(im => one(im)).join('')}</div><div class="img-strip-hint">← 横向滑动查看 ${imgs.length} 张 →</div></div>`);
    continue;
  }

  // Embedded video / iframe (single or multi-line) → breakout media figure
  if (/^<(video|iframe)\b/i.test(trimmed)) {
    const tag = trimmed.match(/^<(video|iframe)/i)[1].toLowerCase();
    const buf = [originalLines[i]];
    let j = i + 1;
    if (!new RegExp(`</${tag}>|/>\\s*$`, 'i').test(trimmed)) {
      while (j < originalLines.length) { buf.push(originalLines[j]); j++; if (new RegExp(`</${tag}>`, 'i').test(originalLines[j - 1])) break; }
    }
    skipUntil = j + 1;
    addBlock(`<figure class="figure-card media-embed media-${tag}">${buf.join('\n')}</figure>`);
    continue;
  }

  // ── Code blocks (fenced ``` ) ──
  if (trimmed.startsWith('```')) {
    const lang = trimmed.slice(3).trim();
    let codeLines = [];
    let j = i + 1;
    while (j < originalLines.length) {
      if (originalLines[j].trim().startsWith('```')) { j++; break; }
      codeLines.push(originalLines[j]);
      j++;
    }
    skipUntil = j + 1;
    if (lang === 'chart') { addBlock(renderChart(codeLines)); continue; }
    addBlock(`<pre><code${lang ? ` class="language-${escHtml(lang)}"` : ''}>${escHtml(codeLines.join('\n'))}</code></pre>`);
    continue;
  }

  // ── Markdown pipe tables ( | col | col | ) ──
  // Alignment from the separator row (:--, :-:, --:), numeric columns auto right-aligned with
  // tabular figures, optional caption line directly after the table: "表：…" / "Table: …".
  if (/^\|(.+)\|$/.test(trimmed)) {
    let tableLines = [trimmed];
    let j = i + 1;
    while (j < originalLines.length && /^\|(.+)\|$/.test(originalLines[j].trim())) { tableLines.push(originalLines[j].trim()); j++; }
    let caption = '';
    if (j < originalLines.length && /^(表|Table|数据来源|来源|Source)\s*[:：]/i.test(originalLines[j].trim())) { caption = originalLines[j].trim(); j++; }
    skipUntil = j + 1; // j is the first unconsumed line (0-based) → 1-based j+1
    const parseRow = (row) => row.replace(/\\\|/g, '\u0000').split('|').slice(1, -1).map(c => c.trim().replace(/\u0000/g, '|'));
    const headers = parseRow(tableLines[0]);
    const sep = tableLines[1] && /^[\s|:\-]+$/.test(tableLines[1]) ? parseRow(tableLines[1]) : null;
    const bodyRows = tableLines.slice(sep ? 2 : 1).map(parseRow);
    const isNum = c => /^[-+]?[\d.,]+\s*%?[*†‡]?$|^[–—-]$|^\*\*[-+]?[\d.,]+%?\*\*$/.test(c.trim());
    const align = headers.map((_, k) => {
      const sp = sep && sep[k] || '';
      if (/^:-+:$/.test(sp)) return 'center';
      if (/-+:$/.test(sp)) return 'right';
      if (/^:-+$/.test(sp)) return 'left';
      const col = bodyRows.map(r => r[k] || '').filter(Boolean);
      return col.length && col.every(c => isNum(c.split(/\s*\/\s*|<br>/)[0])) ? 'num' : '';
    });
    let tableHtml = `<figure class="table-wrap">${caption ? `<figcaption class="table-caption">${inlineMd(caption)}</figcaption>` : ''}<table><thead><tr>`;
    headers.forEach((h, k) => { tableHtml += `<th${align[k] ? ` class="al-${align[k]}"` : ''}>${inlineMd(h)}</th>`; });
    tableHtml += '</tr></thead><tbody>';
    bodyRows.forEach(row => {
      tableHtml += '<tr>';
      row.forEach((cell, k) => { tableHtml += `<td${align[k] ? ` class="al-${align[k]}"` : ''}>${inlineMd(cell)}</td>`; });
      tableHtml += '</tr>';
    });
    tableHtml += '</tbody></table></figure>';
    addBlock(tableHtml);
    continue;
  }

  // ── HTML table pass-through ──
  if (trimmed.startsWith('<table')) {
    // Check if table is on a single line
    if (trimmed.includes('</table>')) {
      addBlock(`<div class="table-wrap">${trimmed}</div>`);
      continue;
    }
    // Multi-line HTML table
    let htmlBlock = [trimmed];
    let j = i + 1;
    while (j < originalLines.length) {
      const nextLine = originalLines[j];
      htmlBlock.push(nextLine);
      if (nextLine.includes('</table>')) { j++; break; }
      j++;
    }
    skipUntil = j + 1;
    addBlock(`<div class="table-wrap">${htmlBlock.join('\n')}</div>`);
    continue;
  }

  // ── Document title (# ) — already shown in the hero from meta.title ──
  if (/^#\s+/.test(trimmed) && !trimmed.startsWith('##')) {
    const h1 = trimmed.replace(/^#\s+/, '').trim();
    const norm = t => t.replace(/[\s*_`]/g, '');
    if (norm(h1) !== norm(anno.meta.title || '')) addBlock(`<h3>${inlineMd(h1)}</h3>`);
    continue;
  }

  // ── Thematic break (---, ***, ___) ── used to leak out as a literal "---" paragraph
  if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed.replace(/\s+/g, ''))) {
    addBlock('<hr class="divider">');
    continue;
  }

  // ── Section headings ──
  if (trimmed.startsWith('## ')) {
    flushSection();
    sectionCount++;
    // For zh mode: extract Chinese portion from mixed headings like "Squash and Stretch 挤压与拉伸"
    let headingText = trimmed.replace(/^##\s+/, '');
    if (anno.meta.lang === 'zh') {
      // Extract Chinese portion: find the first Chinese character, take everything from there
      const zhStart = headingText.search(/[一-鿿]/);
      if (zhStart !== -1) headingText = headingText.slice(zhStart).trim();
    } else if (anno.meta.lang === 'en') {
      // Keep only the English part before Chinese characters
      const enMatch = headingText.match(/^([^一-鿿]+)/);
      if (enMatch) headingText = enMatch[1].trim();
    }
    // Auto-numbered sections (01/02/…) — strip the author's own ordinal prefix so the number
    // isn't shown twice: 一、 / 二. / 第三部分 / 第3章： / 1. / 01 / Part 2: …
    headingText = headingText.replace(/^\s*(?:第\s*[一二三四五六七八九十百零〇两\d]+\s*[部分章节篇讲回]*\s*[、.．:：\-—\s]*|[一二三四五六七八九十]+\s*[、.．:：]\s*|\(?[一二三四五六七八九十]+\)\s*|（[一二三四五六七八九十]+）\s*|\d{1,2}\s*[、.．:：)]\s*|(?:Part|Chapter|Section)\s+\d+\s*[:.\-—]?\s*)/i, '').trim() || headingText;
    currentSection = {
      num: String(sectionCount).padStart(2, '0'),
      title: headingText,
      blocks: []
    };
    inSection = true;
    continue;
  }

  if (trimmed.startsWith('### ')) {
    addBlock(`<h3>${inlineMd(trimmed.replace(/^###\s+/, ''))}</h3>`);
    continue;
  }

  // ── Check upgrades ──
  const upgrade = upgradeMap.get(lineNum);

  // Pullquote — Swiss: vertical accent bar left, large light text right
  if (upgrade && upgrade.type === 'pullquote') {
    // Pullquote may sit on a "> …" line: strip the markdown marker (it used to leak as a literal ">")
    let text = trimmed.replace(/^(>\s?)+/, '').trim().replace(/^\*\*/, '').replace(/\*\*$/, '');
    let pqCite = '';
    const cm = text.match(/^(.*[”"」』）)])\s*[（(]([^（）()]{1,80})[）)]\s*[。.]?$/);
    if (cm) { text = cm[1]; pqCite = cm[2]; }
    let rendered = inlineMd(text);
    if (upgrade.accent) {
      rendered = rendered.replace(upgrade.accent, `<span class="accent-mark">${upgrade.accent}</span>`);
    }
    if (styleName === 'swiss') {
      addBlock(`<div class="pullquote pullquote-swiss"><div class="pq-bar"></div><div class="pq-content"><p>${rendered}</p>${pqCite ? `<div class="pq-cite">${inlineMd(pqCite)}</div>` : ''}</div></div>`);
    } else {
      addBlock(`<div class="pullquote"><p>${rendered}</p>${pqCite ? `<div class="pq-cite">${inlineMd(pqCite)}</div>` : ''}</div>`);
    }
    continue;
  }

  // Highlight card — Swiss: split layout with accent sidebar label
  if (upgrade && upgrade.type === 'highlight') {
    let text = trimmed.replace(/^\*\*/, '').replace(/\*\*$/, '');
    if (upgrade.lines_end) {
      const endLine = upgrade.lines_end;
      let combined = [];
      for (let j = i; j < originalLines.length && (j + 1) <= endLine; j++) {
        const lt = originalLines[j].trim();
        if (lt && !/^!\[/.test(lt)) combined.push(lt);
      }
      text = combined.join(' ');
      skipUntil = endLine + 1;
    }
    text = text.replace(/^\*\*/, '').replace(/\*\*$/, '');
    if (styleName === 'swiss') {
      addBlock(`<div class="highlight-card highlight-swiss"><div class="hl-label">${upgrade.label || ''}</div><div class="hl-body"><p>${inlineMd(text)}</p></div></div>`);
    } else {
      addBlock(`<div class="highlight-card"><p>${inlineMd(text)}</p><div class="attr">${upgrade.label || ''}</div></div>`);
    }
    continue;
  }

  // Def card — Swiss: inline left-right term/definition
  if (upgrade && upgrade.type === 'def-card') {
    const parsed = parseDefCard(trimmed);
    if (parsed) {
      if (styleName === 'swiss') {
        addBlock(`<div class="def-card def-card-swiss"><div class="dc-term"><span class="dc-label">${TERM_LABEL}</span>${escHtml(parsed.term)}</div><div class="dc-body">${inlineMd(parsed.body)}</div></div>`);
      } else {
        addBlock(`<div class="def-card"><div class="def-card-label">${TERM_LABEL}</div><div class="def-card-term">${escHtml(parsed.term)}</div><div class="def-card-body">${inlineMd(parsed.body)}</div></div>`);
      }
      continue;
    }
  }

  // Gallery — Swiss: grid tiles instead of scroll
  if (upgrade && upgrade.type === 'gallery') {
    if (styleName === 'swiss') {
      let html = '<div class="gallery-grid">';
      for (const item of upgrade.items) {
        html += `<div class="gallery-grid-item"><div class="img-placeholder"><span>${escHtml(item.title)}</span></div><div class="gallery-cap">${escHtml(item.desc)}</div></div>`;
      }
      html += '</div>';
      addBlock(html);
    } else {
      let html = '<div class="gallery-hint">← 横向滚动查看更多 →</div><div class="gallery">';
      for (const item of upgrade.items) {
        html += `<div class="gallery-item"><div class="img-placeholder"><span>${escHtml(item.title)}</span></div><div class="gallery-cap">${escHtml(item.desc)}</div></div>`;
      }
      html += '</div>';
      addBlock(html);
    }
    continue;
  }

  // Process / timeline
  if (upgrade && upgrade.type === 'process') {
    let html = '<div class="process">';
    upgrade.items.forEach((item, idx) => {
      html += `<div class="process-step"><div class="process-num">${String(idx + 1).padStart(2, '0')}</div><div class="process-content"><div class="process-title">${escHtml(item.title)}</div><div class="process-desc">${inlineMd(item.desc)}</div></div></div>`;
    });
    html += '</div>';
    addBlock(html);
    // Skip the original numbered list lines
    for (const ln of upgrade.lines) {
      dropLines.add(ln);
    }
    continue;
  }

  // Checklist
  if (upgrade && upgrade.type === 'checklist') {
    let html = '<ul class="checklist">';
    // Gather list items from original lines
    for (const ln of upgrade.lines) {
      const content = originalLines[ln - 1].trim().replace(/^[-*]\s*/, '');
      html += `<li>${inlineMd(content)}</li>`;
      if (ln !== lineNum) dropLines.add(ln);
    }
    html += '</ul>';
    addBlock(html);
    continue;
  }

  // Skip lines consumed by gallery/process/checklist
  if (galleryRange.has(lineNum) || processRange.has(lineNum) || checklistRange.has(lineNum)) {
    if (!upgradeMap.has(lineNum)) continue;
  }

  // ── Standard blockquote (non-def-card) ──
  if (/^>/.test(trimmed) && !defCardLines.has(lineNum)) {
    const parsed = parseDefCard(trimmed);
    if (parsed) {
      if (styleName === 'swiss') {
        addBlock(`<div class="def-card def-card-swiss"><div class="dc-term"><span class="dc-label">${TERM_LABEL}</span>${escHtml(parsed.term)}</div><div class="dc-body">${inlineMd(parsed.body)}</div></div>`);
      } else {
        addBlock(`<div class="def-card"><div class="def-card-label">${TERM_LABEL}</div><div class="def-card-term">${escHtml(parsed.term)}</div><div class="def-card-body">${inlineMd(parsed.body)}</div></div>`);
      }
      continue;
    }
    // Regular blockquote — collect contiguous ">" lines (a blank line ends the quote,
    // as in CommonMark; old code swallowed blanks and merged separate quotes).
    let bqRaw = [trimmed];
    let j = i + 1;
    while (j < originalLines.length && /^>/.test(originalLines[j].trim())) { bqRaw.push(originalLines[j].trim()); j++; }
    skipUntil = j + 1;
    addBlock(renderQuote(bqRaw));
    continue;
  }

  // ── Ordered list ──
  if (/^\d+\.\s/.test(trimmed)) {
    let items = [trimmed.replace(/^\d+\.\s*/, '')];
    let j = i + 1;
    while (j < originalLines.length) {
      const nextTrimmed = originalLines[j].trim();
      if (/^\d+\.\s/.test(nextTrimmed)) {
        if (!dropLines.has(j + 1)) items.push(nextTrimmed.replace(/^\d+\.\s*/, ''));
        j++;
      } else if (nextTrimmed === '') {
        j++;
      } else {
        break;
      }
    }
    skipUntil = j + 1;
    addBlock('<ol>' + items.map(it => `<li>${inlineMd(it)}</li>`).join('') + '</ol>');
    continue;
  }

  // ── Unordered list ──
  if (/^[-*]\s/.test(trimmed)) {
    let items = [trimmed.replace(/^[-*]\s*/, '')];
    let j = i + 1;
    while (j < originalLines.length) {
      const nextTrimmed = originalLines[j].trim();
      if (/^[-*]\s/.test(nextTrimmed) && !dropLines.has(j + 1)) {
        items.push(nextTrimmed.replace(/^[-*]\s*/, ''));
        j++;
      } else if (nextTrimmed === '') {
        j++;
      } else {
        break;
      }
    }
    skipUntil = j + 1;
    addBlock('<ul>' + items.map(it => `<li>${inlineMd(it)}</li>`).join('') + '</ul>');
    continue;
  }

  // ── Default: paragraph ──
  addBlock(`<p>${inlineMd(trimmed)}</p>`);
}

flushSection();

// Footnote list: into the document's own 脚注 / Footnotes section if it has one, else a new last section
if (footnotes.size) {
  const list = `<ol class="footnotes">${[...footnotes].map(([id, f]) =>
    `<li id="fn-${fnId(id)}">${inlineMd(escHtml(f.text))} <a class="fn-back" href="#fnref-${fnId(id)}" aria-label="返回正文">↩</a></li>`).join('')}</ol>`;
  const own = sections.find(sec => sec.title && /footnote|脚注|注释|注脚/i.test(sec.title));
  if (own) own.blocks.push(list);
  else sections.push({ num: String(++sectionCount).padStart(2, '0'), title: docLang === 'en' ? 'Footnotes' : '脚注', blocks: [list] });
}

// ── HTML escape helper ──
function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Assemble full HTML ──
const meta = anno.meta;
const isSwiss = styleName === 'swiss';
const tagsHtml = meta.tags.map(t => `<span>${escHtml(t)}</span>`).join('');

let bodyHtml = '';

const docType = (frontmatter.type || 'article').toUpperCase();
const docStatus = (frontmatter.status || 'final').toUpperCase();

const chromeMetaItems = [
  ['author', meta.author],
  ['date', meta.date],
  ['reading', meta.reading_time],
].map(([k, v]) =>
  `<div class="cm-item"><span class="cm-key">${escHtml(k)}</span> <span class="cm-val">${escHtml(v)}</span></div>`
);

const chromeTagsHtml = meta.tags.map(t =>
  `<span class="chrome-tag">${escHtml(t)}</span>`
).join('');

if (!isSwiss) {
  // Magazine masthead: one quiet line — tags · author · date · reading time, one hairline below.
  const parts = [...meta.tags.map(t => `<span class="dl-tag">${escHtml(t)}</span>`),
    meta.author && `<span>${escHtml(meta.author)}</span>`, meta.date && `<span>${escHtml(meta.date)}</span>`,
    meta.reading_time && `<span>${escHtml(meta.reading_time)}</span>`].filter(Boolean);
  bodyHtml += `\n<div class="doc-chrome doc-line">${parts.join('<span class="dl-sep">·</span>')}</div>\n`;
} else bodyHtml += `
<div class="doc-chrome">
  <div class="doc-chrome-bar">
    <div class="chrome-l">
      <span class="chrome-accent">${escHtml(docType)}</span>
      <span class="chrome-sep"></span>
      <span>${escHtml(docStatus)}</span>
    </div>
    <div class="chrome-r">
      <span>归藏 Page</span>
      <span class="chrome-sep"></span>
      <span>${escHtml(meta.date)}</span>
    </div>
  </div>
  <div class="doc-chrome-rule"></div>
  <div class="doc-chrome-meta">
    ${chromeMetaItems.join('<div class="cm-dot"></div>')}
  </div>
  <div class="doc-chrome-tags">${chromeTagsHtml}</div>
</div>
`;

// Hero — Swiss uses cover card with configurable image
// Hero image: must be a photograph / video frame, never a chart, table or screenshot of text.
// If meta.hero_image is missing, "auto", or looks like a chart/table, pick the first local image
// whose filename + alt don't look like data graphics, preferring 照片/视频截图/photo/frame.
const NOT_HERO = /(chart|table|index|bench|score|graph|plot|diagram|highlight|screenshot-of-text|图表|表格|评测|基准|指数|榜|博客|blog|官方)/i;
const PREFER_HERO = /(photo|frame|照片|视频截图|现场|全景|wide)/i;
function pickHero() {
  const cands = [];
  originalLines.forEach(l => { for (const m of l.matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g)) cands.push({ alt: m[1], src: m[2] }); });
  const ok = cands.filter(c => !NOT_HERO.test(c.src + ' ' + c.alt));
  return (ok.find(c => PREFER_HERO.test(c.src + ' ' + c.alt)) || ok[0] || {}).src;
}
let heroImg = meta.hero_image;
if (!heroImg || heroImg === 'auto' || (NOT_HERO.test(heroImg) && !meta.hero_force)) heroImg = pickHero() || heroImg;
heroImg = heroImg || 'https://images.unsplash.com/photo-1509023464722-18d996393ca8?w=1400&h=600&fit=crop';
if (isSwiss) {
  bodyHtml += `
<header class="hero hero-cover">
  <img class="hero-bg" src="${heroImg}" alt="" />
  <div class="hero-overlay">
    <div class="hero-kicker">${escHtml(docType)} — ${escHtml(meta.date)}</div>
    <h1>${escHtml(meta.title)}</h1>
    <p class="hero-subtitle">${escHtml(meta.subtitle)}</p>
  </div>
</header>
`;
} else {
  bodyHtml += `
<header class="hero">
  <h1>${escHtml(meta.title)}</h1>
  <p class="hero-subtitle">${escHtml(meta.subtitle)}</p>
</header>
`;
}

// Build TOC + Sections
const tocItems = [];
let secIdx = 0;
for (const sec of sections) {
  const secId = sec.num ? `s-${sec.num}` : `s-${secIdx}`;
  if (sec.title) tocItems.push({ id: secId, num: sec.num, title: sec.title });
  const isFootnote = sec.title && /footnote|脚注|注释|注脚/i.test(sec.title);
  const isRefs = /来源|参考|资料|延伸阅读|链接|references?|sources?|further reading/i.test(sec.title || '');
  bodyHtml += `<section class="section${isFootnote ? ' section-footnote' : ''}${isRefs ? ' refs' : ''}" id="${secId}">`;
  if (isSwiss && sec.num && sec.title) {
    bodyHtml += `<div class="section-header"><div class="section-number">${sec.num}</div><h2>${inlineMd(sec.title)}</h2></div>`;
  } else {
    if (sec.num) bodyHtml += isSwiss ? `<div class="section-number">${sec.num}</div>` : `<div class="section-number sn-sym"><span class="sn-side sn-l"><span class="sn-star s3">✦</span><span class="sn-star s2">✦</span><span class="sn-star s1">✦</span></span><span class="sn-num">${sec.num}</span><span class="sn-side sn-r"><span class="sn-star s1">✦</span><span class="sn-star s2">✦</span><span class="sn-star s3">✦</span></span></div>`;
    if (sec.title) bodyHtml += `<h2>${inlineMd(sec.title)}</h2>`;
  }
  bodyHtml += sec.blocks.join('\n');
  bodyHtml += '</section>';
  secIdx++;
}

// Footer
bodyHtml += `
<div class="divider-dot">· · ·</div>
<footer><p>归藏 Page · Built with constrained HTML</p></footer>
`;

// ── Load CSS based on style flag ──
// import.meta.dirname only exists on Node >= 20.11; older Node used to fall back to '.'
// and then silently skip ui.css/ui.js (empty try/catch) -> no buttons. Resolve robustly.
const scriptDir = import.meta.dirname || dirname(fileURLToPath(import.meta.url));
let assetsDir = resolve(scriptDir, '..', 'assets');
if (!existsSync(assetsDir)) assetsDir = scriptDir;
const family = styleName === 'swiss' ? 'swiss' : 'magazine';
function readAsset(name) {
  const p = resolve(assetsDir, name);
  if (!existsSync(p)) { console.error(`✗ missing asset: ${p}`); process.exit(1); }
  return readFileSync(p, 'utf-8');
}
// 设计系统（主题、字号角色、间距、共享组件）在前，风格自己的版式在后，设置面板 ui.css 最后
const gzCss = readAsset(`gz-${family}.css`);
const css = readAsset(`style-${family}.css`);
const uiCss = readAsset('ui.css');
const uiJs = readAsset('ui.js');
const themes = JSON.parse(readAsset('themes.json'));
const theme = themes[family];

// 初始配色：品牌色 > 指定主题 > 默认主题。品牌色不直接用，经 gz-theme.mjs 约束成一套完整主题
const brand = brandArg || meta.brand;
let brandCss = '';
let colors = theme.colors;
let themeId = themeArg || meta.theme || theme.default;
if (brand) {
  try {
    brandCss = execFileSync(process.execPath, [resolve(scriptDir, 'gz-theme.mjs'), 'brand', brand, '--family', family], { encoding: 'utf-8' }).trim();
    const v = (k) => (brandCss.match(new RegExp(`${k}:(#[0-9a-f]{6})`, 'i')) || [])[1];
    colors = [{ id: 'brand', name: '品牌色', en: 'Brand', scheme: 'light', paper: v('--paper'), ink: v('--ink'), accent: v('--accent') }, ...colors];
    themeId = 'brand';
    console.log(brandCss.split('\n')[0]);
  } catch (e) {
    console.warn(`品牌色 ${brand} 无法生成主题，改用预设：${(e.stderr || e.message).toString().trim()}`);
  }
}
if (!colors.some(c => c.id === themeId)) {
  console.warn(`没有主题 ${themeId}，改用默认主题 ${theme.default}`);
  themeId = theme.default;
}
const themeScheme = colors.find(c => c.id === themeId).scheme;

// Static UI markup (settings FAB only — export lives in scripts/export.mjs). Rendered into the HTML itself so the
// controls exist even before/without JS; ui.js only wires up behaviour.
const ICON = {
  sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>',
};
const attr = v => String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
const uiMarkup = `
<div class="hf-fab">
  <button class="hf-fab-btn" id="hf-settings-toggle" type="button" title="设置" aria-haspopup="true">${ICON.sliders}</button>
  <div class="hf-dropdown" id="hf-settings-dropdown">
    <div class="hf-dropdown-label">配色</div>
    <div class="hf-swatches">${colors.map(c =>
      `<button type="button" class="hf-swatch${c.id === themeId ? ' active' : ''}" data-theme-id="${c.id}" data-scheme="${c.scheme}" style="background:linear-gradient(135deg,${c.paper} 0 50%,${c.accent} 50% 100%)" title="${attr(`${c.name} ${c.en}`)}" aria-label="${attr(c.name)}"></button>`).join('')}</div>
    <div class="hf-dropdown-divider"></div>
    <div class="hf-dropdown-label">字体</div>
    <div class="hf-font-options">${theme.fonts.map((f, i) =>
      `<button type="button" class="hf-font-option${i === 0 ? ' active' : ''}" data-vars="${theme.fontVars.join(' ')}" data-family="${attr(f.family)}" data-href="${attr(f.href || '')}"><span class="font-preview" style="font-family:${attr(f.family)}">${theme.preview}</span><span class="font-name">${attr(f.name)}</span></button>`).join('')}</div>
  </div>
</div>`;

// 字体：在线链接（带 data-gz-fonts，--embed 时按页面用字子集化内置）
const fontsTag = await fontLinkTag(theme.fontIds);

// Build TOC HTML
const tocHtml = tocItems.map(t =>
  `<a class="toc-item" href="#${t.id}">${t.num ? `<span class="toc-num">${t.num}</span>` : ''}${escHtml(t.title)}</a>`
).join('\n');

const tocSidebar = `
<div class="toc-scrim" id="toc-scrim"></div>
<nav class="toc" id="toc">
  <button class="toc-toggle" id="toc-toggle" aria-label="Toggle table of contents">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 4h14M2 9h10M2 14h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
  </button>
  <div class="toc-panel" id="toc-panel">
    <div class="toc-header">目录</div>
    ${tocHtml}
  </div>
</nav>`;

const tocScript = `
<script>
(function(){
  const toggle = document.getElementById('toc-toggle');
  const panel = document.getElementById('toc-panel');
  const toc = document.getElementById('toc');
  const scrim = document.getElementById('toc-scrim');
  const narrow = window.matchMedia('(max-width: 1024px)');
  let open = false;
  function setOpen(v) {
    open = v;
    toc.classList.toggle('toc-open', v);
    document.documentElement.classList.toggle('toc-is-open', v);
    toggle.setAttribute('aria-expanded', String(v));
  }
  toggle.addEventListener('click', (e) => { e.stopPropagation(); setOpen(!open); });
  if (scrim) scrim.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && open) setOpen(false); });
  panel.addEventListener('click', (e) => {
    // On narrow screens the drawer covers the text, so close it after jumping;
    // on wide screens it sits beside the text and can stay open.
    if (e.target.closest('.toc-item') && narrow.matches) setOpen(false);
  });
  // Scroll spy
  const sections = document.querySelectorAll('.section[id]');
  const links = document.querySelectorAll('.toc-item');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        links.forEach(l => l.classList.remove('toc-active'));
        const active = panel.querySelector('a[href="#'+entry.target.id+'"]');
        if (active) active.classList.add('toc-active');
      }
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  sections.forEach(s => observer.observe(s));
})();
</script>`;

// ── CJK typography pass (references/design-rules.md §中文排版) ──
// 1) Document language: see docLang at the top.
// 2) Han ↔ Latin/digit spacing ("盘古之白"). clreq §6.3.3: ≤ 1/4 em between Han and
//    Western letters/numerals, none at line start/end. Chrome has no text-autospace yet,
//    so insert a real (collapsible) space wrapped in .hf-sp where the author left none;
//    browsers that support text-autospace hide the span and use the native spacing.
//    Only text nodes are touched — never tags/attributes, <code>, <pre>, <script>, <svg>.
function autospace(html) {
  const HAN = '[\\u3400-\\u4dbf\\u4e00-\\u9fff\\uf900-\\ufaff]';
  const LAT = '[A-Za-z0-9]';
  const re1 = new RegExp(`(${HAN})(${LAT})`, 'g');
  const re2 = new RegExp(`(${LAT}|%)(${HAN})`, 'g');
  const SP = '<span class="hf-sp"> </span>';
  let out = '', skip = 0;
  for (const part of html.split(/(<[^>]+>)/)) {
    if (part.startsWith('<')) {
      const m = part.match(/^<(\/?)(code|pre|script|style|svg|kbd|textarea)\b/i);
      if (m) skip += m[1] ? -1 : (/\/>$/.test(part) ? 0 : 1);
      out += part;
    } else if (skip > 0 || !part) {
      out += part;
    } else {
      out += part.replace(re1, `$1${SP}$2`).replace(re2, `$1${SP}$2`);
    }
  }
  return out;
}
if (docLang.startsWith('zh') && anno.meta.autospace !== false) bodyHtml = autospace(bodyHtml);

const fullHtml = `<!DOCTYPE html>
<html lang="${docLang}" data-hf-style="${styleName}" data-family="${family}" data-medium="page" data-theme="${themeId}" data-scheme="${themeScheme}" style="color-scheme:${themeScheme}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escHtml(meta.title)}</title>
<style>${gzCss}</style>${brandCss ? `\n<style data-gz-brand>${brandCss}</style>` : ''}
<style>${css}</style>
<style>${uiCss}</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
${fontsTag}
</head>
<body>
${tocSidebar}
<div class="container">
${bodyHtml}
</div>
${tocScript}
${uiMarkup}
<script>${uiJs}</script>
</body>
</html>`;

let outHtml = fullHtml;
if (embed) {
  try {
    const r = await embedFonts(fullHtml, { log: (m) => console.log('  ' + m) });
    outHtml = r.html;
    if (r.report.length) console.log(`字体内置：${[...new Set(r.report.map((f) => f.id))].join('、')}，合计 ${(r.report.reduce((n, f) => n + f.bytes, 0) / 1024).toFixed(0)}KB`);
  } catch (e) {
    console.warn(e.code === 'ERR_MODULE_NOT_FOUND'
      ? '字体内置需要先在 skill 目录运行一次 npm install；这次保留在线字体'
      : `字体内置失败，保留在线字体：${e.message}`);
  }
}
writeFileSync(resolve(outPath), outHtml, 'utf-8');
console.log(`✓ Rendered ${sections.length} sections → ${outPath}`);
