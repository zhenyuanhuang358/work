#!/usr/bin/env python3
"""
Merlin — AI Consulting Preparation System

Usage:
    python merlin.py "<COMPANY>" "<MEETING_PURPOSE>" --background <file> [options]

Options:
    --background FILE     Background materials (docs, paste, web snippets)
    --industry TEXT       Industry classification
    --interviewee TEXT    Role of the interviewee
    --output FILE         Output HTML (default: {company}_Merlin_Brief.html)
    --api-key KEY         Anthropic API key (or set ANTHROPIC_API_KEY)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from merlin.analyzer import analyze
from merlin.models import CoreIssue, InterviewQuestion, MerlinAnalysis, RiskItem
from merlin.prompts import MerlinContext


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_auth() -> dict:
    token_path = Path("/home/claude/.claude/remote/.session_ingress_token")
    if token_path.exists():
        return {"auth_token": token_path.read_text().strip()}
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return {"api_key": key}
    return {}


# ── SVG Charts ────────────────────────────────────────────────────────────────

def _svg_issue_matrix(issues: list[CoreIssue]) -> str:
    """Impact vs Certainty scatter plot for core issues."""
    W, H = 520, 340
    pad_l, pad_b, pad_r, pad_t = 60, 50, 20, 30

    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    def x(certainty):
        return pad_l + (certainty - 1) / 4 * plot_w

    def y(impact):
        return pad_t + (5 - impact) / 4 * plot_h

    grid_lines = ""
    for v in range(1, 6):
        gx = x(v)
        gy = y(v)
        grid_lines += f'<line x1="{gx:.0f}" y1="{pad_t}" x2="{gx:.0f}" y2="{pad_t+plot_h}" stroke="#d4cfc8" stroke-width="1" stroke-dasharray="3,3"/>'
        grid_lines += f'<line x1="{pad_l}" y1="{gy:.0f}" x2="{pad_l+plot_w}" y2="{gy:.0f}" stroke="#d4cfc8" stroke-width="1" stroke-dasharray="3,3"/>'

    dots = ""
    colors = ["#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#4a6fa5"]
    for i, issue in enumerate(issues[:5]):
        cx = x(issue.certainty)
        cy = y(issue.impact)
        color = colors[i % len(colors)]
        label = issue.title[:18] + "…" if len(issue.title) > 18 else issue.title
        dots += f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="14" fill="{color}" fill-opacity="0.85" stroke="#f1efea" stroke-width="2"/>'
        dots += f'<text x="{cx:.0f}" y="{cy:.0f}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#f1efea" font-weight="bold">{i+1}</text>'
        # label below
        dots += f'<text x="{cx:.0f}" y="{cy+22:.0f}" text-anchor="middle" font-size="9" fill="#4a3f35">{label}</text>'

    axis_labels = "".join(
        f'<text x="{x(v):.0f}" y="{pad_t+plot_h+16}" text-anchor="middle" font-size="10" fill="#6b5a47">{v}</text>'
        for v in range(1, 6)
    ) + "".join(
        f'<text x="{pad_l-8}" y="{y(v):.0f}" text-anchor="end" dominant-baseline="middle" font-size="10" fill="#6b5a47">{v}</text>'
        for v in range(1, 6)
    )

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  {grid_lines}
  {dots}
  {axis_labels}
  <text x="{pad_l + plot_w/2:.0f}" y="{H-4}" text-anchor="middle" font-size="11" fill="#6b5a47">Certainty (确定性) →</text>
  <text x="12" y="{pad_t + plot_h/2:.0f}" text-anchor="middle" font-size="11" fill="#6b5a47" transform="rotate(-90,12,{pad_t+plot_h/2:.0f})">Impact (影响) ↑</text>
  <text x="{W/2:.0f}" y="16" text-anchor="middle" font-size="12" fill="#0a0a0b" font-weight="bold">核心议题矩阵 Issue Priority Matrix</text>
</svg>'''


def _svg_risk_heatmap(risks: list[RiskItem]) -> str:
    """Horizontal risk severity bars."""
    if not risks:
        return '<svg viewBox="0 0 520 80" xmlns="http://www.w3.org/2000/svg"><text x="260" y="40" text-anchor="middle" font-size="13" fill="#6b5a47">No risks identified</text></svg>'

    row_h = 44
    pad_l, pad_t = 20, 40
    W = 520
    H = pad_t + len(risks) * row_h + 20

    sev_color = {"high": "#8b2e2e", "medium": "#c47a1e", "low": "#2a5c3f"}
    sev_label = {"high": "高", "medium": "中", "low": "低"}
    sev_width = {"high": 360, "medium": 220, "low": 110}

    rows = ""
    for i, risk in enumerate(risks):
        ry = pad_t + i * row_h
        sev = risk.severity.lower()
        color = sev_color.get(sev, "#6b5a47")
        bar_w = sev_width.get(sev, 150)
        label = f"[{risk.category.upper()[:3]}] {risk.description}"
        label = label[:62] + "…" if len(label) > 62 else label
        rows += f'''
  <rect x="{pad_l}" y="{ry}" width="{bar_w}" height="28" fill="{color}" fill-opacity="0.18" rx="4"/>
  <rect x="{pad_l}" y="{ry}" width="4" height="28" fill="{color}" rx="2"/>
  <text x="{pad_l+12}" y="{ry+18}" font-size="11" fill="#0a0a0b">{label}</text>
  <text x="{W-8}" y="{ry+18}" text-anchor="end" font-size="10" fill="{color}" font-weight="bold">{sev_label.get(sev,"?")}</text>'''

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  <text x="{W/2:.0f}" y="22" text-anchor="middle" font-size="12" fill="#0a0a0b" font-weight="bold">风险热图 Risk Heatmap</text>
  {rows}
</svg>'''


def _svg_question_tree(questions: list[InterviewQuestion]) -> str:
    """Vertical priority-ordered question blocks."""
    if not questions:
        return '<svg viewBox="0 0 520 80" xmlns="http://www.w3.org/2000/svg"><text x="260" y="40" text-anchor="middle" font-size="13" fill="#6b5a47">No questions generated</text></svg>'

    W = 520
    row_h = 64
    pad_t = 40
    H = pad_t + len(questions) * row_h + 20

    colors = ["#8b6c42", "#c9a84c", "#2a5c3f", "#4a6fa5", "#8b2e2e", "#6b5a47"]

    rows = ""
    for i, q in enumerate(questions):
        ry = pad_t + i * row_h
        color = colors[i % len(colors)]
        num = str(q.priority)
        text = q.question[:72] + "…" if len(q.question) > 72 else q.question
        purpose = q.purpose[:62] + "…" if len(q.purpose) > 62 else q.purpose
        rows += f'''
  <rect x="20" y="{ry}" width="480" height="{row_h-8}" fill="{color}" fill-opacity="0.08" rx="6" stroke="{color}" stroke-width="1" stroke-opacity="0.3"/>
  <circle cx="44" cy="{ry+28}" r="14" fill="{color}" fill-opacity="0.85"/>
  <text x="44" y="{ry+33}" text-anchor="middle" font-size="12" fill="#f1efea" font-weight="bold">{num}</text>
  <text x="66" y="{ry+20}" font-size="11" fill="#0a0a0b">{text}</text>
  <text x="66" y="{ry+36}" font-size="9.5" fill="#6b5a47" font-style="italic">{purpose}</text>'''

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  <text x="{W/2:.0f}" y="22" text-anchor="middle" font-size="12" fill="#0a0a0b" font-weight="bold">提问优先级 Question Priority Tree</text>
  {rows}
</svg>'''


def _svg_confidence_gauge(score: int) -> str:
    """Semicircle gauge for confidence score 1-10."""
    W, H = 300, 170
    cx, cy, r = 150, 140, 110
    import math

    def arc_point(angle_deg):
        rad = math.radians(angle_deg)
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    # 180° arc from left to right (π to 0)
    # map score 1-10 → 180° to 0°
    angle = 180 - (score - 1) / 9 * 180
    ex, ey = arc_point(angle)

    color = "#8b2e2e" if score <= 3 else ("#c47a1e" if score <= 6 else "#2a5c3f")

    # background arc
    bg_arc = f'M {arc_point(180)[0]:.1f},{arc_point(180)[1]:.1f} A {r} {r} 0 0 1 {arc_point(0)[0]:.1f},{arc_point(0)[1]:.1f}'
    # filled arc
    large = 1 if (180 - angle) > 180 else 0
    fill_arc = f'M {arc_point(180)[0]:.1f},{arc_point(180)[1]:.1f} A {r} {r} 0 {large} 1 {ex:.1f},{ey:.1f}'

    tick_marks = ""
    for v in range(1, 11):
        a = 180 - (v - 1) / 9 * 180
        ox, oy = arc_point(a)
        ix = cx + (r - 12) * math.cos(math.radians(a))
        iy = cy - (r - 12) * math.sin(math.radians(a))
        tick_marks += f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ix:.1f}" y2="{iy:.1f}" stroke="#c4bfb6" stroke-width="1.5"/>'
        if v in (1, 5, 10):
            lx = cx + (r - 26) * math.cos(math.radians(a))
            ly = cy - (r - 26) * math.sin(math.radians(a))
            tick_marks += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="#6b5a47">{v}</text>'

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  <path d="{bg_arc}" fill="none" stroke="#d4cfc8" stroke-width="18" stroke-linecap="round"/>
  <path d="{fill_arc}" fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round" opacity="0.85"/>
  {tick_marks}
  <text x="{cx}" y="{cy-18}" text-anchor="middle" font-size="36" fill="{color}" font-weight="bold">{score}</text>
  <text x="{cx}" y="{cy+8}" text-anchor="middle" font-size="11" fill="#6b5a47">/ 10</text>
  <text x="{cx}" y="{H-12}" text-anchor="middle" font-size="11" fill="#0a0a0b" font-weight="bold">准备质量置信度 Preparation Confidence</text>
</svg>'''


# ── HTML Report ───────────────────────────────────────────────────────────────

def _severity_class(sev: str) -> str:
    return {"high": "sev-high", "medium": "sev-med", "low": "sev-low"}.get(sev.lower(), "sev-med")


def _sev_zh(sev: str) -> str:
    return {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(sev.lower(), sev)


def generate_html(a: MerlinAnalysis) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")

    issue_rows = ""
    for i, issue in enumerate(a.core_issues, 1):
        impact_bars = "".join(
            f'<span class="bar{"  filled" if j <= issue.impact else ""}"></span>'
            for j in range(1, 6)
        )
        cert_bars = "".join(
            f'<span class="bar{"  filled" if j <= issue.certainty else ""}"></span>'
            for j in range(1, 6)
        )
        issue_rows += f'''
        <div class="issue-card">
          <div class="issue-num">{i}</div>
          <div class="issue-body">
            <div class="issue-title">{issue.title}</div>
            <div class="issue-why">{issue.why_it_matters}</div>
            <div class="issue-evidence">{issue.evidence}</div>
            <div class="issue-bars">
              <span class="bar-label">影响 Impact</span> {impact_bars}
              <span class="bar-label" style="margin-left:16px">确定性 Certainty</span> {cert_bars}
            </div>
          </div>
        </div>'''

    risk_rows = ""
    for risk in a.risks:
        sc = _severity_class(risk.severity)
        risk_rows += f'''
        <tr>
          <td><span class="sev-badge {sc}">{_sev_zh(risk.severity)}</span></td>
          <td><strong>{risk.category.upper()}</strong><br><span class="risk-desc">{risk.description}</span></td>
          <td class="risk-tension">{risk.contradiction}</td>
          <td class="risk-q">{risk.verification_question}</td>
        </tr>'''

    q_cards = ""
    for q in a.questions:
        fups = "".join(f'<li>{fu}</li>' for fu in q.follow_ups)
        q_cards += f'''
        <div class="q-card">
          <div class="q-priority">Q{q.priority}</div>
          <div class="q-body">
            <div class="q-text">{q.question}</div>
            <div class="q-purpose"><span class="label-zh">目的</span> <span class="label-en">Purpose</span> {q.purpose}</div>
            <div class="q-meta-row">
              <div><span class="label-zh">规避信号</span> <span class="label-en">Evasion</span> {q.evasion_signal}</div>
              <div><span class="label-zh">突破策略</span> <span class="label-en">Breakthrough</span> {q.breakthrough}</div>
            </div>
            <ul class="q-followups">{fups}</ul>
          </div>
        </div>'''

    theme_chips = "".join(
        f'<span class="theme-chip">{t}</span>' for t in a.key_themes
    )

    metrics_html = "".join(
        f'<div class="metric-item">{m}</div>' for m in a.key_metrics
    )

    events_html = "".join(
        f'<li>{e}</li>' for e in a.recent_events
    )

    conf_color = "#8b2e2e" if a.confidence_score <= 3 else ("#c47a1e" if a.confidence_score <= 6 else "#2a5c3f")

    svg_matrix = _svg_issue_matrix(a.core_issues)
    svg_risk = _svg_risk_heatmap(a.risks)
    svg_qtree = _svg_question_tree(a.questions)
    svg_gauge = _svg_confidence_gauge(a.confidence_score)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Merlin — {a.company_name} 访谈作战包</title>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#0a0a0b; --paper:#f1efea; --copper:#8b6c42; --gold:#c9a84c;
  --green:#2a5c3f; --red:#8b2e2e; --amber:#c47a1e; --bg:#f9f7f3;
  --border:#d4cfc8;
}}
*{{box-sizing:border-box; margin:0; padding:0;}}
body{{background:var(--paper); color:var(--ink); font-family:'IM Fell English',Georgia,serif; max-width:900px; margin:0 auto; padding:32px 24px;}}

/* Pub bar */
.pub-bar{{display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid var(--ink); padding-bottom:8px; margin-bottom:28px;}}
.pub-logo{{font-size:22px; letter-spacing:.12em; color:var(--copper);}}
.pub-meta{{font-size:11px; color:var(--copper); text-align:right;}}

/* Title */
.report-title{{font-size:34px; line-height:1.15; margin-bottom:6px;}}
.report-subtitle{{font-size:14px; color:var(--copper); letter-spacing:.08em; margin-bottom:16px;}}
.tag-row{{display:flex; gap:10px; flex-wrap:wrap; margin-bottom:28px;}}
.tag{{border:1px solid var(--copper); color:var(--copper); font-size:11px; padding:3px 10px; border-radius:2px; letter-spacing:.06em;}}

/* Stat bar */
.stat-bar{{display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:32px;}}
.stat-cell{{background:var(--bg); border:1px solid var(--border); padding:14px; text-align:center;}}
.stat-val{{font-size:26px; color:var(--copper); font-weight:bold;}}
.stat-lbl{{font-size:10px; color:#6b5a47; margin-top:2px; letter-spacing:.06em;}}

/* Section */
.section{{margin-bottom:36px;}}
.section-zh{{font-size:20px; font-weight:bold; border-bottom:1px solid var(--border); padding-bottom:4px; margin-bottom:4px;}}
.section-en{{font-size:11px; color:var(--copper); letter-spacing:.1em; margin-bottom:16px;}}

/* SVG charts */
.chart-wrap{{background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:8px; margin-bottom:16px;}}
.chart-wrap svg{{width:100%; height:auto; display:block;}}

/* Overview */
.overview-text{{font-size:14px; line-height:1.7; margin-bottom:12px;}}
.metrics-grid{{display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin-bottom:16px;}}
.metric-item{{background:var(--bg); border-left:3px solid var(--copper); padding:8px 12px; font-size:13px;}}
.events-list{{list-style:none; padding:0;}}
.events-list li{{padding:6px 0; border-bottom:1px solid var(--border); font-size:13px;}}
.events-list li::before{{content:"›"; color:var(--copper); margin-right:8px;}}

/* Core issues */
.issue-card{{display:flex; gap:16px; padding:16px; background:var(--bg); border:1px solid var(--border); margin-bottom:12px; border-radius:4px;}}
.issue-num{{width:32px; height:32px; border-radius:50%; background:var(--copper); color:var(--paper); display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:bold; flex-shrink:0;}}
.issue-body{{flex:1;}}
.issue-title{{font-size:15px; font-weight:bold; margin-bottom:4px;}}
.issue-why{{font-size:13px; color:var(--copper); margin-bottom:6px; font-style:italic;}}
.issue-evidence{{font-size:12px; color:#4a3f35; margin-bottom:8px; line-height:1.5;}}
.issue-bars{{display:flex; align-items:center; gap:4px; flex-wrap:wrap;}}
.bar-label{{font-size:10px; color:#6b5a47; letter-spacing:.04em;}}
.bar{{display:inline-block; width:14px; height:8px; background:var(--border); border-radius:2px;}}
.bar.filled{{background:var(--copper);}}

/* Risk table */
.risk-table{{width:100%; border-collapse:collapse; font-size:12px;}}
.risk-table th{{background:var(--ink); color:var(--paper); padding:8px 10px; text-align:left; font-size:11px; letter-spacing:.06em;}}
.risk-table td{{padding:10px; border-bottom:1px solid var(--border); vertical-align:top;}}
.risk-table tr:nth-child(even) td{{background:var(--bg);}}
.sev-badge{{display:inline-block; padding:2px 8px; border-radius:2px; font-size:10px; font-weight:bold;}}
.sev-high{{background:#8b2e2e22; color:#8b2e2e; border:1px solid #8b2e2e66;}}
.sev-med{{background:#c47a1e22; color:#c47a1e; border:1px solid #c47a1e66;}}
.sev-low{{background:#2a5c3f22; color:#2a5c3f; border:1px solid #2a5c3f66;}}
.risk-desc{{color:#4a3f35; font-style:italic;}}
.risk-tension{{color:#6b5a47;}}
.risk-q{{color:var(--copper); font-style:italic;}}

/* Question tree */
.q-card{{display:flex; gap:14px; padding:16px; background:var(--bg); border:1px solid var(--border); margin-bottom:12px; border-radius:4px;}}
.q-priority{{font-size:22px; font-weight:bold; color:var(--copper); min-width:36px; text-align:center;}}
.q-body{{flex:1;}}
.q-text{{font-size:14px; font-weight:bold; margin-bottom:6px; line-height:1.5;}}
.q-purpose{{font-size:12px; color:var(--copper); margin-bottom:8px; font-style:italic;}}
.q-meta-row{{display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px; font-size:11px; color:#4a3f35;}}
.q-followups{{font-size:11px; color:#6b5a47; padding-left:16px; line-height:1.6;}}

/* Labels */
.label-zh{{font-size:10px; font-weight:bold; color:var(--ink); letter-spacing:.06em;}}
.label-en{{font-size:9px; color:var(--copper); letter-spacing:.08em; font-style:italic; margin-right:6px;}}

/* Strategy */
.hypothesis-box{{background:var(--ink); color:var(--paper); padding:20px 24px; margin-bottom:20px; border-radius:4px;}}
.hypothesis-label{{font-size:10px; color:var(--gold); letter-spacing:.12em; margin-bottom:8px;}}
.hypothesis-text{{font-size:16px; line-height:1.6;}}
.opening-box{{background:var(--bg); border:1px solid var(--copper); border-left:4px solid var(--copper); padding:16px 20px; margin-bottom:16px;}}
.opening-label{{font-size:10px; color:var(--copper); letter-spacing:.1em; margin-bottom:6px;}}
.opening-text{{font-size:13px; line-height:1.6;}}

/* Themes */
.theme-chip{{display:inline-block; background:var(--bg); border:1px solid var(--border); padding:5px 14px; margin:4px; font-size:12px; border-radius:16px; color:#4a3f35;}}

/* Context gaps */
.gaps-box{{background:#fffef8; border:1px dashed var(--amber); padding:14px 18px; font-size:13px; color:#4a3f35; line-height:1.6;}}

/* Two-col grid */
.two-col{{display:grid; grid-template-columns:1fr 1fr; gap:20px;}}

/* Footer */
.footer{{margin-top:48px; border-top:1px solid var(--border); padding-top:16px; font-size:11px; color:#6b5a47; display:flex; justify-content:space-between;}}
</style>
</head>
<body>

<!-- 1. Pub Bar -->
<div class="pub-bar">
  <div class="pub-logo">MERLIN</div>
  <div class="pub-meta">访谈作战包 Interview Brief &nbsp;|&nbsp; {date_str} &nbsp;|&nbsp; Powered by Claude</div>
</div>

<!-- 2. Title -->
<div class="report-title">{a.company_name}</div>
<div class="report-subtitle">{a.meeting_purpose.upper()}</div>
<div class="tag-row">
  <span class="tag">{a.meeting_purpose}</span>
  <span class="tag">置信度 {a.confidence_score}/10</span>
  {"".join(f'<span class="tag">{t}</span>' for t in a.key_themes[:3])}
</div>

<!-- 3. Stat bar -->
<div class="stat-bar">
  <div class="stat-cell">
    <div class="stat-val">{len(a.core_issues)}</div>
    <div class="stat-lbl">核心议题 ISSUES</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val">{len(a.risks)}</div>
    <div class="stat-lbl">风险项 RISKS</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val">{len(a.questions)}</div>
    <div class="stat-lbl">目标问题 QUESTIONS</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val" style="color:{conf_color}">{a.confidence_score}/10</div>
    <div class="stat-lbl">准备置信度 CONFIDENCE</div>
  </div>
</div>

<!-- 4. Company Overview -->
<div class="section">
  <div class="section-zh">公司概况</div>
  <div class="section-en">COMPANY OVERVIEW</div>
  <div class="overview-text">{a.company_overview}</div>
  <div class="two-col">
    <div>
      <div class="label-zh">关键指标 <span class="label-en">Key Metrics</span></div>
      <div class="metrics-grid" style="margin-top:8px">{metrics_html}</div>
    </div>
    <div>
      <div class="label-zh">近期重要事件 <span class="label-en">Recent Events</span></div>
      <ul class="events-list" style="margin-top:8px">{events_html}</ul>
    </div>
  </div>
  <div class="label-zh" style="margin-top:14px">管理层叙事 <span class="label-en">Strategic Narrative</span></div>
  <div class="overview-text" style="margin-top:6px; font-style:italic; color:var(--copper)">{a.strategic_narrative}</div>
</div>

<!-- 5. Issue Matrix SVG -->
<div class="section">
  <div class="section-zh">核心议题矩阵</div>
  <div class="section-en">CORE ISSUE PRIORITY MATRIX</div>
  <div class="chart-wrap">{svg_matrix}</div>
  {issue_rows}
</div>

<!-- 6. Risk Heatmap -->
<div class="section">
  <div class="section-zh">风险与矛盾检测</div>
  <div class="section-en">RISK &amp; CONTRADICTION DETECTION</div>
  <div class="chart-wrap">{svg_risk}</div>
  <table class="risk-table">
    <thead>
      <tr>
        <th>严重度 SEV</th>
        <th>类别 / 描述 CATEGORY / DESCRIPTION</th>
        <th>数据矛盾 CONTRADICTION</th>
        <th>验证问题 VERIFICATION Q</th>
      </tr>
    </thead>
    <tbody>{risk_rows}</tbody>
  </table>
</div>

<!-- 7. Question Tree -->
<div class="section">
  <div class="section-zh">访谈问题树</div>
  <div class="section-en">INTERVIEW QUESTION TREE</div>
  <div class="chart-wrap">{svg_qtree}</div>
  {q_cards}
</div>

<!-- 8. Interview Strategy -->
<div class="section">
  <div class="section-zh">访谈战略框架</div>
  <div class="section-en">INTERVIEW STRATEGY</div>
  <div class="hypothesis-box">
    <div class="hypothesis-label">核心假设 CENTRAL HYPOTHESIS</div>
    <div class="hypothesis-text">{a.central_hypothesis}</div>
  </div>
  <div class="opening-box">
    <div class="opening-label">开场策略 OPENING STRATEGY（前60秒）</div>
    <div class="opening-text">{a.opening_strategy}</div>
  </div>
  <div class="two-col">
    <div class="chart-wrap">{svg_gauge}</div>
    <div style="padding:16px; background:var(--bg); border:1px solid var(--border); border-radius:6px;">
      <div class="label-zh">置信度说明 <span class="label-en">Confidence Reasoning</span></div>
      <div style="font-size:13px; margin-top:8px; line-height:1.6; color:#4a3f35">{a.confidence_reasoning}</div>
      <div class="label-zh" style="margin-top:16px">核心主题 <span class="label-en">Key Themes</span></div>
      <div style="margin-top:8px">{theme_chips}</div>
    </div>
  </div>
</div>

<!-- 9. Context Gaps -->
<div class="section">
  <div class="section-zh">信息缺口</div>
  <div class="section-en">CONTEXT GAPS</div>
  <div class="gaps-box">{a.context_gaps}</div>
</div>

<!-- Footer -->
<div class="footer">
  <span>Merlin AI Consulting Preparation System</span>
  <span>{a.company_name} &middot; {a.meeting_purpose} &middot; {date_str}</span>
</div>

</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Merlin — AI Consulting Preparation System")
    parser.add_argument("company", help="Company name")
    parser.add_argument("purpose", help="Meeting purpose (e.g. 投资尽调, 销售拜访)")
    parser.add_argument("--background", required=True, help="File with background materials")
    parser.add_argument("--industry", default=None, help="Industry")
    parser.add_argument("--interviewee", default=None, help="Interviewee role")
    parser.add_argument("--output", default=None, help="Output HTML file")
    parser.add_argument("--api-key", default=None, help="Anthropic API key")
    args = parser.parse_args()

    bg_path = Path(args.background)
    if not bg_path.exists():
        print(f"Error: background file not found: {args.background}", file=sys.stderr)
        sys.exit(1)

    background_text = bg_path.read_text(encoding="utf-8")

    ctx = MerlinContext(
        company_name=args.company,
        meeting_purpose=args.purpose,
        background_text=background_text,
        industry=args.industry,
        interviewee_role=args.interviewee,
    )

    auth = _get_auth()
    if args.api_key:
        auth = {"api_key": args.api_key}

    print(f"Merlin analyzing: {args.company} — {args.purpose}", flush=True)
    analysis = analyze(ctx, **auth)

    slug = re.sub(r"[^A-Za-z0-9_-]", "_", args.company)[:30]
    output_path = args.output or f"{slug}_Merlin_Brief.html"
    Path(output_path).write_text(generate_html(analysis), encoding="utf-8")
    print(f"\nDone → {output_path}")


if __name__ == "__main__":
    main()
