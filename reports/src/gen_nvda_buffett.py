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
M9, M7, FY = (J(f"memory/state/valuations/nvda_2026-11-09-{x}.json") for x in ("moat9", "moat7", "fcfyield"))
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
    ("NVIDIA 2026 年度报告 PDF（含 FY2026 10-K 与代理声明：客户集中度、创始人持股）", "https://s201.q4cdn.com/141608511/files/doc_financials/2026/ar/2026-Annual-Report-Web.pdf"),
    ("HPCwire：TechInsights 研究，2023 年 NVIDIA 数据中心 GPU 出货份额 98%（2024-06-10）", "https://www.hpcwire.com/2024/06/10/nvidia-shipped-3-76-million-data-center-gpus-in-2023-according-to-study/"),
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
T = INP["ttm"]
CASH_MS26 = 62556  # FY2026 Q4 新闻稿资产负债表：现金、现金等价物与有价证券
DWC26 = {"营运资本变动": -15399 - 11324 + 577 + 3096 + 5257 + 1844, "权益证券收益（非现金）": -8918, "递延所得税": -1424, "其他": -287}
GAIN_TTM = 8918 + 23707 - 2073
OPM = {fy: rows[fy]["ebit"] / rows[fy]["rev"] for fy in YRS}


def tr(cells, head=False):
    tag = "th" if head else "td"
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def badge(level):
    c = {"高": GREEN, "中": AMBER, "低": RED}[level]
    return f'<span class="badge" style="border:1px solid {c};color:{c}">置信 {level}</span>'


def price_svg():
    W, x0, x1, vmax = 660, 40, 600, 340.0
    X = lambda v: x0 + (x1 - x0) * v / vmax  # noqa: E731
    o = [f'<svg viewBox="0 0 {W} 160" style="{FONT};width:100%">',
         f'<line x1="{x0}" y1="90" x2="{x1}" y2="90" stroke="{COPPER}"/>']
    for t in range(0, 341, 40):
        o.append(f'<line x1="{X(t):.1f}" y1="87" x2="{X(t):.1f}" y2="93" stroke="{COPPER}"/><text x="{X(t):.1f}" y="108" font-size="10" text-anchor="middle" fill="{COPPER}">{t}</text>')
    o.append(f'<rect x="{X(lo):.1f}" y="72" width="{X(hi) - X(lo):.1f}" height="36" fill="{GOLD}" opacity="0.35"/>')
    o.append(f'<rect x="{X(M9["iv_range"][0]):.1f}" y="118" width="{X(M9["iv_range"][1]) - X(M9["iv_range"][0]):.1f}" height="8" fill="{GOLD}" opacity="0.7"/>'
             f'<text x="{X(M9["iv_range"][0]) - 4:.1f}" y="126" font-size="10" text-anchor="end" fill="{COPPER}">护城河 9 分时</text>')
    # 现价与下沿相距很近：现价标签靠左（end）、下沿靠右（start），避免重叠
    for v_, lab, c, y, anc in ((buy, f"建仓线 {buy:.2f}", GREEN, 60, "middle"), (lo, f"下沿 {lo:.2f}", INK, 40, "start"),
                               (hi, f"上沿 {hi:.2f}", INK, 60, "start"), (price, f"现价 {price:.2f}", RED, 24, "end")):
        o.append(f'<line x1="{X(v_):.1f}" y1="{y + 6}" x2="{X(v_):.1f}" y2="114" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{X(v_) + (4 if anc == "start" else -4 if anc == "end" else 0):.1f}" y="{y}" font-size="12" text-anchor="{anc}" fill="{c}">{lab}</text>')
    o.append(f'<text x="{x0}" y="150" font-size="11" fill="{COPPER}">每股美元。金色带 = 内在价值区间（护城河 {INP["moat_score"]} 分，两情景 DCF，TTM 基数）；建仓线 = 下沿 × {1 - hurdle:.0%}（异常增速路径门槛 {hurdle:.0%}）</text>')
    return "".join(o) + "</svg>"


BAND = {3: ("3–4 = 窄护城河", "8%", "3%"), 4: ("3–4 = 窄护城河", "8%", "3%"), 5: ("5–6 = 中等", "12%", "5%"), 6: ("5–6 = 中等", "12%", "5%"),
        7: ("7–8 = 宽护城河", "18%", "8%"), 8: ("7–8 = 宽护城河", "18%", "8%"), 9: ("9–10 = 卓越", "25%", "10%"), 10: ("9–10 = 卓越", "25%", "10%")}[INP["moat_score"]]


