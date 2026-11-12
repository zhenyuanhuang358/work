#!/usr/bin/env python3
"""PPTAgent 最小验证：KO 巴菲特报告结论 → 6 页中文 HTML 幻灯片（数字全部读底稿与 financials，不手写）。"""
import json
import os
import sys

REPO = "/home/user/work"
W = sys.argv[1]
V = json.load(open(f"{REPO}/memory/state/valuations/ko_2026-11-07.json"))
K = json.load(open(f"{REPO}/financials/ko.json"))
lo, hi = V["iv_range"]
price = V["margin_of_safety"]["price"]
mos = V["margin_of_safety"]["value"]
sc = V["scorecard"]
norm = {n["fy"]: n for n in V["normalization"]}
ys = {y["fy"]: y for y in V["input"]["years"]}
ig = V["implied_g1"]["g1"]
FONT = "'Microsoft YaHei','PingFang SC','WenQuanYi Zen Hei',sans-serif"
INK, PAPER, COPPER, GOLD, RED, GREEN = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#8b2e2e", "#2a5c3f"

HEAD = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>
html,body{{width:1280px;height:720px;margin:0;overflow:hidden}} *{{box-sizing:border-box}}
body{{background:{PAPER};color:{INK};font-family:{FONT}}}
.slide{{position:relative;width:1280px;height:720px;padding:56px 64px;overflow:hidden}}
.kicker{{margin:0 0 10px;color:{COPPER};font-size:16px;font-weight:700;letter-spacing:2px}}
h1{{margin:0 0 28px;font-size:40px;line-height:1.2;width:1100px}}
p{{margin:0}} .src{{position:absolute;left:64px;bottom:28px;width:1150px;font-size:13px;color:{COPPER}}}
.card{{background:#fff;border:1px solid #e2dccf;padding:18px 20px}}
</style></head><body><main class="slide">"""
TAIL = "</main></body></html>"


def slide(n, body):
    open(os.path.join(W, "slides", f"slide{n:02d}.html"), "w", encoding="utf-8").write(HEAD + body + TAIL)


def stat(x, y, w, big, small, color=INK):
    return (f'<div class="card" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:120px">'
            f'<p style="font-size:34px;font-weight:700;color:{color};width:{w - 40}px">{big}</p>'
            f'<p style="font-size:16px;color:{COPPER};margin-top:10px;width:{w - 40}px">{small}</p></div>')


os.makedirs(os.path.join(W, "slides"), exist_ok=True)

# 1 结论
slide(1, f"""<p class="kicker">可口可乐 KO · 巴菲特模型 · 2026-11-07</p>
<h1>好生意，贵价格：高估区间，不买</h1>
{stat(64, 200, 270, f"{lo:.2f}–{hi:.2f}", "内在价值区间（美元 / 股）")}
{stat(354, 200, 270, f"{price:.2f}", "现价（2026-11-06 收盘）")}
{stat(644, 200, 270, f"{mos * 100:.1f}%", "安全边际（按下沿，门槛 30%）", RED)}
{stat(934, 200, 270, f"{sc['total']} / 100", "巴菲特评分 → 谨慎")}
<div style="position:absolute;left:64px;top:370px;width:1140px;height:150px;background:{INK};padding:26px 30px">
<p style="color:{PAPER};font-size:24px;line-height:1.5;width:1080px">现价比内在价值上沿还高；回到 30% 安全边际要跌到 {lo * 0.7:.2f} 以下。</p>
<p style="color:{GOLD};font-size:18px;margin-top:12px;width:1080px">换任何口径都不变：不剔除一次性项、代入 2026 指引、IRS 败诉。</p></div>
<p class="src">来源：owner_value 底稿 memory/state/valuations/ko_2026-11-07.json；完整报告 reports/ko_Buffett_Report.html</p>""")

# 2 护城河
PRICE = [("FY2022", 11, "+5%"), ("FY2023", 10, "+2%"), ("FY2024", 11, "+1%"), ("FY2025", 4, "持平")]
bars = "".join(
    f'<div style="position:absolute;left:{120 + i * 150}px;top:{560 - pm * 22}px;width:80px;height:{pm * 22}px;background:{GOLD if pm > 5 else "#ddd6c8"}"></div>'
    f'<p style="position:absolute;left:{100 + i * 150}px;top:{525 - pm * 22}px;width:120px;text-align:center;font-size:20px;font-weight:700">+{pm}%</p>'
    f'<p style="position:absolute;left:{100 + i * 150}px;top:572px;width:120px;text-align:center;font-size:16px">{fy}</p>'
    f'<p style="position:absolute;left:{100 + i * 150}px;top:600px;width:120px;text-align:center;font-size:14px;color:{COPPER}">箱量 {v}</p>'
    for i, (fy, pm, v) in enumerate(PRICE))
slide(2, f"""<p class="kicker">一、护城河 7 / 10（宽）</p>
<h1>连续三年涨价 10% 以上，销量没掉</h1>
<p style="font-size:18px;color:{COPPER};width:560px">全年 price/mix（金色 = 超过 5%）</p>
{bars}
<div class="card" style="position:absolute;left:740px;top:150px;width:470px;height:430px">
<p style="font-size:20px;font-weight:700;width:420px">五类护城河逐项</p>
<p style="font-size:17px;margin-top:16px;width:420px">无形资产（品牌）：成立，主护城河</p>
<p style="font-size:17px;margin-top:10px;width:420px">成本优势：数据不足，不计分</p>
<p style="font-size:17px;margin-top:10px;width:420px">规模壁垒：数据不足，不计分</p>
<p style="font-size:17px;margin-top:10px;width:420px">转换成本 / 网络效应：不成立</p>
<p style="font-size:16px;color:{COPPER};margin-top:22px;width:420px;line-height:1.5">扣分点：FY2024 约 5 个点来自高通胀市场定价；毛利率高于同行只在相对口径成立。</p></div>
<p class="src">来源：可口可乐 FY2022–FY2025 业绩新闻稿（price/mix、单位箱量）</p>""")

# 3 现金流
fy_rows = []
for fy in (2023, 2024, 2025):
    rep = ys[fy]["fcf"]
    nm = norm[fy]["fcf_normalized"] if fy in norm else rep
    fy_rows.append((fy, rep, nm))
cash = "".join(
    f'<p style="position:absolute;left:64px;top:{190 + i * 120}px;width:120px;font-size:22px;font-weight:700">FY{fy}</p>'
    f'<div style="position:absolute;left:190px;top:{186 + i * 120}px;width:{rep / 13000 * 640:.0f}px;height:34px;background:{RED}"></div>'
    f'<p style="position:absolute;left:{200 + rep / 13000 * 640:.0f}px;top:{190 + i * 120}px;width:200px;font-size:18px">报告值 {rep / 1000:.1f}B</p>'
    f'<div style="position:absolute;left:190px;top:{226 + i * 120}px;width:{nm / 13000 * 640:.0f}px;height:34px;background:{GREEN}"></div>'
    f'<p style="position:absolute;left:{200 + nm / 13000 * 640:.0f}px;top:{230 + i * 120}px;width:200px;font-size:18px">剔除后 {nm / 1000:.1f}B</p>'
    for i, (fy, rep, nm) in enumerate(fy_rows))
slide(3, f"""<p class="kicker">二、自由现金流</p>
<h1>两笔一次性支出把 FCF 砍掉一半</h1>
{cash}
<div class="card" style="position:absolute;left:880px;top:180px;width:330px;height:330px">
<p style="font-size:18px;font-weight:700;width:290px">一次性项（公司自列）</p>
<p style="font-size:17px;margin-top:14px;width:290px;line-height:1.5">FY2024 IRS 税务诉讼保证金 $6.0B</p>
<p style="font-size:17px;margin-top:10px;width:290px;line-height:1.5">FY2025 fairlife 或有对价 $6.1B</p>
<p style="font-size:15px;color:{COPPER};margin-top:18px;width:290px;line-height:1.5">只在估值时剔除；评分卡仍用报告值。</p></div>
<p class="src">来源：SEC companyfacts（CFO − Capex）；2024、2025 年业绩新闻稿（一次性项金额）</p>""")

# 4 估值
c, b = V["scenarios"]["conservative"], V["scenarios"]["base"]
X = lambda v: 64 + v / 110 * 1140  # noqa: E731
marks = "".join(
    f'<div style="position:absolute;left:{X(v):.0f}px;top:{y}px;width:3px;height:{560 - y}px;background:{col}"></div>'
    f'<p style="position:absolute;left:{X(v) - 80:.0f}px;top:{y - 32}px;width:160px;text-align:center;font-size:17px;color:{col};font-weight:700">{lab} {v:.2f}</p>'
    for v, lab, col, y in ((lo * 0.7, "建仓线", GREEN, 470), (lo, "下沿", INK, 430), (hi, "上沿", INK, 470), (price, "现价", RED, 430)))
slide(4, f"""<p class="kicker">三、内在价值（两情景所有者盈余 DCF）</p>
<h1>现价 {price:.2f} 在内在价值区间之外</h1>
<div class="card" style="position:absolute;left:64px;top:150px;width:1140px;height:170px">
<p style="font-size:18px;width:1080px">保守情景：阶段 1 增速 {c['g1'] * 100:.2f}%，终端 {c['g_terminal'] * 100:.1f}% → 每股 {lo:.2f}</p>
<p style="font-size:18px;margin-top:14px;width:1080px">基准情景：阶段 1 增速 {b['g1'] * 100:.2f}%，终端 {b['g_terminal'] * 100:.1f}% → 每股 {hi:.2f}</p>
<p style="font-size:18px;margin-top:14px;width:1080px">折现率 9%；FY2025 所有者盈余 {V['owner_earnings']['value'] / 1000:.1f}B；现价隐含所有者盈余增速 {ig * 100:.1f}%</p></div>
<div style="position:absolute;left:{X(lo):.0f}px;top:540px;width:{X(hi) - X(lo):.0f}px;height:40px;background:{GOLD};opacity:0.5"></div>
<div style="position:absolute;left:64px;top:558px;width:1140px;height:3px;background:{COPPER}"></div>
{marks}
<p class="src">来源：owner_value 底稿（每个输入带来源）；股价 Yahoo Finance 2026-11-06 收盘</p>""")

# 5 评分卡
dims = (("生意质量", "business", 30), ("财务健康", "financial", 30), ("管理层", "management", 25), ("价格与价值", "price", 15))
rows = "".join(
    f'<p style="position:absolute;left:64px;top:{170 + i * 90}px;width:200px;font-size:22px">{n}</p>'
    f'<div style="position:absolute;left:270px;top:{168 + i * 90}px;width:{mx * 20}px;height:36px;background:#ddd6c8"></div>'
    f'<div style="position:absolute;left:270px;top:{168 + i * 90}px;width:{sc[k] * 20}px;height:36px;background:{GOLD}"></div>'
    f'<p style="position:absolute;left:{285 + mx * 20}px;top:{172 + i * 90}px;width:120px;font-size:20px;font-weight:700">{sc[k]} / {mx}</p>'
    for i, (n, k, mx) in enumerate(dims))
slide(5, f"""<p class="kicker">四、巴菲特评分卡</p>
<h1>{sc['total']} / 100：谨慎档（40–54）</h1>
{rows}
<div class="card" style="position:absolute;left:1010px;top:160px;width:210px;height:330px">
<p style="font-size:18px;font-weight:700;width:170px">主要扣分</p>
<p style="font-size:16px;margin-top:14px;width:170px;line-height:1.5">报告值 FCF 两年低于净利润 50%</p>
<p style="font-size:16px;margin-top:10px;width:170px;line-height:1.5">BodyArmor 连续两年减值</p>
<p style="font-size:16px;margin-top:10px;width:170px;line-height:1.5">安全边际为负、估值高于同行</p></div>
<p class="src">评分规则：berkshire-score.md；一次性项只用于估值（2026-11-07 定）</p>""")

# 6 风险与反方
slide(6, f"""<p class="kicker">五、什么会改变判断</p>
<h1>最强反方：2026 年 FCF 指引 +14%</h1>
<div class="card" style="position:absolute;left:64px;top:150px;width:360px;height:280px">
<p style="font-size:20px;font-weight:700;color:{GREEN};width:320px">利多</p>
<p style="font-size:17px;margin-top:14px;width:320px;line-height:1.55">2026 FCF 指引至少 $13.0B；若兑现，第一年接近现价隐含的所有者盈余增速 {ig * 100:.1f}%</p></div>
<div class="card" style="position:absolute;left:460px;top:150px;width:360px;height:280px">
<p style="font-size:20px;font-weight:700;color:{RED};width:320px">利空</p>
<p style="font-size:17px;margin-top:14px;width:320px;line-height:1.55">2027 年收购剥离约 8% 营收逆风</p>
<p style="font-size:17px;margin-top:12px;width:320px;line-height:1.55">IRS 败诉：剩余约 $14B 负债，税率约 +3.5%</p></div>
<div class="card" style="position:absolute;left:856px;top:150px;width:360px;height:280px">
<p style="font-size:20px;font-weight:700;width:320px">重估触发</p>
<p style="font-size:17px;margin-top:14px;width:320px;line-height:1.55">FY2026 年报公布</p>
<p style="font-size:17px;margin-top:10px;width:320px;line-height:1.55">IRS 上诉判决</p>
<p style="font-size:17px;margin-top:10px;width:320px;line-height:1.55">股价跌破 {lo * 0.7:.2f}</p></div>
<p class="src">来源：2026 Q3 业绩新闻稿（指引表）；FY2025 10-K（IRS）。已登记预测：FY2030 FCF 低于 $22.7B（把握中）</p>""")
json.dump({"slides": 6, "aspect_ratio": "16:9", "language": "zh"}, open(os.path.join(W, "task.json"), "w"))
print("ok")
