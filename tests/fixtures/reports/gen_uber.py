#!/usr/bin/env python3
"""生成 reports/uber_Copilot_Report.html（Earner 14 节模板，2026-11-06 新流程首次实测）。数字全部来自本会话检索的公开来源。"""
FONT = "font-family:'IM Fell English',Georgia,serif"
INK, PAPER, COPPER, GOLD, GREEN, RED, AMBER = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#c47a1e"


def bars_revenue():
    q = [("Q4'24", 12.0, 1), ("Q1'25", 11.5, 1), ("Q2'25", 12.7, 1), ("Q3'25", 13.5, 1),
         ("Q4'25", 14.4, 0), ("Q1'26", 13.2, 0), ("Q2'26", 14.2, 0), ("Q3'26", 14.8, 0)]
    W, H, base, top = 640, 260, 210, 30
    mx = 16
    out = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">']
    for i, (lab, v, derived) in enumerate(q):
        x = 40 + i * 74
        h = (v / mx) * (base - top)
        col = COPPER if i < 7 else GOLD
        out.append(f'<rect x="{x}" y="{base - h:.1f}" width="46" height="{h:.1f}" fill="{col}" opacity="{0.55 if derived else 1}"/>')
        out.append(f'<text x="{x + 23}" y="{base - h - 6:.1f}" text-anchor="middle" font-size="12" fill="{INK}">{v:.1f}</text>')
        out.append(f'<text x="{x + 23}" y="{base + 18}" text-anchor="middle" font-size="11" fill="{INK}">{lab}</text>')
    out.append(f'<line x1="30" y1="{base}" x2="{W - 10}" y2="{base}" stroke="{INK}" stroke-width="0.6"/>')
    out.append(f'<text x="30" y="16" font-size="11" fill="{COPPER}">营收 Revenue（十亿美元）｜浅色 = 由公司披露同比增速反推</text>')
    out.append(f'<text x="{W - 10}" y="{H - 8}" text-anchor="end" font-size="10" fill="{RED}">2026 起英国网约车改为净额确认，Q3 营收被压低 11 亿美元</text>')
    return "".join(out) + "</svg>"


def bars_segment():
    seg = [("网约车 Mobility", 29.51, 18, 7.52, -2.1), ("外卖 Delivery", 28.54, 22, 5.5, 23), ("货运 Freight", 1.77, 35, 1.76, 34)]
    W, H = 640, 200
    out = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">',
           f'<text x="10" y="16" font-size="11" fill="{COPPER}">Q3\'26 总预订额 Gross Bookings（十亿美元，报告值同比）与营收（同比）</text>']
    for i, (n, gb, g, rev, rg) in enumerate(seg):
        y = 36 + i * 54
        w = gb / 32 * 420
        out.append(f'<text x="10" y="{y + 15}" font-size="12" fill="{INK}">{n}</text>')
        out.append(f'<rect x="130" y="{y}" width="{w:.1f}" height="20" fill="{COPPER}"/>')
        out.append(f'<text x="{136 + w:.1f}" y="{y + 15}" font-size="12" fill="{GREEN}">{gb:.2f}  +{g}%</text>')
        out.append(f'<text x="130" y="{y + 36}" font-size="11" fill="{RED if rg < 0 else GREEN}">营收 {rev:.2f}，{rg:+.1f}%'
                   + ('（英国模式变更）' if rg < 0 else '') + '</text>')
    return "".join(out) + "</svg>"


def bars_eps():
    d = [("Q2'26", 0.83, 0.81), ("Q3'26", 0.94, 0.88), ("Q4'26 指引中值", 1.04, 0.97)]
    W, H, base = 640, 230, 190
    out = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">',
           f'<text x="10" y="16" font-size="11" fill="{COPPER}">非 GAAP 每股收益：共识（灰）vs 实际 / 指引（铜）</text>']
    for i, (lab, est, act) in enumerate(d):
        x = 70 + i * 190
        for j, (v, c) in enumerate(((est, "#9a9a9a"), (act, COPPER))):
            h = v / 1.1 * 150
            out.append(f'<rect x="{x + j * 52}" y="{base - h:.1f}" width="44" height="{h:.1f}" fill="{c}"/>')
            out.append(f'<text x="{x + j * 52 + 22}" y="{base - h - 5:.1f}" text-anchor="middle" font-size="12" fill="{INK}">{v:.2f}</text>')
        col = RED if act < est else GREEN
        out.append(f'<text x="{x + 48}" y="{base + 18}" text-anchor="middle" font-size="11" fill="{INK}">{lab}</text>')
        out.append(f'<text x="{x + 48}" y="{base + 33}" text-anchor="middle" font-size="11" fill="{col}">{act - est:+.2f}</text>')
    return "".join(out) + "</svg>"


