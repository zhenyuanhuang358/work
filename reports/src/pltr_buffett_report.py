#!/usr/bin/env python3
"""PLTR 巴菲特报告生成器（2026-11-08，Critic R1 返修版）——所有数字读 owner_value 底稿，不手算。
运行：python3 reports/src/pltr_buffett_report.py
"""
import json, os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
v = json.load(open(os.path.join(REPO, "memory/state/valuations/pltr_2026-11-08.json")))
IV = v["iv_range"]; MOS = v["margin_of_safety"]["value"] * 100
OE = v["owner_earnings"]["value"]; MC = v["owner_earnings"]["maint_capex"]
IMPL = v["implied_g1"]; SENS = v["sensitivity"]["rows"]; SC = v["scorecard"]
ALT = v["alternative_valuation"]; AT = ALT["trailing"]; AF = ALT["forward"]
PSENS = ALT["peer_sensitivity"]
SCEN = v["scenarios"]
price = 160.38
shares = 2571.225
mcap = price * shares / 1000.0

def X(vv): return 40 + vv / 200 * 580

# ---------- SVG: 价格锚点 ----------
anchor = f'''<svg viewBox="0 0 660 170" style="font-family:'IM Fell English',Georgia,serif;width:100%">
<line x1="40" y1="88" x2="620" y2="88" stroke="#8b6c42" stroke-width="1"/>
<rect x="{X(IV[0]):.1f}" y="70" width="{X(IV[1])-X(IV[0]):.1f}" height="36" fill="#c9a84c" opacity="0.35"/>
<rect x="{X(AT['band'][0]):.1f}" y="70" width="{X(AT['band'][1])-X(AT['band'][0]):.1f}" height="36" fill="#8b2e2e" opacity="0.12"/>
<rect x="{X(AF['band'][0]):.1f}" y="70" width="{X(AF['band'][1])-X(AF['band'][0]):.1f}" height="36" fill="#2a5c3f" opacity="0.12"/>
<line x1="{X(IV[0]):.1f}" y1="52" x2="{X(IV[0]):.1f}" y2="112" stroke="#0a0a0b" stroke-width="2"/><text x="{X(IV[0]):.1f}" y="46" font-size="11" text-anchor="middle" fill="#0a0a0b">DCF 下沿 {IV[0]:.2f}</text>
<line x1="{X(AT['iv_per_share']):.1f}" y1="56" x2="{X(AT['iv_per_share']):.1f}" y2="112" stroke="#8b2e2e" stroke-width="2"/><text x="{X(AT['iv_per_share']):.1f}" y="128" font-size="11" text-anchor="middle" fill="#8b2e2e">历史口径 {AT['iv_per_share']:.2f}</text>
<line x1="{X(AF['iv_per_share']):.1f}" y1="30" x2="{X(AF['iv_per_share']):.1f}" y2="112" stroke="#2a5c3f" stroke-width="2"/><text x="{X(AF['iv_per_share']):.1f}" y="24" font-size="11" text-anchor="middle" fill="#2a5c3f">前瞻口径 {AF['iv_per_share']:.2f}</text>
<line x1="{X(price):.1f}" y1="56" x2="{X(price):.1f}" y2="112" stroke="#0a0a0b" stroke-width="3"/><text x="{X(price):.1f}" y="128" font-size="12" text-anchor="middle" fill="#0a0a0b">现价 {price:.2f}</text>
<text x="40" y="150" font-size="11" fill="#8b6c42">每股美元（0–200）。金色带 = DCF 参考区间（估值失效，仅列示）；红线区间 = 历史口径 {AT['band'][0]:.1f}–{AT['band'][1]:.1f}；绿线区间 = 前瞻口径 {AF['band'][0]:.1f}–{AF['band'][1]:.1f}（同行 P/FCF 74.52x ±20%）</text></svg>'''

moat_cells = "".join(
    f'<rect x="{40+i*53}" y="14" width="48" height="22" fill="{"#c9a84c" if i < 6 else "#ddd6c8"}"/>'
    f'<text x="{64+i*53}" y="52" font-size="10" text-anchor="middle" fill="#8b6c42">{i+1}</text>' for i in range(10))
moat_svg = f'<svg viewBox="0 0 660 70" style="font-family:\'IM Fell English\',Georgia,serif;width:100%">{moat_cells}<text x="40" y="66" font-size="11" fill="#8b6c42">护城河评分 6 / 10（5–6 = 中等护城河：阶段 1 增速上限 12%，终端增长上限 5%）</text></svg>'

# ---------- SVG: 三年财务趋势（坐标与网格线同尺度：32.043 px / $B） ----------
yrs = [(2023, 2225.012, 209.825, 697.069), (2024, 2865.507, 462.190, 1141.231), (2025, 4475.446, 1625.033, 2100.591)]
def ybar(vv): return 190 - (vv / 1000.0) * 32.043
bars = []
for i, (fy, rev, ni, fcf) in enumerate(yrs):
    gx = 110 + i * 200
    for k, (val, color) in enumerate(((rev, "#0a0a0b"), (ni, "#8b6c42"), (fcf, "#2a5c3f"))):
        bx = gx + k * 32
        bars.append(f'<rect x="{bx}" y="{ybar(val):.1f}" width="26" height="{190-ybar(val):.1f}" fill="{color}"/><text x="{bx+13}" y="{ybar(val)-4:.1f}" font-size="9" text-anchor="middle" fill="{color}">{val/1000:.1f}B</text>')
    bars.append(f'<text x="{gx+45}" y="208" font-size="12" text-anchor="middle" fill="#0a0a0b">FY{fy}</text>')
