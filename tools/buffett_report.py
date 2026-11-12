#!/usr/bin/env python3
"""巴菲特报告通用模板（2026-11-10）：估值输入 + 叙述 JSON → reports/<slug>_Buffett_Report.html。

为什么：KO、NVDA 各手写了一份约 350 行的生成脚本，Critic 共 8 轮，退回原因多是脚本里写死的旧数字、
图表说明与正文不一致、敏感性底稿抄旧评分。这里把结构、图表和所有数字固定在模板里：
- 数字只从 owner_value 的结果读；护城河敏感性由模板改分数重跑 owner_value（评分随之重算）。
- 分析师只写叙述 JSON（证据、判断、风险）。叙述里要引用数字时用占位符，不手写：
  {lo} {hi} {price} {mos} {buy} {hurdle} {total} {rating} {implied} {cap} {moat}

用法：python3 tools/buffett_report.py <估值输入.json> <叙述.json> [--out reports/]
叙述 JSON 字段见 tests/fixtures/buffett/nvda_narrative.json（冻结样例）。
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owner_value as ov  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "font-family:'IM Fell English',Georgia,serif"
INK, PAPER, COPPER, GOLD, GREEN, RED, AMBER = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#c47a1e"
BANDS = [(4, "3–4 = 窄护城河", 0.08, 0.03), (6, "5–6 = 中等", 0.12, 0.05), (8, "7–8 = 宽护城河", 0.18, 0.08), (10, "9–10 = 卓越", 0.25, 0.10)]
SCORE_NAMES = {"1A": "护城河强度", "1B": "收入稳定性", "1C": "定价权", "2A": "资本回报率", "2B": "FCF 质量", "2C": "资产负债表",
               "3A": "资本分配", "3B": "利益一致", "3C": "沟通诚实度", "4A": "安全边际", "4B": "相对估值"}


def rating(total):
    return ("强力买入区域" if total >= 85 else "等待买入" if total >= 70 else "观察名单" if total >= 55 else "谨慎" if total >= 40 else "排除")


def m(x):
    return f"${x / 1000:,.1f}B"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def tr(cells, head=False):
    tag = "th" if head else "td"
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def badge(level):
    c = {"高": GREEN, "中": AMBER, "低": RED}[level]
    return f'<span class="badge" style="border:1px solid {c};color:{c}">置信 {level}</span>'


def price_svg(lo, hi, price, buy, hurdle, moat):
    vmax = max(hi, price) * 1.25
    X = lambda v: 40 + 560 * v / vmax  # noqa: E731
    step = max(10, int(vmax / 8 / 10) * 10)
    o = [f'<svg viewBox="0 0 660 150" style="{FONT};width:100%"><line x1="40" y1="90" x2="600" y2="90" stroke="{COPPER}"/>']
    for t in range(0, int(vmax) + 1, step):
        o.append(f'<line x1="{X(t):.1f}" y1="87" x2="{X(t):.1f}" y2="93" stroke="{COPPER}"/><text x="{X(t):.1f}" y="108" font-size="10" text-anchor="middle" fill="{COPPER}">{t}</text>')
    o.append(f'<rect x="{X(lo):.1f}" y="72" width="{X(hi) - X(lo):.1f}" height="36" fill="{GOLD}" opacity="0.35"/>')
    pts = sorted([(buy, f"建仓线 {buy:.2f}", GREEN), (lo, f"下沿 {lo:.2f}", INK), (hi, f"上沿 {hi:.2f}", INK), (price, f"现价 {price:.2f}", RED)])
    for i, (v, lab, c) in enumerate(pts):  # 标签按价位高低错开三层，避免重叠
        y = (24, 42, 60, 24)[i]
        o.append(f'<line x1="{X(v):.1f}" y1="{y + 6}" x2="{X(v):.1f}" y2="114" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{X(v):.1f}" y="{y}" font-size="12" text-anchor="middle" fill="{c}">{lab}</text>')
    o.append(f'<text x="40" y="136" font-size="11" fill="{COPPER}">每股。金色带 = 内在价值区间（护城河 {moat} 分，两情景 DCF）；建仓线 = 下沿 × {1 - hurdle:.0%}（安全边际 {hurdle:.0%}）</text>')
    return "".join(o) + "</svg>"


def moat_svg(moat):
    b = next(x for x in BANDS if moat <= x[0])
    o = [f'<svg viewBox="0 0 660 70" style="{FONT};width:100%">']
    for i in range(10):
        o.append(f'<rect x="{40 + i * 58}" y="14" width="52" height="22" fill="{GOLD if i < moat else "#ddd6c8"}"/><text x="{66 + i * 58}" y="52" font-size="10" text-anchor="middle" fill="{COPPER}">{i + 1}</text>')
    o.append(f'<text x="40" y="66" font-size="11" fill="{COPPER}">护城河评分 {moat} / 10（{b[1]}：阶段 1 增速上限 {b[2]:.0%}，终端增长上限 {b[3]:.0%}）</text>')
    return "".join(o) + "</svg>"


def trend_svg(ys, norm):
    series = [("净利润", [y["net_income"] for y in ys], INK, ""), ("FCF（报告值）", [y.get("fcf_reported", y["fcf"]) for y in ys], RED, "")]
    if norm:
        series.append(("FCF（剔除一次性项）", [y["fcf"] for y in ys], GREEN, "5,4"))
    vmax = max(max(v) for _, v, _, _ in series) * 1.15
    Y = lambda v: 190 - 170 * max(v, 0) / vmax  # noqa: E731
    X = lambda i: 70 + 530 * i / (len(ys) - 1)  # noqa: E731
    o = [f'<svg viewBox="0 0 660 240" style="{FONT};width:100%">']
    for k in range(5):
        t = vmax * k / 4
        o.append(f'<line x1="70" y1="{Y(t):.1f}" x2="600" y2="{Y(t):.1f}" stroke="#e2dccf"/><text x="62" y="{Y(t) + 4:.1f}" font-size="10" text-anchor="end" fill="{COPPER}">{t / 1000:.0f}B</text>')
    for j, (n, vals, c, dash) in enumerate(series):
        o.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))}" fill="none" stroke="{c}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
        for i, v in enumerate(vals):
            o.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.5" fill="{c}"/><text x="{X(i) + 6:.1f}" y="{Y(v) + (-8, 16, -8)[j]:.1f}" font-size="10" fill="{c}">{v / 1000:.1f}</text>')
        o.append(f'<rect x="{70 + j * 180}" y="224" width="10" height="10" fill="{c}"/><text x="{84 + j * 180}" y="233" font-size="11" fill="{INK}">{n}</text>')
    for i, y in enumerate(ys):
        o.append(f'<text x="{X(i):.1f}" y="208" font-size="12" text-anchor="middle" fill="{INK}">FY{y["fy"]}</text>')
    return "".join(o) + "</svg>"


def score_svg(sc):
    dims = (("Business Quality", "business", 30), ("Financial Health", "financial", 30), ("Management Quality", "management", 25), ("Price vs Value", "price", 15))
    o = [f'<svg viewBox="0 0 660 160" style="{FONT};width:100%">']
    for i, (n, k, mx) in enumerate(dims):
        y = 14 + i * 34
        o.append(f'<text x="0" y="{y + 14}" font-size="12" fill="{INK}">{n}</text><rect x="170" y="{y}" width="{mx * 14}" height="20" fill="#ddd6c8"/>'
                 f'<rect x="170" y="{y}" width="{sc[k] * 14}" height="20" fill="{GOLD}"/><text x="{176 + mx * 14}" y="{y + 15}" font-size="12" fill="{COPPER}">{sc[k]} / {mx}</text>')
    o.append(f'<text x="0" y="154" font-size="11" fill="{COPPER}">总分 {sc["total"]} / 100 → {rating(sc["total"])}</text>')
    return "".join(o) + "</svg>"


def build(inp, nar):
    V = ov.run(copy.deepcopy(inp))
    if "iv_range" not in V:
        sys.exit(V.get("verdict", "没有估值结果"))
    if "scorecard_detail" not in V:
        sys.exit("模板要求估值输入带 score_facts（评分由工具查表），见 owner_value.auto_scores")
    lo, hi = V["iv_range"]
    mo = V["margin_of_safety"]
    price, mos, hurdle = mo["price"], mo["value"], mo["hurdle"]
    buy, sc, sd = lo * (1 - hurdle), V["scorecard"], V["scorecard_detail"]
    ig, moat = V.get("implied_g1"), inp["moat_score"]
    band = next(x for x in BANDS if moat <= x[0])
    cs, bs, oe = V["scenarios"]["conservative"], V["scenarios"]["base"], V["owner_earnings"]
    F = {"lo": f"{lo:.2f}", "hi": f"{hi:.2f}", "price": f"{price:.2f}", "mos": f"{mos * 100:.1f}%", "buy": f"{buy:.2f}", "hurdle": f"{hurdle:.0%}",
         "total": sc["total"], "rating": rating(sc["total"]), "implied": pct(ig["g1"]) if ig else "—", "cap": f"{band[2]:.0%}", "moat": moat}
    t = lambda s: str(s).format_map(F)  # noqa: E731
    ys = ov.normalize(inp["years"], {"flags": []})
    sf = inp["score_facts"]
    fin = [("营收", [m(y["revenue"]) for y in ys]), ("毛利率", [pct(g) for g in sf["gross_margin"]]), ("净利润（GAAP）", [m(y["net_income"]) for y in ys]),
           ("营业利润（EBIT）", [m(y["ebit"]) for y in ys]), ("FCF（报告值 = CFO − Capex）", [m(y.get("fcf_reported", y["fcf"])) for y in ys])]
    if V["normalization"]:
        fin.append(("FCF（剔除一次性项）", [m(y["fcf"]) for y in ys]))
    fin += [("FCF / 净利润（报告值）", [pct(y.get("fcf_reported", y["fcf"]) / y["net_income"], 0) for y in ys]), ("ROE（GAAP）", [pct(r) for r in sf["roe"]])]
    if sf.get("roic"):
        fin.append(("ROIC", [pct(r) for r in sf["roic"]]))
    # 护城河敏感性：改分数重跑，评分随之重算（不抄主底稿）
    sens_m = []
    for ms in sorted(set([moat] + list(nar.get("sensitivity_moats", [])))):
        v = V if ms == moat else ov.run(dict(copy.deepcopy(inp), moat_score=ms))
        b = next(x for x in BANDS if ms <= x[0])
        note = "本报告采用" if ms == moat else ("安全边际低于门槛：观察、非买入" if v["margin_of_safety"]["value"] < hurdle else "达到门槛")
        sens_m.append(tr([f"{ms} 分", f"{b[2]:.0%}", f"{v['iv_range'][0]:.2f}–{v['iv_range'][1]:.2f}", f"{v['margin_of_safety']['value'] * 100:.1f}%",
                          f"{v['scorecard']['total']}（{rating(v['scorecard']['total'])}）", note]))
    base = V["base"]["kind"] + (f"，截至 {V['base']['period_end']}" if V["base"].get("period_end") else f" FY{V['base'].get('fy')}")
    cross = ""
    for nm, s_ in (("保守", cs), ("基准", bs)):
        if "exit_multiple_iv" in s_:
            cross += f"{nm}情景终值占比 {pct(s_['terminal_share'], 0)}，超过 60%；股权口径交叉验证每股 {s_['exit_multiple_iv']:.2f}，与 DCF 相差 {abs(s_['exit_multiple_iv'] / (s_['pv_cash'] + s_['pv_terminal']) * inp['shares']['v'] - 1) * 100:.0f}%。"
    cross = cross or f"两个情景终值占比 {pct(cs['terminal_share'], 0)} / {pct(bs['terminal_share'], 0)}，都不超过 60%，不触发交叉验证。"
    dims = [("Business Quality", "business", 30, ("1A", "1B", "1C")), ("Financial Health", "financial", 30, ("2A", "2B", "2C")),
            ("Management Quality", "management", 25, ("3A", "3B", "3C")), ("Price vs Value", "price", 15, ("4A", "4B"))]
    score_rows = "".join(tr([n, mx, sc[k], "；".join(f"{i} {SCORE_NAMES[i]} {sd[i]['score']}：{sd[i]['why']}" for i in ids)]) for n, k, mx, ids in dims)
    zone = V["zone"].split("（")[0]
    verdict = f"现价 {price:.2f}，内在价值 {lo:.2f}–{hi:.2f}，安全边际（下沿）{mos * 100:.1f}%，门槛 {hurdle:.0%}；{buy:.2f} 以下才进入买入区间。"
    flags = "".join(f"<li>{f}</li>" for f in V["flags"])
    css = f""":root{{--ink:{INK};--paper:{PAPER};--copper:{COPPER};--gold:{GOLD}}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Songti SC','Noto Serif SC','IM Fell English',serif;line-height:1.75}}
.wrap{{max-width:860px;margin:0 auto;padding:28px 18px 60px}}
.pub{{display:flex;justify-content:space-between;font-size:12px;color:var(--copper);border-bottom:1px solid var(--copper);padding-bottom:6px}}
h1{{font-size:30px;margin:18px 0 2px}} .en{{font-family:'IM Fell English',serif;color:var(--copper);font-style:italic}}
h2{{font-size:20px;margin:34px 0 8px;border-bottom:2px solid var(--gold);padding-bottom:4px}}
.stat{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:18px 0}} .stat div{{background:#fff;border:1px solid #e2dccf;padding:10px}}
.stat b{{display:block;font-size:20px}} .stat span{{font-size:12px;color:var(--copper)}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}} th,td{{border-bottom:1px solid #e2dccf;padding:6px;text-align:left;vertical-align:top}} th{{color:var(--copper);font-weight:normal}}
.verdict{{background:var(--ink);color:var(--paper);padding:20px 22px;margin:26px 0}} .verdict .en{{color:var(--gold);opacity:.8}}
.src{{font-size:12px;color:var(--copper)}} .badge{{font-size:11px;padding:0 6px;margin-left:6px;white-space:nowrap}}
.note{{margin-top:36px;border-top:1px solid var(--copper);padding-top:12px;font-size:13px}}
@media(max-width:600px){{.stat{{grid-template-columns:repeat(2,1fr)}} table{{font-size:12px}}}}"""
    P = lambda k: "".join(f"<p>{t(x)}</p>" for x in nar.get(k, []))  # noqa: E731
    val_path = f"memory/state/valuations/{inp['ticker'].lower()}_{inp.get('as_of')}.json"
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nar['name_zh']} {inp['ticker']} 巴菲特模型分析</title>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English&display=swap" rel="stylesheet"><style>{css}</style></head>
<body><div class="wrap" data-valuation="{val_path}">
<div class="pub"><span>巴菲特模型分析报告 · Buffett Model Report</span><span>分析日期 {inp.get('as_of')} · 股价日期 {nar['price_date']}</span></div>
<h1>{nar['name_zh']}（{inp['ticker']}）</h1><div class="en">{nar['name_en']} — Moat, Owner Earnings and Margin of Safety</div>
<div class="stat"><div><b>{lo:.2f}–{hi:.2f}</b><span>内在价值区间（每股）</span></div><div><b>{price:.2f}</b><span>现价（{nar['price_date']} 收盘）</span></div>
<div><b>{mos * 100:.1f}%</b><span>安全边际（按下沿；门槛 {hurdle:.0%}）</span></div><div><b>{sc['total']} / 100</b><span>巴菲特评分 → {rating(sc['total'])}</span></div></div>
<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<ul>{"".join(f"<li>{t(b['text'])}{badge(b['conf'])}</li>" for b in nar['bottom_line'])}</ul>
{price_svg(lo, hi, price, buy, hurdle, moat)}
<h2>一、护城河分析 <span class="en">Moat</span></h2>
{moat_svg(moat)}
<p>{t(nar['moat']['lead'])}</p>
<table>{tr(["维度（五类）", "证据", "判定"], True)}{"".join(tr([t(c) for c in r]) for r in nar['moat']['dims'])}</table>
<p>{t(nar['moat']['why'])}</p><p class="src">来源：{t(nar['moat']['src'])}</p>
<h2>二、核心财务指标 <span class="en">Financials</span></h2>
<p>{t(nar['fin']['lead'])}</p>
{trend_svg(ys, V['normalization'])}
<table>{tr(["指标"] + [f"FY{y['fy']}" for y in ys], True)}{"".join(tr([n] + v) for n, v in fin)}</table>
{"".join(f"<p>{t(x)}</p>" for x in nar['fin'].get('notes', []))}<p class="src">来源：{t(nar['fin']['src'])}</p>
<h2>三、管理层评估 <span class="en">Management</span></h2>
<p>{t(nar['mgmt']['lead'])}</p>
<table>{tr(["行为（近 3 年）", "数据", "评分影响"], True)}{"".join(tr([t(c) for c in r]) for r in nar['mgmt']['rows'])}</table>
<p>3A {sd['3A']['score']}：{sd['3A']['why']}。3B {sd['3B']['score']}：{sd['3B']['why']}。3C {sd['3C']['score']}：{sd['3C']['why']}。</p><p class="src">来源：{t(nar['mgmt']['src'])}</p>
<h2>四、内在价值估算 <span class="en">Owner Earnings DCF</span></h2>
<p><strong>内在价值 {lo:.2f}–{hi:.2f}，现价 {price:.2f}，安全边际（下沿）{mos * 100:.1f}%：{zone}。</strong></p>
<p>估值路径：{V['route']}，安全边际门槛 {hurdle:.0%}。基数：{base}。所有者盈余 {m(oe['value'])}（维护性资本支出 {m(oe['maint_capex'])}：{oe.get('why') or oe['method']}）。</p>
{"<ul>" + flags + "</ul>" if flags else ""}{P('valuation_notes')}
<table>{tr(["参数", "保守情景", "基准情景", "依据"], True)}
{tr(["阶段 1 增速（1–5 年）", pct(cs['g1'], 2), pct(bs['g1'], 2), f"护城河 {moat} 分的上限为 {band[2]:.0%}"])}
{tr(["阶段 2 增速（6–10 年）", pct(cs['g2'], 2), pct(bs['g2'], 2), "阶段 1 × 50% / × 60%"])}
{tr(["终端增长率", pct(cs['g_terminal'], 1), pct(bs['g_terminal'], 1), f"上限 {band[3]:.0%} × 60% / × 80%，再受 2.5% / 3% 封顶"])}
{tr(["折现率", pct(inp['r']['v'], 0), pct(inp['r']['v'], 0), inp['r']['src']])}
{tr(["每股内在价值", f"{lo:.2f}", f"{hi:.2f}", "两情景 DCF ÷ 股数"])}</table>
<p>{cross}</p>
<table>{tr(["护城河评分", "阶段 1 增速上限", "内在价值区间", "安全边际（下沿）", "总分", "说明"], True)}{"".join(sens_m)}</table>
<table>{tr(["价格锚点", "价位", "说明"], True)}{tr(["内在价值下沿", f"{lo:.2f}", "安全边际的计算基准"])}{tr(["当前股价", f"{price:.2f}", nar['price_date']])}
{tr(["当前安全边际", f"{mos * 100:.1f}%", "(下沿 − 现价) ÷ 下沿"])}{tr([f"目标买入价（安全边际 {hurdle:.0%}）", f"{buy:.2f}", f"下沿 × {1 - hurdle:.0%}"])}</table>
{f"<p>逆向验证：按基准情景结构倒推，现价要求阶段 1 增速 {pct(ig['g1'])}；护城河 {moat} 分的上限是 {band[2]:.0%}，" + ("现价隐含增速超过上限。" if ig['exceeds_cap'] else "在上限之内。") + "</p>" if ig else ""}
<p class="src">来源：owner_value 底稿 {val_path}（每个输入带来源）。</p>
<div class="verdict"><strong>裁决：{rating(sc['total'])}档，{zone}。</strong>{verdict}<div class="en">{t(nar['verdict_en'])}</div></div>
<p class="src">未核实项：{t(nar['unverified'])}</p>
<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
{score_svg(sc)}
<table>{tr(["维度", "满分", "得分", "逐项依据（工具按 berkshire-score.md 查表；3A–3C 为分析师判断）"], True)}{score_rows}{tr(["总分", 100, sc['total'], rating(sc['total'])])}</table>
<h2>六、主要风险 <span class="en">Risks</span></h2>
<table>{tr(["风险", "说明", "对估值的影响"], True)}{"".join(tr([t(c) for c in r]) for r in nar['risks'])}</table><p>{t(nar['retrigger'])}</p>
<h2>七、数据盲区与敏感性 <span class="en">Gaps and Sensitivity</span></h2>
<ul>{"".join(f"<li>{t(g)}</li>" for g in nar['gaps'])}</ul>
<table>{tr(["变量（以保守情景为底）", "变动", "每股内在价值", "变化"], True)}{"".join(tr([{"r": "折现率 r", "g1": "阶段 1 增速 g1", "g_terminal": "终端增长率"}[x["var"]], f"{x['delta'] * 100:+.1f} 个百分点", f"{x['iv_per_share']:.2f}", f"{x['change'] * 100:+.0f}%"]) for x in V["sensitivity"]["rows"])}</table>
<h2>来源索引 <span class="en">Sources</span></h2>
<ol class="src">{"".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in nar['sources'])}</ol>
<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<table>{tr(["结论", "置信", "为什么"], True)}{"".join(tr([t(c) for c in r]) for r in nar['notes'])}</table>
<p><strong>分析师看法：</strong>{t(nar['analyst_view'])}</p>
<p>本报告的估值与评分数字全部由 tools/owner_value.py 计算，模板只读取。本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&report={inp['ticker'].lower()}">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report={inp['ticker'].lower()}</a></p></div>
</div></body></html>"""
    return V, html


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    od = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), os.path.join(REPO, "reports"))
    inp, nar = (json.load(open(p, encoding="utf-8")) for p in args[:2])
    try:
        V, html = build(inp, nar)
    except ov.NoSource as e:
        sys.exit(f"拒算：{e}")
    out = os.path.join(od, f"{inp['ticker'].lower()}_Buffett_Report.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"{inp['ticker']}：{V['iv_range'][0]:.2f}–{V['iv_range'][1]:.2f}｜安全边际 {V['margin_of_safety']['value']:.1%}｜评分 {V['scorecard']['total']} → {out}")
    print("估值底稿请另跑：python3 tools/owner_value.py <估值输入.json>（报告的 data-valuation 指向它）")


if __name__ == "__main__":
    main()
