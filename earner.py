#!/usr/bin/env python3
"""
财报猎手 Earner — 一键财报分析 CLI

Usage:
    python earner.py AMD "Advanced Micro Devices" "Q1 FY2026" \\
        --transcript transcript.txt \\
        [--eps-est 1.26] [--rev-est 10000] [--price 434] \\
        [--model claude-haiku-4-5-20251001] [--output AMD_Report.html]

Output: {TICKER}_Copilot_Report.html
All data (segments, gross margin, YoY growth) extracted from transcript by LLM.
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


# ── Guidance helper ───────────────────────────────────────────────────────────

def _g(guidance, keyword: str) -> Optional[float]:
    for item in guidance:
        if keyword.lower() in item.metric.lower():
            try:
                return float(item.value)
            except (ValueError, TypeError):
                pass
    return None


# ── Quarter arithmetic ────────────────────────────────────────────────────────

def _parse_qtr(quarter_str: str) -> tuple[Optional[int], Optional[int]]:
    m = re.match(r'Q(\d)\s+FY(\d{4})', quarter_str, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _qtr_back(q: int, fy: int, n: int) -> str:
    """Label for the quarter n steps before Q{q} FY{fy}."""
    qb = q - n
    fyb = fy
    while qb <= 0:
        qb += 4
        fyb -= 1
    return f"Q{qb}'{str(fyb)[2:]}"


def _qtr_fwd(q: int, fy: int, n: int = 1) -> str:
    qf = q + n
    fyf = fy
    while qf > 4:
        qf -= 4
        fyf += 1
    return f"Q{qf}'{str(fyf)[2:]}E"


def _build_rev_bars(rev_actual: float, rev_guide: Optional[float],
                    yoy_pct: Optional[float], quarter_str: str) -> list[dict]:
    """Synthesize 8 quarterly revenue bars (7 estimated + 1 actual) + optional guide."""
    yoy = (yoy_pct or 20) / 100
    qoq = (1 + yoy) ** 0.25 - 1
    q, fy = _parse_qtr(quarter_str)

    bars = []
    for i in range(7, 0, -1):
        est = rev_actual / ((1 + qoq) ** i)
        label = _qtr_back(q, fy, i) if q else f"Q-{i}"
        bars.append({"label": label, "value": est, "type": "est"})

    cur_label = f"Q{q}'{str(fy)[2:]}" if q else "当季"
    bars.append({"label": cur_label, "value": rev_actual, "type": "actual"})

    if rev_guide:
        guide_label = _qtr_fwd(q, fy) if q else "Q2E"
        bars.append({"label": guide_label, "value": rev_guide, "type": "guide"})

    return bars


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _svg_revenue_trend(bars: list[dict]) -> str:
    """8-quarter revenue trend bar chart (7 est. + 1 actual + optional guide)."""
    if not bars:
        return '<p style="color:#6b6560;font-style:italic;font-size:13px">营收数据暂缺</p>'

    W, H = 720, 230
    bar_w = 62
    gap = max(4, (W - 60 - len(bars) * bar_w) // (len(bars) - 1)) if len(bars) > 1 else 0
    total_w = len(bars) * bar_w + max(0, len(bars) - 1) * gap
    x0 = (W - total_w) // 2
    chart_h = 145
    top = 14
    base_y = top + chart_h

    max_v = max(b["value"] for b in bars) * 1.08

    rects, labels, vals = "", "", ""
    for i, b in enumerate(bars):
        x = x0 + i * (bar_w + gap)
        bh = max(4, int(b["value"] / max_v * chart_h))
        y = base_y - bh

        if b["type"] == "actual":
            fill, stroke, sw = "#0a0a0b", "none", 0
        elif b["type"] == "guide":
            fill, stroke, sw = "none", "#8b6c42", 1.5
        else:
            fill, stroke, sw = "#d8d3ca", "none", 0

        rect_attrs = f'x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{fill}"'
        if stroke != "none":
            rect_attrs += f' stroke="{stroke}" stroke-width="{sw}" stroke-dasharray="4,3"'
        rects += f"<rect {rect_attrs}/>"

        rev_b = b["value"] / 1000
        v_str = f"${rev_b:.1f}B" if b["value"] >= 500 else f"${b['value']:.0f}M"
        v_color = "#0a0a0b" if b["type"] == "actual" else ("#8b6c42" if b["type"] == "guide" else "#9b9590")
        vals += f'<text x="{x + bar_w//2}" y="{y - 4}" text-anchor="middle" font-size="9.5" fill="{v_color}">{v_str}</text>'

        lbl_color = "#0a0a0b" if b["type"] == "actual" else ("#8b6c42" if b["type"] == "guide" else "#9b9590")
        lbl_weight = "bold" if b["type"] in ("actual", "guide") else "normal"
        labels += f'<text x="{x + bar_w//2}" y="{base_y + 16}" text-anchor="middle" font-size="9.5" fill="{lbl_color}" font-weight="{lbl_weight}">{b["label"]}</text>'

    note = '<text x="8" y="220" font-size="9" fill="#aaa8a3" font-style="italic">* 浅色柱为估算值，基于YoY增速推算</text>'

    return f'''<svg width="100%" viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif">
  <line x1="{x0-6}" y1="{base_y}" x2="{x0+total_w+6}" y2="{base_y}" stroke="#8b6c42" stroke-width="1"/>
  {rects}{vals}{labels}{note}
</svg>'''


def _svg_segment_bars(segments: list) -> str:
    """Horizontal bar chart for segment revenue breakdown."""
    if not segments:
        return '<p style="color:#9b9590;font-style:italic;font-size:13px;padding:12px 0">分部营收未在财报中单独披露 / Segment revenue not separately disclosed</p>'

    max_rev = max(s["revenue_millions"] for s in segments)
    bar_h, gap = 20, 12
    name_w, chart_w, yoy_w = 140, 380, 120
    W = name_w + chart_w + yoy_w + 20
    total_h = len(segments) * (bar_h + gap) + 30

    rows = ""
    for i, seg in enumerate(segments):
        y = 16 + i * (bar_h + gap)
        bw = max(4, int(seg["revenue_millions"] / max_rev * chart_w))
        rev_str = f"${seg['revenue_millions']/1000:.2f}B" if seg["revenue_millions"] >= 1000 else f"${seg['revenue_millions']:.0f}M"
        yoy = seg.get("yoy_pct")
        if yoy is not None:
            yoy_color = "#2a5c3f" if yoy > 0 else "#8b2e2e"
            yoy_str = f'<text x="{name_w + chart_w + 12}" y="{y+15}" font-size="11" fill="{yoy_color}">{("+" if yoy>0 else "")}{yoy:.0f}% YoY</text>'
        else:
            yoy_str = ""

        rows += f'<text x="{name_w - 8}" y="{y+15}" text-anchor="end" font-size="12" fill="#0a0a0b">{seg["name"]}</text>'
        rows += f'<rect x="{name_w}" y="{y}" width="{bw}" height="{bar_h}" fill="#0a0a0b"/>'
        rows += f'<text x="{name_w + bw + 6}" y="{y+14}" font-size="11" fill="#8b6c42">{rev_str}</text>'
        rows += yoy_str

    return f'''<svg width="100%" viewBox="0 0 {W} {total_h}" font-family="'IM Fell English',Georgia,serif">
  {rows}
</svg>'''


def _svg_eps_comparison(eps_est: Optional[float], eps_act: Optional[float]) -> str:
    """Dual-bar EPS: consensus vs actual."""
    vals = []
    if eps_est is not None:
        vals.append(("共识预期\nConsensus", eps_est, "#8b6c42", False))
    if eps_act is not None:
        beat = (eps_act >= (eps_est or 0))
        color = "#2a5c3f" if beat else "#8b2e2e"
        vals.append(("实际 EPS\nActual", eps_act, color, True))
    if not vals:
        return '<p style="color:#9b9590;font-style:italic;font-size:13px">EPS 数据暂缺</p>'

    max_v = max(abs(v) for _, v, _, _ in vals) * 1.25 or 1
    W, bar_w, gap = 300, 96, 28
    total_w = len(vals) * bar_w + (len(vals) - 1) * gap
    x0 = (W - total_w) // 2
    chart_h = 120
    top = 22

    bars = ""
    for i, (label, v, color, bold) in enumerate(vals):
        x = x0 + i * (bar_w + gap)
        bh = max(6, int(abs(v) / max_v * chart_h))
        y = top + chart_h - bh
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}"/>'
        fw = "bold" if bold else "normal"
        bars += f'<text x="{x+bar_w//2}" y="{y-6}" text-anchor="middle" font-size="13" fill="{color}" font-weight="{fw}">${v:.2f}</text>'
        for j, line in enumerate(label.split("\n")):
            bars += f'<text x="{x+bar_w//2}" y="{top+chart_h+14+j*13}" text-anchor="middle" font-size="10" fill="#6b6560">{line}</text>'

    return f'''<svg width="100%" viewBox="0 0 {W} {top+chart_h+44}" font-family="'IM Fell English',Georgia,serif">
  <line x1="{x0-8}" y1="{top+chart_h}" x2="{x0+total_w+8}" y2="{top+chart_h}" stroke="#8b6c42" stroke-width="1"/>
  {bars}
</svg>'''


def _svg_gm_trend(gm_cur: Optional[float], gm_guide: Optional[float]) -> str:
    """Gross margin line chart: current quarter + guided next quarter."""
    if gm_cur is None:
        return '<p style="color:#9b9590;font-style:italic;font-size:13px">毛利率数据未披露<br>Gross margin not disclosed in transcript</p>'

    points = [("当季\nQ1 Act.", gm_cur, False)]
    if gm_guide:
        points.append(("下季指引\nQ2 Guide", gm_guide, True))

    W, H = 300, 185
    all_v = [p[1] for p in points]
    lo = min(all_v) - 4
    hi = max(all_v) + 4
    span = hi - lo

    def yp(v):
        return int(145 - (v - lo) / span * 100)

    step = W // (len(points) + 1)
    pts = [(step * (i + 1), yp(v)) for i, (_, v, _) in enumerate(points)]

    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    elements = f'<path d="{path}" fill="none" stroke="#0a0a0b" stroke-width="2"/>'

    for i, ((label, v, dashed), (x, y)) in enumerate(zip(points, pts)):
        color = "#8b6c42" if dashed else "#0a0a0b"
        fill = "none" if dashed else "#0a0a0b"
        da = ' stroke-dasharray="5,3"' if dashed else ""
        elements += f'<circle cx="{x}" cy="{y}" r="5" fill="{fill}" stroke="{color}" stroke-width="1.5"{da}/>'
        elements += f'<text x="{x}" y="{y-11}" text-anchor="middle" font-size="12" fill="{color}" font-weight="{"normal" if dashed else "bold"}">{v:.1f}%</text>'
        for j, line in enumerate(label.split("\n")):
            elements += f'<text x="{x}" y="{155+j*13}" text-anchor="middle" font-size="10" fill="#6b6560">{line}</text>'

    # Annotation if improving
    if len(points) == 2 and points[1][1] > points[0][1]:
        diff = points[1][1] - points[0][1]
        mx = (pts[0][0] + pts[1][0]) // 2
        my = (pts[0][1] + pts[1][1]) // 2 - 14
        elements += f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="10" fill="#2a5c3f">+{diff:.1f}pp</text>'

    return f'''<svg width="100%" viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif">
  {elements}
</svg>'''


def _svg_price_range(bear: int, base: int, bull: int, current: Optional[float]) -> str:
    W, H = 680, 110
    lo = bear * 0.88
    hi = bull * 1.12
    span = hi - lo

    def xp(v):
        return int((v - lo) / span * (W - 100) + 50)

    xbear, xbase, xbull = xp(bear), xp(base), xp(bull)

    svg = f'''<svg width="100%" viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif">
  <rect x="{xbear}" y="46" width="{xbull-xbear}" height="10" fill="#e8e4dc" rx="2"/>
  <rect x="{xbear}" y="44" width="{(xbase-xbear)//2}" height="14" fill="#d8d3ca" rx="1" opacity="0.6"/>'''

    for x, label, price, color in [
        (xbear, "熊市 Bear", bear, "#8b2e2e"),
        (xbase, "基准 Base", base, "#0a0a0b"),
        (xbull, "牛市 Bull", bull, "#2a5c3f"),
    ]:
        weight = "bold" if label.startswith("基准") else "normal"
        svg += f'<circle cx="{x}" cy="51" r="{7 if label.startswith("基准") else 5}" fill="{color}"/>'
        svg += f'<text x="{x}" y="32" text-anchor="middle" font-size="13" fill="{color}" font-weight="{weight}">${price}</text>'
        svg += f'<text x="{x}" y="80" text-anchor="middle" font-size="10" fill="#6b6560">{label}</text>'

    if current:
        xc = xp(current)
        svg += f'<polygon points="{xc},{44} {xc-6},{33} {xc+6},{33}" fill="#c9a84c"/>'
        svg += f'<text x="{xc}" y="22" text-anchor="middle" font-size="10" fill="#c9a84c">现价 ${current:.0f}</text>'

    svg += "\n</svg>"
    return svg


# ── Target price calculator ───────────────────────────────────────────────────

def _compute_targets(eps_act: Optional[float], next_q_eps: Optional[float],
                     current_price: Optional[float]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    if not eps_act:
        return None, None, None
    fwd_eps = (next_q_eps or eps_act * 1.05) * 4
    pe = (current_price / (eps_act * 4)) if current_price else 30
    return round(fwd_eps * pe * 0.82), round(fwd_eps * pe), round(fwd_eps * pe * 1.18)


# ── Gap formatting ────────────────────────────────────────────────────────────

def _fmt_gap(gap: Optional[float]) -> str:
    if gap is None:
        return "N/A"
    return f"{'+' if gap > 0 else ''}{gap:.1f}%"


def _gap_cls(gap: Optional[float]) -> str:
    if gap is None:
        return ""
    return "beat" if gap > 2 else ("miss" if gap < -2 else "inline")


# ── Full HTML report ──────────────────────────────────────────────────────────

def generate_html(analysis, consensus, current_price: Optional[float], elapsed: float) -> str:
    from earnings_copilot.models import ManagementTone, RiskSeverity

    # ── Pull structured data ───────────────────────────────────────────────────
    next_q_rev  = _g(analysis.guidance, "Next Q Revenue")
    next_q_eps  = _g(analysis.guidance, "Next Q EPS")
    fy_rev      = _g(analysis.guidance, "FY Revenue")

    eps_est = consensus.eps_estimate if consensus else None
    rev_est = consensus.revenue_estimate if consensus else None

    bear, base, bull = _compute_targets(analysis.eps_actual, next_q_eps, current_price)

    tone_pct = analysis.tone_score * 10
    today = date.today().isoformat()

    # ── Rating pill ────────────────────────────────────────────────────────────
    tone_map = {
        ManagementTone.BULLISH:   ("BUY",    "verdict-pill"),
        ManagementTone.NEUTRAL:   ("HOLD",   "verdict-pill cautious"),
        ManagementTone.CAUTIOUS:  ("HOLD",   "verdict-pill cautious"),
        ManagementTone.DEFENSIVE: ("REDUCE", "verdict-pill bearish"),
    }
    rating_label, rating_cls = tone_map.get(analysis.management_tone, ("HOLD", "verdict-pill cautious"))

    # ── Stat bar values ────────────────────────────────────────────────────────
    eps_gap_str = _fmt_gap(analysis.eps_gap_pct)
    rev_gap_str = _fmt_gap(analysis.revenue_gap_pct)
    eps_cls     = _gap_cls(analysis.eps_gap_pct)
    rev_cls     = _gap_cls(analysis.revenue_gap_pct)

    eps_act_str = f"${analysis.eps_actual:.2f}" if analysis.eps_actual else "N/A"
    rev_act_str = (f"${analysis.revenue_actual/1000:.2f}B"
                   if analysis.revenue_actual and analysis.revenue_actual >= 1000
                   else (f"${analysis.revenue_actual:.0f}M" if analysis.revenue_actual else "N/A"))
    next_q_rev_str = (f"${next_q_rev/1000:.1f}B"
                      if next_q_rev and next_q_rev >= 1000
                      else (f"${next_q_rev:.0f}M" if next_q_rev else "N/A"))
    gm_str = f"{analysis.gross_margin_pct:.1f}%" if analysis.gross_margin_pct else "—"

    # ── Charts ─────────────────────────────────────────────────────────────────
    rev_bars = _build_rev_bars(
        analysis.revenue_actual or 0,
        next_q_rev,
        analysis.yoy_revenue_growth_pct,
        analysis.quarter,
    ) if analysis.revenue_actual else []

    svg_rev = _svg_revenue_trend(rev_bars)
    svg_seg = _svg_segment_bars(analysis.segments or [])
    svg_eps = _svg_eps_comparison(eps_est, analysis.eps_actual)
    svg_gm  = _svg_gm_trend(analysis.gross_margin_pct, analysis.next_quarter_gross_margin_pct)
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

    # ── Q&A ────────────────────────────────────────────────────────────────────
    qa_html = ""
    for q in analysis.analyst_questions[:5]:
        bar = "▓" * q.management_directness + "░" * (5 - q.management_directness)
        evasion = "; ".join(q.evasion_signals[:2]) if q.evasion_signals else "管理层正面回应"
        qa_html += f"""
    <div class="qa-item">
      <div class="qa-firm">{q.analyst_firm} &nbsp;·&nbsp; 回应直接度 {bar} {q.management_directness}/5</div>
      <div class="qa-q">{q.question_summary}</div>
      <div class="qa-signal">{evasion}</div>
    </div>"""

    tension_html = "".join(
        f'<div class="tension-item">⟶ {t}</div>'
        for t in analysis.tension_areas[:3]
    )

    # ── Target price section ───────────────────────────────────────────────────
    if bear and base and bull:
        def updown(v):
            if not current_price or not v:
                return ""
            pct = round((v / current_price - 1) * 100, 1)
            color = "#2a5c3f" if pct >= 0 else "#8b2e2e"
            return f'<span class="sc-updown" style="color:{color}">{("+" if pct>=0 else "")}{pct:.1f}% vs 现价</span>'

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
        <div class="sc-price">${bear}<br>{updown(bear)}</div>
        <div class="sc-logic">增长放缓，竞争加剧，毛利率承压</div>
        <div class="sc-meta">Forward EPS × 低估值倍数</div>
      </div>
      <div class="scenario-card base">
        <div class="sc-label">基准 <em>Base</em></div>
        <div class="sc-price">${base}<br>{updown(base)}</div>
        <div class="sc-logic">当前增长趋势延续，毛利率稳步扩张</div>
        <div class="sc-meta">Forward EPS × 当前 P/E</div>
      </div>
      <div class="scenario-card bull">
        <div class="sc-label">牛市 <em>Bull</em></div>
        <div class="sc-price">${bull}<br>{updown(bull)}</div>
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
          <td>${fwd_eps_val*0.90:.2f}</td><td>${fwd_eps_val:.2f}</td><td>${fwd_eps_val*1.10:.2f}</td></tr>
      <tr><td>估值 P/E 倍数</td>
          <td>低 (−18%)</td><td>维持现值</td><td>高 (+18%)</td></tr>
      <tr><td>营收增长路径</td>
          <td>低于指引</td><td>符合指引</td><td>超越指引</td></tr>
      <tr><td>毛利率趋势</td>
          <td>承压 / 持平</td><td>稳步扩张</td><td>超预期扩张</td></tr>
    </table>
  </div>"""
    else:
        target_section = """
  <div class="section">
    <div class="section-label">
      <span class="section-zh">目标价 · 三情景</span>
      <span class="section-en">Price Target — 12-Month Scenarios</span>
    </div>
    <p style="color:#9b9590;font-style:italic;font-size:14px">
      提供 <code>--price</code> 参数（当前股价）以生成目标价三情景模型
    </p>
  </div>"""

    # ── Guidance text ──────────────────────────────────────────────────────────
    guidance_text = ""
    if next_q_rev:
        guidance_text += f"下季营收指引 {next_q_rev_str}。"
    if fy_rev and fy_rev >= 1000:
        guidance_text += f" 全年营收指引 ${fy_rev/1000:.1f}B。"
    if not guidance_text and analysis.guidance:
        guidance_text = "; ".join(
            f"{g.metric} {g.value}" for g in analysis.guidance
        )
    if not guidance_text:
        guidance_text = "详见财报正文。"

    # ── HTML ───────────────────────────────────────────────────────────────────
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
  html,body{{background:var(--paper);color:var(--ink);
    font-family:'IM Fell English',Georgia,serif;min-height:100vh}}
  .page{{max-width:880px;margin:0 auto;padding:60px 48px 100px}}

  .pub-bar{{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);
    border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:28px;
    display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}

  .headline{{font-size:clamp(26px,4vw,44px);line-height:1.1;margin:0 0 12px}}
  .subhead{{font-size:15px;color:var(--muted);font-style:italic;line-height:1.65;margin-bottom:18px}}
  .tag-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:32px}}
  .tag{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;
    padding:4px 12px;border:1px solid var(--copper);color:var(--copper)}}
  .verdict-pill{{background:var(--green);border-color:var(--green);color:#fff}}
  .verdict-pill.cautious{{background:var(--amber);border-color:var(--amber)}}
  .verdict-pill.bearish{{background:var(--red);border-color:var(--red)}}

  .stat-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;
    background:var(--copper);border:1px solid var(--copper);margin:0 0 36px}}
  .stat-cell{{background:var(--paper);padding:16px;text-align:center}}
  .stat-val{{font-size:clamp(20px,3vw,30px);line-height:1.1}}
  .stat-val.beat{{color:var(--green)}} .stat-val.miss{{color:var(--red)}}
  .stat-val.inline{{color:var(--amber)}}
  .stat-label{{font-size:10px;color:var(--muted);margin-top:6px;font-style:italic;line-height:1.5}}

  .section{{margin:36px 0}}
  .section-label{{margin-bottom:14px;border-bottom:1px solid var(--gold);padding-bottom:6px}}
  .section-zh{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--gold)}}
  .section-en{{font-size:11px;font-style:italic;color:var(--muted);margin-left:10px}}

  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:36px}}
  @media(max-width:620px){{.two-col{{grid-template-columns:1fr}}}}

  .body-text{{font-size:15px;line-height:1.8}}
  .body-text p{{margin-bottom:14px}}
  .label-zh{{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--copper);margin-right:6px}}
  .label-en{{font-size:10px;font-style:italic;color:var(--muted);margin-right:8px}}

  .tone-row{{display:flex;align-items:center;gap:14px;margin:10px 0}}
  .tone-label{{font-size:12px;color:var(--muted);width:72px;flex-shrink:0;font-style:italic}}
  .tone-track{{flex:1;height:5px;background:var(--light);border-radius:3px;overflow:hidden}}
  .tone-fill{{height:100%;border-radius:3px;
    background:linear-gradient(90deg,var(--red),var(--amber),var(--green))}}
  .tone-score{{font-size:14px;width:36px;text-align:right}}

  .verdict-box{{background:var(--ink);padding:32px 36px;margin:36px 0}}
  .verdict-eyebrow{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;
    color:var(--gold);margin-bottom:10px}}
  .verdict-text{{font-size:clamp(15px,2vw,20px);color:var(--paper);
    line-height:1.6;font-style:italic}}
  .verdict-en{{font-size:12px;color:rgba(241,239,234,.4);margin-top:8px;font-style:italic}}

  .risk-table{{width:100%;border-collapse:collapse;margin-top:6px;font-size:14px}}
  .risk-table th{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
    padding:8px 10px;text-align:left;border-bottom:1px solid var(--copper);font-weight:normal}}
  .risk-table td{{padding:11px 10px;border-bottom:1px solid rgba(139,108,66,.1);vertical-align:top}}
  .dot-h{{color:var(--red)}} .dot-m{{color:var(--amber)}} .dot-l{{color:var(--green)}}
  .new-badge{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;
    background:var(--red);color:#fff;padding:1px 5px;margin-left:4px;vertical-align:middle}}

  .chips{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
  .chip{{padding:5px 14px;border:1px solid var(--copper);font-size:13px;
    color:var(--copper);font-style:italic}}

  .qa-item{{margin-bottom:16px;padding:14px 16px;background:var(--light);
    border-left:3px solid var(--gold)}}
  .qa-firm{{font-size:10px;letter-spacing:.09em;text-transform:uppercase;
    color:var(--gold);margin-bottom:6px;font-family:monospace}}
  .qa-q{{font-size:14px;line-height:1.55;margin-bottom:6px}}
  .qa-signal{{font-size:12px;color:var(--red);font-style:italic}}
  .tension-item{{font-size:14px;padding:8px 0;
    border-bottom:1px solid rgba(139,108,66,.1);font-style:italic}}

  .scenario-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;
    background:var(--copper);border:1px solid var(--copper);margin:20px 0}}
  .scenario-card{{background:var(--paper);padding:20px 16px}}
  .sc-label{{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}}
  .sc-label em{{font-style:normal;margin-left:6px;color:var(--muted)}}
  .sc-price{{font-size:clamp(22px,3vw,32px);margin-bottom:8px;line-height:1.2}}
  .sc-updown{{display:block;font-size:12px;margin-top:2px}}
  .scenario-card.bear .sc-price{{color:var(--red)}}
  .scenario-card.bull .sc-price{{color:var(--green)}}
  .sc-logic{{font-size:13px;color:var(--ink);line-height:1.5;
    margin-bottom:8px;font-style:italic}}
  .sc-meta{{font-size:11px;color:var(--muted)}}

  .assumption-table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}
  .assumption-table th{{padding:8px 12px;text-align:center;
    border-bottom:2px solid var(--copper);font-weight:normal;
    color:var(--muted);font-size:10px;letter-spacing:.09em;text-transform:uppercase}}
  .assumption-table th:first-child{{text-align:left}}
  .assumption-table td{{padding:10px 12px;border-bottom:1px solid rgba(139,108,66,.1);
    text-align:center}}
  .assumption-table td:first-child{{text-align:left;font-style:italic}}
  .assumption-table em{{font-style:normal;color:var(--muted);font-size:11px;margin-left:6px}}

  .footer{{margin-top:60px;padding-top:18px;border-top:1px solid var(--copper);
    font-size:11px;color:var(--muted);display:flex;
    justify-content:space-between;flex-wrap:wrap;gap:8px}}