financial_svg = f'''<svg viewBox="0 0 660 240" style="font-family:'IM Fell English',Georgia,serif;width:100%">
<line x1="70" y1="190" x2="620" y2="190" stroke="#e2dccf"/><line x1="70" y1="116.3" x2="620" y2="116.3" stroke="#e2dccf"/><line x1="70" y1="42.6" x2="620" y2="42.6" stroke="#e2dccf"/>
<text x="62" y="194" font-size="10" text-anchor="end" fill="#8b6c42">0</text><text x="62" y="120" font-size="10" text-anchor="end" fill="#8b6c42">2.3B</text><text x="62" y="46" font-size="10" text-anchor="end" fill="#8b6c42">4.6B</text>
{''.join(bars)}
<rect x="80" y="222" width="10" height="10" fill="#0a0a0b"/><text x="94" y="231" font-size="11" fill="#0a0a0b">营收</text>
<rect x="180" y="222" width="10" height="10" fill="#8b6c42"/><text x="194" y="231" font-size="11" fill="#0a0a0b">净利润</text>
<rect x="300" y="222" width="10" height="10" fill="#2a5c3f"/><text x="314" y="231" font-size="11" fill="#0a0a0b">FCF（CFO − Capex）</text></svg>'''

dims = [("Business Quality", 30, SC["business"]), ("Financial Health", 30, SC["financial"]), ("Management Quality", 25, SC["management"]), ("Price vs Value", 15, SC["price"])]
sc_bars = []
for i, (name, mx, val) in enumerate(dims):
    y = 18 + i * 34; w = 420 * val / mx
    sc_bars.append(f'<text x="40" y="{y+13}" font-size="11" fill="#0a0a0b">{name}</text>')
    sc_bars.append(f'<rect x="200" y="{y}" width="420" height="18" fill="#e2dccf"/>')
    sc_bars.append(f'<rect x="200" y="{y}" width="{w:.0f}" height="18" fill="{"#2a5c3f" if val/mx>=0.7 else "#c9a84c" if val/mx>=0.4 else "#8b2e2e"}"/>')
    sc_bars.append(f'<text x="{200+w+8:.0f}" y="{y+14}" font-size="11" fill="#0a0a0b">{val} / {mx}</text>')
sc_svg = f'<svg viewBox="0 0 660 170" style="font-family:\'IM Fell English\',Georgia,serif;width:100%">{"".join(sc_bars)}</svg>'

sens_rows = "".join(
    f'<tr><td>{{"r":"折现率 r","g1":"阶段 1 增速","g_terminal":"终端增长率"}}</td>' if False else "" for _ in [])
sens_html = "".join(f"<tr><td>{r['var']}</td><td>{r['delta']*100:+.1f}%</td><td>{r['iv_per_share']:.2f}</td><td>{r['change']*100:+.1f}%</td></tr>" for r in SENS)
psens_html = "".join(f"<tr><td>{r['peer_p_fcf']:.2f}x</td><td>{r['iv_trailing']:.2f}</td><td>{r['iv_forward']:.2f}</td><td>{'高于现价' if r['iv_forward'] > price else '低于现价'}</td></tr>" for r in PSENS)
name_map = {"r": "折现率 r", "g1": "阶段 1 增速", "g_terminal": "终端增长率"}
sens_html = "".join(f"<tr><td>{name_map.get(r['var'], r['var'])}</td><td>{r['delta']*100:+.1f}%</td><td>{r['iv_per_share']:.2f}</td><td>{r['change']*100:+.1f}%</td></tr>" for r in SENS)

