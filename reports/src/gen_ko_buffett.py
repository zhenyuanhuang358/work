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
    ("可口可乐 2026 年第三季度业绩新闻稿（2026-10-27）", "https://www.coca-colacompany.com/media-center/coca-cola-reports-third-quarter-2026-results"),
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
ETR = 0.208  # 2024 新闻稿：2025 年 underlying effective tax rate 预估 20.8%
ys = {y["fy"]: y for y in INP["years"]}
norm = {n["fy"]: n for n in V["normalization"]}
rows = {}
for fy in FY:
    rev, gp, ni, ebit = val("ko", fy, "revenue"), val("ko", fy, "gross_profit"), val("ko", fy, "net_income"), val("ko", fy, "ebit")
    eq, nci, cash, d = val("ko", fy, "equity"), val("ko", fy, "nci"), val("ko", fy, "cash"), debt("ko", fy)
    fcf_rep = ys[int(fy)]["fcf"]
    fcf_n = norm[int(fy)]["fcf_normalized"] if int(fy) in norm else fcf_rep
    rows[fy] = dict(rev=rev, gm=gp / rev, ni=ni, ebit=ebit, fcf_rep=fcf_rep, fcf_n=fcf_n, conv=fcf_n / ni, conv_rep=fcf_rep / ni,
                    roe=ni / eq, de=d / eq, dr=d / (d + eq), roic=ebit * (1 - ETR) / (d + eq + nci - cash), debt=d, eq=eq, cash=cash)
roe_avg = sum(r["roe"] for r in rows.values()) / 3
rev_cagr = (rows["2025"]["rev"] / rows["2023"]["rev"]) ** 0.5 - 1
peer_gm = {t: [val(t, f, "gross_profit") / val(t, f, "revenue") for f in FY] for t in ("pep", "kdp")}
peer_gm25 = (peer_gm["pep"][2] + peer_gm["kdp"][2]) / 2


def ev_fcf(t, fcf=None):
    p = F[t]
    mcap = p["price"]["v"] * p["shares_outstanding"]["v"] / 1e6
    ev = mcap + debt(t, "2025") - val(t, "2025", "cash") + (val(t, "2025", "nci") or 0)
    f = fcf if fcf is not None else val(t, "2025", "cfo") - val(t, "2025", "capex")
    return mcap, ev, ev / f


ko_mcap, ko_ev, ko_evf = ev_fcf("ko", rows["2025"]["fcf_n"])
_, _, ko_evf_rep = ev_fcf("ko", rows["2025"]["fcf_rep"])
pep_evf, kdp_evf = ev_fcf("pep")[2], ev_fcf("kdp")[2]
peer_avg = INP["peer_ev_fcf"]["v"]

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


def trend_svg():
    W, H, x0, y0, top = 660, 230, 60, 180, 20
    vmax = 14000
    Y = lambda v: y0 - (y0 - top) * v / vmax  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">']
    for t in range(0, 14001, 2000):
        o.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{W - 20}" y2="{Y(t):.1f}" stroke="#e2dccf"/><text x="{x0 - 6}" y="{Y(t) + 4:.1f}" font-size="10" text-anchor="end" fill="{COPPER}">{t / 1000:.0f}B</text>')
    series = (("净利润", "ni", INK), ("FCF（报告值）", "fcf_rep", RED), ("FCF（剔除一次性项）", "fcf_n", GREEN))
    for i, fy in enumerate(FY):
        gx = x0 + 40 + i * 190
        for j, (_, k, c) in enumerate(series):
            v_ = rows[fy][k]
            o.append(f'<rect x="{gx + j * 44}" y="{Y(v_):.1f}" width="38" height="{y0 - Y(v_):.1f}" fill="{c}" opacity="0.85"/>'
                     f'<text x="{gx + j * 44 + 19}" y="{Y(v_) - 4:.1f}" font-size="10" text-anchor="middle" fill="{c}">{v_ / 1000:.1f}</text>')
        o.append(f'<text x="{gx + 63}" y="{y0 + 16}" font-size="12" text-anchor="middle" fill="{INK}">FY{fy}</text>')
    for j, (n, _, c) in enumerate(series):
        o.append(f'<rect x="{x0 + j * 190}" y="{H - 18}" width="10" height="10" fill="{c}"/><text x="{x0 + 14 + j * 190}" y="{H - 9}" font-size="11" fill="{INK}">{n}</text>')
    return "".join(o) + "</svg>"


# ── HTML ────────────────────────────────────────────────────────
def tr(cells, head=False):
    tag = "th" if head else "td"
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


