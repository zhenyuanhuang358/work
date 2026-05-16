#!/usr/bin/env python3
"""
财报猎手 Earner — 一键财报分析 CLI

Usage:
    python earner.py AMD "Advanced Micro Devices" "Q1 FY2026" \\
        --transcript transcript.txt \\
        [--eps-est 1.26] [--rev-est 10000] [--price 434] \\
        [--model claude-haiku-4-5-20251001] [--output AMD_Report.html]

Output: {TICKER}_Copilot_Report.html
"""

import argparse
import asyncio
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_auth_token() -> str:
    token_file = os.environ.get(
        "CLAUDE_SESSION_INGRESS_TOKEN_FILE",
        "/home/claude/.claude/remote/.session_ingress_token",
    )
    try:
        return Path(token_file).read_text().strip()
    except FileNotFoundError:
        return ""


# ── Data helpers ──────────────────────────────────────────────────────────────

def _g(guidance, keyword: str) -> Optional[float]:
    """Extract a numeric guidance value by keyword match."""
    for item in guidance:
        if keyword.lower() in item.metric.lower():
            try:
                return float(item.value)
            except (ValueError, TypeError):
                pass
    return None


def _extract_gm(analysis) -> Optional[float]:
    """Best-effort gross margin extraction from text fields."""
    text = " ".join([
        analysis.tone_reasoning,
        " ".join(analysis.key_themes),
        " ".join(r.description for r in analysis.risk_factors),
    ])
    # Match patterns like "52.8%", "gross margin of 54%", "GM 46.9%"
    matches = re.findall(r'(?:gross\s*margin|gm)[^\d]*(\d{2,3}(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    if matches:
        return float(matches[0])
    # Any standalone "4X.X%" pattern near "margin"
    matches = re.findall(r'(\d{2}(?:\.\d+)?)\s*%', text)
    candidates = [float(m) for m in matches if 30 <= float(m) <= 80]
    return candidates[0] if candidates else None


def _extract_segments(analysis) -> list[dict]:
    """Try to extract segment revenues from themes and transcript context."""
    segments = []
    combined = " ".join(analysis.key_themes + [r.description for r in analysis.risk_factors])
    # Match patterns like "Data Center $5.8B +57%", "DC $5.8B", "gaming $563M"
    pattern = r'([A-Za-z\s&/]+)\s+\$?([\d.]+)\s*([BM])\b(?:[^%]*\+?([\d.]+)\s*%)?'
    for m in re.finditer(pattern, combined):
        name, val, unit, yoy = m.group(1).strip(), float(m.group(2)), m.group(3), m.group(4)
        if len(name) < 3 or len(name) > 30:
            continue
        rev_m = val * 1000 if unit == "B" else val
        if rev_m < 10:  # skip sub-$10M noise
            continue
        segments.append({"name": name, "rev_m": rev_m, "yoy": float(yoy) if yoy else None})
    # Deduplicate by name
    seen, unique = set(), []
    for s in segments:
        key = s["name"].lower()[:8]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:6]