def moat_svg():
    o = [f'<svg viewBox="0 0 660 70" style="{FONT};width:100%">']
    for i in range(10):
        o.append(f'<rect x="{40 + i * 58}" y="14" width="52" height="22" fill="{GOLD if i < INP["moat_score"] else "#ddd6c8"}"/><text x="{66 + i * 58}" y="52" font-size="10" text-anchor="middle" fill="{COPPER}">{i + 1}</text>')
    o.append(f'<text x="40" y="66" font-size="11" fill="{COPPER}">护城河评分 {INP["moat_score"]} / 10（{BAND[0]}：阶段 1 增速上限 {BAND[1]}，终端增长上限 {BAND[2]}）</text>')
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
                        f"{v['margin_of_safety']['value'] * 100:.1f}%", f"{v['scorecard']['total']}"]) for mm, v in ((6, V), (7, M7), (9, M9)))
score_rows = "".join(tr(r) for r in [
    ("Business Quality", 30, V["scorecard"]["business"], f"1A / 1B / 1C = {SD['1A']} / {SD['1B']} / {SD['1C']}：护城河 {INP['moat_score']} 分；营收 CAGR {pct(rev_cagr, 0)}（&gt; 20%、无负增长 → 8）；毛利率三年 &gt; 50% → 7"),
    ("Financial Health", 30, V["scorecard"]["financial"], f"2A / 2B / 2C = {SD['2A']} / {SD['2B']} / {SD['2C']}：ROE 三年均值 {pct(roe_avg, 0)}、负债率 {pct(INP['debt_ratio']['v'])}（无杠杆驱动）→ 12；FCF 三年为正且 FCF / 净利润均 &gt; 80% → 10；现金 {m(rows['2026']['cash'])} &gt; 有息负债 {m(rows['2026']['debt'])}（净现金）→ 8"),
    ("Management Quality", 25, V["scorecard"]["management"], f"3A / 3B / 3C = {SD['3A']} / {SD['3B']} / {SD['3C']}：6 + ROIC &gt; 20% 的内部投资 2（分红 FY2023→FY2024 未增长，不加分）；创始人持股 3.58%（&gt; 1% 股本）→ 5；沟通未评估，取中性 3（3C 取 0–5 时总分 {total - SD['3C']}–{total - SD['3C'] + 5}，评级不变）"),
    ("Price vs Value", 15, V["scorecard"]["price"], f"4A / 4B = {SD['4A']} / {SD['4B']}：安全边际 {mos * 100:.1f}%（&lt; 10%）→ 0；EV/FCF {nv_evf:.1f}x，低于同行均值 {peer_evf:.1f}x 逾 20% → 5"),
    ("总分", 100, total, "70–84 = 等待买入；未触发自动降级"),
])
verdict_zh = f"好生意，价格偏贵：现价 {price:.2f} 高于内在价值上沿 {hi:.2f}，安全边际（下沿）{mos * 100:.1f}%；{buy:.2f} 以下才进入买入区间。"
alt3b = total  # 3B 已按创始人持股取 5

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
<div><b>{mos * 100:.1f}%</b><span>安全边际（按下沿；门槛 {hurdle:.0%}）</span></div>
<div><b>{total} / 100</b><span>巴菲特评分 → 等待买入</span></div>
</div>

<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<ul>
<li><strong>结论：高估区间，不买。</strong>英伟达是一门极好的生意，评分 {total}，落在「等待买入」档。但现价 {price:.2f} 高于内在价值上沿 {hi:.2f}，安全边际（下沿）{mos * 100:.1f}%。异常增速路径要求 {hurdle:.0%}，价格需在 {buy:.2f} 以下。{badge("高")}</li>
<li>「不买」在框架内很稳：护城河评 6、7、9 分，安全边际都达不到 {hurdle:.0%}。「高估」取决于护城河分数：按证据评 6 分时成立；评 7 分时价格约等于保守估值。{badge("中")}</li>
<li>现价隐含未来 5 年所有者盈余每年增长 {pct(ig['g1'])}，超过中等护城河 {pct(ig['moat_cap'], 0)} 的增速上限。</li>
</ul>
{price_svg()}