def line_margin():
    p = [("Q4'24", 4.2, 0), ("Q3'25", 4.5, 0), ("Q4'25", 4.6, 0), ("Q2'26", 4.8, 0), ("Q3'26", 5.0, 0), ("Q4'26E", 4.95, 1)]
    W, H, lo, hi = 640, 230, 4.0, 5.2
    qpos = [0, 3, 4, 6, 7, 8]  # 真实季度序号（Q4'24=0 … Q4'26E=8）；Q1'25、Q2'25、Q1'26 未取得，留空
    xs = [50 + q * 68 for q in qpos]
    ys = [190 - (v - lo) / (hi - lo) * 150 for _, v, _ in p]
    out = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">',
           f'<text x="10" y="16" font-size="11" fill="{COPPER}">调整后 EBITDA / 总预订额（%）——Uber 不按毛利率口径披露，以此代替</text>']
    for a_, b_ in ((0, 1), (2, 3)):  # 中间缺季度的两段（Q4'24→Q3'25、Q4'25→Q2'26）用细虚线
        out.append(f'<line x1="{xs[a_]}" y1="{ys[a_]:.1f}" x2="{xs[b_]}" y2="{ys[b_]:.1f}" stroke="{COPPER}" stroke-width="1" stroke-dasharray="2,3"/>')
    for a_, b_ in ((1, 2), (3, 4)):  # 相邻季度实线
        out.append(f'<line x1="{xs[a_]}" y1="{ys[a_]:.1f}" x2="{xs[b_]}" y2="{ys[b_]:.1f}" stroke="{COPPER}" stroke-width="2"/>')
    solid = ""
    out.append(f'<line x1="{xs[-2]}" y1="{ys[-2]:.1f}" x2="{xs[-1]}" y2="{ys[-1]:.1f}" stroke="{COPPER}" stroke-width="2" stroke-dasharray="5,4"/>')
    for (lab, v, e), x, y in zip(p, xs, ys):
        out.append(f'<circle cx="{x}" cy="{y:.1f}" r="4" fill="{GOLD if e else COPPER}"/>')
        out.append(f'<text x="{x}" y="{y - 10:.1f}" text-anchor="middle" font-size="12" fill="{INK}">{v:.2f}</text>')
        out.append(f'<text x="{x}" y="212" text-anchor="middle" font-size="11" fill="{INK}">{lab}</text>')
    out.append(f'<text x="{xs[0]}" y="{ys[0] + 18:.1f}" text-anchor="middle" font-size="10" fill="{RED}">低点</text>')
    out.append(f'<text x="{xs[-1]}" y="{ys[-1] + 18:.1f}" text-anchor="middle" font-size="10" fill="{AMBER}">指引中值</text>')
    return "".join(out) + "</svg>"


def price_range(px=69.53, bear=51, base=76, bull=103):
    W, H, lo, hi = 640, 120, 40, 110
    X = lambda v: 30 + (v - lo) / (hi - lo) * 580  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" style="{FONT};width:100%">',
           f'<line x1="30" y1="60" x2="610" y2="60" stroke="{INK}" stroke-width="1"/>']
    for v, n, c in ((bear, "熊市", RED), (base, "基准", COPPER), (bull, "牛市", GREEN)):
        out.append(f'<circle cx="{X(v):.1f}" cy="60" r="7" fill="{c}"/>')
        out.append(f'<text x="{X(v):.1f}" y="90" text-anchor="middle" font-size="12" fill="{c}">{n} ${v}</text>')
    out.append(f'<path d="M{X(px):.1f},48 l-6,-14 h12 z" fill="{GOLD}"/>')
    out.append(f'<text x="{X(px):.1f}" y="26" text-anchor="middle" font-size="12" fill="{INK}">现价 ${px}</text>')
    return "".join(out) + "</svg>"


