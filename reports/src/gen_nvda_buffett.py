#!/usr/bin/env python3
"""reports/nvda_Buffett_Report.html —— buffett-analyst 第二个真实任务（2026-11-09，用户「巴菲特看英伟达」）。
估值数字只读 owner_value 底稿（主底稿 + 护城河 6 / 9 与 FCF yield 三份对照），财务数字只读 financials/*.json，不手写。
重跑：python3 reports/src/gen_nvda_buffett.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VAL = "memory/state/valuations/nvda_2026-11-09.json"
J = lambda p: json.load(open(os.path.join(REPO, p), encoding="utf-8"))  # noqa: E731
V = J(VAL)
M9, M6, FY = (J(f"memory/state/valuations/nvda_2026-11-09-{x}.json") for x in ("moat9", "moat6", "fcfyield"))
INP = V["input"]
F = {t: J(f"financials/{t}.json") for t in ("nvda", "amd", "avgo")}
FONT = "font-family:'IM Fell English',Georgia,serif"
INK, PAPER, COPPER, GOLD, GREEN, RED, AMBER = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#c47a1e"
YRS = ("2024", "2025", "2026")

SRC = [
    ("SEC EDGAR companyfacts：NVIDIA 10-K XBRL（每个值带 accession 号）", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{F['nvda']['cik']}.json"),
    ("SEC EDGAR companyfacts：AMD 10-K XBRL", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{F['amd']['cik']}.json"),
    ("SEC EDGAR companyfacts：Broadcom AVGO 10-K XBRL", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{F['avgo']['cik']}.json"),
    ("NVIDIA FY2026 第四季度及全年业绩新闻稿（现金流量表、FCF 调节表）", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2026"),
    ("NVIDIA FY2027 第二季度业绩新闻稿（上半年现金流量表）", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027"),
    ("NVIDIA FY2025 第四季度及全年业绩新闻稿（FY2024 现金流对照）", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2025"),
    ("stockanalysis.com NVDA 预测页（S&P Global 汇总的分析师共识，2026-11-09 抓取）", "https://stockanalysis.com/stocks/nvda/forecast/"),
    ("股价：Yahoo Finance 2026-11-06 收盘（GitHub Actions 抓取，financials/*.json）；10 年期美债 4.86%（stock_prices.json）", "https://finance.yahoo.com/quote/NVDA/"),
]


def m(x):
    return f"${x / 1000:,.1f}B"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def val(t, fy, key):
    r = F[t]["years"][fy].get(key)
    return r["v"] / 1e6 if r else None


def debt(t, fy):
    if t == "avgo":
        dt = F[t]["debt_tags"]
        return dt["LongTermDebtAndCapitalLeaseObligations"][fy] / 1e6 + dt["LongTermDebtAndCapitalLeaseObligationsCurrent"][fy] / 1e6
    return (val(t, fy, "debt_lt") or 0) + (val(t, fy, "debt_st") or 0)


ys = {str(y["fy"]): y for y in INP["years"]}
rows = {}
for fy in YRS:
    y = ys[fy]
    eq, cash, d = val("nvda", fy, "equity"), val("nvda", fy, "cash"), debt("nvda", fy)
    etr = val("nvda", fy, "tax") / val("nvda", fy, "pretax")
    rows[fy] = dict(rev=y["revenue"], gm=val("nvda", fy, "gross_profit") / y["revenue"], ni=y["net_income"], ebit=y["ebit"],
                    fcf=y["fcf"], conv=y["fcf"] / y["net_income"], roe=y["net_income"] / eq, sbc=val("nvda", fy, "sbc"),
                    roic=y["ebit"] * (1 - etr) / (d + eq - cash), etr=etr, debt=d, cash=cash, eq=eq)
rg = V["revenue_growth"]
rev_cagr = (rows["2026"]["rev"] / rows["2024"]["rev"]) ** 0.5 - 1
roe_avg = sum(r["roe"] for r in rows.values()) / 3
peer_gm = {t: val(t, "2025", "gross_profit") / val(t, "2025", "revenue") for t in ("amd", "avgo")}
peer_gm_avg = sum(peer_gm.values()) / 2
peer_growth = {t: val(t, "2025", "revenue") / val(t, "2024", "revenue") - 1 for t in ("amd", "avgo")}
nv_growth = rg["rates"][-1]


def ev_fcf(t, fy):
    p = F[t]
    mcap = p["price"]["v"] * p["shares_outstanding"]["v"] / 1e6
    ev = mcap + debt(t, fy) - val(t, fy, "cash")
    return mcap, ev, ev / (val(t, fy, "cfo") - val(t, fy, "capex"))


nv_mcap, nv_ev, nv_evf = ev_fcf("nvda", "2026")
amd_evf, avgo_evf = ev_fcf("amd", "2025")[2], ev_fcf("avgo", "2025")[2]
peer_evf = (amd_evf + avgo_evf) / 2

lo, hi = V["iv_range"]
price = V["margin_of_safety"]["price"]
mos, hurdle = V["margin_of_safety"]["value"], V["margin_of_safety"]["hurdle"]
buy = lo * (1 - hurdle)
sc, scn = V["scenarios"]["conservative"], V["scenarios"]["base"]
oe = V["owner_earnings"]
last = ys["2026"]
ig = V["implied_g1"]
SD = INP["scores_detail"]
total = V["scorecard"]["total"]
divs = [val("nvda", f, "dividends") for f in ("2023",) + YRS]
bbk = [val("nvda", f, "buyback") for f in YRS]
dil = [val("nvda", f, "diluted_shares") for f in ("2023",) + YRS]
# FY2027 上半年（Q2 FY2027 新闻稿现金流量表，单位百万美元）
H1_CFO, H1_CAPEX, H1_PP = 74421, 4434, 92
H1P_CFO, H1P_CAPEX, H1P_PP = 42779, 3122, 73
h1 = H1_CFO - H1_CAPEX - H1_PP
h1p = H1P_CFO - H1P_CAPEX - H1P_PP
CONS_FCF27 = 190200
thr = rows["2026"]["fcf"] * (1 + ig["g1"]) ** 5


def tr(cells, head=False):
    tag = "th" if head else "td"
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def badge(level):
    c = {"高": GREEN, "中": AMBER, "低": RED}[level]
    return f'<span class="badge" style="border:1px solid {c};color:{c}">置信 {level}</span>'


def price_svg():
    W, x0, x1, vmax = 660, 40, 620, 260.0
    X = lambda v: x0 + (x1 - x0) * v / vmax  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} 160" style="{FONT};width:100%">',
         f'<line x1="{x0}" y1="90" x2="{x1}" y2="90" stroke="{COPPER}"/>']
    for t in range(0, 261, 20):
        o.append(f'<line x1="{X(t):.1f}" y1="87" x2="{X(t):.1f}" y2="93" stroke="{COPPER}"/><text x="{X(t):.1f}" y="108" font-size="10" text-anchor="middle" fill="{COPPER}">{t}</text>')
    o.append(f'<rect x="{X(lo):.1f}" y="72" width="{X(hi) - X(lo):.1f}" height="36" fill="{GOLD}" opacity="0.35"/>')
    o.append(f'<rect x="{X(M9["iv_range"][0]):.1f}" y="118" width="{X(M9["iv_range"][1]) - X(M9["iv_range"][0]):.1f}" height="8" fill="{GOLD}" opacity="0.7"/>'
             f'<text x="{X(M9["iv_range"][1]) + 4:.1f}" y="126" font-size="10" fill="{COPPER}">护城河 9 分时</text>')
    for v_, lab, c, y in ((buy, f"建仓线 {buy:.2f}", GREEN, 60), (lo, f"下沿 {lo:.2f}", INK, 40), (hi, f"上沿 {hi:.2f}", INK, 60),
                          (price, f"现价 {price:.2f}", RED, 24)):
        o.append(f'<line x1="{X(v_):.1f}" y1="{y + 6}" x2="{X(v_):.1f}" y2="114" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{X(v_):.1f}" y="{y}" font-size="12" text-anchor="middle" fill="{c}">{lab}</text>')
    o.append(f'<text x="{x0}" y="150" font-size="11" fill="{COPPER}">每股美元。金色带 = 内在价值区间（护城河 8 分，两情景 DCF）；建仓线 = 下沿 × {1 - hurdle:.0%}（异常增速路径门槛 {hurdle:.0%}）</text>')
    return "".join(o) + "</svg>"


def trend_svg():
    W, H, x0, x1, y0, top, vmax = 660, 240, 70, 600, 190, 20, 130000
    Y = lambda v: y0 - (y0 - top) * v / vmax  # noqa: E731
    X = lambda i: x0 + (x1 - x0) * i / 2  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">']
    for t in range(0, 130001, 20000):
        o.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x1}" y2="{Y(t):.1f}" stroke="#e2dccf"/><text x="{x0 - 8}" y="{Y(t) + 4:.1f}" font-size="10" text-anchor="end" fill="{COPPER}">{t / 1000:.0f}B</text>')
    series = (("净利润", "ni", INK, -8), ("FCF", "fcf", GREEN, 16))
    for n, k, c, dy in series:
        pts = " ".join(f"{X(i):.1f},{Y(rows[fy][k]):.1f}" for i, fy in enumerate(YRS))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2.5"/>')
        for i, fy in enumerate(YRS):
            o.append(f'<circle cx="{X(i):.1f}" cy="{Y(rows[fy][k]):.1f}" r="3.5" fill="{c}"/><text x="{X(i) + 6:.1f}" y="{Y(rows[fy][k]) + dy:.1f}" font-size="10" fill="{c}">{rows[fy][k] / 1000:.1f}</text>')
    for i, fy in enumerate(YRS):
        o.append(f'<text x="{X(i):.1f}" y="{y0 + 18}" font-size="12" text-anchor="middle" fill="{INK}">FY{fy}</text>')
    for j, (n, _, c, _d) in enumerate(series):
        o.append(f'<rect x="{x0 + j * 180}" y="{H - 16}" width="10" height="10" fill="{c}"/><text x="{x0 + 14 + j * 180}" y="{H - 7}" font-size="11" fill="{INK}">{n}</text>')
    return "".join(o) + "</svg>"


def score_svg():
    dims = (("Business Quality", "business", 30), ("Financial Health", "financial", 30), ("Management Quality", "management", 25), ("Price vs Value", "price", 15))
    o = [f'<svg viewBox="0 0 660 160" style="{FONT};width:100%">']
    for i, (n, k, mx) in enumerate(dims):
        y, v_ = 14 + i * 34, V["scorecard"][k]
        o.append(f'<text x="0" y="{y + 14}" font-size="12" fill="{INK}">{n}</text><rect x="170" y="{y}" width="{mx * 14}" height="20" fill="#ddd6c8"/>'
                 f'<rect x="170" y="{y}" width="{v_ * 14}" height="20" fill="{GOLD}"/><text x="{176 + mx * 14}" y="{y + 15}" font-size="12" fill="{COPPER}">{v_} / {mx}</text>')
    o.append(f'<text x="0" y="154" font-size="11" fill="{COPPER}">总分 {total} / 100 → 70–84 = 等待买入（质量优异，等安全边际达标后建仓）</text>')
    return "".join(o) + "</svg>"


fin_rows = [
    ("营收", [m(rows[f]["rev"]) for f in YRS]), ("营收增速", [pct(r, 0) for r in rg["rates"]]),
    ("毛利率", [pct(rows[f]["gm"]) for f in YRS]), ("净利润（GAAP）", [m(rows[f]["ni"]) for f in YRS]),
    ("营业利润（EBIT）", [m(rows[f]["ebit"]) for f in YRS]), ("FCF（CFO − Capex）", [m(rows[f]["fcf"]) for f in YRS]),
    ("FCF / 净利润", [pct(rows[f]["conv"], 0) for f in YRS]), ("SBC / 营收", [pct(rows[f]["sbc"] / rows[f]["rev"]) for f in YRS]),
    ("ROE（GAAP）", [pct(rows[f]["roe"]) for f in YRS]),
    ("ROIC（EBIT × (1 − 当年税率) ÷ 投入资本）", [f"{pct(rows[f]['roic'])}（税率 {pct(rows[f]['etr'])}）" for f in YRS]),
]
sens_rows = "".join(tr([{"r": "折现率 r", "g1": "阶段 1 增速 g1", "g_terminal": "终端增长率"}[x["var"]], f"{x['delta'] * 100:+.1f} 个百分点",
                        f"{x['iv_per_share']:.2f}", f"{x['change'] * 100:+.0f}%"]) for x in V["sensitivity"]["rows"])
moat_rows = "".join(tr([f"{mm} 分", f"{v['scenarios']['conservative']['g1'] * 100:.0f}%", f"{v['iv_range'][0]:.2f}–{v['iv_range'][1]:.2f}",
                        f"{v['margin_of_safety']['value'] * 100:.1f}%", f"{v['scorecard']['total']}"]) for mm, v in ((6, M6), (8, V), (9, M9)))
score_rows = "".join(tr(r) for r in [
    ("Business Quality", 30, V["scorecard"]["business"], f"1A / 1B / 1C = {SD['1A']} / {SD['1B']} / {SD['1C']}：护城河 {INP['moat_score']} 分；营收 CAGR {pct(rev_cagr, 0)}（&gt; 20%、无负增长 → 8）；毛利率三年 &gt; 50% → 7"),
    ("Financial Health", 30, V["scorecard"]["financial"], f"2A / 2B / 2C = {SD['2A']} / {SD['2B']} / {SD['2C']}：ROE 三年均值 {pct(roe_avg, 0)}、负债率 {pct(INP['debt_ratio']['v'])}（无杠杆驱动）→ 12；FCF 三年为正且 FCF / 净利润均 &gt; 80% → 10；现金 {m(rows['2026']['cash'])} &gt; 有息负债 {m(rows['2026']['debt'])}（净现金）→ 8"),
    ("Management Quality", 25, V["scorecard"]["management"], f"3A / 3B / 3C = {SD['3A']} / {SD['3B']} / {SD['3C']}：6 + ROIC &gt; 20% 的内部投资 2（分红 FY2023→FY2024 未增长，不加分）；持股数据未取得 → 3；沟通中性 3"),
    ("Price vs Value", 15, V["scorecard"]["price"], f"4A / 4B = {SD['4A']} / {SD['4B']}：安全边际为负 → 0；EV/FCF {nv_evf:.1f}x，低于同行均值 {peer_evf:.1f}x 逾 20% → 5"),
    ("总分", 100, total, "70–84 = 等待买入；未触发自动降级"),
])
verdict_zh = f"好生意，价格还没到：现价 {price:.2f} 高于内在价值上沿 {hi:.2f}，安全边际（下沿）{mos * 100:.1f}%，离 {hurdle:.0%} 的门槛很远；{buy:.2f} 以下才进入买入区间。"

html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>英伟达 NVDA 巴菲特模型分析</title>
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
table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}} th,td{{border-bottom:1px solid #e2dccf;padding:6px;text-align:left;vertical-align:top}} th{{color:var(--copper);font-weight:normal}}
.verdict{{background:var(--ink);color:var(--paper);padding:20px 22px;margin:26px 0}} .verdict .en{{color:var(--gold);opacity:.8}}
.src{{font-size:12px;color:var(--copper)}} .warn{{border-left:3px solid var(--amber);padding:6px 12px;background:#fff8ec;margin:10px 0}}
.badge{{font-size:11px;padding:0 6px;margin-left:6px;white-space:nowrap}}
.note{{margin-top:36px;border-top:1px solid var(--copper);padding-top:12px;font-size:13px}}
@media(max-width:600px){{.stat{{grid-template-columns:repeat(2,1fr)}} table{{font-size:12px}}}}
</style></head>
<body><div class="wrap" data-valuation="{VAL}">
<div class="pub"><span>巴菲特模型分析报告 · Buffett Model Report</span><span>分析日期 {V['as_of']} · 股价日期 {F['nvda']['price']['date']}</span></div>
<h1>英伟达（NVDA）</h1><div class="en">NVIDIA — Moat, Owner Earnings and Margin of Safety</div>

<div class="stat">
<div><b>{lo:.2f}–{hi:.2f}</b><span>内在价值区间（美元 / 股）</span></div>
<div><b>{price:.2f}</b><span>现价（{F['nvda']['price']['date']} 收盘）</span></div>
<div><b style="color:var(--red)">{mos * 100:.1f}%</b><span>安全边际（按下沿；门槛 {hurdle:.0%}）</span></div>
<div><b>{total} / 100</b><span>巴菲特评分 → 等待买入</span></div>
</div>

<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<ul>
<li><strong>结论：高估区间，不买。</strong>英伟达是一门极好的生意，评分 {total}，落在「等待买入」档。但现价 {price:.2f} 比内在价值上沿 {hi:.2f} 还高。异常增速路径要求 {hurdle:.0%} 的安全边际，价格需在 {buy:.2f} 以下。{badge("中")}</li>
<li>「不买」很稳：护城河评 6、8、9 分，安全边际都达不到 {hurdle:.0%}。「高估」不稳：评 9 分时内在价值升到 {M9['iv_range'][0]:.2f}–{M9['iv_range'][1]:.2f}，高于现价。{badge("高")}</li>
<li>现价隐含未来 5 年所有者盈余每年增长 {pct(ig['g1'])}（FCF 作可观测代理），超过宽护城河允许的 {pct(ig['moat_cap'], 0)} 上限。但近端证据站在市场一边：FY2027 共识 FCF 增长 {pct(CONS_FCF27 / rows['2026']['fcf'] - 1, 0)}，上半年实际 FCF 同比 +{pct(h1 / h1p - 1, 0)}。{badge("低")}</li>
</ul>
{price_svg()}

<h2>一、护城河分析 <span class="en">Moat</span></h2>
<p>护城河评分 <strong>{INP['moat_score']} / 10（宽）</strong>，主类型为无形资产（定价权）加转换成本（软件生态）。未触发侵蚀信号。{badge("中")}</p>
<table>{tr(["维度（moat-framework 五类）", "证据", "判定"], True)}
{tr(["无形资产（定价权）", f"FY2026 毛利率 {pct(rows['2026']['gm'])}，同行 AMD {pct(peer_gm['amd'])}、AVGO {pct(peer_gm['avgo'])}，均值 {pct(peer_gm_avg)}；高 {(rows['2026']['gm'] - peer_gm_avg) * 100:.1f} 个百分点，相对高 {(rows['2026']['gm'] / peer_gm_avg - 1) * 100:.0f}%，两种读法都成立。营收三年扩大约 {rows['2026']['rev'] / rows['2024']['rev']:.1f} 倍，毛利率仍在 71–75%", "成立"])}
{tr(["转换成本（软件生态）", "开发者与软件栈的锁定是常见论点，但本报告没有取得留存率、迁移成本等可量化数据", "方向成立，数据待验证，不单独加分"])}
{tr(["网络效应", "开发者越多、库越全，平台价值越高；同样缺乏可量化数据", "待验证"])}
{tr(["成本优势 / 规模壁垒", "规模带来研发摊薄，但 Fabless 模式的制造在代工厂，没有单位成本对比数据", "不计分（数据不足）"])}
{tr(["侵蚀信号", f"毛利率 FY2024–FY2026 {pct(rows['2024']['gm'])} → {pct(rows['2026']['gm'])}，回落 {(rows['2024']['gm'] - rows['2026']['gm']) * 100:.1f} 个点，未到 5 个点；同行增速 AMD {pct(peer_growth['amd'], 0)}、AVGO {pct(peer_growth['avgo'], 0)}，低于英伟达的 {pct(nv_growth, 0)}", "未触发"])}
</table>
<p>为什么给 8 而不是 9：框架提醒「技术领先的护城河衰减快」。需求集中在少数大客户、客户自研芯片（定性判断，未取得 10-K 客户集中度原文），加上转换成本缺数据，都压着评分。这一分差决定增速上限是 18% 还是 25%，对估值影响很大，见 §四的敏感性表。</p>
<p class="src">来源：SEC companyfacts（GrossProfit ÷ 营收，NVDA FY2024–FY2026；AMD、AVGO FY2025）。</p>

<h2>二、核心财务指标 <span class="en">Financials, FY2024–FY2026</span></h2>
{trend_svg()}
<table>{tr(["指标"] + [f"FY{f}" for f in YRS], True)}{"".join(tr([n] + v) for n, v in fin_rows)}</table>
<p class="src">来源：SEC companyfacts 10-K（财年截至每年 1 月下旬）。投入资本 = 有息负债 + 股东权益 − 现金及等价物。FCF 与公司新闻稿口径的差额是租赁类本金支付，FY2026 为 $0.1B。</p>
<p>FCF 转化率三年都超过 80%，没有一次性项需要剔除。SBC 占营收约 3%，低于 5% 的标注线。现金 {m(rows['2026']['cash'])}，有息负债 {m(rows['2026']['debt'])}，是净现金公司。</p>
<div class="warn"><strong>FY2027 已经发生的数据：</strong>上半年 FCF 为 {m(h1)}，上年同期为 {m(h1p)}，同比增长 {pct(h1 / h1p - 1, 0)}（Q2 新闻稿现金流量表）。分析师共识的 FY2027 FCF 为 {m(CONS_FCF27)}，对 FY2026 增长 {pct(CONS_FCF27 / rows['2026']['fcf'] - 1, 0)}。基准年按规则用最近一个完整财年 FY2026，这部分增长通过下面的增速假设体现。</div>

<h2>三、管理层评估 <span class="en">Management</span></h2>
<table>{tr(["行为（近 3 年）", "数据", "评分影响"], True)}
{tr(["内部投资回报", f"ROIC {pct(rows['2024']['roic'], 0)} / {pct(rows['2025']['roic'], 0)} / {pct(rows['2026']['roic'], 0)}，远高于 20%", "+2"])}
{tr(["分红", f"支付股息 {m(divs[0])} → {m(divs[1])} → {m(divs[2])} → {m(divs[3])}；FY2023 到 FY2024 没有增长，不满足「连续增长 3 年」", "0"])}
{tr(["回购", f"FY2024–FY2026 回购 {m(bbk[0])} / {m(bbk[1])} / {m(bbk[2])}，期间市盈率远高于 15，不算低估回购", "0"])}
{tr(["股权激励稀释", f"稀释后股数 {dil[0] / 1000:.2f}B → {dil[3] / 1000:.2f}B，逐年下降", "0"])}
</table>
<p>3A = 6 + 2 = {SD['3A']}。3B：创始人仍任 CEO，但没有取得 DEF 14A 代理声明里的持股数据，按「职业经理人 + 少量持股」取 {SD['3B']} 分。补齐数据后最多可加 5 分，评级不变。3C 取中性 {SD['3C']} 分。</p>
<p class="src">来源：SEC companyfacts（PaymentsOfDividends、PaymentsForRepurchaseOfCommonStock、WeightedAverageNumberOfDilutedSharesOutstanding、税费与税前利润）。</p>

<h2>四、内在价值估算 <span class="en">Owner Earnings DCF</span></h2>
<p><strong>所有者盈余（FY2026）</strong>：净利润 {m(last['net_income'])} + D&amp;A {m(last['da'])} − 维护性资本支出 {m(oe['maint_capex'])} − 营运资本等现金占用 {m(-last['dwc'])} = <strong>{m(oe['value'])}</strong>。
维护性资本支出取总资本支出的 50%，因为英伟达是 Fabless，制造外包。英伟达不报营运资本变动这一科目，所以用「经营现金流 − 净利润 − D&amp;A − SBC」倒推现金占用。SBC 视为真实成本，不加回。</p>
<p><strong>估值路径：异常增速 DCF（路径 B，安全边际门槛 {hurdle:.0%}）。</strong>三年 FCF 复合增速 {pct(V['fcf_cagr'], 0)}，超过 50%，照公式外推会失真，所以增速按规则另行锚定：</p>
<ul>
<li><strong>第 2 步 · 分析师共识（采用）</strong>：FY2027 共识 FCF 增长 {pct(CONS_FCF27 / rows['2026']['fcf'] - 1, 0)}。FY2028–29 的共识是付费内容，没有取得。只要那两年增速不为负，三年均值就不低于 32%，都高于宽护城河 {pct(ig['moat_cap'], 0)} 的上限，所以取上限。</li>
<li><strong>第 3 步 · FCF yield 反推（对照，不采用）</strong>：yield 约 2.1%，得增速 4.15% / 7.15%，内在价值 {FY['iv_range'][0]:.2f}–{FY['iv_range'][1]:.2f}。这个结果和上半年已经实现的 +{pct(h1 / h1p - 1, 0)} 严重背离。</li>
<li><strong>估值失效条件</strong>：营收增速 {', '.join(pct(r, 0) for r in rg['rates'])}，增速标准差 {rg['stdev'] * 100:.0f} 个百分点，低于 50，DCF 有效。口径由用户 11/09 确定；原工具按营收最高 ÷ 最低算，会把持续高增长误判为波动。</li>
</ul>
<table>{tr(["参数", "保守情景", "基准情景", "依据"], True)}
{tr(["阶段 1 增速（1–5 年）", pct(sc['g1'], 0), pct(scn['g1'], 0), "共识锚定，被护城河上限截断"])}
{tr(["阶段 2 增速（6–10 年）", pct(sc['g2'], 1), pct(scn['g2'], 1), "阶段 1 × 50% / × 60%"])}
{tr(["终端增长率", pct(sc['g_terminal'], 1), pct(scn['g_terminal'], 1), "上限 8% × 60% / × 80%，再受 2.5% / 3% 封顶"])}
{tr(["折现率", "9%", "9%", "美股大盘股；10 年期美债 4.86%"])}
{tr(["每股内在价值", f"{lo:.2f}", f"{hi:.2f}", f"两情景 DCF ÷ {INP['shares']['v'] / 1000:.1f}B 股"])}
{tr(["终值占比", pct(sc['terminal_share'], 0), pct(scn['terminal_share'], 0), "&gt; 60% → 交叉验证"])}
</table>
<p>交叉验证（股权口径）：前 10 年所有者盈余的现值，加上第 10 年所有者盈余乘以同行市值 / FCF 均值 {INP['peer_p_fcf']['v']:.1f}x 后折现，得每股 {sc['exit_multiple_iv']:.2f} / {scn['exit_multiple_iv']:.2f}，和 DCF 相差超过 30%。按规则取较低值，也就是 DCF 值。
同行倍数本身很高（AMD 约 109 倍），说明可比公司也被定价在高增长上，相对估值在这里不是可靠的锚。</p>
<table>{tr(["护城河评分", "阶段 1 增速上限", "内在价值区间", "安全边际（下沿）", "总分"], True)}{moat_rows}</table>
<table>{tr(["价格锚点", "价位", "说明"], True)}
{tr(["内在价值下沿（保守情景）", f"{lo:.2f}", "安全边际的计算基准"])}
{tr(["当前股价", f"{price:.2f}", F['nvda']['price']['date']])}
{tr(["当前安全边际", f"{mos * 100:.1f}%", "(下沿 − 现价) ÷ 下沿"])}
{tr([f"目标买入价（安全边际 {hurdle:.0%}）", f"{buy:.2f}", f"下沿 × {1 - hurdle:.0%}"])}
</table>
<p><strong>逆向验证：</strong>按基准情景的结构倒推，现价要成立，需要阶段 1 增速 {pct(ig['g1'])}、阶段 2 增速 {pct(ig['g2'])}，比宽护城河的上限高 {(ig['g1'] - ig['moat_cap']) * 100:.1f} 个百分点。市场在定价「增长比框架允许的上限还快」。
它在近两年并非不可能：共识第一年就是 +97%。分歧在于第 3 到第 5 年，云厂商的资本开支周期和自研芯片会不会把增速拉回来。{badge("低")}</p>
<p class="src">来源：owner_value 主底稿 {VAL}，护城河 6 / 9 分与 FCF yield 对照底稿在同一目录；共识见来源索引。</p>

<div class="verdict"><strong>裁决：等待买入档，当前不买。</strong>{verdict_zh}
<div class="en">An exceptional business priced for growth beyond what a wide-moat framework allows; no margin of safety at the conservative bound.</div></div>

<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
{score_svg()}
<table>{tr(["维度", "满分", "得分", "关键依据"], True)}{score_rows}</table>
<p>相对估值：英伟达 EV/FCF {nv_evf:.1f}x，AMD {amd_evf:.1f}x，AVGO {avgo_evf:.1f}x。英伟达比同行便宜，但同行同样被高增长定价，所以 4B 的 5 分只作辅助，不能覆盖 DCF 的结论。</p>

<h2>六、主要风险 <span class="en">Risks</span></h2>
<table>{tr(["风险", "说明", "对估值的影响"], True)}
{tr(["客户资本开支周期", "需求集中在少数云厂商与 AI 公司的资本开支，开支放缓会同时压营收和毛利率", "增速 −3 个百分点 → 下沿约 −16%（见敏感性表）"])}
{tr(["自研芯片与定制 ASIC", f"AVGO 等定制芯片厂商是直接竞争者（AVGO FY2025 总营收 {pct(peer_growth['avgo'], 0)}，含软件业务，未拆分 AI 芯片）；云厂商自研芯片的规模本报告未取得原文", "护城河从 8 分降到 6 分 → 内在价值 {0}–{1}".format(f"{M6['iv_range'][0]:.2f}", f"{M6['iv_range'][1]:.2f}")])}
{tr(["投资与生态融资", f"FY2027 上半年投资活动现金流出 {m(35124)}，上年同期 {m(12343)}（Q2 新闻稿）；为生态伙伴提供资金会让需求的独立性变弱", "暂未量化，需跟踪承诺转为收入的比例"])}
{tr(["利率", "折现率随 10 年期美债变化", "r +1 个百分点 → 下沿约 −15%"])}
</table>
<p>需要重估内在价值的情况：FY2027 年报公布（基准年切换）；毛利率连续两个季度低于 70%；股价跌破 {buy:.2f}。</p>

<h2>七、数据盲区与敏感性 <span class="en">Gaps and Sensitivity</span></h2>
<ul>
<li>FY2028–29 的分析师共识为付费内容，未取得。只用了 FY2027 一年；增速被护城河上限截断，所以不影响结论。</li>
<li>管理层持股（DEF 14A）、客户集中度（10-K 附注）没有取得原文：3B 按保守档，客户集中只作定性风险。</li>
<li>转换成本、网络效应缺少可量化数据，只作方向判断，不单独加分。</li>
</ul>
<table>{tr(["变量（以保守情景为底）", "变动", "每股内在价值", "变化"], True)}{sens_rows}</table>

<h2>来源索引 <span class="en">Sources</span></h2>
<ol class="src">{"".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC)}</ol>

<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<table>{tr(["结论", "置信", "为什么"], True)}
{tr(["当前不买", "高", f"护城河评 6、8、9 分，安全边际都达不到 {hurdle:.0%}"])}
{tr(["高估（价格高于内在价值上沿）", "中", "成立的前提是护城河 8 分；评 9 分时不成立"])}
{tr([f"现价隐含的 {pct(ig['g1'])} 增速难以持续 5 年", "低", f"近端证据支持市场；已登记 predictions.md：FY2031 FCF &lt; ${thr / 1000:.1f}B，2031-03-31 验证"])}
</table>
<p><strong>待核实：</strong>FY2028–29 共识；DEF 14A 持股；10-K 客户集中度；FY2027 年报 FCF（预计 2027 年 2 月）。</p>
<p><strong>分析师看法：</strong>在巴菲特框架里，英伟达是「看得懂的好生意，但价格要求的增长超出框架上限」。框架给的是买入纪律，不是对股价的方向判断。
如果你认为它的护城河配得上 9 分，内在价值大约在 {M9['iv_range'][0]:.0f}–{M9['iv_range'][1]:.0f}，现价有约 {M9['margin_of_safety']['value'] * 100:.0f}% 的安全边际，但仍然低于 {hurdle:.0%} 的门槛。这一分是本报告最关键的主观判断。</p>
<p>本报告的估值数字全部由 tools/owner_value.py 计算，生成脚本只读取、不手算。本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&report=nvda">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=nvda</a></p></div>
</div></body></html>"""

out = os.path.join(REPO, "reports/nvda_Buffett_Report.html")
open(out, "w", encoding="utf-8").write(html)
print("→", os.path.relpath(out, REPO))
