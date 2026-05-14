#!/usr/bin/env python3
"""
refresh-index.py — Scan all artifacts and regenerate INDEX.html

Usage:
    python3 refresh-index.py              # run from artifacts/ root
    python3 scripts/refresh-index.py     # run from work/ root
"""

import json, os, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── Resolve root ────────────────────────────────────────────────────────────
script_dir   = Path(__file__).parent.resolve()
ARTIFACTS    = script_dir.parent          # always = artifacts/
INDEX_HTML   = ARTIFACTS / "INDEX.html"

# ── Discover all artifacts ───────────────────────────────────────────────────
def discover():
    arts = []
    for meta_path in sorted(ARTIFACTS.rglob("meta.json"), reverse=True):
        try:
            with open(meta_path) as f:
                m = json.load(f)
        except Exception:
            continue
        folder  = meta_path.parent
        rel     = folder.relative_to(ARTIFACTS)   # e.g. research/2026-05-14/AAPL-…
        has_png = (folder / "preview.png").exists()
        has_pdf = (folder / "export.pdf").exists()
        has_htm = (folder / "index.html").exists()
        arts.append({
            **m,
            "_rel":     str(rel).replace("\\", "/"),
            "_has_png": has_png,
            "_has_pdf": has_pdf,
            "_has_htm": has_htm,
        })
    return arts

# ── Card template ────────────────────────────────────────────────────────────
def card_html(a):
    rel      = a["_rel"]
    ticker   = a.get("ticker",   "—")
    period   = a.get("period",   "")
    title    = a.get("title",    a.get("id", rel))
    summary  = a.get("summary",  "")
    rating   = a.get("rating",   "")
    slides   = a.get("slides",   "")
    style    = a.get("style",    "")
    tags_raw = a.get("tags",     [])
    created  = a.get("created",  "")
    target   = a.get("target",   "")

    badge_txt = f"{slides} Slides" if isinstance(slides, int) and slides > 1 else (style or "Report")
    rating_html = f'<div class="card-rating">{rating}</div>' if rating else ""
    target_html = f' · Target ${target}' if target else ""
    tags_html   = "".join(f'<span class="tag">{t}</span>' for t in tags_raw)
    data_tags   = " ".join([style] + ([ticker] if ticker != "—" else []) + list(tags_raw))

    png_btn = f'<a class="btn" href="{rel}/preview.png" download>↓ PNG</a>' if a["_has_png"] else ""
    pdf_btn = f'<a class="btn" href="{rel}/export.pdf" download>↓ PDF</a>' if a["_has_pdf"] else ""
    open_btn= f'<a class="btn primary" href="{rel}/index.html" target="_blank">↗ Open</a>' if a["_has_htm"] else ""

    thumb_img = f'<img src="{rel}/preview.png" alt="{title}" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' if a["_has_png"] else ""
    ph_style  = f'<div class="ph-style">{style}</div>' if style else ""

    return f"""
    <div class="acard" data-tags="{data_tags}" data-date="{created}">
      <div class="thumb-wrap">
        {thumb_img}
        <div class="thumb-placeholder" style="display:{'none' if a['_has_png'] else 'flex'}">
          <div class="ph-ticker">{ticker}</div>
          {ph_style}
        </div>
        <div class="style-badge">{badge_txt}</div>
      </div>
      <div class="card-body">
        <div class="card-ticker-row">
          <div class="card-ticker">{ticker}</div>
          <div class="card-period">{period}</div>
          {rating_html}
        </div>
        <div class="card-title">{title}</div>
        <div class="card-summary">{summary}{target_html}</div>
        <div class="card-tags">{tags_html}</div>
        <div class="card-actions">
          {open_btn}{pdf_btn}{png_btn}
        </div>
      </div>
    </div>"""