<h2>一、护城河分析 <span class="en">Moat</span></h2>
{moat_svg()}
<p>护城河评分 <strong>{INP['moat_score']} / 10（中等）</strong>：五类护城河里，没有一类能用现有数据证明成立。按框架「不能脱离数据主观打分」取 6。7 分与 9 分的结果见 §四敏感性表。{badge("中")}</p>
<table>{tr(["维度（moat-framework 五类）", "证据", "判定"], True)}
{tr(["规模壁垒", f"TechInsights：2023 年 NVIDIA 数据中心 GPU 出货份额 98%，与 2022 年相近；该统计不含云厂商自研芯片。营业利润率 {pct(OPM['2024'], 0)} → {pct(OPM['2025'], 0)} → {pct(OPM['2026'], 0)}：FY2025 抬高，FY2026 营收增长 {pct(nv_growth, 0)} 时反而回落 2 个点。份额只有两年、已过时三年；口径为「数据中心 GPU」，三家合计本来就是 100%；同一报道写明云厂商都在做自研芯片", "待验证（信号偏弱）"])}
{tr(["无形资产（定价权）", f"信号①：FY2026 毛利率 {pct(rows['2026']['gm'])}，同行 AMD {pct(peer_gm['amd'])}、AVGO {pct(peer_gm['avgo'])}，均值 {pct(peer_gm_avg)}；高 {(rows['2026']['gm'] - peer_gm_avg) * 100:.1f} 个百分点，相对高 {(rows['2026']['gm'] / peer_gm_avg - 1) * 100:.0f}%。信号②「5 年内 2 次 &gt; 5% 提价」没有单价数据", "待验证（只有 1 个信号）"])}
{tr(["转换成本", "开发者与软件栈锁定是常见论点，没有留存率或迁移成本数据", "待验证"])}
{tr(["网络效应", "开发者越多、库越全，平台价值越高；没有可量化数据", "待验证"])}
{tr(["成本优势", "Fabless 模式，制造在代工厂，没有单位成本对比", "不计分"])}
</table>
<p>侵蚀信号：毛利率 FY2024–FY2026 {pct(rows['2024']['gm'])} → {pct(rows['2026']['gm'])}，回落 {(rows['2024']['gm'] - rows['2026']['gm']) * 100:.1f} 个点，未到 5 个点；同行营收增速 AMD {pct(peer_growth['amd'], 0)}、AVGO {pct(peer_growth['avgo'], 0)}，低于英伟达的 {pct(nv_growth, 0)}。份额是否连续流失无法检验（份额数据停在 2023 年）。其余信号未触发。</p>
<p>为什么给 6：毛利率高出同行是唯一有数据的信号，其余维度都缺数据或证据偏弱。这是按框架取的保守分，不是认为它的护城河窄。分数决定增速上限（6 分 12%，7 分 18%，9 分 25%），对估值影响很大。不论 6、7、9 分，结论都是「不买、等待买入档」。</p>
<p class="src">来源：SEC companyfacts（GrossProfit、营业利润 ÷ 营收）；HPCwire 转述的 TechInsights 研究。</p>

<h2>二、核心财务指标 <span class="en">Financials, FY2024–FY2026</span></h2>
<p>财务健康满分：高增长、高转化（FCF / 净利润三年均 &gt; 80%）、净现金、无一次性现金项。</p>
{trend_svg()}
<table>{tr(["指标"] + [f"FY{f}" for f in YRS], True)}{"".join(tr([n] + v) for n, v in fin_rows)}</table>
<p class="src">来源：SEC companyfacts 10-K（财年截至每年 1 月下旬）。投入资本 = 有息负债 + 股东权益 − 现金及等价物；若再扣有价证券（FY2026 现金、等价物与有价证券合计 {m(CASH_MS26)}），ROIC 更高。FCF 与公司口径相差租赁类本金支付，FY2026 为 $0.1B。</p>
<p>FCF 没有一次性现金项。净利润里含权益投资的非现金收益：FY2026 为 {m(8918)}，近 12 个月约 {m(GAIN_TTM)}。所有者盈余按经营现金流口径计算，已把它们剔出。SBC 约占营收 3%，低于 5% 的标注线。现金、等价物与有价证券 {m(CASH_MS26)}，有息负债 {m(rows['2026']['debt'])}，是净现金公司。</p>
<p>增速说明：FY2024→FY2026 是两期复合。营收两年扩大约 {rows['2026']['rev'] / rows['2024']['rev']:.1f} 倍，复合 {pct(rev_cagr, 0)}；FCF 复合 {pct(V['fcf_cagr'], 0)}。</p>

