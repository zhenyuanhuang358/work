#!/usr/bin/env python3
"""
Merlin Research Mode — four-agent client outline research.

Usage:
    python merlin_research.py "<COMPANY>" --outline <file> [options]

Options:
    --outline FILE        Client's research outline / questionnaire
    --background FILE     Optional pre-loaded background materials
    --industry TEXT       Industry classification
    --output FILE         Output HTML (default: {company}_Research_Report.html)
    --api-key KEY         Anthropic API key (or set ANTHROPIC_API_KEY)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from merlin.research_agents import ResearchResult, run_research
from merlin.research_prompts import ResearchContext


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

def _svg_section_confidence(sections: list, answers: list) -> str:
    """Horizontal confidence bars per section."""
    if not sections:
        return '<svg viewBox="0 0 520 60" xmlns="http://www.w3.org/2000/svg"><text x="260" y="30" text-anchor="middle" font-size="12" fill="#6b5a47">No sections</text></svg>'

    conf_map = {a.get("section_id"): a.get("confidence", "medium") for a in answers}
    conf_color = {"high": "#2a5c3f", "medium": "#c47a1e", "low": "#8b2e2e"}
    conf_w = {"high": 380, "medium": 240, "low": 100}
    conf_zh = {"high": "高", "medium": "中", "low": "低"}

    row_h = 40
    pad_t = 36
    W = 520
    H = pad_t + len(sections) * row_h + 16

    rows = ""
    for s in sections:
        sid = s.get("id", 0)
        title = s.get("title", f"Section {sid}")
        title = title[:44] + "…" if len(title) > 44 else title
        conf = conf_map.get(sid, "medium")
        color = conf_color.get(conf, "#c47a1e")
        w = conf_w.get(conf, 200)
        ry = pad_t + (sid - 1) * row_h

        rows += f'''
  <rect x="20" y="{ry+4}" width="{w}" height="26" fill="{color}" fill-opacity="0.15" rx="4"/>
  <rect x="20" y="{ry+4}" width="4" height="26" fill="{color}" rx="2"/>
  <text x="30" y="{ry+22}" font-size="11" fill="#0a0a0b">{sid}. {title}</text>
  <text x="{W-8}" y="{ry+22}" text-anchor="end" font-size="10" fill="{color}" font-weight="bold">{conf_zh.get(conf,"?")}</text>'''

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  <text x="{W/2:.0f}" y="22" text-anchor="middle" font-size="12" fill="#0a0a0b" font-weight="bold">各节置信度 Section Confidence</text>
  {rows}
</svg>'''


def _svg_agent_flow() -> str:
    """Static four-agent pipeline diagram."""
    W, H = 520, 100
    agents = [
        ("情报员", "Scout", 70, "#8b6c42"),
        ("分析师", "Analyst", 210, "#2a5c3f"),
        ("侦探", "Forensic", 350, "#8b2e2e"),
        ("战略家", "Strategist", 490, "#4a6fa5"),
    ]
    nodes = ""
    for zh, en, cx, color in agents:
        nodes += f'''
  <circle cx="{cx}" cy="50" r="28" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="1.5"/>
  <text x="{cx}" y="46" text-anchor="middle" font-size="11" fill="{color}" font-weight="bold">{zh}</text>
  <text x="{cx}" y="60" text-anchor="middle" font-size="9" fill="{color}" font-style="italic">{en}</text>'''

    arrows = ""
    xs = [70, 210, 350]
    for x in xs:
        arrows += f'<line x1="{x+28}" y1="50" x2="{x+112}" y2="50" stroke="#d4cfc8" stroke-width="1.5" marker-end="url(#arr)"/>'

    return f'''<svg viewBox="0 0 {W} {H}" font-family="'IM Fell English',Georgia,serif" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#d4cfc8"/>
    </marker>
  </defs>
  <rect width="{W}" height="{H}" fill="#f9f7f3" rx="6"/>
  {arrows}
  {nodes}
</svg>'''


# ── HTML Report ───────────────────────────────────────────────────────────────

def _conf_badge(conf: str) -> str:
    colors = {"high": "#2a5c3f", "medium": "#c47a1e", "low": "#8b2e2e"}
    labels = {"high": "高置信", "medium": "中置信", "low": "低置信"}
    c = colors.get(conf, "#6b5a47")
    l = labels.get(conf, conf)
    return f'<span style="display:inline-block;padding:1px 8px;border-radius:2px;font-size:10px;font-weight:bold;background:{c}22;color:{c};border:1px solid {c}66">{l}</span>'


def _integrity_color(integrity: str) -> str:
    return {"high": "#2a5c3f", "medium": "#c47a1e", "low": "#8b2e2e"}.get(integrity, "#6b5a47")


def generate_research_html(r: ResearchResult) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Build section title lookup
    section_titles = {s.get("id"): s.get("title", f"Section {s.get('id')}") for s in r.sections}

    # Answer cards
    answer_cards = ""
    for ans in r.answers:
        sid = ans.get("section_id", "?")
        title = section_titles.get(sid, f"Section {sid}")
        conf = ans.get("confidence", "medium")
        answer = ans.get("answer", "")
        caveat = ans.get("caveat", "")
        data_points = ans.get("supporting_data", [])
        flags = ans.get("red_flags", [])

        dp_html = "".join(f'<li>{dp}</li>' for dp in data_points)
        flag_html = ""
        if flags:
            flag_html = "".join(
                f'<div class="ans-flag">⚑ {f}</div>' for f in flags if f
            )

        answer_cards += f'''
        <div class="ans-card">
          <div class="ans-header">
            <span class="ans-num">{sid}</span>
            <span class="ans-title">{title}</span>
            {_conf_badge(conf)}
          </div>
          <div class="ans-body">{answer}</div>
          {"<ul class='ans-data'>" + dp_html + "</ul>" if dp_html else ""}
          {flag_html}
          {"<div class='ans-caveat'>注意 · " + caveat + "</div>" if caveat else ""}
        </div>'''

    # Red flag rows
    flag_rows = ""
    sev_color = {"high": "#8b2e2e", "medium": "#c47a1e", "low": "#2a5c3f"}
    sev_zh = {"high": "高", "medium": "中", "low": "低"}
    type_zh = {
        "contradiction": "数据矛盾",
        "narrative_gap": "叙事缺口",
        "absence": "信息缺失",
        "timing": "时序异常",
        "source_conflict": "来源冲突",
    }
    for flag in r.red_flags:
        sev = flag.get("severity", "medium")
        sc = sev_color.get(sev, "#6b5a47")
        ftype = type_zh.get(flag.get("type", ""), flag.get("type", ""))
        flag_rows += f'''
        <tr>
          <td><span style="color:{sc};font-weight:bold">{sev_zh.get(sev,"?")} </span></td>
          <td>{ftype}</td>
          <td>{flag.get("description","")}</td>
          <td style="color:var(--copper);font-style:italic">{flag.get("resolution_question","")}</td>
        </tr>'''

    integ_color = _integrity_color(r.overall_integrity)
    high_count = sum(1 for a in r.answers if a.get("confidence") == "high")
    med_count = sum(1 for a in r.answers if a.get("confidence") == "medium")
    low_count = sum(1 for a in r.answers if a.get("confidence") == "low")

    svg_conf = _svg_section_confidence(r.sections, r.answers)
    svg_flow = _svg_agent_flow()

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Merlin Research — {r.company_name}</title>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#0a0a0b; --paper:#f1efea; --copper:#8b6c42; --gold:#c9a84c;
  --green:#2a5c3f; --red:#8b2e2e; --amber:#c47a1e; --bg:#f9f7f3;
  --border:#d4cfc8;
}}
*{{box-sizing:border-box; margin:0; padding:0;}}
body{{background:var(--paper); color:var(--ink); font-family:'IM Fell English',Georgia,serif; max-width:900px; margin:0 auto; padding:32px 24px;}}
.pub-bar{{display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid var(--ink); padding-bottom:8px; margin-bottom:28px;}}
.pub-logo{{font-size:22px; letter-spacing:.12em; color:var(--copper);}}
.pub-meta{{font-size:11px; color:var(--copper); text-align:right;}}
.report-title{{font-size:34px; line-height:1.15; margin-bottom:6px;}}
.report-subtitle{{font-size:14px; color:var(--copper); letter-spacing:.08em; margin-bottom:16px;}}
.tag-row{{display:flex; gap:10px; flex-wrap:wrap; margin-bottom:28px;}}
.tag{{border:1px solid var(--copper); color:var(--copper); font-size:11px; padding:3px 10px; border-radius:2px; letter-spacing:.06em;}}
.stat-bar{{display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:32px;}}
.stat-cell{{background:var(--bg); border:1px solid var(--border); padding:14px; text-align:center;}}
.stat-val{{font-size:26px; color:var(--copper); font-weight:bold;}}
.stat-lbl{{font-size:10px; color:#6b5a47; margin-top:2px; letter-spacing:.06em;}}
.section{{margin-bottom:36px;}}
.section-zh{{font-size:20px; font-weight:bold; border-bottom:1px solid var(--border); padding-bottom:4px; margin-bottom:4px;}}
.section-en{{font-size:11px; color:var(--copper); letter-spacing:.1em; margin-bottom:16px;}}
.chart-wrap{{background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:8px; margin-bottom:16px;}}
.chart-wrap svg{{width:100%; height:auto; display:block;}}
/* Executive summary */
.exec-box{{background:var(--ink); color:var(--paper); padding:20px 24px; margin-bottom:20px; border-radius:4px;}}
.exec-label{{font-size:10px; color:var(--gold); letter-spacing:.12em; margin-bottom:8px;}}
.exec-text{{font-size:14px; line-height:1.7;}}
.verdict-box{{background:var(--bg); border:1px solid var(--copper); border-left:4px solid var(--copper); padding:12px 18px; margin-bottom:20px; font-size:13px; color:#4a3f35; font-style:italic;}}
/* Answer cards */
.ans-card{{background:var(--bg); border:1px solid var(--border); border-radius:4px; padding:18px; margin-bottom:14px;}}
.ans-header{{display:flex; align-items:center; gap:10px; margin-bottom:10px; flex-wrap:wrap;}}
.ans-num{{width:28px; height:28px; border-radius:50%; background:var(--copper); color:var(--paper); display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:bold; flex-shrink:0;}}
.ans-title{{font-size:15px; font-weight:bold; flex:1;}}
.ans-body{{font-size:13px; line-height:1.7; margin-bottom:10px;}}
.ans-data{{font-size:11px; color:#4a3f35; padding-left:18px; margin-bottom:8px; line-height:1.6;}}
.ans-flag{{font-size:11px; color:var(--red); background:#8b2e2e11; border-left:3px solid var(--red); padding:4px 10px; margin-bottom:4px;}}
.ans-caveat{{font-size:11px; color:var(--amber); font-style:italic; margin-top:6px;}}
/* Flag table */
.flag-table{{width:100%; border-collapse:collapse; font-size:12px;}}
.flag-table th{{background:var(--ink); color:var(--paper); padding:8px 10px; text-align:left; font-size:11px; letter-spacing:.06em;}}
.flag-table td{{padding:9px; border-bottom:1px solid var(--border); vertical-align:top;}}
.flag-table tr:nth-child(even) td{{background:var(--bg);}}
.footer{{margin-top:48px; border-top:1px solid var(--border); padding-top:16px; font-size:11px; color:#6b5a47; display:flex; justify-content:space-between;}}
</style>
</head>
<body>

<!-- Pub Bar -->
<div class="pub-bar">
  <div class="pub-logo">MERLIN RESEARCH</div>
  <div class="pub-meta">客户提纲研究报告 &nbsp;|&nbsp; {date_str} &nbsp;|&nbsp; 四智能体协作</div>
</div>

<!-- Title -->
<div class="report-title">{r.company_name}</div>
<div class="report-subtitle">CLIENT OUTLINE RESEARCH REPORT</div>
<div class="tag-row">
  <span class="tag">{len(r.sections)} 节提纲</span>
  <span class="tag">{len(r.answers)} 条回答</span>
  <span class="tag">{len(r.red_flags)} 个风险信号</span>
  <span class="tag" style="border-color:{integ_color};color:{integ_color}">数据完整性 {r.overall_integrity.upper()}</span>
</div>

<!-- Stat bar -->
<div class="stat-bar">
  <div class="stat-cell">
    <div class="stat-val" style="color:var(--green)">{high_count}</div>
    <div class="stat-lbl">高置信回答 HIGH CONF</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val" style="color:var(--amber)">{med_count}</div>
    <div class="stat-lbl">中置信回答 MED CONF</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val" style="color:var(--red)">{low_count}</div>
    <div class="stat-lbl">低置信回答 LOW CONF</div>
  </div>
  <div class="stat-cell">
    <div class="stat-val">{len(r.red_flags)}</div>
    <div class="stat-lbl">风险信号 RED FLAGS</div>
  </div>
</div>

<!-- Agent pipeline diagram -->
<div class="section">
  <div class="section-zh">四智能体协作流程</div>
  <div class="section-en">FOUR-AGENT PIPELINE</div>
  <div class="chart-wrap">{svg_flow}</div>
</div>

<!-- Executive Summary -->
<div class="section">
  <div class="section-zh">执行摘要</div>
  <div class="section-en">EXECUTIVE SUMMARY</div>
  <div class="exec-box">
    <div class="exec-label">战略家综合判断 STRATEGIST SYNTHESIS</div>
    <div class="exec-text">{r.executive_summary}</div>
  </div>
  <div class="verdict-box">{r.data_verdict}</div>
</div>

<!-- Section confidence -->
<div class="section">
  <div class="section-zh">各节置信度</div>
  <div class="section-en">SECTION CONFIDENCE MAP</div>
  <div class="chart-wrap">{svg_conf}</div>
</div>

<!-- Answers -->
<div class="section">
  <div class="section-zh">逐条回答</div>
  <div class="section-en">ANSWERS BY SECTION</div>
  {answer_cards}
</div>

<!-- Red flags -->
<div class="section">
  <div class="section-zh">风险信号</div>
  <div class="section-en">RED FLAGS &amp; CONTRADICTIONS</div>
  <table class="flag-table">
    <thead>
      <tr>
        <th>严重度</th>
        <th>类型 TYPE</th>
        <th>描述 DESCRIPTION</th>
        <th>解决问题 RESOLUTION Q</th>
      </tr>
    </thead>
    <tbody>{flag_rows if flag_rows else '<tr><td colspan="4" style="text-align:center;color:#6b5a47;padding:16px">No significant red flags detected</td></tr>'}</tbody>
  </table>
</div>

<div class="footer">
  <span>Merlin Research Mode · 四智能体协作</span>
  <span>{r.company_name} · {date_str}</span>
</div>

</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Merlin Research — four-agent client outline research")
    parser.add_argument("company", help="Company name")
    parser.add_argument("--outline", required=True, help="Client outline / questionnaire file")
    parser.add_argument("--background", default=None, help="Optional pre-loaded background materials")
    parser.add_argument("--industry", default=None, help="Industry")
    parser.add_argument("--output", default=None, help="Output HTML file")
    parser.add_argument("--api-key", default=None, help="Anthropic API key")
    args = parser.parse_args()

    outline_path = Path(args.outline)
    if not outline_path.exists():
        print(f"Error: outline file not found: {args.outline}", file=sys.stderr)
        sys.exit(1)

    outline_text = outline_path.read_text(encoding="utf-8")
    background_text = ""
    if args.background:
        bg_path = Path(args.background)
        if bg_path.exists():
            background_text = bg_path.read_text(encoding="utf-8")

    ctx = ResearchContext(
        company_name=args.company,
        outline_text=outline_text,
        industry=args.industry,
        background_text=background_text,
    )

    auth = _get_auth()
    if args.api_key:
        auth = {"api_key": args.api_key}

    print(f"Merlin Research: {args.company}", flush=True)
    result = run_research(ctx, **auth)

    slug = re.sub(r"[^A-Za-z0-9_-]", "_", args.company)[:30]
    output_path = args.output or f"{slug}_Research_Report.html"
    Path(output_path).write_text(generate_research_html(result), encoding="utf-8")
    print(f"\nDone → {output_path}")


if __name__ == "__main__":
    main()