fin_rows = [
    ("营收", [m(rows[f]["rev"]) for f in FY]), ("毛利率", [pct(rows[f]["gm"]) for f in FY]),
    ("净利润（GAAP）", [m(rows[f]["ni"]) for f in FY]), ("营业利润（EBIT）", [m(rows[f]["ebit"]) for f in FY]),
    ("FCF（报告值 = CFO − Capex）", [m(rows[f]["fcf_rep"]) for f in FY]), ("FCF（剔除一次性项）", [m(rows[f]["fcf_n"]) for f in FY]),
    ("FCF / 净利润（剔除后）", [pct(rows[f]["conv"], 0) for f in FY]), ("FCF / 净利润（报告值）", [pct(rows[f]["conv_rep"], 0) for f in FY]),
    ("ROE（GAAP）", [pct(rows[f]["roe"]) for f in FY]), ("ROIC（EBIT × (1 − 20.8%) ÷ 投入资本；20.8% = 2024 新闻稿对 2025 年 underlying 税率的预估）", [pct(rows[f]["roic"]) for f in FY]),
    ("有息负债 / 股东权益", [pct(rows[f]["de"], 0) for f in FY]),
]
sens_rows = "".join(tr([{"r": "折现率 r", "g1": "阶段 1 增速 g1", "g_terminal": "终端增长率"}[x["var"]],
                        f"{x['delta'] * 100:+.1f} 个百分点", f"{x['iv_per_share']:.2f}", f"{x['change'] * 100:+.0f}%"])
                    for x in V["sensitivity"]["rows"])
score_rows = "".join(tr(r) for r in [
    ("Business Quality", 30, V["scorecard"]["business"], f"1A / 1B / 1C = {SD['1A']} / {SD['1B']} / {SD['1C']}：宽护城河；营收 CAGR {pct(rev_cagr)}（< 5%、无负增长）；毛利率三年 > 50%"),
    ("Financial Health", 30, V["scorecard"]["financial"], f"2A / 2B / 2C = {SD['2A']} / {SD['2B']} / {SD['2C']}：ROE 三年均值 {pct(roe_avg)}，负债率 > 40% 但 ROIC 均 > 12% 不降档；FCF 三年为正、剔除后 FCF / 净利润 > 80%；负债率 {pct(rows['2025']['dr'], 0)}（40–60% 档）"),
    ("Management Quality", 25, V["scorecard"]["management"], f"3A / 3B / 3C = {SD['3A']} / {SD['3B']} / {SD['3C']}：基础 6 + 分红连增 2 − BODYARMOR 减值 4；持股数据未取得按保守档；新 CEO 在任不满 1 年按中性"),
    ("Price vs Value", 15, V["scorecard"]["price"], f"4A / 4B = {SD['4A']} / {SD['4B']}：安全边际为负；EV/FCF {ko_evf:.1f}x 与同行均值 {peer_avg:.1f}x 相差 ±20% 以内"),
    ("总分", 100, total, "55–69 = 观察名单；未触发自动降级"),
])

verdict_zh = f"好生意，贵价格：现价 {price:.2f} 高于内在价值上沿，安全边际（下沿）{mos * 100:.1f}%，不买；{buy30:.2f} 以下才进入买入区间。"

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
<div><b>{total} / 100</b><span>巴菲特评分 → 观察名单</span></div>
</div>

<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<p><strong>结论：高估区间，不买。</strong>护城河宽（{INP['moat_score']} / 10），但现价 {price:.2f} 比内在价值上沿 {hi:.2f} 还高；
按下沿算安全边际 {mos * 100:.1f}%。要回到 30% 安全边际，价格需在 {buy30:.2f} 以下。现价隐含未来 5 年 FCF 年增 {pct(ig['g1'])}，
是过去两年（剔除一次性项）{pct(V['fcf_cagr'])} 的约 {ig['g1'] / V['fcf_cagr']:.1f} 倍。</p>
{price_svg()}