# ── Build INDEX.html ─────────────────────────────────────────────────────────
def build_index(arts):
    # Group by date
    by_date = defaultdict(list)
    for a in arts:
        by_date[a.get("created", "unknown")].append(a)

    all_tags   = sorted({t for a in arts for t in a.get("tags", [])})
    tickers    = sorted({a.get("ticker","") for a in arts if a.get("ticker")})
    styles     = sorted({a.get("style","")  for a in arts if a.get("style")})
    total      = len(arts)
    updated    = datetime.now().strftime("%Y-%m-%d")

    # Filter buttons
    extra_filters = ""
    for t in tickers:
        extra_filters += f'<button class="filter-btn" data-filter="{t}">{t}</button>\n    '
    for s in ["editorial", "dataviz", "dashboard"]:
        if s in " ".join(styles + all_tags):
            extra_filters += f'<button class="filter-btn" data-filter="{s}">{s.title()}</button>\n    '

    # Cards grouped by date
    cards_html = ""
    for date in sorted(by_date.keys(), reverse=True):
        cards_html += f"""
    <div class="date-sep"><span>{date}</span></div>"""
        for a in by_date[date]:
            cards_html += card_html(a)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AlphaFlow Artifact Library</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#08131f;--bg2:#0b1a2b;--card:#0e2038;--card2:#112540;
    --bdr:rgba(201,168,76,.16);--bdr2:rgba(255,255,255,.05);
    --gold:#C9A84C;--green:#00D4AA;--text:#DCE8F8;--t2:#7A9BBF;--t3:#3E5E7A;
    --mono:'JetBrains Mono',monospace;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;
    background-image:linear-gradient(rgba(201,168,76,.02) 1px,transparent 1px),linear-gradient(90deg,rgba(201,168,76,.02) 1px,transparent 1px);
    background-size:40px 40px}}
  .hdr{{background:var(--bg2);border-bottom:1px solid var(--bdr);padding:0 40px;height:58px;
    display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
  .hdr-brand{{display:flex;align-items:center;gap:14px}}
  .brand-logo{{background:var(--gold);color:var(--bg);font-family:var(--mono);font-size:12px;font-weight:700;letter-spacing:.1em;padding:5px 10px}}
  .brand-name{{font-size:14px;font-weight:600;letter-spacing:.02em}}
  .brand-sub{{font-size:10px;color:var(--t2);letter-spacing:.1em;text-transform:uppercase;margin-top:1px}}
  .hdr-stats{{display:flex;gap:28px;align-items:center}}
  .stat{{display:flex;flex-direction:column;align-items:flex-end;gap:1px}}
  .stat-val{{font-family:var(--mono);font-size:16px;font-weight:600;color:var(--gold)}}
  .stat-lbl{{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}}
  .main{{padding:32px 40px 60px;max-width:1440px;margin:0 auto}}
  .filter-bar{{display:flex;gap:12px;align-items:center;margin-bottom:28px;flex-wrap:wrap}}
  .filter-lbl{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);margin-right:4px}}
  .filter-btn{{background:var(--card);border:1px solid var(--bdr2);color:var(--t2);font-size:11px;font-weight:500;
    padding:5px 14px;cursor:pointer;transition:all .2s;letter-spacing:.04em;font-family:'Inter',sans-serif}}
  .filter-btn:hover{{border-color:var(--bdr);color:var(--text)}}
  .filter-btn.active{{background:rgba(201,168,76,.1);border-color:var(--gold);color:var(--gold)}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:20px}}
  .acard{{background:var(--card);border:1px solid var(--bdr2);display:flex;flex-direction:column;transition:border-color .2s,background .2s;position:relative;overflow:hidden}}
  .acard:hover{{border-color:var(--bdr);background:var(--card2)}}
  .acard::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--gold);opacity:0;transition:opacity .2s}}
  .acard:hover::before{{opacity:1}}
  .thumb-wrap{{width:100%;padding-top:56.25%;position:relative;overflow:hidden;background:#0a1828;border-bottom:1px solid var(--bdr2)}}
  .thumb-wrap img{{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;object-position:top;transition:transform .4s ease}}
  .acard:hover .thumb-wrap img{{transform:scale(1.02)}}
  .thumb-placeholder{{position:absolute;top:0;left:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}}
  .ph-ticker{{font-family:var(--mono);font-size:28px;font-weight:700;color:var(--gold);opacity:.25}}
  .ph-style{{font-size:10px;letter-spacing:.1em;color:var(--t3);text-transform:uppercase}}
  .style-badge{{position:absolute;top:10px;right:10px;background:rgba(8,19,31,.75);border:1px solid var(--bdr);
    color:var(--gold);font-size:9px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:3px 8px;font-family:var(--mono);backdrop-filter:blur(4px)}}
  .card-body{{padding:18px 20px 16px;display:flex;flex-direction:column;flex:1;gap:10px}}
  .card-ticker-row{{display:flex;align-items:center;gap:10px}}
  .card-ticker{{background:var(--gold);color:var(--bg);font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.1em;padding:3px 9px}}
  .card-period{{font-size:11px;color:var(--t2);font-family:var(--mono)}}
  .card-rating{{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.1em;font-family:var(--mono);
    border:1px solid rgba(0,212,170,.35);background:rgba(0,212,170,.08);color:var(--green);padding:2px 9px}}
  .card-title{{font-size:14px;font-weight:600;color:var(--text);line-height:1.35}}
  .card-summary{{font-size:11px;color:var(--t2);line-height:1.55}}
  .card-tags{{display:flex;flex-wrap:wrap;gap:6px}}
  .tag{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;color:var(--t3);background:rgba(255,255,255,.04);border:1px solid var(--bdr2);padding:2px 8px}}
  .card-actions{{display:flex;gap:8px;margin-top:4px;padding-top:12px;border-top:1px solid var(--bdr2)}}
  .btn{{flex:1;text-decoration:none;text-align:center;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
    font-family:var(--mono);padding:7px 10px;transition:all .15s;cursor:pointer;border:1px solid var(--bdr2);color:var(--t2);background:transparent}}
  .btn:hover{{border-color:var(--gold);color:var(--gold);background:rgba(201,168,76,.05)}}
  .btn.primary{{border-color:var(--bdr);color:var(--text);background:rgba(255,255,255,.04)}}
  .btn.primary:hover{{border-color:var(--gold);color:var(--gold)}}
  .date-sep{{grid-column:1/-1;display:flex;align-items:center;gap:14px;margin-bottom:-4px;margin-top:8px}}
  .date-sep span{{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);font-family:var(--mono);white-space:nowrap}}
  .date-sep::before,.date-sep::after{{content:'';flex:1;height:1px;background:var(--bdr2)}}
  .how-to{{background:var(--card);border:1px solid var(--bdr2);padding:24px 28px;margin-top:32px}}
  .how-to h2{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--t2);margin-bottom:16px;font-weight:500}}
  .cmds{{display:flex;flex-direction:column;gap:8px}}
  .cmd-row{{display:flex;align-items:baseline;gap:12px}}
  .cmd-lbl{{font-size:9.5px;color:var(--t3);letter-spacing:.06em;width:110px;flex-shrink:0}}
  code{{font-family:var(--mono);font-size:11px;color:var(--t2);background:rgba(255,255,255,.04);border:1px solid var(--bdr2);padding:3px 10px;white-space:nowrap}}
  .ftr{{border-top:1px solid var(--bdr2);padding:14px 40px;display:flex;justify-content:space-between;align-items:center}}
  .ftr-l{{font-size:9.5px;color:var(--t3);letter-spacing:.07em}}
  .ftr-r{{font-size:9.5px;color:var(--t3);font-family:var(--mono)}}
  .empty{{grid-column:1/-1;text-align:center;padding:60px;color:var(--t3);font-family:var(--mono);font-size:13px}}
