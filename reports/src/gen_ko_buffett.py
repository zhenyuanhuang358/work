#!/usr/bin/env python3
"""reports/ko_Buffett_Report.html —— buffett-analyst 首个真实任务（2026-11-07，用户「跑」）。
报告里的估值数字一律从 owner_value 底稿读（memory/state/valuations/ko_2026-11-07.json），财务数字从 financials/*.json 读，
不手写；文字判断（护城河、管理层）对应的原文在 pages/。重跑：python3 reports/src/gen_ko_buffett.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VAL = "memory/state/valuations/ko_2026-11-07.json"
V = json.load(open(os.path.join(REPO, VAL), encoding="utf-8"))
INP = V["input"]
F = {t: json.load(open(os.path.join(REPO, f"financials/{t}.json"))) for t in ("ko", "pep", "kdp")}
FONT = "font-family:'IM Fell English',Georgia,serif"
INK, PAPER, COPPER, GOLD, GREEN, RED, AMBER = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#c47a1e"
FY = ("2023", "2024", "2025")

SRC = [
    ("SEC EDGAR companyfacts：可口可乐 10-K XBRL（每个值带 accession 号）", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000021344.json"),
    ("SEC EDGAR companyfacts：百事 PEP 10-K XBRL", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{F['pep']['cik']}.json"),
    ("SEC EDGAR companyfacts：Keurig Dr Pepper KDP 10-K XBRL", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{F['kdp']['cik']}.json"),
    ("可口可乐 2024 年第四季度及全年业绩新闻稿", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1128/coca-cola-reports-fourth-quarter-and-full-year-2024-results"),
    ("可口可乐 2025 年第四季度及全年业绩新闻稿", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1151/coca-cola-reports-fourth-quarter-and-full-year-2025-results"),
    ("可口可乐 CEO 交接公告（2025-12-10）", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1147/the-coca-cola-company-announces-ceo-succession-plan-chief-operating-officer-henrique-braun-to-succeed-james-quincey-as-ceo-in-2026"),
    ("可口可乐 2026 年第三季度业绩新闻稿（2026-10-27，含上调后的全年指引表）", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1176/coca-cola-reports-third-quarter-2026-results-and-raises-full-year-guidance"),
    ("可口可乐 2022 年第四季度及全年业绩新闻稿", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1076/coca-cola-reports-fourth-quarter-and-full-year-2022-results"),
    ("可口可乐 2023 年第四季度及全年业绩新闻稿", "https://investors.coca-colacompany.com/news-events/press-releases/detail/1101/coca-cola-reports-fourth-quarter-and-full-year-2023-results"),
    ("可口可乐 FY2025 10-K（公司投资者网站 PDF 副本，accession 0001628280-26-010047）", "https://investors.coca-colacompany.com/filings-reports/all-sec-filings/content/0001628280-26-010047/0001628280-26-010047.pdf"),
    ("股价：Yahoo Finance 2026-11-06 收盘（GitHub Actions 抓取，financials/*.json）；10 年期美债 4.86%（stock_prices.json）", "https://finance.yahoo.com/quote/KO/"),
]


def m(x):  # 百万美元 → 「$X.XB」
    return f"${x / 1000:,.1f}B"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def val(t, fy, key):
    r = F[t]["years"][fy].get(key)
    return r["v"] / 1e6 if r else None


def debt(t, fy):
    dt = F[t]["debt_tags"]
    if t == "ko":
        return dt["LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"][fy] / 1e6 + dt["NotesAndLoansPayable"][fy] / 1e6
    return dt["LongTermDebtNoncurrent"][fy] / 1e6 + dt["DebtCurrent"][fy] / 1e6


# ── 派生指标（公式写在报告里，可复算）────────────────────────────
ETR = {fy: val("ko", fy, "tax") / val("ko", fy, "pretax") for fy in FY}  # 各年 GAAP 实际税率（Critic R1：不套单一预估税率）
ys = {y["fy"]: y for y in INP["years"]}
norm = {n["fy"]: n for n in V["normalization"]}
rows = {}
for fy in FY:
    rev, gp, ni, ebit = val("ko", fy, "revenue"), val("ko", fy, "gross_profit"), val("ko", fy, "net_income"), val("ko", fy, "ebit")
    eq, nci, cash, d = val("ko", fy, "equity"), val("ko", fy, "nci"), val("ko", fy, "cash"), debt("ko", fy)
    fcf_rep = ys[int(fy)]["fcf"]
    fcf_n = norm[int(fy)]["fcf_normalized"] if int(fy) in norm else fcf_rep
    rows[fy] = dict(rev=rev, gm=gp / rev, ni=ni, ebit=ebit, fcf_rep=fcf_rep, fcf_n=fcf_n, conv=fcf_n / ni, conv_rep=fcf_rep / ni,
                    roe=ni / eq, de=d / eq, dr=d / (d + eq), etr=ETR[fy], roic=ebit * (1 - ETR[fy]) / (d + eq + nci - cash), debt=d, eq=eq, cash=cash)
roe_avg = sum(r["roe"] for r in rows.values()) / 3
rev_cagr = (rows["2025"]["rev"] / rows["2023"]["rev"]) ** 0.5 - 1
peer_gm = {t: [val(t, f, "gross_profit") / val(t, f, "revenue") for f in FY] for t in ("pep", "kdp")}
peer_gm25 = (peer_gm["pep"][2] + peer_gm["kdp"][2]) / 2
GY = ("2022",) + FY
gm_cmp = {f: (val("ko", f, "gross_profit") / val("ko", f, "revenue"),
              sum(val(t, f, "gross_profit") / val(t, f, "revenue") for t in ("pep", "kdp")) / 2) for f in GY}
gm_ok = sum(1 for a, b in gm_cmp.values() if a / b - 1 >= 0.10)
# 价格证据：各年业绩新闻稿原文（全年 price/mix、单位箱量）
PRICE = [("2022", 11, 5, "detail/1076"), ("2023", 10, 2, "detail/1101"), ("2024", 11, 1, "detail/1128（约 5 个点来自高通胀市场）"), ("2025", 4, 0, "detail/1151")]
# 2026 指引（Q3 新闻稿指引表）与 IRS（FY2025 10-K）
FCF26_GUIDE = 13000.0
IRS_REMAIN, IRS_DEPOSIT = 14000.0, 6000.0


def ev_fcf(t, fcf=None):
    p = F[t]
    mcap = p["price"]["v"] * p["shares_outstanding"]["v"] / 1e6
    ev = mcap + debt(t, "2025") - val(t, "2025", "cash") + (val(t, "2025", "nci") or 0)
    f = fcf if fcf is not None else val(t, "2025", "cfo") - val(t, "2025", "capex")
    return mcap, ev, ev / f


ko_mcap, ko_ev, ko_evf = ev_fcf("ko", rows["2025"]["fcf_n"])
_, _, ko_evf_rep = ev_fcf("ko", rows["2025"]["fcf_rep"])
pep_evf, kdp_evf = ev_fcf("pep")[2], ev_fcf("kdp")[2]
peer_avg = (pep_evf + kdp_evf) / 2  # 4B 用 EV/FCF（berkshire-score.md）；交叉验证另用 P/FCF（底稿）

lo, hi = V["iv_range"]
price = V["margin_of_safety"]["price"]
mos = V["margin_of_safety"]["value"]
buy30 = lo * 0.70
sc, scn = V["scenarios"]["conservative"], V["scenarios"]["base"]
oe = V["owner_earnings"]
last = ys[2025]
dwc_adj = last['dwc'] + sum(a['amount'] for a in last.get('adjustments', []))
assert abs(last['net_income'] + last['da'] - oe['maint_capex'] + dwc_adj - oe['value']) < 1e-6  # 与底稿 OE 闭合
ig = V["implied_g1"]
g26 = FCF26_GUIDE / rows["2025"]["fcf_n"] - 1
lo26 = lo * FCF26_GUIDE / rows["2025"]["fcf_n"]
need_after26 = (rows["2025"]["fcf_n"] * (1 + ig["g1"]) ** 5 / FCF26_GUIDE) ** 0.25 - 1
sh = INP["shares"]["v"]
irs_ps, dep_ps = IRS_REMAIN / sh, IRS_DEPOSIT / sh
IRS_ETR_UP = 0.035  # 10-K：继续适用 Tax Court 方法，2026 年实际税率约 +3.5%
irs_tax = val("ko", "2025", "pretax") * IRS_ETR_UP
lo_irs = lo * (1 - irs_tax / oe["value"]) - irs_ps
pb = ko_mcap / rows["2025"]["eq"]
thr30 = rows["2025"]["fcf_n"] * (1 + ig["g1"]) ** 5
wa = V["without_adjustments"]
SD = INP["scores_detail"]
total = V["scorecard"]["total"]
divs = [val("ko", f, "dividends") for f in ("2022",) + FY]
bb = [val("ko", f, "buyback") for f in FY]
dil = [val("ko", f, "diluted_shares") for f in ("2022",) + FY]


# ── SVG ─────────────────────────────────────────────────────────
def price_svg():
    W, x0, x1 = 660, 40, 620
    vmax = 110.0
    X = lambda v: x0 + (x1 - x0) * v / vmax  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} 150" style="{FONT};width:100%">',
         f'<line x1="{x0}" y1="80" x2="{x1}" y2="80" stroke="{COPPER}" stroke-width="1"/>']
    for t in range(0, 111, 10):
        o.append(f'<line x1="{X(t):.1f}" y1="77" x2="{X(t):.1f}" y2="83" stroke="{COPPER}"/><text x="{X(t):.1f}" y="98" font-size="10" text-anchor="middle" fill="{COPPER}">{t}</text>')
    o.append(f'<rect x="{X(lo):.1f}" y="62" width="{X(hi) - X(lo):.1f}" height="36" fill="{GOLD}" opacity="0.35"/>')
    for v_, lab, c, y in ((buy30, f"建仓线 {buy30:.2f}", GREEN, 50), (lo, f"下沿 {lo:.2f}", INK, 30), (hi, f"基准 IV {hi:.2f}", INK, 50),
                          (price, f"现价 {price:.2f}", RED, 30)):
        o.append(f'<line x1="{X(v_):.1f}" y1="{y + 6}" x2="{X(v_):.1f}" y2="104" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{X(v_):.1f}" y="{y}" font-size="12" text-anchor="middle" fill="{c}">{lab}</text>')
    o.append(f'<text x="{x0}" y="132" font-size="11" fill="{COPPER}">每股美元。金色带 = 内在价值区间（保守 → 基准，owner_value 两情景 DCF）；建仓线 = 下沿 × 70%（安全边际 30%）</text>')
    return "".join(o) + "</svg>"


def moat_svg():
    o = [f'<svg viewBox="0 0 660 70" style="{FONT};width:100%">']
    for i in range(10):
        c = GOLD if i < INP["moat_score"] else "#ddd6c8"
        o.append(f'<rect x="{40 + i * 58}" y="14" width="52" height="22" fill="{c}"/>')
        o.append(f'<text x="{66 + i * 58}" y="52" font-size="10" text-anchor="middle" fill="{COPPER}">{i + 1}</text>')
    o.append(f'<text x="40" y="66" font-size="11" fill="{COPPER}">护城河评分 {INP["moat_score"]} / 10（7–8 = 宽护城河：阶段 1 增速上限 18%，终端增长上限 8%）</text>')
    return "".join(o) + "</svg>"


def trend_svg():  # 三年趋势折线（output-template：财务指标用趋势线）
    W, H, x0, x1, y0, top = 660, 240, 70, 600, 190, 20
    vmax = 14000
    Y = lambda v: y0 - (y0 - top) * v / vmax  # noqa: E731
    X = lambda i: x0 + (x1 - x0) * i / 2  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">']
    for t in range(0, 14001, 2000):
        o.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x1}" y2="{Y(t):.1f}" stroke="#e2dccf"/><text x="{x0 - 8}" y="{Y(t) + 4:.1f}" font-size="10" text-anchor="end" fill="{COPPER}">{t / 1000:.0f}B</text>')
    series = (("净利润", "ni", INK, ""), ("FCF（报告值）", "fcf_rep", RED, ""), ("FCF（剔除一次性项）", "fcf_n", GREEN, "5,4"))
    for n, k, c, dash in series:
        pts = " ".join(f"{X(i):.1f},{Y(rows[fy][k]):.1f}" for i, fy in enumerate(FY))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
        for i, fy in enumerate(FY):
            v_ = rows[fy][k]
            dy = -8 if k == "ni" else 16
            o.append(f'<circle cx="{X(i):.1f}" cy="{Y(v_):.1f}" r="3.5" fill="{c}"/><text x="{X(i) + 6:.1f}" y="{Y(v_) + dy:.1f}" font-size="10" fill="{c}">{v_ / 1000:.1f}</text>')
    for i, fy in enumerate(FY):
        o.append(f'<text x="{X(i):.1f}" y="{y0 + 18}" font-size="12" text-anchor="middle" fill="{INK}">FY{fy}</text>')
    for j, (n, _, c, _d) in enumerate(series):
        o.append(f'<rect x="{x0 + j * 180}" y="{H - 16}" width="10" height="10" fill="{c}"/><text x="{x0 + 14 + j * 180}" y="{H - 7}" font-size="11" fill="{INK}">{n}</text>')
    return "".join(o) + "</svg>"


def score_svg():  # 评分卡分段进度条（output-template）
    dims = (("Business Quality", "business", 30), ("Financial Health", "financial", 30), ("Management Quality", "management", 25), ("Price vs Value", "price", 15))
    o = [f'<svg viewBox="0 0 660 160" style="{FONT};width:100%">']
    for i, (n, k, mx) in enumerate(dims):
        y = 14 + i * 34
        v_ = V["scorecard"][k]
        o.append(f'<text x="0" y="{y + 14}" font-size="12" fill="{INK}">{n}</text>'
                 f'<rect x="170" y="{y}" width="{mx * 14}" height="20" fill="#ddd6c8"/>'
                 f'<rect x="170" y="{y}" width="{v_ * 14}" height="20" fill="{GOLD}"/>'
                 f'<text x="{176 + mx * 14}" y="{y + 15}" font-size="12" fill="{COPPER}">{v_} / {mx}</text>')
    o.append(f'<text x="0" y="154" font-size="11" fill="{COPPER}">总分 {total} / 100 → 40–54 = 谨慎（按 berkshire-score.md 字面口径；见 §五一致性说明）</text>')
    return "".join(o) + "</svg>"


def badge(level):
    c = {"高": GREEN, "中": AMBER, "低": RED}[level]
    return f'<span class="badge" style="border:1px solid {c};color:{c}">置信 {level}</span>'


def tr(cells, head=False):
    tag = "th" if head else "td"
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


fin_rows = [
    ("营收", [m(rows[f]["rev"]) for f in FY]), ("毛利率", [pct(rows[f]["gm"]) for f in FY]),
    ("净利润（GAAP）", [m(rows[f]["ni"]) for f in FY]), ("营业利润（EBIT）", [m(rows[f]["ebit"]) for f in FY]),
    ("FCF（报告值 = CFO − Capex）", [m(rows[f]["fcf_rep"]) for f in FY]), ("FCF（剔除一次性项）", [m(rows[f]["fcf_n"]) for f in FY]),
    ("FCF / 净利润（报告值）", [pct(rows[f]["conv_rep"], 0) for f in FY]), ("FCF / 净利润（剔除后）", [pct(rows[f]["conv"], 0) for f in FY]),
    ("ROE（GAAP）", [pct(rows[f]["roe"]) for f in FY]),
    ("ROIC（EBIT × (1 − 当年实际税率) ÷ 投入资本）", [f"{pct(rows[f]['roic'])}（税率 {pct(rows[f]['etr'])}）" for f in FY]),
    ("有息负债 / 股东权益", [pct(rows[f]["de"], 0) for f in FY]),
]
sens_rows = "".join(tr([{"r": "折现率 r", "g1": "阶段 1 增速 g1", "g_terminal": "终端增长率"}[x["var"]],
                        f"{x['delta'] * 100:+.1f} 个百分点", f"{x['iv_per_share']:.2f}", f"{x['change'] * 100:+.0f}%"])
                    for x in V["sensitivity"]["rows"])
alt_total = total - SD["2B"] + 10 - SD["4B"] + 3  # 仅作附注（用户 11/07 定：一次性项只用于估值）  # 若 2B / 4B 改用剔除一次性项的 FCF
score_rows = "".join(tr(r) for r in [
    ("Business Quality", 30, V["scorecard"]["business"], f"1A / 1B / 1C = {SD['1A']} / {SD['1B']} / {SD['1C']}：护城河 {INP['moat_score']} 分（宽）；营收 CAGR {pct(rev_cagr)}（< 5%、无负增长 → 2）；毛利率三年 > 50% → 7"),
    ("Financial Health", 30, V["scorecard"]["financial"], f"2A / 2B / 2C = {SD['2A']} / {SD['2B']} / {SD['2C']}：ROE 三年均值 {pct(roe_avg)}，负债率 > 40% 用 ROIC 复核均 > 12%，不降档 → 12；报告值 FCF / 净利润 {pct(rows['2023']['conv_rep'], 0)} / {pct(rows['2024']['conv_rep'], 0)} / {pct(rows['2025']['conv_rep'], 0)}，两年低于 50% → 2；负债率 {pct(rows['2025']['dr'], 0)}（40–60% 档）→ 2"),
    ("Management Quality", 25, V["scorecard"]["management"], f"3A / 3B / 3C = {SD['3A']} / {SD['3B']} / {SD['3C']}：6 + 分红连增 2 − BodyArmor 并购后两年减值 4；职业经理人 + PSU / RSU 激励、持股数据缺失 → 少量持股档 3；新 CEO 在任不满 1 年取中性 3"),
    ("Price vs Value", 15, V["scorecard"]["price"], f"4A / 4B = {SD['4A']} / {SD['4B']}：安全边际为负 → 0；EV/FCF（报告值）{ko_evf_rep:.0f}x，高于同行均值 {peer_avg:.1f}x 逾 20% → 1"),
    ("总分", 100, total, "40–54 = 谨慎；未触发自动降级"),
])

verdict_zh = f"好生意，贵价格：现价 {price:.2f} 高于内在价值上沿 {hi:.2f}，安全边际（下沿）{mos * 100:.1f}%，不买；{buy30:.2f} 以下才进入买入区间。"
gm_table = "".join(tr([f"FY{f}", pct(a), pct(b), f"{(a / b - 1) * 100:+.1f}%", "✓" if a / b - 1 >= 0.10 else "✗"]) for f, (a, b) in gm_cmp.items())
price_table = "".join(tr([f"FY{f}", f"+{pm}%", f"+{v_}%" if v_ else "持平", "✓" if pm > 5 else "✗", src]) for f, pm, v_, src in PRICE)

html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>可口可乐 KO 巴菲特模型分析</title>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English&display=swap" rel="stylesheet">
<style>
:root{{--ink:{INK};--paper:{PAPER};--copper:{COPPER};--gold:{GOLD};--green:{GREEN};--red:{RED};--amber:{AMBER}}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Songti SC','Noto Serif SC','IM Fell English',serif;line-height:1.75}}
.wrap{{max-width:860px;margin:0 auto;padding:28px 18px 60px}}
.pub{{display:flex;justify-content:space-between;font-size:12px;color:var(--copper);border-bottom:1px solid var(--copper);padding-bottom:6px}}
h1{{font-size:30px;margin:18px 0 2px}} .en{{font-family:'IM Fell English',serif;color:var(--copper);font-style:italic}}
h2{{font-size:20px;margin:34px 0 8px;border-bottom:2px solid var(--gold);padding-bottom:4px}}
.stat{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:18px 0}}
.stat div{{background:#fff;border:1px solid #e2dccf;padding:10px}} .stat b{{display:block;font-size:20px}} .stat span{{font-size:12px;color:var(--copper)}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}} th,td{{border-bottom:1px solid #e2dccf;padding:6px 6px;text-align:left;vertical-align:top}} th{{color:var(--copper);font-weight:normal}}
.verdict{{background:var(--ink);color:var(--paper);padding:20px 22px;margin:26px 0}} .verdict .en{{color:var(--gold);opacity:.8}}
.src{{font-size:12px;color:var(--copper)}} .warn{{border-left:3px solid var(--amber);padding:6px 12px;background:#fff8ec;margin:10px 0}}
.quote{{border-left:3px solid var(--gold);padding:4px 12px;font-style:italic;font-family:'IM Fell English',serif;margin:8px 0}}
.badge{{font-size:11px;padding:0 6px;margin-left:6px;white-space:nowrap}}
.note{{margin-top:36px;border-top:1px solid var(--copper);padding-top:12px;font-size:13px}}
@media(max-width:600px){{.stat{{grid-template-columns:repeat(2,1fr)}} table{{font-size:12px}}}}
</style></head>
<body><div class="wrap" data-valuation="{VAL}">
<div class="pub"><span>巴菲特模型分析报告 · Buffett Model Report</span><span>分析日期 {V['as_of']} · 股价日期 {F['ko']['price']['date']}</span></div>
<h1>可口可乐（KO）</h1><div class="en">The Coca-Cola Company — Moat, Owner Earnings and Margin of Safety</div>

<div class="stat">
<div><b>{lo:.2f}–{hi:.2f}</b><span>内在价值区间（美元 / 股）</span></div>
<div><b>{price:.2f}</b><span>现价（{F['ko']['price']['date']} 收盘）</span></div>
<div><b style="color:var(--red)">{mos * 100:.1f}%</b><span>安全边际（按下沿；门槛 30%）</span></div>
<div><b>{total} / 100</b><span>巴菲特评分 → 谨慎</span></div>
</div>

<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<ul>
<li><strong>结论：高估区间，不买。</strong>护城河宽（{INP['moat_score']} / 10），但现价 {price:.2f} 比内在价值上沿 {hi:.2f} 还高。按下沿算，安全边际 {mos * 100:.1f}%；要回到 30% 安全边际，价格需在 {buy30:.2f} 以下。换任何一种口径结论都不变：不剔除一次性项、代入 2026 指引、IRS 败诉。{badge("高")}</li>
<li>评分 {total} / 100，落在「谨慎」档。生意质量高；扣分主要来自三处：报告值 FCF 被两笔一次性支出压低，估值偏贵，管理层数据有缺口。{badge("中")}</li>
<li>现价隐含未来 5 年 FCF 每年增长 {pct(ig['g1'])}。2026 年指引 +{pct(g26)}，第一年接近兑现；之后能否持续，是多空分歧所在。{badge("中")}</li>
</ul>
{price_svg()}

<h2>一、护城河分析 <span class="en">Moat</span></h2>
{moat_svg()}
<p>护城河类型：<strong>无形资产（品牌定价权）</strong>。评分 {INP['moat_score']} / 10，属宽护城河；未触发侵蚀信号，不下调。{badge("中")}</p>
<table>{tr(["维度（moat-framework 五类）", "证据", "判定"], True)}
{tr(["无形资产（品牌）", "信号①毛利率高于同行、信号②连续三年 > 5% 涨价且销量增长，见下两表", "成立，主护城河；决定 7 分"])}
{tr(["成本优势", f"浓缩液模式毛利率比同行高 {(rows['2025']['gm'] - peer_gm25) * 100:.1f} 个百分点，但这反映商业模式（卖浓缩液、装瓶外包），框架要求的「单位成本低于对手 15%+」没有可比数据", "不计分（数据不足）"])}
{tr(["转换成本", "消费者换饮料几乎零成本；框架明说消费端「习惯 ≠ 转换成本」", "不成立"])}
{tr(["网络效应", "饮料不因用户多而对单个用户更有价值", "不成立"])}
{tr(["规模壁垒", "全球装瓶分销体系是规模优势，但本报告没有 CR3 与新进入者退出数据", "不计分（数据不足）"])}
</table>
<p><strong>信号①：毛利率持续高于同行均值 10% 以上</strong>（同行 = PEP、KDP 两家均值；相对口径）：四年里 {gm_ok} 年达标，基本成立，但不是每年都成立。</p>
<table>{tr(["财年", "KO 毛利率", "同行均值", "KO 相对高出", "≥ 10%"], True)}{gm_table}</table>
<p class="src">两种读法：按相对口径（KO ÷ 同行 − 1）四年 {gm_ok} 年达标；按百分点口径，KO 只高 {min((a - b) for a, b in gm_cmp.values()) * 100:.1f}–{max((a - b) for a, b in gm_cmp.values()) * 100:.1f} 个点，四年都不达标。PEP 含大量零食业务，毛利率可比性有限，所以这条信号按「基本成立」处理，不作强证据。</p>
<p><strong>信号②：5 年内至少 2 次 > 5% 的实质性涨价，且客户没有流失</strong>（用单位箱量代替流失率）：FY2022–FY2024 连续三年全年 price/mix ≥ 10%，同期箱量 +5% / +2% / +1%，成立。
需要打折扣的地方：涨价里有一部分来自高通胀市场，FY2024 公司明说约 5 个点来自高通胀市场定价。</p>
<table>{tr(["财年", "全年 price/mix", "单位箱量", "> 5%", "出处（业绩新闻稿）"], True)}{price_table}</table>
<p>份额：FY2025 与 2026 Q3 均在无酒精即饮饮料（NARTD）赢得价值份额；2026 Q3 EMEA 份额下滑（法国、英国）。侵蚀信号：毛利率三年 {pct(rows['2023']['gm'])} → {pct(rows['2025']['gm'])}，无压缩；没有连续两年份额流失，未触发。</p>
<p>为什么给 7：两个核心信号都成立，但信号①不是年年成立，信号②掺有通胀定价。如果评 6（中等护城河）：1A 从 12 降到 8，总分 {total - 4}，仍在「谨慎」档；
内在价值不变，因为两个情景的增速都没碰到 12% / 18% 的上限，终端增长被 2.5% / 3% 封顶。</p>
<p class="src">来源：SEC companyfacts（GrossProfit ÷ 营收）；2022–2025 年业绩新闻稿（price/mix、单位箱量、份额）；2026 Q3 新闻稿（份额）。</p>
<p>主要挑战：减糖与健康饮品趋势对含糖碳酸饮料的长期压力。</p>

<h2>二、核心财务指标 <span class="en">Financials, FY2023–FY2025</span></h2>
{trend_svg()}
<table>{tr(["指标"] + [f"FY{f}" for f in FY], True)}{"".join(tr([n] + v) for n, v in fin_rows)}</table>
<p class="src">来源：SEC companyfacts 10-K（百万美元换算为十亿）。有息负债 = 长期债务含一年内到期部分 + 应付票据及借款（KO 2024 年起改报 LongTermDebtAndCapitalLeaseObligations 标签）；实际税率 = IncomeTaxExpenseBenefit ÷ 税前利润；投入资本 = 有息负债 + 股东权益 + 少数股东权益 − 现金（不扣现金时 FY2024 ROIC 约为 11.7%，「三年都 > 12%」依赖这个口径）。</p>
<div class="warn"><strong>两笔一次性现金流出（金额是公司在业绩新闻稿里自己列的）：</strong>FY2024 向美国国税局（IRS）缴纳税务诉讼保证金 $6.0B；FY2025 支付 fairlife 并购或有对价 $6.1B。
这两笔把 FCF 压到 {m(rows['2024']['fcf_rep'])} / {m(rows['2025']['fcf_rep'])}。<strong>只有估值</strong>按剔除后的 {m(rows['2024']['fcf_n'])} / {m(rows['2025']['fcf_n'])} 计算，与公司公布的 $10.8B / $11.4B 接近，差额是取整。
评分卡仍按规则用报告值。不剔除时 FCF 复合增速为 {pct(wa['fcf_cagr'])}，内在价值降到 {wa['iv_range'][0]:.2f}–{wa['iv_range'][1]:.2f}：<strong>结论不变，仍是高估</strong>。</div>
<p class="quote">“Both decreased versus the prior year, primarily due to a $6.0 billion deposit made to the U.S. Internal Revenue Service … related to ongoing tax litigation.” — 2024 年业绩新闻稿</p>
<p class="quote">“… which reflects $6.1 billion of the contingent consideration payment made during the first quarter in conjunction with the acquisition of fairlife, LLC.” — 2025 年业绩新闻稿</p>
<p>ROIC {pct(rows['2025']['roic'])} 高于 9% 的折现率，创造价值。ROE 三年均值 {pct(roe_avg)} 里有杠杆成分：有息负债约为股东权益的 {rows['2025']['de']:.1f} 倍。用 ROIC 复核，三年都高于 12%，不降档。</p>

<h2>三、管理层评估 <span class="en">Management</span></h2>
<table>{tr(["行为（近 3 年）", "数据", "评分影响"], True)}
{tr(["分红", f"支付普通股股息 {m(divs[0])} → {m(divs[1])} → {m(divs[2])} → {m(divs[3])}，连续增长", "+2"])}
{tr(["回购", f"FY2023–FY2025 回购 {m(bb[0])} / {m(bb[1])} / {m(bb[2])}；现价市净率约 {pb:.1f}x（市值 ÷ FY2025 股东权益），PB 要降到 2 以下，股价需下跌约 {(1 - 2 / pb) * 100:.0f}%；没有「低估时回购」的证据", "0"])}
{tr(["并购后减值", "2021 年 11 月收购 BodyArmor 剩余 85% 股权；BodyArmor 商标 FY2024、FY2025 分别计提减值 $760M、$960M（10-K）", "−4"])}
{tr(["股权激励稀释", f"稀释后股数 {dil[0] / 1000:.2f}B → {dil[3] / 1000:.2f}B，逐年下降", "0"])}
</table>
<p>3A = 6 + 2 − 4 = {SD['3A']}。3B：职业经理人，有绑定激励（10-K 披露 PSU / RSU 等股权激励，FY2025 股权激励费用 {m(val('ko', '2025', 'sbc'))}）。未取得 DEF 14A 里的持股数据，按「职业经理人 + 少量持股」取 {SD['3B']} 分。</p>
<div class="warn">管理层变动：James Quincey 任 CEO 九年后，2026-03-31 卸任，改任执行董事长；由原 COO Henrique Braun 接任（1996 年加入公司）。Braun 在任约 7 个月，不满 1 年。按规则 3C 取中性 {SD['3C']} 分，新任 CEO 的加分行为暂不计入。</div>
<p class="src">来源：SEC companyfacts（PaymentsOfDividendsCommonStock、PaymentsForRepurchaseOfCommonStock、WeightedAverageNumberOfDilutedSharesOutstanding）；FY2025 10-K（BodyArmor 收购与两次减值）；CEO 交接公告；2026 Q3 新闻稿（Braun 以 CEO 身份发言）。</p>

<h2>四、内在价值估算 <span class="en">Owner Earnings DCF</span></h2>
<p><strong>所有者盈余（FY2025）</strong>：净利润 {m(last['net_income'])} + D&amp;A {m(last['da'])} − 维护性资本支出 {m(oe['maint_capex'])} − 营运资本增加 {m(-dwc_adj)}（报告值 {m(-last['dwc'])}，已加回 fairlife 支付 $6.1B）= <strong>{m(oe['value'])}</strong>。
维护性资本支出取总资本支出的 50%。理由：轻资产消费品的 D&amp;A 不能代表维护性资本支出。取 50% 后为 {m(oe['maint_capex'])}，与 D&amp;A {m(last['da'])} 几乎相等，两种口径结论相同。</p>
<table>{tr(["参数", "保守情景", "基准情景", "依据"], True)}
{tr(["阶段 1 增速（1–5 年）", pct(sc['g1'], 2), pct(scn['g1'], 2), f"剔除后 FCF 复合增速 {pct(V['fcf_cagr'], 2)} × 60% / × 85%，未触 18% 上限"])}
{tr(["阶段 2 增速（6–10 年）", pct(sc['g2'], 2), pct(scn['g2'], 2), "阶段 1 × 50% / × 60%"])}
{tr(["终端增长率", pct(sc['g_terminal'], 1), pct(scn['g_terminal'], 1), "护城河上限 8% × 60% / × 80%，再受 2.5% / 3% 封顶（3% = 全球 GDP 参考值上限，用户 11/07 定）"])}
{tr(["折现率", "9%", "9%", "美股大盘股 9%；10 年期美债 4.86% 在 4–5% 区间，不调整"])}
{tr(["每股内在价值", f"{lo:.2f}", f"{hi:.2f}", "两情景 DCF ÷ 4.30B 股"])}
{tr(["终值占比", pct(sc['terminal_share'], 0), pct(scn['terminal_share'], 0), "两个情景都 ≤ 60%，不触发出口倍数交叉验证"])}
</table>
<p>终值集中度：基准情景终值占比 {pct(scn['terminal_share'], 0)}，两个情景都在 60% 以内，结果不过度依赖终值，不需要做出口倍数交叉验证。
交叉验证公式已按用户 11/07 的决定改为股权口径（前 10 年所有者盈余现值 + 第 10 年所有者盈余 × 同行市值 / FCF，再折现）；底稿备有同行 P/FCF {INP['peer_p_fcf']['v']:.1f}x。</p>
<table>{tr(["价格锚点", "价位", "说明"], True)}
{tr(["内在价值下沿（保守情景）", f"{lo:.2f}", "安全边际的计算基准"])}
{tr(["当前股价", f"{price:.2f}", F['ko']['price']['date']])}
{tr(["当前安全边际", f"{mos * 100:.1f}%", f"(下沿 − 现价) ÷ 下沿；现价比下沿高 {(price / lo - 1) * 100:.0f}%"])}
{tr(["目标买入价（安全边际 30%）", f"{buy30:.2f}", "下沿 × 70%，严格建仓线"])}
{tr(["目标买入价（安全边际 35%）", f"{lo * 0.65:.2f}", "下沿 × 65%，保守建仓线"])}
</table>
<p><strong>逆向验证：现价隐含什么？</strong>按基准情景的结构倒推，现价 {price:.2f} 要成立，需要阶段 1 增速 {pct(ig['g1'])}、阶段 2 增速 {pct(ig['g2'])}、终端增长 {pct(ig['g_terminal'], 0)}。这个增速是过去两年 FCF 复合增速 {pct(V['fcf_cagr'])}（剔除一次性项）的约 {ig['g1'] / V['fcf_cagr']:.1f} 倍。{badge("中")}</p>
<div class="warn"><strong>2026 年指引代入：</strong>Q3 新闻稿把 2026 全年 FCF 指引上调到至少 {m(FCF26_GUIDE)}，原指引约 $12.4B；比 FY2025 剔除一次性项后的 {m(rows['2025']['fcf_n'])} 高 {pct(g26)}，与现价隐含的 {pct(ig['g1'])} 接近，但没有超过。
指引里没有再列一次性项。Q1 多出的 6 天和 Q4 少掉的 6 天在全年层面相互抵消。<br>
重估结果有三点：
<br>① 粗算：所有者盈余与 FCF 同比例上调，内在价值下沿约为 {lo:.2f} × {FCF26_GUIDE / rows['2025']['fcf_n']:.3f} ≈ {lo26:.1f}，安全边际仍约 {(lo26 - price) / lo26 * 100:.0f}%，不买的结论不变。
<br>② 定性：第一年基本兑现隐含增速，不能叫「激进」。准确的说法是：现价要求 2027–2030 年 FCF 每年再增长约 {pct(need_after26)}。
<br>③ 反方证据：公司提示 2027 年收购与剥离会带来约 8% 的营收逆风（Q3 新闻稿）。</div>
<p class="src">来源：owner_value 底稿 {VAL}（每个输入带来源）；2026 Q3 新闻稿指引表（FCF 至少 $13.0B，经营现金流至少 $15.2B，资本支出约 $2.2B）。</p>

<div class="verdict"><strong>裁决：谨慎，当前不买。</strong>{verdict_zh}
<div class="en">Wonderful business, demanding price: shares trade above the base-case intrinsic value; no margin of safety at the conservative bound, even after the raised 2026 cash-flow guidance.</div></div>

<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
{score_svg()}
<table>{tr(["维度", "满分", "得分", "关键依据"], True)}{score_rows}</table>
<p>口径说明：berkshire-score.md 没有授权用正态化 FCF 打分，所以 2B、4B 按报告值 FCF 打分，KO 和同行两边都用 CFO − Capex。
如果两项都改用剔除一次性项的 FCF（KO 为 {ko_evf:.1f}x，同行未做正态化），2B 为 10 分、4B 为 3 分，总分 {alt_total}，进入「观察名单」。
这个分歧只影响评级的档位，不影响「不买」。规则是否应允许正态化，留给你定（见分析师附注）。</p>

<h2>六、主要风险 <span class="en">Risks</span></h2>
<table>{tr(["风险", "说明", "对估值的影响"], True)}
{tr(["IRS 税务诉讼", f"2007–2009 税年的负债 $6.0B 已作为保证金支付。10-K 估计 2010–2025 税年剩余的潜在税款与利息「可能约 $14B」，利息继续累计。公司认为上诉「more likely than not」胜诉", f"败诉：一次性负债每股约 −{irs_ps:.2f}（$14B ÷ 4.30B 股）。10-K 还估计，继续适用 Tax Court 方法会使实际税率上升约 3.5%：按 FY2025 税前利润算，每年约 {m(irs_tax)}，所有者盈余约 −{irs_tax / oe['value'] * 100:.1f}%。两项合计，下沿 {lo:.2f} → 约 {lo_irs:.1f}。胜诉：保证金退回，每股约 +{dep_ps:.2f}。两种结果都不改变结论"])}
{tr(["健康与减糖趋势", "含糖碳酸饮料的长期需求承压；公司靠无糖产品与非碳酸品类对冲（2026 Q3 Coca-Cola Zero Sugar +16%）", "压低长期增速；增速 −3 个百分点 → 下沿约 −16%"])}
{tr(["收购与剥离", "公司提示 2027 年收购剥离带来约 8% 营收逆风、约 2% 可比 EPS 逆风", "营收基数缩小，FCF 增速可能放缓"])}
{tr(["利率", "折现率随 10 年期美债变化", "r +1 个百分点 → 下沿约 −13%"])}
</table>
<p>需要重估内在价值的情况：FY2026 年报公布（基准年切到 FY2026）；IRS 上诉判决公布；股价跌破 {buy30:.2f}。</p>

<h2>七、数据盲区与敏感性 <span class="en">Gaps and Sensitivity</span></h2>
<ul>
<li>管理层持股比例（DEF 14A）未取得 → 3B 取 3 分。补齐后最多 +5 分（总分 ≤ {total + 5}，仍在「谨慎」档），不改变「不买」。</li>
<li>IRS 上诉的时间表与结果未知 → 风险段给出败诉 / 胜诉两端。</li>
<li>规模壁垒的 CR3 与新进入者数据未取得 → 规模壁垒不计分。</li>
</ul>
<table>{tr(["变量（以保守情景为底）", "变动", "每股内在价值", "变化"], True)}{sens_rows}</table>

<h2>来源索引 <span class="en">Sources</span></h2>
<ol class="src">{"".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC)}</ol>

<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<table>{tr(["结论", "置信", "为什么"], True)}
{tr(["高估、不买", "高", "四种口径（报告值、剔除一次性项、2026 指引、IRS 败诉）都给出负的安全边际"])}
{tr(["护城河 7 / 10（宽）", "中", "两个核心信号成立，但毛利率信号不是年年成立，涨价证据掺有通胀定价；评 6 时结论不变"])}
{tr([f"评分 {total}（谨慎）", "中", f"按规则字面口径；若允许正态化 FCF 则为 {alt_total}（观察名单）"])}
{tr(["现价隐含增速难以持续 5 年", "中", f"已登记 predictions.md：FY2030 FCF < ${thr30 / 1000:.1f}B，2031-02-28 验证"])}
</table>
<p><strong>待核实：</strong>DEF 14A 管理层持股；IRS 上诉进展与败诉后的税率；FY2026 年报 FCF（预计 2027 年 2 月）。</p>
<p><strong>分析师看法与分歧：</strong>KO 是巴菲特意义上的好生意，问题只在价格。最强的反方论据是 2026 年 FCF 指引 +{pct(g26)}，已接近现价的隐含增速；
但这需要连续 5 年做到，而 2027 年公司自己提示约 8% 的收购剥离营收逆风。本报告按用户 11/07 定的三条规则计算：
① 一次性项只用于估值，不用于评分卡（若用于评分卡为 {alt_total} 分）；
② 基准终端增长封顶 3%；
③ 交叉验证用股权口径。</p>
<p>本报告所有估值数字由 tools/owner_value.py 计算，底稿为 {VAL}；生成脚本只读取，不手算。本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&report=ko">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=ko</a></p></div>
</div></body></html>"""

out = os.path.join(REPO, "reports/ko_Buffett_Report.html")
open(out, "w", encoding="utf-8").write(html)
print("→", os.path.relpath(out, REPO))