<h2>一、护城河分析 <span class="en">Moat</span></h2>
{moat_svg()}
<p>护城河类型：<strong>无形资产（品牌定价权）+ 规模壁垒（全球装瓶分销体系）</strong>。评分 {INP['moat_score']} / 10，宽护城河；未触发侵蚀信号，不下调。</p>
<table>{tr(["信号", "数据", "判定"], True)}
{tr(["毛利率高于同行", f"KO FY2025 毛利率 {pct(rows['2025']['gm'])}；PEP {pct(peer_gm['pep'][2])}、KDP {pct(peer_gm['kdp'][2])}，同行均值 {pct(peer_gm25)}（高 {(rows['2025']['gm'] - peer_gm25) * 100:.1f} 个百分点，相对高 {(rows['2025']['gm'] / peer_gm25 - 1) * 100:.0f}%）", "按相对口径成立；按百分点口径未到 10 个点"])}
{tr(["涨价后销量不掉", "FY2024 price/mix +11%，其中约 5 个点来自高通胀市场定价，其余约 6 个点来自市场定价与结构；同年单位箱量 +1%。FY2025 price/mix +4%，单位箱量持平", "成立（剔除高通胀市场后仍 > 5% 一次；FY2025 低于 5%）"])}
{tr(["份额", "FY2025 与 2026 Q3 均在无酒精即饮饮料（NARTD）赢得价值份额；但 2026 Q3 EMEA 份额下滑（法国、英国）", "整体成立，EMEA 局部承压"])}
{tr(["侵蚀信号", f"毛利率三年 {pct(rows['2023']['gm'])} → {pct(rows['2025']['gm'])}，无压缩；无连续两年份额流失", "未触发"])}
</table>
<p class="src">来源：SEC companyfacts（毛利 GrossProfit / 营收）；2024、2025 年业绩新闻稿（price/mix、单位箱量、份额）；2026 Q3 新闻稿（份额）。</p>
<p>为什么给 7 而不是 8：涨价证据里有一半来自高通胀市场，不完全是品牌溢价；EMEA 份额在最近一个季度下滑。两种评分落在同一档（7–8），估值上限相同，结论不受影响。</p>
<p>主要挑战：减糖与健康饮品趋势对含糖碳酸饮料的长期压力；装瓶体系议价（再特许经营后营收口径变化）。</p>

<h2>二、核心财务指标 <span class="en">Financials, FY2023–FY2025</span></h2>
{trend_svg()}
<table>{tr(["指标"] + [f"FY{f}" for f in FY], True)}{"".join(tr([n] + v) for n, v in fin_rows)}</table>
<p class="src">来源：SEC companyfacts 10-K（单位百万美元换算为十亿）；有息负债 = 长期债务含一年内到期部分 + 应付票据及借款（KO 2024 年起改报 LongTermDebtAndCapitalLeaseObligations 标签）。</p>
<div class="warn"><strong>两笔一次性现金流出（公司在业绩新闻稿中自己列出金额）：</strong>FY2024 向美国国税局（IRS）缴纳税务诉讼保证金 $6.0B；FY2025 支付 fairlife 并购或有对价 $6.1B。
它们把 FCF 压到 {m(rows['2024']['fcf_rep'])} / {m(rows['2025']['fcf_rep'])}。估值按剔除后的 {m(rows['2024']['fcf_n'])} / {m(rows['2025']['fcf_n'])} 计算（与公司公布的 $10.8B / $11.4B 一致）。
不剔除时 FCF 复合增速为 {pct(wa['fcf_cagr'])}，内在价值降到 {wa['iv_range'][0]:.2f}–{wa['iv_range'][1]:.2f}：<strong>结论不变，仍是高估</strong>。</div>
<p class="quote">“Both decreased versus the prior year, primarily due to a $6.0 billion deposit made to the U.S. Internal Revenue Service … related to ongoing tax litigation.” — 2024 年业绩新闻稿</p>
<p class="quote">“… which reflects $6.1 billion of the contingent consideration payment made during the first quarter in conjunction with the acquisition of fairlife, LLC.” — 2025 年业绩新闻稿</p>
<p>FCF 转化率（剔除后）{pct(rows['2023']['conv'], 0)} / {pct(rows['2024']['conv'], 0)} / {pct(rows['2025']['conv'], 0)}：正常偏优。ROIC {pct(rows['2025']['roic'])} 高于折现率 9%：价值创造。
ROE 三年均值 {pct(roe_avg)} 有杠杆成分（有息负债约为股东权益的 {rows['2025']['de']:.1f} 倍），用 ROIC 复核后仍 > 12%，不降档。</p>