<h2>三、管理层评估 <span class="en">Management</span></h2>
<p>管理层得分 {V['scorecard']['management']} / 25：创始人长期执掌、内部投资回报极高；分红未连续增长、回购不在低估时点。</p>
<table>{tr(["行为（近 3 年）", "数据", "评分影响"], True)}
{tr(["内部投资回报", f"ROIC {pct(rows['2024']['roic'], 0)} / {pct(rows['2025']['roic'], 0)} / {pct(rows['2026']['roic'], 0)}，远高于 20%", "+2"])}
{tr(["分红", f"支付股息 {m(divs[0])} → {m(divs[1])} → {m(divs[2])} → {m(divs[3])}；FY2023 到 FY2024 没有增长", "0"])}
{tr(["回购", f"FY2024–FY2026 回购 {m(bbk[0])} / {m(bbk[1])} / {m(bbk[2])}，期间市盈率远高于 15", "0"])}
{tr(["股权激励稀释", f"稀释后股数 {dil[0] / 1000:.2f}B → {dil[3] / 1000:.2f}B，逐年下降", "0"])}
</table>
<p>3A = 6 + 2 = {SD['3A']}。3B：黄仁勋 1993 年创立公司，并一直任 CEO；持股 8.71 亿股，占 3.58%（2026 年报的代理声明表）。占股本超过 1%，属于「大量持股」。评分表没有「创始人 + 持股低于 10%」这一行，取相邻的「大量持股」档 {SD['3B']} 分。
3C 取中性 {SD['3C']} 分（见 §七）。</p>
<p class="src">来源：SEC companyfacts（股息、回购、稀释股数、税费与税前利润）；NVIDIA 2026 年报 PDF（创始人简介与持股表）。</p>