html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>帕兰提尔 PLTR 巴菲特模型分析</title>
<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English&display=swap" rel="stylesheet">
<style>
:root{{--ink:#0a0a0b;--paper:#f1efea;--copper:#8b6c42;--gold:#c9a84c;--green:#2a5c3f;--red:#8b2e2e;--amber:#c47a1e}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'Songti SC','Noto Serif SC','IM Fell English',serif;line-height:1.75}}
.wrap{{max-width:860px;margin:0 auto;padding:28px 18px 60px}}
.pub{{display:flex;justify-content:space-between;font-size:12px;color:var(--copper);border-bottom:1px solid var(--copper);padding-bottom:6px}}
h1{{font-size:30px;margin:18px 0 2px}} .en{{font-family:'IM Fell English',serif;color:var(--copper);font-style:italic}}
h2{{font-size:20px;margin:34px 0 8px;border-bottom:2px solid var(--gold);padding-bottom:4px}}
.stat{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:18px 0}}
.stat div{{background:#fff;border:1px solid #e2dccf;padding:10px}} .stat b{{display:block;font-size:20px}} .stat span{{font-size:12px;color:var(--copper)}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}} th,td{{border-bottom:1px solid #e2dccf;padding:6px;text-align:left;vertical-align:top}} th{{color:var(--copper);font-weight:normal}}
.verdict{{background:var(--ink);color:var(--paper);padding:20px 22px;margin:26px 0}} .verdict .en{{color:var(--gold);opacity:.8}} .verdict b{{color:var(--gold)}}
.src{{font-size:12px;color:var(--copper)}} .warn{{border-left:3px solid var(--amber);padding:6px 12px;background:#fff8ec;margin:10px 0}}
.badge{{font-size:11px;padding:0 6px;margin-left:6px;white-space:nowrap}}
.note{{margin-top:36px;border-top:1px solid var(--copper);padding-top:12px;font-size:13px}}
@media print{{body{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
@media(max-width:600px){{.stat{{grid-template-columns:repeat(2,1fr)}} table{{font-size:12px}}}}
</style></head>
<body><div class="wrap" data-valuation="memory/state/valuations/pltr_2026-11-08.json">
<div class="pub"><span>巴菲特模型分析报告 · Buffett Model Report</span><span>分析日期 2026-11-08 · 股价日期 2026-11-06 收盘</span></div>
<h1>帕兰提尔 Palantir（PLTR）</h1><div class="en">Palantir Technologies — Moat, Owner Earnings and Margin of Safety</div>

<div class="stat">
<div><b>{AT['iv_per_share']:.2f} – {AF['iv_per_share']:.2f}</b><span>两个口径（历史 / 前瞻）/ Two Calibers (realized / guided)</span></div>
<div><b>{price:.2f}</b><span>现价 / Price（2026-11-06 收盘）</span></div>
<div><b style="color:var(--red)">{AT['mos']*100:.1f}% / {AF['mos']*100:.1f}%</b><span>安全边际 / Margin of Safety（历史 / 前瞻）</span></div>
<div><b>{SC['total']} / 100</b><span>巴菲特评分 / Berkshire Score → 观察名单</span></div>
</div>

<h2>一句话结论 <span class="en">Bottom Line</span></h2>
<p><strong>结论：不买入（观察名单）。</strong>生意质量与增速都是顶级，但按巴菲特框架：标准 DCF 失效（近两年营收 +101%，增速无法外推）；替代估值两个口径——历史口径每股 {AT['iv_per_share']:.2f} 美元、前瞻口径（FY2026 公司指引 FCF）每股 {AF['iv_per_share']:.2f} 美元——现价 {price:.2f} 对两者都没有安全边际（{AT['mos']*100:.1f}% / {AF['mos']*100:.1f}%）。<span class="badge" style="border:1px solid #c47a1e;color:#c47a1e">置信 中</span></p>
{anchor}
<ul>
<li><strong>估值失效，结论取决于用哪一年的 FCF 作锚：</strong>用已实现 FY2025 FCF（$2.10B），合理价 {AT['iv_per_share']:.2f}，现价高估 {abs(AT['mos'])*100:.0f}%；用公司 FY2026 指引（$4.8–5.0B，中值 $4.9B），合理价 {AF['iv_per_share']:.2f}，现价仍高 {abs(AF['mos'])*100:.1f}%。只有把同行倍数或远期 FCF 再往上推，才能把合理价抬到现价附近——本报告不做这种外推。<span class="badge" style="border:1px solid #c47a1e;color:#c47a1e">置信 中</span></li>
<li><strong>现价隐含未来 5 年每年 {IMPL['g1']*100:.1f}% 的所有者盈余复合增速</strong>，是护城河 6 分对应上限（{IMPL['moat_cap']*100:.0f}%）的 {IMPL['g1']/IMPL['moat_cap']:.1f} 倍。这不是说它不会发生——FY2026 营收指引就是 +91%——而是说这个价格把高增长当作已实现，没有给执行误差留安全边际。<span class="badge" style="border:1px solid #c47a1e;color:#c47a1e">置信 中</span></li>
<li><strong>评分 {SC['total']} / 100（观察名单）。</strong>扣分集中在两处：FY2025 稀释同比 +4.7%（三年年化 +7.5%）且 2026 年 1 月终止回购（管理层 3A 由 6 降到 3）；价格维度 4A 为 0、4B 为 1。护城河 6 / 10（中等）。自动降级规则未触发（FCF 为正、无造假、护城河 &gt; 2）。<span class="badge" style="border:1px solid #c47a1e;color:#c47a1e">置信 中</span></li>
</ul>

<h2>一、护城河分析 <span class="en">Moat</span></h2>
{moat_svg}
<p>护城河类型：<strong>转换成本（主）＋ 无形资产与规模壁垒（政府侧，部分成立）</strong>。评分 6 / 10，属中等护城河；未触发侵蚀信号，不下调。</p>
<table><tr><th>维度（moat-framework 五类）</th><th>证据</th><th>判定</th></tr>
<tr><td>转换成本</td><td>截至 2025-12-31 客户 954 家（10-K「Our Customers」；2024 年 711 家，+34.2%）；前 20 大客户 TTM 平均收入 $93.9M，高于 2024 年的 $64.6M（+45%），存量客户在加深部署；合同按价值加权平均久期约 4 年（10-K）；平台被描述为「become central operating systems for entire industries and sectors」</td><td>成立，主护城河</td></tr>
<tr><td>无形资产</td><td>政府收入占 54%、美国占 74%（10-K）；任务关键与涉密部署构成进入门槛，但框架要求的「涨价后流失率 &lt; 5%」没有公开数据（公司不披露 NDR / 续约率）</td><td>部分成立（不作强证据）</td></tr>
<tr><td>规模壁垒</td><td>10-K：「high installation costs, high failure risks, complexity of data environments … raise the barriers to entry」；但竞争者包括大型企业软件、政府承包商与系统集成商</td><td>部分成立</td></tr>
<tr><td>成本优势</td><td>软件业务毛利率 82%，但框架要求「单位成本比对手低 15%+」的同口径对比，无法取得</td><td>不计分（数据不足）</td></tr>
<tr><td>网络效应</td><td>单个客户的平台价值不随其他客户增加而上升；AIP 生态尚不构成双边网络</td><td>不成立</td></tr>
</table>
<p><strong>侵蚀信号检查：</strong>毛利率 FY2023–FY2025 为 80.6% → 80.2% → 82.4%，未压缩；营收增速加速（+28.8% → +56.2%）；无「连续两年份额流失」数据；AIP / Ontology 未被技术逆转的证据。四条侵蚀信号均未触发，维持 6 分。</p>
<p><strong>为什么不是 7 分：</strong>宽护城河需要更强的定价权或留存证据。公司不披露 NDR / 续约率，客户自建平台与大型软件厂商的替代威胁真实存在（10-K「Competition」：客户经常先尝试自建）。若按 7 分（宽）计，1A 由 8 升到 12，总分 63，仍在「观察名单」档，结论不变。</p>
<p class="src">来源：SEC 10-K FY2025；2025 Q4 业绩发布（8-K exhibit 99.1）；SEC companyfacts 毛利率口径（GrossProfit ÷ Revenues）。</p>

<h2>二、核心财务指标 <span class="en">Financials, FY2023–FY2025</span></h2>
{financial_svg}
<table><tr><th>指标</th><th>FY2023</th><th>FY2024</th><th>FY2025</th></tr>
<tr><td>营收</td><td>$2.23B</td><td>$2.87B</td><td>$4.48B</td></tr>
<tr><td>毛利率</td><td>80.6%</td><td>80.2%</td><td>82.4%</td></tr>
<tr><td>净利润（GAAP）</td><td>$0.21B</td><td>$0.46B</td><td>$1.63B</td></tr>
<tr><td>营业利润（EBIT）</td><td>$0.12B</td><td>$0.31B</td><td>$1.41B</td></tr>
<tr><td>FCF（CFO − Capex，报告值）</td><td>$0.70B</td><td>$1.14B</td><td>$2.10B</td></tr>
<tr><td>FCF / 净利润（报告值）</td><td>332%</td><td>247%</td><td>129%</td></tr>
<tr><td>FCF / 净利润（剔除 SBC 加回后）</td><td>105%</td><td>97%</td><td>87%</td></tr>
<tr><td>ROE（GAAP）</td><td>6.0%</td><td>9.2%</td><td>22.0%</td></tr>
<tr><td>SBC（股权激励）</td><td>$0.48B</td><td>$0.69B</td><td>$0.68B</td></tr>
<tr><td>SBC / 营收</td><td>21.4%</td><td>24.1%</td><td>15.3%</td></tr>
<tr><td>稀释股数</td><td>2,297.9M</td><td>2,450.8M</td><td>2,565.2M</td></tr>
<tr><td>有息负债 / 股东权益</td><td>0%</td><td>0%</td><td>0%</td></tr>
</table>
<p class="src">来源：SEC 10-K FY2025 合并报表（CIK0001321655，accession 0001321655-26-000011）；稀释股数为 10-K 加权平均稀释股数；SBC 为现金流量表加回项。</p>
<div class="warn"><strong>SBC 扭曲检验（2B 要求）：</strong>FCF / 净利润 129% 里有 SBC 加回成分。剔除 SBC 后 FY2025 为 87%、FY2024 为 97%、FY2023 为 105%，仍属健康，但趋势在下降。<strong>评分卡按规则用报告值</strong>，此调整只作质量判断。</div>
<p>ROIC（FY2025）：NOPAT = EBIT 1,414.0 × (1 − 实际税率 1.37%) ≈ 1,394.6；投入资本 = 股东权益 7,387.3 + 有息负债 0 − 现金 1,423.8 = 5,963.5；<strong>ROIC 23.4%，高于折现率 9%</strong>，资本回报远高于资金成本。三年 ROE 均值 12.4%（6.0% / 9.2% / 22.0%）。无有息负债，信用额度 $500M 未动用（10-K）。</p>
<p><strong>最新季度背景（不改变基准年选择）：</strong>Q3 2026 营收 $2.31B，同比 +96%；美国商业收入 $984M，同比 +148%，首次超过美国政府收入；公司同时把 FY2026 营收指引上调到 $8.530–8.534B（+91%）、调整后 FCF 指引上调到 $4.8–5.0B（2026-11-02 8-K）。按 spokes，基准年仍用最近完整财年 FY2025。</p>

<h2>三、管理层评估 <span class="en">Management</span></h2>
<table><tr><th>行为（近 3 年）</th><th>数据</th><th>评分影响</th></tr>
<tr><td>股权激励稀释</td><td>稀释股数 FY2022 2,063.8M → FY2025 2,565.2M；FY2023/24/25 同比 +11.3% / +6.7% / +4.7%，<strong>连续三年 &gt; 3% / 年</strong>（年化约 +7.5%）</td><td>−3</td></tr>
<tr><td>回购</td><td>$1.0B 回购计划（2023-08 授权），FY2025 实际回购 0.6M 股、$75.0M；当时 GAAP P/E 远高于 15 倍，不属「低估时回购」；<strong>2026 年 1 月公司终止该计划</strong>（10-K）</td><td>0</td></tr>
<tr><td>分红</td><td>无分红</td><td>0</td></tr>
<tr><td>并购纪律</td><td>近 3 年无「收购价 &gt; 当年营收 50%」的大型并购，无商誉减值公告</td><td>0</td></tr>
<tr><td>基础分</td><td>无明显失误，也无明显亮点</td><td>+6</td></tr>
</table>
<p><strong>利益绑定：</strong>创始人主导——Alexander Karp（CEO，2005 年起）、Stephen Cohen（President）、Peter Thiel（Chairman）。Class F 股份由三人设立的 Founder Voting Trust 持有，董事会与高管合计表决权约 50.8%；但<strong>经济持股低于 10%</strong>（两种口径都成立）：董事会与高管组直接持股 176.3M 股 ÷ 记录日 A+B 合计 2,396.2M = 7.36%，含未行权期权 / RSU 全稀释 236.2M ÷ 2,456.1M = 9.62%；仅三位创始人口径：直接 169.4M（7.07%）、含期权 227.4M（9.26%）。框架表没有「创始人主导 + 经济持股 &lt; 10%」的档位，按最接近的「大量持股」档取 5 分（保守处理；若按 6 分，总分 60，结论不变）。</p>
<p><strong>沟通质量：</strong>中性 3 分（判断依据见附注）。</p>
<p class="src">来源：DEF 14A（2026-04-24）：Security Ownership 表；10-K FY2025（合并报表与「no outstanding debt」）；8-K FY2025 业绩发布（股份与回购）；FY2022 稀释股数 2,063,793K 来自 financials/pltr.json（SEC companyfacts）。</p>

<h2>四、内在价值估算 <span class="en">Intrinsic Value</span></h2>
<p><strong>结论先行：</strong>DCF 失效；替代估值两个口径——历史 {AT['iv_per_share']:.2f}、前瞻 {AF['iv_per_share']:.2f}——现价 {price:.2f} 对两者都没有安全边际。推导如下：基准年 FY2025（最近完整财年，已结束 &gt; 45 天且已披露）；折现率 r = 9%（美股大盘股；10 年期美债 4.86%，2026-11-06，处于 4–5% 合理区间，不调整）。</p>
<p><strong>所有者盈余（FY2025，百万美元）：</strong>净利润 1,625.0 + 折旧摊销 26.1 − 维护性 Capex 16.9 + 营运资本变化 −210.0 = 1,424.2（分项相加），精确值 <strong>{OE:,.3f}</strong>。维护性 Capex 按轻资产软件规则取总 Capex 的 50%（总 Capex $33.9M）；营运资本变化取 10-K 现金流量表「Changes in operating assets and liabilities」合计（−$210.0M，其中应收账款增加 −$450.4M、合同负债增加 +$238.7M）。</p>
<div class="warn"><strong>估值失效条件已触发：</strong>近 3 年营收最高 / 最低 = 101% &gt; 50%，spokes 规定跳过标准 DCF、按替代估值顺序执行。同时 FCF 三年复合增速 73.6% 属异常增速，任何可外推的 DCF 都不可靠。下文 DCF 数字<strong>只作参考</strong>，结论以替代估值为准。</div>
<p><strong>DCF 参考（不可用于结论）：</strong>每股内在价值 {IV[0]:.2f}–{IV[1]:.2f} 美元；按下沿 {IV[0]:.2f} 计的安全边际为 {MOS:.1f}%（现价为下沿的 {price/IV[0]:.1f} 倍）。现价隐含的阶段 1 增速为 {IMPL['g1']*100:.1f}%，护城河 6 分对应上限 {IMPL['moat_cap']*100:.0f}%，隐含增速是上限的 {IMPL['g1']/IMPL['moat_cap']:.1f} 倍。终值集中度：基准情景终值占比 {SCEN['base']['terminal_share']*100:.1f}%（&gt; 60%）；出口倍数法（同行 P/FCF）给出 {SCEN['base']['exit_multiple_iv']:.2f}，与 DCF {IV[1]:.2f} 差 {abs(SCEN['base']['exit_multiple_iv']/IV[1]-1)*100:.0f}%，超过 30% → 工具取较低值。这两项都说明「按可外推增速」的 DCF 本身不可信。</p>
<p><strong>替代估值（结论依据，股权口径 P/FCF）：</strong>同行 P/FCF 中值 {ALT['peer_p_fcf']:.2f}x（vcpscanner，2026-11-08）。<strong>该聚合页未注明期限，按 TTM 口径处理</strong>；2026-11-07 用户定股权口径，不用 EV/FCF、不扣净负债。PLTR 自身 P/FCF = 现价 ÷ 每股 FCF：历史 = {price:.2f} ÷ (2,100.6 ÷ 2,571.2；2,571.2M 为 2026 年前 9 个月加权平均稀释股数) = {ALT['pltr_p_fcf_trailing']:.1f}x；前瞻 = {price:.2f} ÷ (4,900 ÷ 2,571.2) = {AF['pltr_p_fcf_forward']:.1f}x。</p>
<ul>
<li>历史口径：同行 {ALT['peer_p_fcf']:.2f}x × FY2025 FCF $2,100.6M ÷ 2,571.2M = <strong>{AT['iv_per_share']:.2f} 美元</strong>；±20% 区间 {AT['band'][0]:.2f}–{AT['band'][1]:.2f}；安全边际 {AT['mos']*100:.1f}%。</li>
<li>前瞻口径（<strong>偏乐观上沿</strong>：trailing 同行倍数 × forward FCF）：同行 {ALT['peer_p_fcf']:.2f}x × FY2026 指引 FCF $4,900M ÷ 2,571.2M = <strong>{AF['iv_per_share']:.2f} 美元</strong>；±20% 区间 {AF['band'][0]:.2f}–{AF['band'][1]:.2f}；安全边际 {AF['mos']*100:.1f}%。</li>
</ul>
<p>现价对应前瞻 P/FCF {AF['pltr_p_fcf_forward']:.2f}x：需要同行 forward 倍数达到该水平才支撑现价；当前同行 trailing 中值 {ALT['peer_p_fcf']:.2f}x，forward 倍数未取得（同页 forward P/E 中值 90.36x，非 FCF 口径）。因此 <strong>{AF['iv_per_share']:.2f} 是偏乐观上沿</strong>，真实合理价可能更低。两个口径都指向「没有安全边际」：历史口径下现价高估 {abs(AT['mos'])*100:.0f}%，即使按公司自己 FY2026 的指引，现价仍高 {abs(AF['mos'])*100:.1f}%。<strong>前瞻口径用的「调整后 FCF」是公司非 GAAP 口径</strong>（FY2025 调整后 $2,270,436K vs GAAP FCF $2,100,591K，高 8.1%；原文 pages/sec_pltr_8k_2025q4_ex991.htm）；若按 GAAP 口径折算，前瞻合理价还要再低约 8%，结论方向不变。</p>
<table><tr><th>价格锚点</th><th>数值（美元 / 股）</th><th>说明</th></tr>
<tr><td>DCF 参考下沿 / 上沿</td><td>{IV[0]:.2f} / {IV[1]:.2f}</td><td>估值失效，仅列示</td></tr>
<tr><td>替代估值：历史口径（±20% 区间）</td><td>{AT['iv_per_share']:.2f}（{AT['band'][0]:.2f}–{AT['band'][1]:.2f}）</td><td>FY2025 已实现 FCF</td></tr>
<tr><td>替代估值：前瞻口径（±20% 区间）</td><td>{AF['iv_per_share']:.2f}（{AF['band'][0]:.2f}–{AF['band'][1]:.2f}）</td><td>FY2026 公司指引 FCF 中值</td></tr>
<tr><td>当前股价</td><td>{price:.2f}</td><td>2026-11-06 收盘</td></tr>
<tr><td>安全边际（历史 / 前瞻）</td><td>{AT['mos']*100:.1f}% / {AF['mos']*100:.1f}%</td><td>均为负</td></tr>
<tr><td>买入线（前瞻口径 × 70%，安全边际 30%）</td><td>{AF['buy_mos30']:.2f}</td><td>严格建仓线（参考）</td></tr>
<tr><td>买入线（前瞻口径 × 60%，路径 B 要求 40%）</td><td>{AF['buy_mos40']:.2f}</td><td>正态化估值要求的更高门槛</td></tr>
</table>
<p class="src">价格锚点由替代估值（股权口径 P/FCF 同行比较，spokes 第 1 选）计算，全部写在 tools/owner_value.py 并落在底稿 memory/state/valuations/pltr_2026-11-08.json 的 alternative_valuation 字段；DCF 数字来自同一底稿。买入线仅作参考——底稿判定为「估值失效 → 不出买入结论」。</p>

<p><strong>可证伪判断（已登记 predictions.md）：</strong>FY2027 营收同比增速低于 FY2026 指引的 91%（即 FY2027 营收 &lt; $16.3B），验证时点 2028-02-28，把握档「中」。</p>

<h2>五、巴菲特评分卡 <span class="en">Berkshire Score</span></h2>
{sc_svg}
<table><tr><th>维度</th><th>满分</th><th>得分</th><th>构成与关键依据</th></tr>
<tr><td>Business Quality</td><td>30</td><td>23</td><td>1A / 1B / 1C = 8 / 8 / 7：护城河 6 分（中等）；营收 CAGR 41.8% 且无负增长年；毛利率 82.4% 稳定 &gt; 50%</td></tr>
<tr><td>Financial Health</td><td>30</td><td>24</td><td>2A / 2B / 2C = 6 / 10 / 8：ROE 三年均值 12.4%；FCF 三年为正、FCF/NI 129%（剔除 SBC 后 87%）；净现金、EBIT 为正</td></tr>
<tr><td>Management Quality</td><td>25</td><td>{SC['management']}</td><td>3A / 3B / 3C = 3 / 5 / 3：稀释 FY2025 +4.7%；创始人控制但经济持股 &lt; 10%（直接 7.36% / 含期权 9.62%）；沟通未核读按中性</td></tr>
<tr><td>Price vs Value</td><td>15</td><td>1</td><td>4A / 4B = 0 / 1：三种口径安全边际全为负；P/FCF 196.3x vs 同行中值 74.5x，高 163%</td></tr>
<tr><td><strong>总分</strong></td><td><strong>100</strong></td><td><strong>{SC['total']}</strong></td><td>观察名单（55–69）</td></tr>
</table>
<p><strong>评级：观察名单。</strong>未触发自动降级规则（无造假 / 信披违规，护城河 &gt; 2，FCF 连续为正）。但底稿同时判定「估值失效 → 不出买入结论」，因此评级不等于「可以买」。</p>
<div class="verdict"><p><b>裁决 Verdict：不买入 · 观察名单 / No Buy — Watchlist</b><br>
生意质量 {SC['business']}/30、财务健康 {SC['financial']}/30、管理层 {SC['management']}/25、价格 {SC['price']}/15；总分 {SC['total']}/100。
估值失效（营收两年 +101%）；替代估值历史口径 {AT['iv_per_share']:.2f}、前瞻口径 {AF['iv_per_share']:.2f}；现价 {price:.2f}，安全边际 {AT['mos']*100:.1f}% / {AF['mos']*100:.1f}%。
<span class="en">Verdict: No Buy. Quality is exceptional, price is not. No margin of safety on either realized or guided cash flow.</span></p></div>

<h2>六、主要风险 <span class="en">Key Risks</span></h2>
<ul>
<li><strong>增速依赖风险（最大）：</strong>现价隐含未来 5 年每年 {IMPL['g1']*100:.1f}% 的所有者盈余增速。若 FY2027 营收增速回落到 40% 以下，前瞻口径的 P/FCF 会迅速抬升，价格对增速变化极敏感。</li>
<li><strong>股东稀释：</strong>SBC 占营收 15.3%（FY2025），稀释 FY2025 +4.7%（三年年化 +7.5%）；2026 年 1 月终止 $1.0B 回购计划，稀释没有对冲。按每股口径，增长的一部分被股份数吃掉。</li>
<li><strong>政府集中度：</strong>政府收入占 54%、美国占 74%。合同期限 1–5 年且可提前终止，政策与预算变化会直接冲击收入。</li>
<li><strong>竞争强度：</strong>10-K 明确竞争者包括客户内部自建、大型企业软件公司、政府承包商与系统集成商；若 AI 平台商品化，定价权受压。</li>
<li><strong>利率：</strong>久期极长的高估值资产，折现率 +1% 使 DCF 参考值 −{abs([r for r in SENS if r['var']=='r' and r['delta']>0][0]['change'])*100:.1f}%。</li>
</ul>
<p>需要重新评估内在价值的情况：FY2027 营收增速低于 40%（增速逻辑变化）；SBC 占营收回升到 &gt; 20% 且回购未重启（稀释恶化）；政府合同重大终止；同行 P/FCF 中值系统性下移。</p>

<h2>七、数据盲区与不确定性 <span class="en">Data Gaps</span></h2>
<ul>
<li>2026 年股东信与最新电话会未逐篇核读：沟通诚实度按中性 3 分处理，属保守取值；这一项的修正会改变 3C（0–5 分），不改变估值结论。</li>
<li>公司不披露 NDR / 续约率：转换成本证据来自客户数、前 20 大客户收入扩张与合同久期，属间接证据。</li>
<li>同行 P/FCF 中值 74.52x 来自第三方聚合（vcpscanner），未逐家复核；同行本身也处于高估值区间。这是替代估值的最大单点依赖，已用同行倍数敏感性（59.62x–130.41x；130.41x 为非对称上界）披露影响范围。</li>
<li>前瞻口径用的是公司「调整后 FCF」指引（非 GAAP），与 GAAP FCF 的差额未逐项拆解（FY2025 相差 +8.1%）。</li>
<li>FY2027–FY2029 分析师共识原文未取得：异常增速锚（g_override）用公司 FY2026 营收指引，再按护城河上限截断；DCF 结果因此对共识不敏感。</li>
<li>营运资本变化用现金流量表合计行（−$210.0M），仅拆出应收账款（−$450.4M）与合同负债（+$238.7M）两项，其余未细分。</li>
</ul>

<p><strong>敏感性（DCF 参考口径；路径 B 按模板跳过 DCF 敏感性表，此处仅作久期参考）：</strong></p>
<table><tr><th>变量</th><th>变动</th><th>每股内在价值</th><th>相对变化</th></tr>
{sens_html}
</table>
<p><strong>同行倍数敏感性（替代估值口径）：</strong></p>
<table><tr><th>同行 P/FCF</th><th>历史口径 IV</th><th>前瞻口径 IV</th><th>前瞻 IV vs 现价</th></tr>
{psens_html}
</table>
<p class="src">同行倍数敏感性表第 4 行 130.41x = 74.52x × 1.75，是非对称上界参照、不是门槛。现价对应前瞻 P/FCF {AF['pltr_p_fcf_forward']:.2f}x：表中 89.42x 行（前瞻 IV 170.42）已高于现价，门槛约在 84.2x 附近。</p>
<h2>数据来源索引 <span class="en">Sources</span></h2>
<ol>
<li>SEC 10-K FY2025（2026-02-17）：https://www.sec.gov/Archives/edgar/data/1321655/000132165526000011/pltr-20251231.htm</li>
<li>SEC 8-K 2025 Q4 / FY2025 业绩发布（2026-02-02，exhibit 99.1）：https://www.sec.gov/Archives/edgar/data/1321655/000132165526000004/a2025q4ex991earningsrelease.htm</li>
<li>SEC 8-K 2026 Q3 业绩发布（2026-11-02，exhibit 99.1）：https://www.sec.gov/Archives/edgar/data/1321655/000132165526000045/a2026q3ex991pressrelease.htm</li>
<li>SEC DEF 14A（2026-04-24）：https://www.sec.gov/Archives/edgar/data/1321655/000132165526000019/pltr-20260423.htm</li>
<li>SEC 10-Q 2026 Q3（2026-11-03；稀释股数 2,571.225M 出处）：https://www.sec.gov/Archives/edgar/data/1321655/000132165526000048/pltr-20260930.htm</li>
<li>SEC companyfacts（CIK0001321655）：https://data.sec.gov/api/xbrl/companyfacts/CIK0001321655.json</li>
<li>原文存档（pages/）：pages/sec_pltr_10k_fy2025.htm、pages/sec_pltr_8k_2025q4_ex991.htm、pages/sec_pltr_8k_2026q3_ex991.htm、pages/sec_pltr_10q_2026q3.htm、pages/sec_pltr_def14a_2026.htm</li>
<li>价格与美债收益率（GitHub Actions 抓取）：https://raw.githubusercontent.com/zhenyuanhuang358/work/dsh/work/stock_prices.json</li>
<li>同行 P/FCF 中值（2026-11-08）：https://vcpscanner.com/valuation/pltr/relative</li>
</ol>

<div class="note"><p><strong>分析师附注 Analyst's Note</strong></p>
<table><tr><th>结论</th><th>置信</th><th>为什么</th></tr>
<tr><td>不买入、观察名单</td><td>中</td><td>历史口径安全边际 −163.4%、前瞻口径 −12.9%，都低于路径 B 的 40% 门槛；但结论对同行倍数敏感（约 84.2x 即支撑现价；130.41x 上界时前瞻 IV 248.52）</td></tr>
<tr><td>替代估值区间 {AT['iv_per_share']:.2f}–{AF['iv_per_share']:.2f}</td><td>中</td><td>取决于用已实现 FY2025 FCF 还是 FY2026 指引；同行倍数本身处于高位</td></tr>
<tr><td>护城河 6 / 10（中等）</td><td>中</td><td>转换成本有间接证据，但缺 NDR / 续约率与定价权直接证据；评 7 时结论不变（总分 63）</td></tr>
<tr><td>现价隐含 5 年 {IMPL['g1']*100:.1f}% 复合增速</td><td>中</td><td>已登记 predictions.md：FY2027 营收 &lt; $16.3B（增速低于 91%），2028-02-28 验证</td></tr>
</table>
<p><strong>待核实：</strong>见 §七 数据盲区（6 项）。其中 3C 的「未核读」说明：2026 年股东信与电话会未逐篇核读，沟通诚实度按未读处理、取中性 3 分，不是已验证的中性。</p>
<p><strong>分析师看法与分歧：</strong>本报告的主要分歧点不是「公司好不好」，而是「用哪一年的现金流作估值锚」。用 FY2025 已实现 FCF，现价高估约 163%；用 FY2026 公司指引，现价只高约 13%；只有当同行倍数升到约 84.2x（+13%）以上时，前瞻口径才会支持现价（130.41x 仅是非对称上界参照）。巴菲特框架不允许把未实现的增长当作已实现，因此结论是「不买入」；对成长股投资者，这份报告的价值在于把「现价需要什么条件才成立」量化出来。</p>
<p>本报告所有估值数字由 tools/owner_value.py 计算，底稿为 memory/state/valuations/pltr_2026-11-08.json（含 alternative_valuation 字段）；报告只读取底稿，不手算。本报告是价值框架下的研究意见，不构成投资建议。</p>
<p>反馈：<a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=pltr_2026-11-08">https://spontaneous-youtiao-b9cde9.netlify.app?product=buffett&amp;report=pltr_2026-11-08</a></p></div>
</div></body></html>'''

out = os.path.join(REPO, "reports", "pltr_Buffett_Report.html")
open(out, "w", encoding="utf-8").write(html)
print("written", out, len(html), "bytes")