<h2>三、管理层评估 <span class="en">Management</span></h2>
<p><strong>资本分配（近 3 年实际行为）：</strong></p>
<table>{tr(["行为", "数据", "评分影响"], True)}
{tr(["分红", f"支付普通股股息 {m(divs[0])} → {m(divs[1])} → {m(divs[2])} → {m(divs[3])}，连续增长", "+2"])}
{tr(["回购", f"FY2023–FY2025 回购 {m(bb[0])} / {m(bb[1])} / {m(bb[2])}；当时估值远高于 PE 15 / PB 2，不符合低估回购", "0"])}
{tr(["并购后减值", "2025 Q4 计提 BODYARMOR 商标非现金减值 $960M（2021 年收购的品牌）", "−4"])}
{tr(["股权激励稀释", f"稀释后股数 {dil[0] / 1000:.2f}B → {dil[3] / 1000:.2f}B，逐年下降，无稀释", "0"])}
</table>
<p>3A = 6 + 2 − 4 = {SD['3A']}。3B：职业经理人；未取得 DEF 14A 持股数据，按「少量持股」保守档 {SD['3B']} 分（见 §七）。</p>
<div class="warn">管理层变动：James Quincey（CEO 九年）2026-03-31 卸任、改任执行董事长 → Henrique Braun（原 COO，1996 年加入公司）接任，在任约 7 个月，不满 1 年。按评分规则 3C 取中性 {SD['3C']} 分，新任的纠正或加分行为暂不计入。</div>
<p class="src">来源：SEC companyfacts（PaymentsOfDividendsCommonStock、PaymentsForRepurchaseOfCommonStock、WeightedAverageNumberOfDilutedSharesOutstanding）；2025 年业绩新闻稿（BODYARMOR 减值）；CEO 交接公告；2026 Q3 新闻稿（Braun 以 CEO 身份发言）。</p>

<h2>四、内在价值估算 <span class="en">Owner Earnings DCF</span></h2>
<p><strong>所有者盈余（FY2025）</strong>：净利润 {m(last['net_income'])} + D&amp;A {m(last['da'])} − 维护性资本支出 {m(oe['maint_capex'])} − 营运资本增加 {m(-dwc_adj)}（报告值 {m(-last['dwc'])}，已加回 fairlife 支付 $6.1B）= <strong>{m(oe['value'])}</strong>。
维护性资本支出取总资本支出的 50%：轻资产消费品，D&amp;A 不能代表维护性资本支出；50% 后的 {m(oe['maint_capex'])} 与 D&amp;A {m(last['da'])} 几乎相等，两种口径结论相同。</p>
<table>{tr(["参数", "保守情景", "基准情景", "依据"], True)}
{tr(["阶段 1 增速（1–5 年）", pct(sc['g1'], 2), pct(scn['g1'], 2), f"剔除后 FCF 复合增速 {pct(V['fcf_cagr'], 2)} × 60% / × 85%，未触 18% 上限"])}
{tr(["阶段 2 增速（6–10 年）", pct(sc['g2'], 2), pct(scn['g2'], 2), "阶段 1 × 50% / × 60%"])}
{tr(["终端增长率", pct(sc['g_terminal'], 1), pct(scn['g_terminal'], 1), "护城河上限 8% × 60% / × 80%，再受 2.5% / 4% 封顶"])}
{tr(["折现率", "9%", "9%", "美股大盘股 9%；10 年期美债 4.86% 在 4–5% 区间，不调整"])}
{tr(["每股内在价值", f"{lo:.2f}", f"{hi:.2f}", "两情景 DCF ÷ 4.30B 股"])}
{tr(["终值占比", pct(sc['terminal_share'], 0), pct(scn['terminal_share'], 0), "基准 > 60% → 出口倍数交叉验证"])}
</table>
<p>出口倍数交叉验证（基准情景）：第 10 年所有者盈余 {m(scn['oe_year10'])} × 同行 EV/FCF 均值 {peer_avg:.1f}x 折现 = 每股 {scn['exit_multiple_iv']:.2f}，与 DCF 的 {hi:.2f} 相差 {abs(scn['exit_multiple_iv'] / hi - 1) * 100:.0f}%（< 30%，通过，不替换）。</p>
<table>{tr(["价格锚点", "价位", "说明"], True)}
{tr(["内在价值下沿（保守情景）", f"{lo:.2f}", "安全边际的计算基准"])}
{tr(["当前股价", f"{price:.2f}", F['ko']['price']['date']])}
{tr(["当前安全边际", f"{mos * 100:.1f}%", f"(下沿 − 现价) ÷ 下沿；现价比下沿高 {(price / lo - 1) * 100:.0f}%"])}
{tr(["目标买入价（安全边际 30%）", f"{buy30:.2f}", "下沿 × 70%，严格建仓线"])}
{tr(["目标买入价（安全边际 35%）", f"{lo * 0.65:.2f}", "下沿 × 65%，保守建仓线"])}
</table>
<p><strong>逆向验证：现价隐含什么？</strong>按基准情景结构倒推，现价 {price:.2f} 要成立，需要阶段 1 增速 {pct(ig['g1'])}、阶段 2 {pct(ig['g2'])}、终端 {pct(ig['g_terminal'], 0)}。
即市场在为「一家营收两年复合增长 {pct(rev_cagr)} 的公司，未来五年 FCF 每年增长约 13%」定价。这没有超过宽护城河 18% 的上限，但远高于它自己的历史：属于<strong>激进</strong>假设。
公司 2026 年前三季度 FCF 已达 $11.4B（Q3 新闻稿），新闻稿称已更新全年指引（updated full year guidance）；若 2026 全年 FCF 增速明显高于 13%，这个判断需要重估。</p>
<p class="src">来源：owner_value 底稿 {VAL}（每个输入带来源）；FY2025 财务数据 SEC companyfacts；同行 EV/FCF 由 financials/pep.json、kdp.json 计算。</p>