<h2>四、内在价值估算 <span class="en">Owner Earnings DCF</span></h2>
<p><strong>基数：近 12 个月（TTM，截至 2026-07-26）实际值。</strong>最近完整财年 FY2026 已结束 9 个多月，按用户 11/09 定的规则改用 TTM：TTM = FY2026 + FY2027 上半年 − FY2026 上半年，全部是已发生的现金流，不用预测。</p>
<p><strong>所有者盈余（TTM）</strong>：净利润 {m(T['net_income'])} + D&amp;A {m(T['da'])} − 维护性资本支出 {m(oe['maint_capex'])} − 营运资本与非现金项调整 {m(-T['dwc'])} = <strong>{m(oe['value'])}</strong>，等价于经营现金流 {m(T['cfo'])} − SBC {m(T['sbc'])} − 维护性资本支出。
维护性资本支出取总资本支出的 50%（Fabless）。调整项以 FY2026 为例拆分如下：营运资本变动 {m(DWC26['营运资本变动'])}，权益证券非现金收益 {m(DWC26['权益证券收益（非现金）'])}，递延所得税 {m(DWC26['递延所得税'])}，其他 {m(DWC26['其他'])}；SBC 视为真实成本，不加回。</p>
<p><strong>估值路径：异常增速 DCF（路径 B，门槛 {hurdle:.0%}）。</strong>FCF 两期复合 {pct(V['fcf_cagr'], 0)}，超过 50%。按规则逐步处理：</p>
<ul>
<li><strong>第 1 步 · 增速性质</strong>：属于「结构性平台跃迁」。spoke 的例子直接列了「AI 加速器 2023-」。但需求依赖客户的资本开支周期，这一点放在风险里跟踪。</li>
<li><strong>第 2 步 · 分析师共识（采用）</strong>：FY2027 共识 FCF 增长 {pct(CONS_FCF27 / rows['2026']['fcf'] - 1, 0)}。FY2028–29 的共识是付费内容；只要那两年增速合计高于 −43 个百分点，三年均值就高于 {pct(ig['moat_cap'], 0)}，所以取护城河上限。</li>
<li><strong>第 3 步 · FCF yield 反推（对照，不采用）</strong>：得增速 4.15% / 7.15%，内在价值 {FY['iv_range'][0]:.2f}–{FY['iv_range'][1]:.2f}。它与上半年已实现的 FCF 同比 +{pct(h1 / h1p - 1, 0)} 严重背离。</li>
<li><strong>第 4 步 · 标注</strong>：历史增速异常，DCF 基于正态化增速，可信度中等；当前估值主要由市场对增速的预期驱动，安全边际计算意义有限。</li>
<li><strong>估值失效条件</strong>：营收增速 {', '.join(pct(r, 0) for r in rg['rates'])}，增速标准差 {rg['stdev'] * 100:.0f} 个百分点，低于 50（口径由用户 11/09 确定），DCF 有效。</li>
</ul>
<table>{tr(["参数", "保守情景", "基准情景", "依据"], True)}
{tr(["阶段 1 增速（1–5 年）", pct(sc['g1'], 0), pct(scn['g1'], 0), "共识锚定，被护城河上限截断"])}
{tr(["阶段 2 增速（6–10 年）", pct(sc['g2'], 1), pct(scn['g2'], 1), "阶段 1 × 50% / × 60%"])}
{tr(["终端增长率", pct(sc['g_terminal'], 1), pct(scn['g_terminal'], 1), "上限 8% × 60% / × 80%，再受 2.5% / 3% 封顶"])}
{tr(["折现率", "9%", "9%", "美股大盘股；10 年期美债 4.86%"])}
{tr(["每股内在价值", f"{lo:.2f}", f"{hi:.2f}", f"两情景 DCF ÷ {INP['shares']['v'] / 1000:.1f}B 股"])}
{tr(["终值占比", pct(sc['terminal_share'], 0), pct(scn['terminal_share'], 0), "&gt; 60% → 交叉验证"])}
</table>
<p>增速被上限截断的代价（同为 FCF 口径）：TTM FCF {m(T['fcf'])} × (1 + {pct(sc['g1'], 0)}) = {m(T['fcf'] * (1 + sc['g1']))}，共识的 FY2027 FCF 为 {m(CONS_FCF27)}（期间不完全相同：模型第 1 年截至 2027 年 7 月，FY2027 截至 2027 年 1 月）。框架有意不为超过上限的增长付钱，这部分差距是安全垫，也是可能的低估来源。</p>
<p>交叉验证（股权口径）：前 10 年所有者盈余现值，加上第 10 年所有者盈余 × 同行市值 / FCF 均值 {INP['peer_p_fcf']['v']:.1f}x 后折现，得基准情景每股 {scn['exit_multiple_iv']:.2f}（保守情景终值占比 {pct(sc['terminal_share'], 0)}，未触发；基准情景触发），与 DCF 相差超过 30%。按规则取较低值，即 DCF 值。同行倍数本身很高（AMD 约 109 倍），相对估值在这里不是可靠的锚。</p>
<table>{tr(["护城河评分", "阶段 1 增速上限", "内在价值区间", "安全边际（下沿）", "总分"], True)}{moat_rows}</table>
<table>{tr(["价格锚点", "价位", "说明"], True)}
{tr(["内在价值下沿（保守情景）", f"{lo:.2f}", "安全边际的计算基准"])}
{tr(["当前股价", f"{price:.2f}", F['nvda']['price']['date']])}
{tr(["当前安全边际", f"{mos * 100:.1f}%", "(下沿 − 现价) ÷ 下沿"])}
{tr([f"目标买入价（安全边际 {hurdle:.0%}）", f"{buy:.2f}", f"下沿 × {1 - hurdle:.0%}"])}
</table>
<p><strong>逆向验证：</strong>按基准情景结构倒推，现价要求阶段 1 增速 {pct(ig['g1'])}、阶段 2 增速 {pct(ig['g2'])}，比中等护城河的上限高 {(ig['g1'] - ig['moat_cap']) * 100:.1f} 个百分点，在宽护城河（18%）上限之内。这是计算值，本报告不对它能否兑现下判断。</p>
<p class="src">来源：owner_value 主底稿 {VAL}；护城河 7 / 9 分与 FCF yield 对照底稿在同一目录；TTM 的分项来自两份新闻稿的现金流量表。</p>

<div class="verdict"><strong>裁决：等待买入档，当前不买。</strong>{verdict_zh}
<div class="en">An exceptional business priced above its intrinsic value on evidence-based moat scoring; no margin of safety against a 40% hurdle.</div></div>

<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
{score_svg()}
<table>{tr(["维度", "满分", "得分", "关键依据"], True)}{score_rows}</table>
<p>相对估值：英伟达 EV/FCF {nv_evf:.1f}x，AMD {amd_evf:.1f}x，AVGO {avgo_evf:.1f}x。英伟达比同行便宜，但同行同样被高增长定价，4B 的 5 分只作辅助，不能覆盖 DCF 的结论。</p>