SRC = [
    ("Motley Fool：Uber Q3 2026 电话会原文（2026-11-04）", "https://www.fool.com/earnings/call-transcripts/2026/11/04/uber-uber-q3-2026-earnings-call-transcript/"),
    ("SEC 8-K：Uber Q3 2026 业绩新闻稿（2026-11-04）", "https://www.sec.gov/Archives/edgar/data/0001543151/000154315126000039/uberq326earningspressrelea.htm"),
    ("公司投资者关系：Q3 2026 新闻稿 PDF", "https://s23.q4cdn.com/407969754/files/doc_earnings/2026/q3/earnings-result/Uber-Q3-26-Earnings-Press-Release.pdf"),
    ("SEC 8-K：Q2 2026 新闻稿（Q3 指引）", "https://www.sec.gov/Archives/edgar/data/0001543151/000154315126000027/uberq226earningspressrelea.htm"),
    ("SEC 10-Q：2026-09-30 季报", "https://www.sec.gov/Archives/edgar/data/0001543151/000154315126000041/uber-20260930.htm"),
    ("Business Wire：Q4 及 2025 全年业绩", "https://www.businesswire.com/news/home/20260204947622/en/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2025"),
    ("Business Wire：Q1 2026 业绩", "https://www.businesswire.com/news/home/20260506718774/en/Uber-Announces-Results-for-First-Quarter-2026"),
    ("Investing.com：Q3 营收 14.8 vs 共识 14.67", "https://www.investing.com/news/earnings/uber-q3-profit-revenue-beat-estimates-as-gross-bookings-jump-20-4998819"),
    ("Yahoo / Zacks：EPS 共识 0.94 与口径争议", "https://finance.yahoo.com/markets/stocks/articles/uber-q3-earnings-miss-estimates-180600289.html"),
    ("Quartz：营收增速放缓与司机供给", "https://qz.com/uber-revenue-growth-slows-driver-shortages-110426"),
    ("Benzinga：UBER 盈利预测（Q4 共识 1.04）", "https://www.benzinga.com/quote/UBER/earnings-forecasts"),
    ("MarketBeat：Q2 非 GAAP EPS 0.81 vs 0.83", "https://www.marketbeat.com/instant-alerts/uber-technologies-nyseuber-trading-down-53-following-weak-earnings-2026-08-05/"),
]

CSS = f"""
:root{{--ink:{INK};--paper:{PAPER};--copper:{COPPER};--gold:{GOLD};--green:{GREEN};--red:{RED};--amber:{AMBER}}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'IM Fell English','Songti SC',Georgia,serif;line-height:1.7}}
.wrap{{max-width:880px;margin:0 auto;padding:24px 18px}}
section{{margin:26px 0}}
.pub{{display:flex;justify-content:space-between;font-size:12px;border-bottom:1px solid var(--copper);padding-bottom:6px;color:var(--copper)}}
h1{{font-size:30px;margin:14px 0 2px}} .h1en{{font-style:italic;color:var(--copper)}}
.tag{{display:inline-block;border:1px solid var(--copper);padding:2px 10px;margin:8px 6px 0 0;font-size:13px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}} .stat{{background:#fff;padding:10px;border-top:3px solid var(--gold)}}
.stat b{{display:block;font-size:20px}} .stat small{{color:var(--copper)}}
.section-zh{{font-size:20px;font-weight:bold}} .section-en{{font-style:italic;color:var(--copper);font-size:13px;margin-bottom:8px}}
.label-zh{{font-weight:bold;color:var(--copper)}} .label-en{{font-style:italic;font-size:12px;color:#777;margin-left:6px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .card{{background:#fff;padding:10px;border-top:4px solid var(--copper)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td,th{{border-bottom:1px solid #d8d2c6;padding:6px;text-align:left}}
.verdict{{background:var(--ink);color:var(--paper);padding:18px}} .verdict-en{{opacity:.6;font-style:italic}}
.bar{{height:10px;background:#ddd}} .bar i{{display:block;height:10px;background:var(--copper)}}
.chip{{display:inline-block;background:#fff;border:1px solid var(--gold);padding:3px 10px;margin:4px;border-radius:12px;font-size:13px}}
.badge{{font-size:11px;padding:0 5px;border:1px solid var(--copper);margin-left:4px;color:var(--copper)}}
.quote{{border-left:3px solid var(--gold);background:#fff;padding:8px 12px;margin:8px 0;font-style:italic}} .quote small{{display:block;font-style:normal;color:var(--copper)}}
.note{{font-size:13px;background:#fff;padding:12px;border-left:3px solid var(--copper)}}
footer{{font-size:12px;color:#777;border-top:1px solid var(--copper);padding-top:8px}}
@media(max-width:640px){{.stats,.cards,.two{{grid-template-columns:1fr}}}}
"""