def _compute_targets(eps_act: Optional[float], next_q_eps: Optional[float],
                     current_price: Optional[float]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Bull / Base / Bear price targets using P/E model."""
    if not eps_act:
        return None, None, None
    fwd_eps = (next_q_eps or eps_act * 1.05) * 4
    if current_price:
        current_pe = current_price / (eps_act * 4)
    else:
        current_pe = 30  # default tech/semi sector multiple
    base = round(fwd_eps * current_pe)
    bear = round(fwd_eps * current_pe * 0.82)
    bull = round(fwd_eps * current_pe * 1.18)
    return bear, base, bull


def _fmt_gap(gap: Optional[float], label: str = "") -> str:
    if gap is None:
        return "N/A"
    sign = "+" if gap > 0 else ""
    return f"{sign}{gap:.1f}%"


def _gap_cls(gap: Optional[float]) -> str:
    if gap is None:
        return ""
    if gap > 2:
        return "beat"
    if gap < -2:
        return "miss"
    return "inline"


# ── SVG charts ────────────────────────────────────────────────────────────────

def _svg_revenue_trend(rev_actual: Optional[float], rev_est: Optional[float],
                       next_q_rev: Optional[float], quarter: str) -> str:
    """Bar chart: estimate / actual / guide."""
    vals = [
        ("共识预期", rev_est, "#8b6c42"),
        ("实际营收", rev_actual, "#0a0a0b"),
        ("Q2 指引", next_q_rev, "#c9a84c"),
    ]
    vals = [(label, v, c) for label, v, c in vals if v is not None]
    if not vals:
        return '<p style="color:#6b6560;font-style:italic;font-size:13px">营收数据暂缺</p>'

    max_v = max(v for _, v, _ in vals)
    w, h, bar_w, gap = 680, 200, min(120, 680 // (len(vals) * 2)), 24
    total_w = len(vals) * (bar_w + gap) - gap
    x0 = (w - total_w) // 2
    chart_h = 140
    top = 20

    bars_svg = ""
    labels_svg = ""
    for i, (label, v, color) in enumerate(vals):
        bh = int(v / max_v * chart_h)
        x = x0 + i * (bar_w + gap)
        y = top + chart_h - bh
        fill = color
        bars_svg += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{fill}"/>'
        # Value label on top of bar
        display_v = f"${v/1000:.2f}B" if v >= 1000 else f"${v:.0f}M"
        bars_svg += f'<text x="{x + bar_w//2}" y="{y - 5}" text-anchor="middle" font-size="11" fill="{fill}">{display_v}</text>'
        labels_svg += f'<text x="{x + bar_w//2}" y="{top + chart_h + 18}" text-anchor="middle" font-size="11" fill="#6b6560">{label}</text>'

    return f'''<svg width="100%" viewBox="0 0 {w} {top+chart_h+40}" font-family="'IM Fell English',Georgia,serif">
  <line x1="{x0-8}" y1="{top+chart_h}" x2="{x0+total_w+8}" y2="{top+chart_h}" stroke="#8b6c42" stroke-width="1"/>
  {bars_svg}
  {labels_svg}
</svg>'''


def _svg_segment_bars(segments: list[dict]) -> str:
    """Horizontal bars for segment revenue breakdown."""
    if not segments:
        return '<p style="color:#6b6560;font-style:italic;font-size:13px">分部数据需人工填写</p>'

    max_rev = max(s["rev_m"] for s in segments)
    bar_h, gap, left, chart_w = 22, 14, 160, 400
    total_h = len(segments) * (bar_h + gap) - gap + 40

    rows = ""
    for i, seg in enumerate(segments):
        y = 20 + i * (bar_h + gap)
        bw = int(seg["rev_m"] / max_rev * chart_w)
        rev_str = f"${seg['rev_m']/1000:.1f}B" if seg["rev_m"] >= 1000 else f"${seg['rev_m']:.0f}M"
        yoy_str = f" +{seg['yoy']:.0f}% YoY" if seg.get("yoy") else ""
        rows += f'<text x="0" y="{y+16}" font-size="12" fill="#0a0a0b">{seg["name"]}</text>'
        rows += f'<rect x="{left}" y="{y}" width="{bw}" height="{bar_h}" fill="#0a0a0b"/>'
        rows += f'<text x="{left+bw+8}" y="{y+15}" font-size="11" fill="#8b6c42">{rev_str}{yoy_str}</text>'

    return f'''<svg width="100%" viewBox="0 0 680 {total_h}" font-family="'IM Fell English',Georgia,serif">
  {rows}
</svg>'''


def _svg_eps_comparison(eps_est: Optional[float], eps_act: Optional[float]) -> str:
    """Dual-bar EPS comparison."""
    vals = []
    if eps_est is not None:
        vals.append(("共识预期", eps_est, "#8b6c42"))
    if eps_act is not None:
        color = "#2a5c3f" if (eps_act or 0) >= (eps_est or 0) else "#8b2e2e"
        vals.append(("实际 EPS", eps_act, color))
    if not vals:
        return '<p style="color:#6b6560;font-style:italic;font-size:13px">EPS 数据暂缺</p>'

    max_v = max(abs(v) for _, v, _ in vals) * 1.2 or 1
    w, h, bar_w, gap = 300, 180, 80, 30
    total_w = len(vals) * (bar_w + gap) - gap
    x0 = (w - total_w) // 2
    chart_h = 120
    top = 20

    bars = ""
    for i, (label, v, color) in enumerate(vals):
        bh = int(abs(v) / max_v * chart_h)
        x = x0 + i * (bar_w + gap)
        y = top + chart_h - bh
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}"/>'
        bars += f'<text x="{x+bar_w//2}" y="{y-5}" text-anchor="middle" font-size="12" fill="{color}">${v:.2f}</text>'
        bars += f'<text x="{x+bar_w//2}" y="{top+chart_h+18}" text-anchor="middle" font-size="11" fill="#6b6560">{label}</text>'

    return f'''<svg width="100%" viewBox="0 0 {w} {top+chart_h+36}" font-family="'IM Fell English',Georgia,serif">
  <line x1="{x0-8}" y1="{top+chart_h}" x2="{x0+total_w+8}" y2="{top+chart_h}" stroke="#8b6c42" stroke-width="1"/>
  {bars}
</svg>'''


def _svg_gm_trend(gm_cur: Optional[float], gm_guide: Optional[float]) -> str:
    """Gross margin line chart."""
    if gm_cur is None:
        return '<p style="color:#6b6560;font-style:italic;font-size:13px">毛利率数据需从财报提取</p>'

    points = [("当季", gm_cur, False)]
    if gm_guide:
        points.append(("Q2E", gm_guide, True))

    w, h = 300, 180
    all_v = [p[1] for p in points]
    lo, hi = min(all_v) - 3, max(all_v) + 3
    span = hi - lo or 1

    def y_pos(v):
        return int(140 - (v - lo) / span * 100)

    step = w // (len(points) + 1)
    pts = [(step * (i + 1), y_pos(v)) for i, (_, v, _) in enumerate(points)]

    path = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
    circles = ""
    labels = ""
    for i, ((label, v, dashed), (x, y)) in enumerate(zip(points, pts)):
        fill = "#0a0a0b" if not dashed else "none"
        stroke = "#0a0a0b" if not dashed else "#8b6c42"
        dash = ' stroke-dasharray="4,3"' if dashed else ""
        circles += f'<circle cx="{x}" cy="{y}" r="5" fill="{fill}" stroke="{stroke}"{dash}/>'
        labels += f'<text x="{x}" y="{y-10}" text-anchor="middle" font-size="11" fill="{stroke}">{v:.1f}%</text>'
        labels += f'<text x="{x}" y="165" text-anchor="middle" font-size="10" fill="#6b6560">{label}</text>'

    return f'''<svg width="100%" viewBox="0 0 {w} 180" font-family="'IM Fell English',Georgia,serif">
  <path d="{path}" fill="none" stroke="#0a0a0b" stroke-width="2"/>
  {circles}
  {labels}
</svg>'''


def _svg_price_range(bear: int, base: int, bull: int,
                     current: Optional[float]) -> str:
    """Horizontal price range bar with scenario markers."""
    w, h = 680, 100
    lo, hi = bear * 0.9, bull * 1.1
    span = hi - lo

    def xp(v):
        return int((v - lo) / span * (w - 80) + 40)

    xbear, xbase, xbull = xp(bear), xp(base), xp(bull)

    svg = f'''<svg width="100%" viewBox="0 0 {w} {h}" font-family="'IM Fell English',Georgia,serif">
  <!-- range bar -->
  <rect x="{xbear}" y="44" width="{xbull - xbear}" height="12" fill="#e8e4dc" rx="2"/>
  <rect x="{xbase - 2}" y="40" width="4" height="20" fill="#0a0a0b"/>
  <!-- bear marker -->
  <circle cx="{xbear}" cy="50" r="6" fill="#8b2e2e"/>
  <text x="{xbear}" y="30" text-anchor="middle" font-size="11" fill="#8b2e2e">${bear}</text>
  <text x="{xbear}" y="80" text-anchor="middle" font-size="10" fill="#6b6560">熊市</text>
  <!-- base marker -->
  <text x="{xbase}" y="30" text-anchor="middle" font-size="11" fill="#0a0a0b">${base}</text>
  <text x="{xbase}" y="80" text-anchor="middle" font-size="10" fill="#6b6560">基准</text>
  <!-- bull marker -->
  <circle cx="{xbull}" cy="50" r="6" fill="#2a5c3f"/>
  <text x="{xbull}" y="30" text-anchor="middle" font-size="11" fill="#2a5c3f">${bull}</text>
  <text x="{xbull}" y="80" text-anchor="middle" font-size="10" fill="#6b6560">牛市</text>'''

    if current:
        xc = xp(current)
        svg += f'''
  <!-- current price arrow -->
  <polygon points="{xc},{42} {xc-6},{32} {xc+6},{32}" fill="#c9a84c"/>
  <text x="{xc}" y="20" text-anchor="middle" font-size="10" fill="#c9a84c">现价 ${current:.0f}</text>'''

    svg += "\n</svg>"
    return svg


# ── Full HTML report ──────────────────────────────────────────────────────────

def generate_html(analysis, consensus, current_price: Optional[float], elapsed: float) -> str:
    from earnings_copilot.models import ManagementTone, RiskSeverity

    # ── Pull data ──────────────────────────────────────────────────────────────
    next_q_rev  = _g(analysis.guidance, "Next Q Revenue")
    next_q_eps  = _g(analysis.guidance, "Next Q EPS")
    fy_rev      = _g(analysis.guidance, "FY Revenue")

    eps_est = consensus.eps_estimate if consensus else None
    rev_est = consensus.revenue_estimate if consensus else None

    gm_cur   = _extract_gm(analysis)
    gm_guide = None  # could extend to parse Q2 GM from guidance note

    segments = _extract_segments(analysis)
    bear, base, bull = _compute_targets(analysis.eps_actual, next_q_eps, current_price)

    tone_pct = analysis.tone_score * 10
    today = date.today().isoformat()

    # ── Tone pill class ────────────────────────────────────────────────────────
    tone_map = {
        ManagementTone.BULLISH: ("BUY", "verdict-pill"),
        ManagementTone.NEUTRAL: ("HOLD", "verdict-pill cautious"),
        ManagementTone.CAUTIOUS: ("HOLD", "verdict-pill cautious"),
        ManagementTone.DEFENSIVE: ("REDUCE", "verdict-pill bearish"),
    }
    rating_label, rating_cls = tone_map.get(analysis.management_tone, ("HOLD", "verdict-pill cautious"))

    eps_gap_str = _fmt_gap(analysis.eps_gap_pct)
    rev_gap_str = _fmt_gap(analysis.revenue_gap_pct)
    eps_cls     = _gap_cls(analysis.eps_gap_pct)
    rev_cls     = _gap_cls(analysis.revenue_gap_pct)

    eps_actual_str = f"${analysis.eps_actual:.2f}" if analysis.eps_actual else "N/A"
    rev_actual_str = (
        f"${analysis.revenue_actual/1000:.2f}B"
        if analysis.revenue_actual and analysis.revenue_actual >= 1000
        else (f"${analysis.revenue_actual:.0f}M" if analysis.revenue_actual else "N/A")
    )
    next_q_rev_str = (
        f"${next_q_rev/1000:.1f}B" if next_q_rev and next_q_rev >= 1000
        else (f"${next_q_rev:.0f}M" if next_q_rev else "N/A")
    )
    gm_str = f"{gm_cur:.1f}%" if gm_cur else "见正文"

    # ── Charts ─────────────────────────────────────────────────────────────────
    svg_rev = _svg_revenue_trend(analysis.revenue_actual, rev_est, next_q_rev, analysis.quarter)
    svg_seg = _svg_segment_bars(segments)
    svg_eps = _svg_eps_comparison(eps_est, analysis.eps_actual)
    svg_gm  = _svg_gm_trend(gm_cur, gm_guide)
    svg_rng = _svg_price_range(bear, base, bull, current_price) if bear else ""

    # ── Themes chips ───────────────────────────────────────────────────────────
    chips_html = "".join(
        f'<span class="chip">{t}</span>'
        for t in analysis.key_themes[:8]
    )

    # ── Risk table ─────────────────────────────────────────────────────────────
    sev_map = {
        RiskSeverity.HIGH:   ("高", "dot-h"),
        RiskSeverity.MEDIUM: ("中", "dot-m"),
        RiskSeverity.LOW:    ("低", "dot-l"),
    }
    risk_rows = ""
    for r in analysis.risk_factors:
        sev_label, sev_cls = sev_map.get(r.severity, ("中", "dot-m"))
        badge = '<span class="new-badge">NEW</span>' if r.is_new else ""
        risk_rows += f"""
      <tr>
        <td><span class="{sev_cls}">●</span> {sev_label}{badge}</td>
        <td><strong>{r.category}</strong></td>
        <td>{r.description}</td>
      </tr>"""

    # ── Q&A section ────────────────────────────────────────────────────────────
    qa_html = ""
    for q in analysis.analyst_questions[:5]:
        evasion = "; ".join(q.evasion_signals[:2]) if q.evasion_signals else "管理层正面回应"
        directness_bar = "▓" * q.management_directness + "░" * (5 - q.management_directness)
        qa_html += f"""
    <div class="qa-item">
      <div class="qa-firm">{q.analyst_firm} &nbsp;·&nbsp; 回应直接度 {directness_bar} {q.management_directness}/5</div>
      <div class="qa-q">{q.question_summary}</div>
      <div class="qa-signal">{evasion}</div>
    </div>"""

    tension_html = ""
    for t in analysis.tension_areas[:3]:
        tension_html += f'<div class="tension-item">⟶ {t}</div>'

    # ── Target price section ───────────────────────────────────────────────────
    if bear and base and bull:
        base_updown = round((base / current_price - 1) * 100, 1) if current_price else None
        bear_updown = round((bear / current_price - 1) * 100, 1) if current_price else None
        bull_updown = round((bull / current_price - 1) * 100, 1) if current_price else None

        def updown_str(v):
            if v is None:
                return ""
            return f'<br><span style="font-size:11px;color:{"#2a5c3f" if v>=0 else "#8b2e2e"}">{("+" if v>=0 else "")}{v:.1f}% vs 现价</span>'

        fwd_eps_val = (next_q_eps or (analysis.eps_actual * 1.05 if analysis.eps_actual else 0)) * 4

        target_section = f"""
  <div class="section">
    <div class="section-label">
      <span class="section-zh">目标价 · 三情景</span>
      <span class="section-en">Price Target — 12-Month Scenarios</span>
    </div>
    {svg_rng}
    <div class="scenario-cards">
      <div class="scenario-card bear">
        <div class="sc-label">熊市 <em>Bear</em></div>
        <div class="sc-price">${bear}{updown_str(bear_updown)}</div>
        <div class="sc-logic">增长放缓，竞争加剧，毛利率承压</div>
        <div class="sc-meta">Forward EPS × 低估值倍数</div>
      </div>
      <div class="scenario-card base">
        <div class="sc-label">基准 <em>Base</em></div>
        <div class="sc-price">${base}{updown_str(base_updown)}</div>
        <div class="sc-logic">当前增长趋势延续，毛利率稳步扩张</div>
        <div class="sc-meta">Forward EPS × 当前 P/E</div>
      </div>
      <div class="scenario-card bull">
        <div class="sc-label">牛市 <em>Bull</em></div>
        <div class="sc-price">${bull}{updown_str(bull_updown)}</div>
        <div class="sc-logic">超预期增长，新品催化，估值重评</div>
        <div class="sc-meta">Forward EPS × 高估值倍数</div>
      </div>
    </div>
    <table class="assumption-table">
      <tr>
        <th>核心假设 <em>Key Assumption</em></th>
        <th>熊市 <em>Bear</em></th>
        <th>基准 <em>Base</em></th>
        <th>牛市 <em>Bull</em></th>
      </tr>
      <tr><td>Forward EPS (年化)</td>
        <td>${fwd_eps_val*0.9:.2f}</td><td>${fwd_eps_val:.2f}</td><td>${fwd_eps_val*1.1:.2f}</td></tr>
      <tr><td>估值 P/E 倍数</td>
        <td>低</td><td>维持现值</td><td>重评上行</td></tr>
      <tr><td>营收增长路径</td>
        <td>低于指引</td><td>符合指引</td><td>超越指引</td></tr>
      <tr><td>毛利率趋势</td>
        <td>承压</td><td>稳步扩张</td><td>超预期扩张</td></tr>
    </table>
  </div>"""
    else:
        target_section = """
  <div class="section">
    <div class="section-label">
      <span class="section-zh">目标价 · 三情景</span>
      <span class="section-en">Price Target — 12-Month Scenarios</span>
    </div>
    <p style="color:#6b6560;font-style:italic;font-size:14px">请通过 --price 参数提供当前股价以生成目标价模型</p>
  </div>"""

    # ── Full HTML ──────────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{analysis.ticker} {analysis.quarter} — 财报猎手 Earner</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&display=swap');
  :root {{
    --ink:#0a0a0b; --paper:#f1efea; --copper:#8b6c42; --gold:#c9a84c;
    --muted:#6b6560; --light:#e8e4dc; --red:#8b2e2e; --green:#2a5c3f; --amber:#c47a1e;
  }}
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{background:var(--paper);color:var(--ink);font-family:'IM Fell English',Georgia,serif;min-height:100vh}}
  .page{{max-width:860px;margin:0 auto;padding:60px 48px 100px}}

  /* pub bar */
  .pub-bar{{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);
    border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:28px;
    display:flex;justify-content:space-between;align-items:center}}
  .pub-name{{font-weight:normal}}

  /* headline */
  .headline{{font-size:clamp(26px,4vw,44px);line-height:1.1;margin:0 0 12px}}
  .subhead{{font-size:15px;color:var(--muted);font-style:italic;line-height:1.6;margin-bottom:16px}}
  .tag-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:32px}}
  .tag{{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
    padding:4px 12px;border:1px solid var(--copper);color:var(--copper)}}
  .verdict-pill{{background:var(--green);border-color:var(--green);color:#fff}}
  .verdict-pill.cautious{{background:var(--amber);border-color:var(--amber)}}
  .verdict-pill.bearish{{background:var(--red);border-color:var(--red)}}

  /* stat bar */
  .stat-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;
    background:var(--copper);border:1px solid var(--copper);margin:0 0 36px}}
  .stat-cell{{background:var(--paper);padding:16px;text-align:center}}
  .stat-val{{font-size:clamp(20px,3vw,30px);line-height:1}}
  .stat-val.beat{{color:var(--green)}} .stat-val.miss{{color:var(--red)}} .stat-val.inline{{color:var(--amber)}}
  .stat-label{{font-size:10px;color:var(--muted);margin-top:6px;font-style:italic;line-height:1.4}}

  /* sections */
  .section{{margin:36px 0}}
  .section-label{{margin-bottom:14px;border-bottom:1px solid var(--gold);padding-bottom:6px}}
  .section-zh{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--gold)}}
  .section-en{{font-size:11px;font-style:italic;color:var(--muted);margin-left:12px}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:32px}}
  @media(max-width:600px){{.two-col{{grid-template-columns:1fr}}}}

  /* body text */
  .body-text{{font-size:15px;line-height:1.8;color:var(--ink)}}
  .body-text p{{margin-bottom:14px}}
  .label-zh{{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--copper);margin-right:6px}}
  .label-en{{font-size:10px;font-style:italic;color:var(--muted);margin-right:8px}}

  /* tone */
  .tone-row{{display:flex;align-items:center;gap:14px;margin:10px 0}}
  .tone-label{{font-size:12px;color:var(--muted);width:72px;flex-shrink:0;font-style:italic}}
  .tone-track{{flex:1;height:5px;background:var(--light);border-radius:3px;overflow:hidden}}
  .tone-fill{{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--red),var(--amber),var(--green))}}
  .tone-score{{font-size:14px;color:var(--ink);width:36px;text-align:right}}

  /* verdict */
  .verdict-box{{background:var(--ink);padding:32px 36px;margin:36px 0}}
  .verdict-eyebrow{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);margin-bottom:10px}}
  .verdict-text{{font-size:clamp(15px,2vw,20px);color:var(--paper);line-height:1.55;font-style:italic}}
  .verdict-en{{font-size:12px;color:rgba(241,239,234,.45);margin-top:8px;font-style:italic}}

  /* risk table */
  .risk-table{{width:100%;border-collapse:collapse;margin-top:6px}}
  .risk-table th{{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
    padding:8px 10px;text-align:left;border-bottom:1px solid var(--copper);font-weight:normal}}
  .risk-table td{{padding:11px 10px;border-bottom:1px solid rgba(139,108,66,.1);
    font-size:14px;vertical-align:top}}
  .dot-h{{color:var(--red)}} .dot-m{{color:var(--amber)}} .dot-l{{color:var(--green)}}
  .new-badge{{font-size:9px;letter-spacing:.08em;text-transform:uppercase;
    background:var(--red);color:#fff;padding:1px 5px;margin-left:5px;vertical-align:middle}}

  /* chips */
  .chips{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
  .chip{{padding:5px 14px;border:1px solid var(--copper);font-size:13px;color:var(--copper);font-style:italic}}

  /* q&a */
  .qa-item{{margin-bottom:18px;padding:14px 16px;background:var(--light);border-left:3px solid var(--gold)}}
  .qa-firm{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-bottom:6px;font-family:monospace}}
  .qa-q{{font-size:14px;color:var(--ink);margin-bottom:6px;line-height:1.5}}
  .qa-signal{{font-size:12px;color:var(--red);font-style:italic}}
  .tension-item{{font-size:14px;color:var(--ink);padding:8px 0;border-bottom:1px solid rgba(139,108,66,.1);font-style:italic}}

  /* scenario cards */
  .scenario-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;
    background:var(--copper);border:1px solid var(--copper);margin:20px 0}}
  .scenario-card{{background:var(--paper);padding:20px 16px}}
  .scenario-card.bear .sc-price{{color:var(--red)}}
  .scenario-card.bull .sc-price{{color:var(--green)}}
  .sc-label{{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}}
  .sc-label em{{font-style:normal;margin-left:6px;color:var(--muted)}}
  .sc-price{{font-size:clamp(22px,3vw,32px);margin-bottom:8px;line-height:1}}
  .sc-logic{{font-size:13px;color:var(--ink);line-height:1.5;margin-bottom:8px;font-style:italic}}
  .sc-meta{{font-size:11px;color:var(--muted)}}

  /* assumption table */
  .assumption-table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}
  .assumption-table th{{padding:8px 12px;text-align:center;border-bottom:2px solid var(--copper);
    font-weight:normal;color:var(--muted);font-size:10px;letter-spacing:.1em;text-transform:uppercase}}
  .assumption-table th:first-child{{text-align:left}}
  .assumption-table td{{padding:10px 12px;border-bottom:1px solid rgba(139,108,66,.1);color:var(--ink);text-align:center}}
  .assumption-table td:first-child{{text-align:left;font-style:italic}}
  .assumption-table em{{font-style:normal;color:var(--muted);font-size:11px;margin-left:6px}}

  /* footer */
  .footer{{margin-top:60px;padding-top:18px;border-top:1px solid var(--copper);
    font-size:11px;color:var(--muted);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
</style>
</head>
<body>
<div class="page">

  <!-- 1. Pub Bar -->
  <div class="pub-bar">
    <span class="pub-name">财报猎手 Earner &nbsp;·&nbsp; Earnings Intelligence</span>
    <span>{today} &nbsp;·&nbsp; AI Generated &nbsp;·&nbsp; Not Investment Advice</span>
  </div>

  <!-- 2. Headline + Tag Row -->
  <h1 class="headline">{analysis.ticker} {analysis.quarter}<br>{analysis.headline}</h1>
  <p class="subhead">{analysis.one_line_verdict}</p>
  <div class="tag-row">
    <span class="tag">{analysis.ticker} · 美股</span>
    <span class="tag">{analysis.quarter}</span>
    <span class="tag {rating_cls}">{rating_label}</span>
    <span class="tag">语气评分 {analysis.tone_score}/10</span>
  </div>

  <!-- 3. Stat Bar -->
  <div class="stat-bar">
    <div class="stat-cell">
      <div class="stat-val {eps_cls}">{eps_gap_str}</div>
      <div class="stat-label">EPS 超/低预期<br>{eps_actual_str} vs {f"${eps_est:.2f}E" if eps_est else "共识预期"}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val {rev_cls}">{rev_gap_str}</div>
      <div class="stat-label">营收超/低预期<br>{rev_actual_str} 实际</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val">{next_q_rev_str}</div>
      <div class="stat-label">下季营收指引<br>Next Quarter Guide</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val">{gm_str}</div>
      <div class="stat-label">当季毛利率<br>Non-GAAP GM</div>
    </div>
  </div>

  <!-- 4. Revenue Trend -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">季度营收</span>
      <span class="section-en">Revenue — Estimate · Actual · Guidance</span>
    </div>
    {svg_rev}
  </div>

  <!-- 5. Segment Breakdown -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">分部营收</span>
      <span class="section-en">Segment Revenue Breakdown</span>
    </div>
    {svg_seg}
  </div>

  <!-- 6. EPS + Gross Margin (two-col) -->
  <div class="section">
    <div class="two-col">
      <div>
        <div class="section-label">
          <span class="section-zh">EPS 对比</span>
          <span class="section-en">Consensus vs Actual</span>
        </div>
        {svg_eps}
      </div>
      <div>
        <div class="section-label">
          <span class="section-zh">毛利率</span>
          <span class="section-en">Gross Margin Trend</span>
        </div>
        {svg_gm}
      </div>
    </div>
  </div>

  <!-- 7. Core Analysis -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">核心分析</span>
      <span class="section-en">Core Analysis</span>
    </div>
    <div class="body-text">
      <p>
        <span class="label-zh">业绩总结</span><span class="label-en">Results Summary</span>
        {analysis.ticker} {analysis.quarter} {analysis.headline}
        EPS {eps_actual_str}（共识预期 {f"${eps_est:.2f}" if eps_est else "N/A"}，超预期 {eps_gap_str}），
        营收 {rev_actual_str}（{rev_gap_str}）。
      </p>
      <p>
        <span class="label-zh">前瞻指引</span><span class="label-en">Forward Guidance</span>
        {"下季营收指引 " + next_q_rev_str + "。" if next_q_rev else ""}
        {"全年营收指引 $" + f"{fy_rev/1000:.1f}B。" if fy_rev and fy_rev >= 1000 else ""}
        {"; ".join(g.metric + " " + (g.value or "") for g in analysis.guidance) if analysis.guidance else "详见财报。"}
      </p>
      <p>
        <span class="label-zh">管理层基调</span><span class="label-en">Management Tone</span>
        {analysis.tone_reasoning}
      </p>
      <p>
        <span class="label-zh">核心主题</span><span class="label-en">Key Themes</span>
        {" · ".join(analysis.key_themes[:5]) if analysis.key_themes else "见下方主题列表。"}
      </p>
    </div>
  </div>

  <!-- 8. Target Price Scenarios -->
  {target_section}

  <!-- 9. Verdict Box -->
  <div class="verdict-box">
    <div class="verdict-eyebrow">财报猎手 Earner &nbsp;·&nbsp; Verdict</div>
    <p class="verdict-text">{analysis.one_line_verdict}</p>
    <p class="verdict-en">{analysis.ticker} {analysis.quarter} &nbsp;·&nbsp; Tone {analysis.management_tone.value} {analysis.tone_score}/10</p>
  </div>

  <!-- 10. Management Tone -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">管理层语气</span>
      <span class="section-en">Management Tone Analysis</span>
    </div>
    <div class="tone-row">
      <span class="tone-label">信心指数</span>
      <div class="tone-track"><div class="tone-fill" style="width:{tone_pct}%"></div></div>
      <span class="tone-score">{analysis.tone_score}/10</span>
    </div>
    <p class="body-text" style="margin-top:12px;font-size:14px;color:var(--muted)">{analysis.tone_reasoning}</p>
  </div>

  <!-- 11. Key Themes -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">核心主题</span>
      <span class="section-en">Key Themes</span>
    </div>
    <div class="chips">{chips_html}</div>
  </div>

  <!-- 12. Risk Matrix -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">风险矩阵</span>
      <span class="section-en">Risk Matrix</span>
    </div>
    <table class="risk-table">
      <tr>
        <th>严重性 <em style="font-style:italic;font-size:9px">Severity</em></th>
        <th>类别 <em style="font-style:italic;font-size:9px">Category</em></th>
        <th>描述 <em style="font-style:italic;font-size:9px">Description</em></th>
      </tr>
      {risk_rows}
    </table>
  </div>

  <!-- 13. Analyst Q&A -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">分析师追问 · 张力区域</span>
      <span class="section-en">Analyst Q&amp;A — Tension Analysis</span>
    </div>
    {qa_html}
    {('<div style="margin-top:18px"><div class="section-label"><span class="section-zh">主要张力</span><span class="section-en">Tension Areas</span></div>' + tension_html + '</div>') if tension_html else ''}
  </div>

  <!-- 14. Footer -->
  <div class="footer">
    <span>财报猎手 Earner &nbsp;·&nbsp; 由 Claude AI 生成 &nbsp;·&nbsp; 仅供参考，不构成投资建议</span>
    <span>分析耗时 {elapsed:.1f}s &nbsp;·&nbsp; {today}</span>
  </div>

</div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="财报猎手 Earner — 一键财报分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python earner.py AMD "Advanced Micro Devices" "Q1 FY2026" \\
      --transcript amd_q1.txt --eps-est 1.26 --rev-est 10000 --price 434
        """
    )
    parser.add_argument("ticker",   help="股票代码，如 AMD")
    parser.add_argument("company",  help="公司全名，如 'Advanced Micro Devices'")
    parser.add_argument("quarter",  help="季度，如 'Q1 FY2026'")
    parser.add_argument("--transcript", required=True, metavar="FILE",
                        help="财报电话会议记录 .txt 文件路径")
    parser.add_argument("--eps-est",   type=float, metavar="N", help="共识 EPS 预期")
    parser.add_argument("--rev-est",   type=float, metavar="N", help="共识营收预期（百万美元）")
    parser.add_argument("--price",     type=float, metavar="N", help="当前股价（用于目标价计算）")
    parser.add_argument("--model",     default="claude-haiku-4-5-20251001",
                        help="分析模型（默认: claude-haiku-4-5-20251001）")
    parser.add_argument("--output",    metavar="FILE",
                        help="输出 HTML 文件路径（默认: {TICKER}_Copilot_Report.html）")
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"ERROR: transcript file not found: {args.transcript}")
        sys.exit(1)
    transcript = transcript_path.read_text(encoding="utf-8")

    auth_token = get_auth_token()
    if not auth_token and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: no auth token. Set ANTHROPIC_API_KEY or run inside Claude Code.")
        sys.exit(1)

    # Override model for this run
    import earnings_copilot.analysis.analyzer as analyzer_module
    analyzer_module.MODEL = args.model

    from earnings_copilot.analysis.prompts import PromptContext
    from earnings_copilot.analysis.analyzer import analyze_earnings_call
    from earnings_copilot.models import ExpectationData

    consensus = ExpectationData(
        ticker=args.ticker.upper(),
        eps_estimate=args.eps_est,
        revenue_estimate=args.rev_est,
        source="provided" if (args.eps_est or args.rev_est) else "none",
    )

    ctx = PromptContext(
        ticker=args.ticker.upper(),
        company_name=args.company,
        quarter=args.quarter,
        transcript=transcript,
        eps_estimate=args.eps_est,
        revenue_estimate_millions=args.rev_est,
    )

    print(f"\n{'='*60}")
    print(f"财报猎手 Earner — {args.ticker.upper()} {args.quarter}")
    print(f"Model: {args.model}")
    print("="*60)

    t0 = time.time()
    loop = asyncio.get_event_loop()
    analysis = await loop.run_in_executor(
        None,
        lambda: analyze_earnings_call(ctx, auth_token=auth_token or None,
                                      api_key=os.environ.get("ANTHROPIC_API_KEY")),
    )
    elapsed = time.time() - t0

    print(f"\n✓ 分析完成，耗时 {elapsed:.1f}s")
    print(f"  Tone: {analysis.management_tone.value} ({analysis.tone_score}/10)")
    print(f"  EPS: {analysis.eps_actual} (gap: {analysis.eps_gap_pct}%)")
    print(f"  Revenue: {analysis.revenue_actual}M (gap: {analysis.revenue_gap_pct}%)")
    print(f"  Themes: {', '.join(analysis.key_themes[:3])}")

    html = generate_html(analysis, consensus, args.price, elapsed)

    out_path = args.output or f"{args.ticker.upper()}_Copilot_Report.html"
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"\n✓ 报告已生成: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