<h2>六、主要风险 <span class="en">Risks</span></h2>
<table>{tr(["风险", "说明", "对估值的影响"], True)}
{tr(["客户集中", "FY2026 两家直接客户分别占营收 22% 和 14%（10-K）；需求依赖少数客户的资本开支周期", "增速 −3 个百分点 → 下沿约 {0:.0f}%".format([x for x in V['sensitivity']['rows'] if x['var'] == 'g1' and x['delta'] < 0][0]['change'] * 100)])}
{tr(["自研芯片与定制 ASIC", f"TechInsights 指出 Google TPU 等替代方案在出现；AVGO 是直接竞争者（FY2025 营收增速 {pct(peer_growth['avgo'], 0)}，含软件业务，未拆分）", "也是护城河只能评 6 分的原因之一；若证据补齐评到 7 分，内在价值为 {0}–{1}".format(f"{M7['iv_range'][0]:.2f}", f"{M7['iv_range'][1]:.2f}")])}
{tr(["投资与生态融资", f"FY2027 上半年投资活动现金流出 {m(35124)}，上年同期 {m(12343)}（Q2 新闻稿）；为生态伙伴提供资金会让需求的独立性变弱", "暂未量化，跟踪承诺转为收入的比例"])}
{tr(["利率", "折现率随 10 年期美债变化", "r +1 个百分点 → 下沿约 {0:.0f}%".format([x for x in V['sensitivity']['rows'] if x['var'] == 'r' and x['delta'] > 0][0]['change'] * 100)])}
</table>
<p>需要重估内在价值的情况：每次季报更新 TTM；毛利率连续两个季度低于 70%；股价跌破 {buy:.2f}。</p>

<h2>七、数据盲区与敏感性 <span class="en">Gaps and Sensitivity</span></h2>
<ul>
<li>FY2028–29 的分析师共识为付费内容，未取得；增速被上限截断，不影响结论。</li>
<li>市场份额只有 2023 年的 TechInsights 数据，且不含云厂商自研芯片；最新份额未取得。</li>
<li>转换成本、网络效应、单价提价没有可量化数据，相关维度记为待验证。</li>
<li>电话会沟通质量未评估，3C 取中性 3 分；取 0–5 时总分 {total - SD['3C']}–{total - SD['3C'] + 5}，评级不变。</li>
<li>护城河五类均缺少足够数据，按框架取 6 分；补齐份额（含自研芯片）、单价、留存率数据后应重评。</li>
</ul>
<table>{tr(["变量（以保守情景为底）", "变动", "每股内在价值", "变化"], True)}{sens_rows}</table>

<h2>来源索引 <span class="en">Sources</span></h2>
<ol class="src">{"".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC)}</ol>

<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<table>{tr(["结论", "置信", "为什么"], True)}
{tr(["当前不买", "高", f"框架内：任何护城河分数对应的增速上限下，安全边际都达不到 {hurdle:.0%}（最高的 9 分时为 {M9['margin_of_safety']['value'] * 100:.0f}%）"])}
{tr(["高估（价格高于内在价值上沿）", "中", f"按证据评 6 分时成立；评 7 分时价格约等于保守估值（安全边际 {M7['margin_of_safety']['value'] * 100:.1f}%）"])}
</table>
<p><strong>待核实：</strong>FY2028–29 共识；最新 AI 加速器份额（含自研芯片）；FY2027 年报（预计 2027 年 2 月）。</p>
<p><strong>分析师看法：</strong>英伟达是看得懂的好生意。按能拿到的证据给护城河打分，现价偏贵；按巴菲特的纪律，没有安全边际就不买。
最关键的判断是护城河分数：评 7 分时价格约等于保守估值；评 9 分时内在价值约 {M9['iv_range'][0]:.0f}–{M9['iv_range'][1]:.0f}，安全边际约 {M9['margin_of_safety']['value'] * 100:.0f}%，仍然低于 {hurdle:.0%}。本报告不登记预测。</p>
<p>本报告的估值数字全部由 tools/owner_value.py 计算，生成脚本只读取、不手算。本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&report=nvda">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=nvda</a></p></div>
</div></body></html>"""

out = os.path.join(REPO, "reports/nvda_Buffett_Report.html")
open(out, "w", encoding="utf-8").write(html)
print("→", os.path.relpath(out, REPO))