</style>
</head>
<body>

<header class="hdr">
  <div class="hdr-brand">
    <div class="brand-logo">AF</div>
    <div>
      <div class="brand-name">AlphaFlow Artifact Library</div>
      <div class="brand-sub">HTML · PNG · PDF · Private Design Corpus</div>
    </div>
  </div>
  <div class="hdr-stats">
    <div class="stat"><div class="stat-val" id="visible-count">{total}</div><div class="stat-lbl">Artifacts</div></div>
    <div class="stat"><div class="stat-val">{len(tickers)}</div><div class="stat-lbl">Tickers</div></div>
    <div class="stat"><div class="stat-val">{len(by_date)}</div><div class="stat-lbl">Dates</div></div>
  </div>
</header>

<div class="main">
  <div class="filter-bar">
    <span class="filter-lbl">Filter</span>
    <button class="filter-btn active" data-filter="all">All ({total})</button>
    {extra_filters}
  </div>

  <div class="grid" id="grid">
    {cards_html}
  </div>

  <div class="how-to">
    <h2>工作流 · 一条命令保存新成果</h2>
    <div class="cmds">
      <div class="cmd-row">
        <span class="cmd-lbl">保存 + 截图 + PDF</span>
        <code>./scripts/save.sh research NVDA-Q1-2026 /path/to/nvda.html --screenshot --pdf</code>
      </div>
      <div class="cmd-row">
        <span class="cmd-lbl">重建画廊</span>
        <code>python3 scripts/refresh-index.py</code>
      </div>
      <div class="cmd-row">
        <span class="cmd-lbl">本地预览</span>
        <code>./scripts/preview.sh 8000  →  http://localhost:8000</code>
      </div>
    </div>
  </div>
</div>

<footer class="ftr">
  <div class="ftr-l">ALPHAFLOW ARTIFACT LIBRARY · {total} ARTIFACTS · PRIVATE DESIGN CORPUS</div>
  <div class="ftr-r">AUTO-GENERATED {updated}</div>
</footer>

<script>
  document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      let n = 0;
      document.querySelectorAll('.acard').forEach(c => {{
        const show = f === 'all' || (c.dataset.tags||'').toLowerCase().includes(f.toLowerCase());
        c.style.display = show ? '' : 'none';
        if (show) n++;
      }});
      document.querySelectorAll('.date-sep').forEach(sep => {{
        const next = sep.nextElementSibling;
        sep.style.display = (next && next.style.display !== 'none') ? '' : 'none';
      }});
      document.getElementById('visible-count').textContent = n;
    }});
  }});
</script>
</body>
</html>"""
    return html

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    arts = discover()
    if not arts:
        print("⚠  No meta.json files found. Nothing to index.")
        sys.exit(0)

    html = build_index(arts)
    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"✓ INDEX.html rebuilt  ({len(arts)} artifacts)")
    for a in arts:
        print(f"   {a['_rel']:<52}  {'PNG' if a['_has_png'] else '   '} {'PDF' if a['_has_pdf'] else '   '}")

if __name__ == "__main__":
    main()
