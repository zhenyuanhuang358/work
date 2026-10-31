(function () {
  'use strict';

  // Theme options live in assets/themes.json; render.mjs writes the controls
  // into the HTML statically, so this file only wires up behaviour.
  const style = document.documentElement.dataset.hfStyle || 'swiss';
  const $ = (id) => document.getElementById(id);
  // Per page: a reader's choice on one page (or a brand page's palette) doesn't leak into other pages
  const STORE = 'hf-page-prefs:' + style + ':' + location.pathname;

  // ── Helpers ──
  function closeAllDropdowns() {
    document.querySelectorAll('.hf-dropdown.open').forEach(d => d.classList.remove('open'));
  }

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.hf-dropdown') && !e.target.closest('.hf-fab-btn')) {
      closeAllDropdowns();
    }
  });

  // PDF / long-image export is no longer in the page: the model runs scripts/export.mjs.

  document.getElementById('hf-settings-toggle').addEventListener('click', (e) => {
    e.stopPropagation();
    const dd = document.getElementById('hf-settings-dropdown');
    const wasOpen = dd.classList.contains('open');
    closeAllDropdowns();
    if (!wasOpen) dd.classList.add('open');
  });

  // ── Theme switching ──
  // Every palette is a [data-theme] block in the inlined design-system CSS; a swatch only
  // switches <html data-theme>. Text, rule and accent-text colours come with the theme,
  // contrast-checked, so nothing is set inline.
  function applyTheme(sw) {
    document.querySelectorAll('.hf-swatch').forEach(s => s.classList.toggle('active', s === sw));
    const root = document.documentElement;
    root.dataset.theme = sw.dataset.themeId;
    root.dataset.scheme = sw.dataset.scheme || 'light';
    root.style.colorScheme = root.dataset.scheme;
  }
  // ── Font switching ──
  // An option swaps the Latin face of the body stack (the CJK face stays); its stylesheet
  // is loaded on first use.
  function applyFont(opt) {
    document.querySelectorAll('.hf-font-option').forEach(o => o.classList.toggle('active', o === opt));
    (opt.dataset.vars || '--font-sans').split(' ').forEach(v => document.documentElement.style.setProperty(v, opt.dataset.family));
    const href = opt.dataset.href;
    if (href && !document.querySelector(`link[data-hf-font="${href}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.dataset.hfFont = href;
      link.href = href;
      document.head.appendChild(link);
    }
  }
  function save() {
    try {
      const sw = document.querySelector('.hf-swatch.active');
      const fo = document.querySelector('.hf-font-option.active');
      localStorage.setItem(STORE, JSON.stringify({ theme: sw && sw.dataset.themeId, font: fo && fo.dataset.family }));
    } catch (e) {}
  }
  document.querySelectorAll('.hf-swatch').forEach(sw => sw.addEventListener('click', (e) => { e.stopPropagation(); applyTheme(sw); save(); }));
  document.querySelectorAll('.hf-font-option').forEach(opt => opt.addEventListener('click', (e) => { e.stopPropagation(); applyFont(opt); save(); }));
  try {
    const prefs = JSON.parse(localStorage.getItem(STORE) || 'null');
    if (prefs) {
      const sw = [...document.querySelectorAll('.hf-swatch')].find(s => s.dataset.themeId === prefs.theme);
      if (sw && !sw.classList.contains('active')) applyTheme(sw);
      const fo = [...document.querySelectorAll('.hf-font-option')].find(o => o.dataset.family === prefs.font);
      if (fo && !fo.classList.contains('active')) applyFont(fo);
    }
  } catch (e) {}

  // ── Make lazy images print/export-safe ──
  // loading="lazy" images below the fold are blank in PDF/long-image exports.
  function eagerImages() { document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; }); }
  window.addEventListener('beforeprint', eagerImages);
  if (document.readyState === 'complete') setTimeout(eagerImages, 800);
  else window.addEventListener('load', () => setTimeout(eagerImages, 800));

  // ── Editable text ──
  const editableSelectors = [
    '.hero h1',
    '.hero-subtitle',
    '.hero-cover h1',
    '.hero-cover .hero-subtitle',
    '.section h2',
    '.section h3',
    '.section p',
    '.section li',
    '.pullquote p',
    '.pullquote-swiss .pq-content p',
    '.highlight-card p',
    '.highlight-swiss .hl-body p',
    '.def-card-body',
    '.def-card-swiss .dc-body',
    '.process-title',
    '.process-desc',
    '.aside-content p',
    '.summary-item-title',
    '.summary-item-desc',
    'blockquote p',
    'td',
  ];
  editableSelectors.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
      el.setAttribute('contenteditable', 'true');
      el.setAttribute('spellcheck', 'false');
    });
  });
})();