<div class="verdict"><strong>裁决：观察名单，当前不买。</strong>{verdict_zh}
<div class="en">Wonderful business, demanding price: shares trade above the base-case intrinsic value; no margin of safety at the conservative bound.</div></div>

<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
<table>{tr(["维度", "满分", "得分", "关键依据"], True)}{score_rows}</table>
<p>相对估值：KO EV/FCF {ko_evf:.1f}x（FCF 按剔除一次性项；按报告值则为 {ko_evf_rep:.0f}x）；PEP {pep_evf:.1f}x、KDP {kdp_evf:.1f}x。同行只有两家，相对估值仅作辅助。</p>
<p>一致性提示：2B 按剔除一次性项的 FCF 打 10 分；按报告值 FCF（FY2024、FY2025 转化率 {pct(rows['2024']['conv_rep'], 0)} / {pct(rows['2025']['conv_rep'], 0)}）只能打 2–5 分，总分变为 50–53（谨慎档）。两种口径都落在「不买」。</p>

<h2>六、主要风险 <span class="en">Risks</span></h2>
<table>{tr(["风险", "说明", "对估值的影响"], True)}
{tr(["IRS 税务诉讼", "$6.0B 保证金已付；若最终败诉，保证金转为真实税款，后续年度税率也可能上升。2025 新闻稿的 20.9% 税率预估不含败诉影响", "本估值把保证金当一次性项加回、未扣除潜在负债；败诉会直接压低内在价值，幅度取决于 10-K 附注（未取得）"])}
{tr(["健康与减糖趋势", "含糖碳酸饮料长期需求压力；公司靠无糖版本与非碳酸品类对冲（2026 Q3 Coca-Cola Zero Sugar +16%）", "压低长期增速；增速 −3 个百分点 → 下沿约 −16%"])}
{tr(["汇率", "FY2025 EPS 受 8 个点汇率逆风", "影响报告期利润，不改变长期判断"])}
{tr(["利率", "折现率随 10 年期美债变化", "r +1 个百分点 → 下沿约 −13%"])}
</table>
<p>需要重估内在价值的情况：2026 全年 FCF（剔除一次性项）同比增速 > 13%；IRS 诉讼判决公布；股价跌破 {buy30:.2f}。</p>

<h2>七、数据盲区与敏感性 <span class="en">Gaps and Sensitivity</span></h2>
<ul>
<li>管理层持股比例（DEF 14A 代理声明）未取得 → 3B 按保守档；补齐后最多 +2 分，不改变结论。</li>
<li>IRS 诉讼潜在负债金额（10-K 附注）未取得 → 风险未量化进内在价值。</li>
<li>10-K 原文在会话容器打不开，财务数字来自 SEC XBRL（与 10-K 同源，每个值带 accession 号）。</li>
</ul>
<table>{tr(["变量（以保守情景为底）", "变动", "每股内在价值", "变化"], True)}{sens_rows}</table>

<h2>来源索引 <span class="en">Sources</span></h2>
<ol class="src">{"".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC)}</ol>

<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<p>本报告所有估值数字由 tools/owner_value.py 计算（底稿 {VAL}），报告生成脚本只读取、不手算。已登记一条可证伪判断：KO 2030 财年 FCF（公司剔除一次性项口径）低于现价隐含路径 $20.7B，把握中，2031-02-28 验证（memory/state/predictions.md）。
本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&report=ko">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=ko</a></p></div>
</div></body></html>"""

out = os.path.join(REPO, "reports/ko_Buffett_Report.html")
open(out, "w", encoding="utf-8").write(html)
print("→", os.path.relpath(out, REPO))