</style>
</head>
<body>
<div class="page">

  <!-- 1. Pub Bar -->
  <div class="pub-bar">
    <span>财报猎手 Earner &nbsp;·&nbsp; Earnings Intelligence</span>
    <span>{today} &nbsp;·&nbsp; AI-Generated Research &nbsp;·&nbsp; Not Investment Advice</span>
  </div>

  <!-- 2. Headline + Tags -->
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
      <div class="stat-label">EPS 超/低预期<br>{eps_act_str} vs {f"${eps_est:.2f}E" if eps_est else "共识"}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-val {rev_cls}">{rev_gap_str}</div>
      <div class="stat-label">营收超/低预期<br>{rev_act_str} 实际</div>
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

  <!-- 4. Revenue Trend (8 quarters) -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">季度营收走势</span>
      <span class="section-en">Quarterly Revenue Trend</span>
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

  <!-- 6. EPS Comparison + Gross Margin (two-col) -->
  <div class="section two-col">
    <div>
      <div class="section-label">
        <span class="section-zh">EPS 对比</span>
        <span class="section-en">Consensus vs Actual</span>
      </div>
      {svg_eps}
    </div>
    <div>
      <div class="section-label">
        <span class="section-zh">毛利率走势</span>
        <span class="section-en">Gross Margin Trend</span>
      </div>
      {svg_gm}
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
        {analysis.ticker} {analysis.quarter}：{analysis.headline}
        EPS {eps_act_str}（共识 {f"${eps_est:.2f}" if eps_est else "N/A"}，{eps_gap_str}），
        营收 {rev_act_str}（{rev_gap_str}）。
        {"YoY 营收增速 +" + str(analysis.yoy_revenue_growth_pct) + "%。" if analysis.yoy_revenue_growth_pct else ""}
      </p>
      <p>
        <span class="label-zh">前瞻指引</span><span class="label-en">Forward Guidance</span>
        {guidance_text}
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
    <p class="verdict-en">{analysis.ticker} {analysis.quarter} &nbsp;·&nbsp; Tone: {analysis.management_tone.value} {analysis.tone_score}/10</p>
  </div>

  <!-- 10. Management Tone -->
  <div class="section">
    <div class="section-label">
      <span class="section-zh">管理层语气</span>
      <span class="section-en">Management Tone Analysis</span>
    </div>
    <div class="tone-row">
      <span class="tone-label">信心指数</span>
      <div class="tone-track">
        <div class="tone-fill" style="width:{tone_pct}%"></div>
      </div>
      <span class="tone-score">{analysis.tone_score}/10</span>
    </div>
    <p class="body-text" style="margin-top:12px;font-size:14px;color:var(--muted)">
      {analysis.tone_reasoning}
    </p>
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
        <th>严重性</th>
        <th>类别 <em style="font-style:italic;font-size:9px;font-weight:normal">Category</em></th>
        <th>描述 <em style="font-style:italic;font-size:9px;font-weight:normal">Description</em></th>
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
    {('<div style="margin-top:20px"><div class="section-label"><span class="section-zh">主要张力</span><span class="section-en">Tension Areas</span></div>' + tension_html + '</div>') if tension_html else ''}
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
                        help="输出路径（默认: {TICKER}_Copilot_Report.html）")
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
        lambda: analyze_earnings_call(
            ctx,
            auth_token=auth_token or None,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        ),
    )
    elapsed = time.time() - t0

    print(f"\n✓ 分析完成，耗时 {elapsed:.1f}s")
    print(f"  Tone: {analysis.management_tone.value} ({analysis.tone_score}/10)")
    print(f"  EPS: {analysis.eps_actual}  Revenue: {analysis.revenue_actual}M")
    print(f"  GM: {analysis.gross_margin_pct}%  YoY: {analysis.yoy_revenue_growth_pct}%")
    print(f"  Segments: {len(analysis.segments)}  Themes: {len(analysis.key_themes)}")

    html = generate_html(analysis, consensus, args.price, elapsed)

    out_path = args.output or f"{args.ticker.upper()}_Copilot_Report.html"
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"\n✓ 报告已生成: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