def sec(n, zh, en, inner):
    return f'<section data-sec="{n}"><div class="section-zh">{zh}</div><div class="section-en">{en}</div>{inner}</section>'


def build():
    P = []
    P.append('<section data-sec="1"><div class="pub"><span>Earnings Copilot · 财报猎手</span><span>2026-11-06 · 现价取自 2026-11-06 盘中缓存</span></div></section>')
    P.append('<section data-sec="2"><h1>Uber 2026 年第三季度：利润加速，营收被会计口径压住</h1>'
             '<div class="h1en">Uber Q3 2026 — Profit Accelerates While Revenue Optics Lag</div>'
             '<span class="tag">评级：中性偏多 · Hold / Accumulate</span><span class="tag">语气评分 68 / 100</span>'
             '<span class="tag">UBER · NYSE</span></section>')
    stats = [("总预订额", "$59.8B", "+20% 同比", "官方"), ("调整后 EBITDA", "$2.96B", "+31%，利润率 5.0%", "官方"),
             ("营收", "$14.8B", "+10%，共识 14.67", "官方"), ("非 GAAP EPS", "$0.88", "+35%，共识 0.89–0.94", "官方 / 共识")]
    P.append('<section data-sec="3"><div class="stats">' + "".join(
        f'<div class="stat"><small>{a}</small><b>{b}</b>{c}<span class="badge">{d}</span></div>' for a, b, c, d in stats) + "</div></section>")
    P.append(sec(4, "季度营收走势", "Quarterly Revenue Trend", bars_revenue() +
                 '<p><span class="label-zh">读法</span><span class="label-en">Read</span>营收同比只有 +10%，但这是会计口径变化造成的：'
                 '2026 年起英国网约车把司机收入从营收中扣除，单 Q3 就压低营收 11 亿美元。看业务真实增速应看总预订额 +20%。</p>'))
    P.append(sec(5, "分部营收与预订额", "Segment Breakdown", bars_segment() +
                 '<p><span class="label-zh">判断</span><span class="label-en">Call</span>增长引擎已经从网约车换到外卖与货运：'
                 '外卖预订额 +22%（CEO 口述 +23%，差异可能来自汇率口径，待核实）、营收 +23%，内生增速还在加快；但 CEO 说外卖骑手供给是「目前最大的挑战」，供给问题不只在网约车。网约车营收 −2.1% 全部来自英国口径，预订额仍 +18%。</p>'))
    P.append('<section data-sec="6"><div class="two"><div><div class="section-zh">EPS 对比</div><div class="section-en">EPS vs Consensus</div>'
             + bars_eps() + '</div><div><div class="section-zh">利润率走势</div><div class="section-en">Margin Trend</div>' + line_margin()
             + '</div></div><p><span class="label-zh">要点</span><span class="label-en">Key</span>每股收益连续两个季度略低于共识（Q2 差 2 美分、Q3 差 6 美分），Q4 指引中值也低于共识，'
               '但利润率在上台阶：EBITDA 占预订额从 Q4\'24 的 4.2% 升到 Q3\'26 的 5.0%；Q4 指引隐含 4.95%，持平略降。共识的问题是投资亏损与无人驾驶投入，不是主业赚钱能力。</p></section>')
    P.append(sec(7, "核心分析", "Core Analysis",
                 '<p><span class="label-zh">增长</span><span class="label-en">Growth</span>预订额 +20% 落在指引 58.25–60.25B 的上半区，Q4 指引 63.25–65.25B（固定汇率 +18–22%），没有减速信号。</p>'
                 '<p><span class="label-zh">盈利</span><span class="label-en">Profitability</span>调整后 EBITDA 2.96B 打在指引 2.86–2.96B 的上沿，增速 +31% 快于预订额 +20%——经营杠杆在兑现。</p>'
                 '<p><span class="label-zh">GAAP 噪音</span><span class="label-en">GAAP Noise</span>GAAP EPS 只有 0.25，是因为股权投资重估亏损 4.76 亿美元；部分媒体拿它比非 GAAP 共识写成「大幅不及」，属口径错配。</p>'
                 '<p><span class="label-zh">隐患</span><span class="label-en">Watch</span>网约车低于公司自身预期——管理层原话是国际市场「司机供给跟不上需求」（巴西、印度油价推高司机成本），Q4 加大供给投入会压低抽成率，但 CFO 同一句话说利润率「不会有什么实质影响」，Q4 EPS 指引中值仍 +37%；代价落在需求端——补贴从乘客挪给司机，CEO 承认「有时意味着乘客价格更高」。非 GAAP EPS 连续两季低于共识，Q4 指引也低于共识（1.00–1.04）；Delivery Hero 收购尚未完成（CEO 原话「hopeful potential acquisition」）。</p>'
                 '<p><span class="label-zh">资本配置转向</span><span class="label-en">Capital Allocation</span>过去 12 个月自由现金流创纪录 104 亿美元；CEO 说钱够做并购也够回购，但紧接着表态「会收缩并购」，明年重心是内生增长、无人驾驶（100 亿美元投入承诺）和择机回购——回购托底在增强，新的大型收购概率在下降。美国网约车保险成本在改善（CFO）。</p>'))
    rows = [("总预订额增速（2027）", "12%", "18%", "22%"), ("EBITDA / 预订额", "4.8%", "5.3%", "5.6%"),
            ("2027 非 GAAP EPS", "$3.90", "$4.50", "$4.90"), ("P/E", "13×", "17×", "21×")]
    P.append(sec(8, "目标价三情景（12 个月）", "Price Targets — 12 Months", price_range() +
                 '<p><span class="label-zh">现价已经假设了什么</span><span class="label-en">What the price implies</span>'
                 '现价 69.53 ÷ Q4 指引年化 EPS 3.88 ≈ 17.9 倍：<b>现价隐含未来一年 EPS 零增长；本报告基准假设 2027 EPS 4.50，即比年化值 +16%</b>（公司给的 +34–39% 是 Q4 单季同比，期间不同，不能直接比）。'
                 '市场在为无人驾驶颠覆打折，不是在为本季业绩打折。</p>'
                 '<div class="cards">'
                 f'<div class="card" style="border-color:{RED}"><b>熊市 $51</b>（−27%）<span class="badge">把握 中</span><br>无人驾驶车队压低网约车抽成，司机供给问题拖累增速，Delivery Hero 并表吃掉利润；EPS 3.90 × 13 倍</div>'
                 f'<div class="card"><b>基准 $76</b>（+9%）<span class="badge">把握 低</span><br>预订额 +18%、利润率继续上台阶；EPS 4.50 × 17 倍（略低于现估值 17.9 倍）= 76.5，取 $76</div>'
                 f'<div class="card" style="border-color:{GREEN}"><b>牛市 $103</b>（+48%）<span class="badge">把握 低</span><br>无人驾驶变成 Uber 平台上的供给而非对手（管理层目标：无人驾驶订单利润率与人类司机相当），估值修复；EPS 4.90 × 21 倍</div></div>'
                 '<table><tr><th>关键假设</th><th>熊市</th><th>基准</th><th>牛市</th></tr>'
                 + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in rows) + "</table>"))
    P.append('<section data-sec="9"><div class="verdict"><b>裁决：中性偏多。</b>业务在加速（预订额 +20%、EBITDA +31%），估值只要求零增长；'
             '但 EPS 连续小幅不及与无人驾驶不确定性，让估值修复需要催化剂。12 个月基准 $76（把握：低——方向可参考，点位不要据此行动）。<div style="margin-top:6px;font-size:12px">未核实项：Q4 EPS 共识取值；外卖预订额口径（+22% 与 CEO 口述 +23%）。</div>'
             '<div class="verdict-en">Verdict: Hold / Accumulate. Fundamentals accelerating; valuation prices in no growth; re-rating needs an AV catalyst.</div>'
             '<div style="margin-top:8px;font-size:12px">本报告影响期权关注清单里的 UBER（基本面名单：可卖 put）——期权动作走期权流水线。</div>'
             '<div style="margin-top:6px;font-size:12px">反馈：<a style="color:#c9a84c" href="https://spontaneous-youtiao-b9cde9.netlify.app?product=earner&report=uber">https://spontaneous-youtiao-b9cde9.netlify.app?product=earner&report=uber</a></div></div></section>')
    tone = [("指引信心 Guidance confidence（越高越好）", 75), ("执行力 Execution（越高越好）", 70), ("防御性 Defensiveness（越高越防御，扣分项）", 50)]
    P.append(sec(10, "管理层语气", "Management Tone", "".join(
        f'<p>{n}：{v}<div class="bar"><i style="width:{v}%"></i></div></p>' for n, v in tone) +
        '<p><span class="label-zh">依据</span><span class="label-en">Basis</span>综合 68 分（中性偏乐观）= 0.4×75 + 0.4×70 + 0.2×(100−50)：'
        '管理层对 10 月与 Q4「非常乐观」，主动承认网约车低于自身预期；问答里一处回避（无人驾驶车队融资结构未披露）、一处只给定性（网约车分部利润率），防御性计 50。执行力扣分来自供给问题与 EPS 连续不及。依据电话会原文（Motley Fool）。</p>'
        + '<div class="quote">“We are very optimistic about the trends as we see them in October and going into Q4.”<small>CEO Dara Khosrowshahi｜对 10 月和 Q4 的趋势非常乐观</small></div><div class="quote">“Mobility continued to see healthy growth but came in below our expectations as a result of driver supply not keeping pace with strong consumer demand, in several international markets.”<small>CEO Dara Khosrowshahi｜网约车低于公司自己的预期：多个国际市场司机供给跟不上需求</small></div><div class="quote">“We still are running into supply constraints rather than demand constraints.”<small>CFO Balaji Krishnamurthy｜卡在供给，不是需求</small></div><div class="quote">“We expect approximately 700 fully-driverless vehicles on Uber by year end, and more than 2,000 by the end of 27.”<small>CEO Dara Khosrowshahi｜年底约 700 辆完全无人驾驶车上线，2027 年底超 2,000 辆</small></div><div class="quote">“Our goal is for AV trips to deliver margins comparable to human driven trips over time.”<small>CFO Balaji Krishnamurthy｜目标：无人驾驶订单利润率最终与人类司机相当</small></div>'))
    P.append(sec(11, "核心主题", "Key Themes", "".join(f'<span class="chip">{c}</span>' for c in (
        "利润增速 > 预订额增速", "外卖成为第二引擎", "卡在供给不在需求（网约车 + 外卖骑手）", "收缩并购、转向回购", "英国口径压低营收", "无人驾驶：年底 700 辆 → 2027 年 2,000+，对手还是供给", "Delivery Hero 收购与融资", "GAAP 投资重估噪音"))))
    risks = [("无人驾驶颠覆网约车抽成", "Autonomous disruption", "中", "高"), ("Delivery Hero 收购未完成", "Pending M&A", "中", "中"),
             ("司机 / 外卖骑手供给紧张推高补贴、乘客涨价（管理层已承认）", "Driver & courier supply", "高", "中"),
             ("无人驾驶车辆融资：早期放自己资产负债表（CEO），但近期 700 / 2,000 辆投入「fairly limited」，2028 年万辆级后靠第三方资本（CFO）；结构未披露；另有 100 亿美元生态投入承诺", "AV fleet financing", "中", "低"),
             ("DoorDash 与 Instacart 合并改变外卖 / 生鲜竞争", "Competitive consolidation", "中", "低"), ("英国等地监管与司机身份", "Regulation", "低", "中"), ("汇率逆风（约 1 个百分点）", "FX headwind", "高", "低")]
    P.append(sec(12, "风险矩阵", "Risk Matrix", '<table><tr><th>风险</th><th>概率</th><th>影响</th></tr>' + "".join(
        f'<tr><td>{a}<br><i style="color:#777;font-size:12px">{b}</i></td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in risks) + "</table>"))
    qa = [("Eric Sheridan：无人驾驶车队怎么融资、要占多少资产负债表和自由现金流？",
           "CFO：「not ready to say a lot on the structures」，只举了与 Santander 的 10 亿美元传统车队融资做模板；近期投入「fairly limited」，长期「should be financed by third party capital」；CEO 补充早期车辆先放自己表上。", "回避（方向清楚，结构未披露）"),
          ("Nikhil Devnani：国际市场供给问题这季是不是变了、会持续多久？",
           "CFO：全年延续的问题，中东战争推高油价、新兴市场最敏感；CEO：叠加 9–12 月旺季的季节性压力。", "部分回答（没给持续时间）"),
          ("Mark Mahaney：网约车分部 8% 利润率在加大供给投入后还守得住吗？",
           "CFO：理念是全公司利润率同比扩张，分部「理想情况下」也一样，但季度会有波动；同一段说「I would not call out any kind of meaningful changes in the margin trajectory for the business」。", "部分回答（定性说利润率轨迹无实质变化，未给分部数字，未正面回答 8% 能否守住）"),
          ("Michael Morton：DoorDash 与 Instacart 合并对你们有什么影响？",
           "CEO：「not gonna affect us too much」，生鲜零售年化 150 亿美元、增速 40%。", "正面回应，但没量化竞争影响")]
    P.append(sec(13, "分析师追问", "Analyst Q&A Tension", "<table><tr><th>真实提问</th><th>管理层怎么答</th><th>判断</th></tr>" + "".join(f"<tr><td>{q}</td><td>{a}</td><td>{v}</td></tr>" for q, a, v in qa) + "</table>"))
    P.append('<section data-sec="14"><div class="note"><div class="section-zh">分析师附注</div><div class="section-en">Analyst\'s Note</div>'
             '<p>数据口径：营收、预订额、EBITDA、EPS、指引取自公司 8-K / 新闻稿；Q4\'24–Q3\'25 营收由公司披露的同比增速反推（与 2025 年报值相差不超过 0.1B）。'
             'Q2\'26 EBITDA 利润率 4.8% 由约 2.8B ÷ 58.0B 推算；Q1\'26 利润率未取得，图中空缺。</p>'
             '<p>EPS 共识来源不一：Q3 共识 LSEG（8 月）0.89、Zacks（财报时）0.94，图中用 0.94；Q4 共识 Benzinga 1.04（有链接，图中采用）；媒体转述的 LSEG 均值 1.00 未找到可链接原文。「指引低于共识」在两个口径下都成立，差额 3–7 美分。</p>'
             '<p><b>置信度总表</b>：经营数字（预订额、EBITDA、营收、指引）高——公司 8-K；EPS 共识 中——来源分歧；语气评分 中——依据电话会原文，权重与回避判断为分析师主观；三情景 熊市 中 / 基准 低 / 牛市 低（已登记 predictions.md）。</p>'
             '<p><b>待核实</b>：Q4 EPS 共识取值（1.00 还是 1.04）；外卖预订额 +22% 与 CEO 口述 +23% 的口径差异；Q1\'26 EBITDA 利润率缺口；EBITDA 精确值 2,963M（只核到四舍五入水平）。</p>'
             '<p>电话会原文由 GitHub Actions 按给定链接抓取（scripts/fetch_transcript.py，Motley Fool，4.2 万字符，CEO 12 段 / CFO 8 段 / 9 位分析师提问）；引用均为原文英文，中文为意译。财报前期权隐含波动未存档，Step 0 只做估值隐含部分。</p>'
             '<p>股价反应：财报前一交易日 11/02 收 66.71，11/04 收 70.22（两个交易日 +5.3%，11/03 收盘缺失）；现价 69.53。</p>'
             '<p>三情景已登记 predictions.md（2027-11-05 收盘验证）。</p>'
             '<div class="section-zh" style="font-size:16px;margin-top:10px">来源索引</div><div class="section-en">Sources</div><ol>'
             + "".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC) + '</ol></div>'
             '<footer>Earnings Copilot · 本报告为研究分析，不构成投资建议 · 生成于 2026-11-06</footer></section>')
    return ('<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Uber Q3 2026 财报分析</title><style>{CSS}</style></head><body><div class="wrap">' + "".join(P) + "</div></body></html>")


if __name__ == "__main__":
    import sys
    open(sys.argv[1], "w", encoding="utf-8").write(build())
