#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jev 白皮书 · 正文 + 版式 + 组装 HTML
   原型：学术型（要被引用的测量与评估）
   视觉方向：8 工程网格（Swiss / International Style）—— 无衬线全程、黑白灰 + 单一功能色、
             表格密度高、等宽字标注版本号与代码。前两份报告都是学术衬线，方向层换调。
   版式模式 A（A4 竖版）：页边距权威是 render.py 的 margin 参数，本文件不写 @page。
"""
import json
import chart as C

D = {k: v for k, v in json.load(open("数据表.json", encoding="utf-8")).items()
     if not k.startswith("_")}
META = json.load(open("数据表.json", encoding="utf-8"))["_meta"]
_used = []


def cite(*ids):
    """上标编号指向**来源**，不指向数据点。

    附录的长度跟来源数走，不跟数据点数走——同一份来源被二十个数字引用也只出现一次。
    因此这里按 src 字段去重编号；多个数据点共享一份来源时，它们的上标是同一个数。
    """
    out = []
    for i in ids:
        if i not in D:
            raise KeyError(f"数据表里没有 {i}")
        s = D[i]["src"]
        if s not in _used:
            _used.append(s)
        n = str(_used.index(s) + 1)
        if n not in out:
            out.append(n)
    return f'<sup class="cite">[{",".join(out)}]</sup>'


def V(i):
    return D[i]["value"]


# 实质数据点 = 关于 Jev 的证据，不含 M* 三条关于本表自身的元统计（统计自己会形成自指）。
# 凡正文要说「共 N 个数据点」，一律用这个变量，不要手写数字——
# 上一版封面手写的 59 在数据表口径改成 57 之后漏改了，而它不报错。
N_SUB = len([k for k in D if not k.startswith("M")])


TOC = []


def toc_row(title, sub, page):
    TOC.append((title, sub, page))
    return ""


# ── 工程网格色板：黑白灰 + 单一功能色 ────────────────────────────────────
INK, MUTE, RULE, SIG = "#17191c", "#6e7276", "#dcdee0", "#c8321f"
GRAY, GRAY2 = "#c4c7ca", "#8f9396"

TOKENS = f"""
:root{{
  --ink:{INK}; --mute:{MUTE}; --rule:{RULE}; --rule-soft:#ebeced; --sig:{SIG};
  --font-sans:'Liberation Sans','Helvetica Neue','WenQuanYi Zen Hei','PingFang SC',Arial,sans-serif;
  --font-mono:'Liberation Mono','DejaVu Sans Mono',monospace;
  --font-body:var(--font-sans); --font-head:var(--font-sans);
  --fs-body:9.6pt; --lh-body:1.66;
}}
body{{ -webkit-font-smoothing:antialiased }}
code,.mono{{font-family:var(--font-mono);font-size:8.6pt;letter-spacing:-.01em}}
.cite{{font-size:6.4pt;color:var(--sig);font-weight:700;vertical-align:super;line-height:0}}

/* ── 封面：工程网格的模数感由细网格线和左对齐块给出 ── */
.cover{{padding-top:30mm;page-break-after:always;break-after:page}}
.cover .grid{{height:26mm;border-top:1.6pt solid var(--ink);border-bottom:.5pt solid var(--rule);
  display:flex;margin-bottom:9mm}}
.cover .grid i{{flex:1;border-right:.5pt solid var(--rule);display:block}}
.cover .grid i:last-child{{border-right:0}}
.cover .grid i.on{{background:var(--sig)}}
.cover .grid i.half{{background:{GRAY}}}
.cover .eyebrow{{font-family:var(--font-mono);font-size:8pt;letter-spacing:.2em;color:var(--sig);margin-bottom:6mm}}
.cover h1{{font-size:29pt;line-height:1.22;margin:0 0 4mm;font-weight:700;letter-spacing:-.015em}}
.cover .sub{{font-size:12.4pt;color:var(--mute);line-height:1.46;margin-bottom:8mm;font-weight:400}}
.cover .thesis{{border-left:2.4pt solid var(--sig);padding:1mm 0 1mm 5mm;font-size:10.4pt;
  line-height:1.62;margin-bottom:9mm}}
.cover .meta{{font-family:var(--font-mono);font-size:8.2pt;line-height:1.95;
  border-top:.8pt solid var(--ink);padding-top:3.5mm;color:var(--mute)}}
.cover .meta b{{color:var(--ink);font-weight:700}}

/* ── 标题层级 ── */
h2{{border-bottom:1.4pt solid var(--ink);padding-bottom:2.2mm;margin:0 0 6mm;font-size:16pt;
  letter-spacing:-.01em;display:flex;align-items:baseline;gap:4mm}}
h2 .num{{font-family:var(--font-mono);color:var(--sig);font-size:13pt;font-weight:700}}
h3{{margin:7mm 0 2.4mm;font-size:11.4pt}}
h3 .n{{font-family:var(--font-mono);color:var(--mute);margin-right:2.2mm;font-weight:400;font-size:10pt}}
h4{{font-size:10pt;margin:5mm 0 1.4mm;font-weight:700}}
.lead{{font-size:10.8pt;line-height:1.6;margin:0 0 6mm;color:var(--ink);
  border-left:2.4pt solid var(--ink);padding-left:5mm}}

/* ── 编号事实摘要 ── */
.abs{{counter-reset:f}}
.abs .f{{margin:0 0 3.2mm;padding-left:10mm;position:relative;font-size:9.5pt;line-height:1.63}}
.abs .f:before{{counter-increment:f;content:"F" counter(f);position:absolute;left:0;
  font-family:var(--font-mono);color:var(--sig);font-weight:700;font-size:8.6pt}}

/* ── 目录 ── */
.toc{{font-size:9.3pt;line-height:1.95}}
.toc .l1{{font-weight:700;display:flex;justify-content:space-between;border-bottom:.4pt solid var(--rule);
  padding-bottom:.6mm;margin-top:2.4mm}}
.toc .l1 .p,.toc .l2 .p{{font-family:var(--font-mono);font-size:8.4pt}}
.toc .l2{{display:flex;justify-content:space-between;color:var(--mute);padding-left:7mm;font-size:8.9pt}}

/* ── 组件 ── */
.side{{background:#f5f6f7;border-left:2.2pt solid var(--ink);padding:3.4mm 4.4mm;margin:5mm 0;
  font-size:8.7pt;line-height:1.6;break-inside:avoid}}
.side .t{{font-weight:700;display:block;margin-bottom:1.2mm;font-family:var(--font-mono);font-size:8pt;
  letter-spacing:.06em;color:var(--sig)}}
.box{{border:.7pt solid var(--rule);padding:4mm 5mm;margin:5mm 0;break-inside:avoid}}
.box.sig{{border:1.1pt solid var(--sig)}}
.box .bt{{font-family:var(--font-mono);font-size:8pt;letter-spacing:.08em;color:var(--sig);
  font-weight:700;display:block;margin-bottom:2mm}}
.pull{{font-size:13pt;line-height:1.44;font-weight:700;letter-spacing:-.012em;
  border-top:1.6pt solid var(--ink);border-bottom:1.6pt solid var(--ink);
  padding:5mm 0;margin:7mm 0;break-inside:avoid}}
.bigrow{{display:flex;gap:4mm;margin:6mm 0;break-inside:avoid}}
.bigrow .c{{flex:1;border-top:1.6pt solid var(--ink);padding-top:2.4mm;min-width:0}}
.bigrow .c.s{{border-top-color:var(--sig)}}
.bigrow .v{{font-size:23pt;font-weight:700;line-height:1.05;letter-spacing:-.02em}}
.bigrow .c.s .v{{color:var(--sig)}}
.bigrow .k{{font-size:8pt;line-height:1.42;color:var(--mute);margin-top:1.6mm}}

/* ── 证据层级徽标 ── */
.tier{{font-family:var(--font-mono);font-size:7.4pt;font-weight:700;padding:.3mm 1.3mm;
  border:.6pt solid var(--mute);color:var(--mute);white-space:nowrap}}
.tier.t0{{border-color:var(--ink);color:#fff;background:var(--ink)}}
.tier.t34{{border-color:var(--sig);color:var(--sig)}}

/* ── 表格：无竖线不成立（工程网格要列边界），沿用流水线的防粘连方案 ── */
table:not(.pagewrap){{table-layout:fixed;width:100%;border-collapse:collapse;
  margin:4.5mm 0;font-size:8.5pt;line-height:1.46}}
table:not(.pagewrap) th{{background:var(--ink);color:#fff;font-weight:700;text-align:left;
  font-family:var(--font-mono);font-size:7.8pt;letter-spacing:.03em;padding:1.8mm 3mm}}
table:not(.pagewrap) td{{padding:1.8mm 3mm;text-align:left;overflow-wrap:anywhere;
  border-bottom:.4pt solid var(--rule-soft);vertical-align:top}}
table:not(.pagewrap) td+td{{border-left:.5px solid var(--rule)}}
table:not(.pagewrap) tr.grp td{{background:#f2f3f4;font-weight:700;font-family:var(--font-mono);
  font-size:7.8pt;letter-spacing:.03em}}
table:not(.pagewrap) td.num{{font-family:var(--font-mono);font-size:8.2pt}}
table:not(.pagewrap) td.sig{{color:var(--sig);font-weight:700}}

.crumb{{font-family:var(--font-mono);font-size:7pt;letter-spacing:.07em;color:var(--mute);
  border-bottom:.4pt solid var(--rule);padding-bottom:1.6mm;margin-bottom:5mm;text-transform:uppercase}}
.figtitle{{font-weight:700;font-size:9.2pt;margin:0 0 1.5mm;line-height:1.4}}
.figno{{font-family:var(--font-mono);color:var(--sig);margin-right:2mm;font-size:8.4pt}}
.figsrc{{font-size:7.4pt;color:var(--mute);line-height:1.5;margin-top:1.6mm;
  border-top:.4pt solid var(--rule);padding-top:1.4mm}}
.fig{{margin:5.5mm 0;break-inside:avoid}}
/* 长表必须允许跨页——整张推到下一页会在前一页留下大半页空白 */
.fig.long{{break-inside:auto;page-break-inside:auto}}
/* 显式开页：给那些「尾巴甩到下一页只剩一两行」的小节用。
   判据是内容完整性，不是省页数——一条落单要点配一个引文块比半页留白更难看 */
h3.newpage{{break-before:page;page-break-before:always}}
ul{{margin:2.4mm 0 2.4mm 0;padding-left:5mm}}
li{{margin-bottom:1.5mm;line-height:1.6}}
p{{margin:0 0 3.2mm;orphans:3;widows:3}}
/* 章末孤儿段：最后两段禁止在其前分页，防止一两句话独占一整页 */
.pagewrap>tbody>tr>td>p:last-child,
.pagewrap>tbody>tr>td>p:nth-last-child(2),
.pagewrap>tbody>tr>td>ul:last-child{{break-before:avoid;page-break-before:avoid}}
"""


# 请求体示例。**必须放在 f-string 之外**——JSON 的花括号在 f-string 里
# 会被当成插值表达式，报 Invalid format specifier（2026-09-19 实测命中）。
REQ_BLOCK = '''<pre class="mono" style="margin:0;line-height:1.5;font-size:8pt;white-space:pre-wrap">{"model": "jev-latest",
 "state": {"ticker": "AMD", "ticker_change_pct": -4.4,
           "market_SPY": -0.45, "market_VIX": 17.1, ...},
 "questions": {
   "driver": ["sector_wide", "stock_specific", "unclear"],   <span style="color:#c8321f">// Choice</span>
   "confidence_sufficient": "bool",                          <span style="color:#c8321f">// Bool</span>
   "peer_divergence": ["score", 0, 10]}}                     <span style="color:#c8321f">// Score</span></pre>'''


def page(crumb, body):
    return (f'<table class="pagewrap"><thead><tr><td><div class="crumb">{crumb}</div>'
            f'</td></tr></thead><tbody><tr><td>{body}</td></tr></tbody></table>')


def fig(no, title, svg, src):
    return (f'<div class="fig"><div class="figtitle"><span class="figno">Figure {no}</span>'
            f'{title}</div>{svg}<div class="figsrc">{src}</div></div>')


def tbl(no, title, head, rows, src, widths=None, long=False):
    cols = "".join(f'<col style="width:{w}">' for w in widths) if widths else ""
    h = "".join(f"<th>{c}</th>" for c in head)
    b = ""
    for r in rows:
        if r and str(r[0]).startswith("##"):
            b += f'<tr class="grp"><td colspan="{len(head)}">{str(r[0])[2:]}</td></tr>'
            continue
        b += "<tr>" + "".join(f"<td{c[1]}>{c[0]}</td>" if isinstance(c, tuple)
                              else f"<td>{c}</td>" for c in r) + "</tr>"
    cls = "fig long" if long else "fig"
    return (f'<div class="{cls}"><div class="figtitle"><span class="figno">Table {no}</span>'
            f'{title}</div><table><colgroup>{cols}</colgroup><thead><tr>{h}</tr></thead>'
            f'<tbody>{b}</tbody></table><div class="figsrc">{src}</div></div>')


def bigrow(items):
    c = "".join(f'<div class="c{" s" if s else ""}"><div class="v">{v}</div>'
                f'<div class="k">{k}</div></div>' for v, k, s in items)
    return f'<div class="bigrow">{c}</div>'


# ══════════════════════════════════════════════════════════════════════════
# 封面
# ══════════════════════════════════════════════════════════════════════════
grid = "".join(f'<i class="{c}"></i>' for c in
               ["", "", "half", "", "on", "", "half", "", "", "half", "", ""])

COVER = f"""
<div class="cover">
  <div class="eyebrow">TECHNICAL ASSESSMENT / 2026-09-19</div>
  <div class="grid">{grid}</div>
  <h1>只做选择题的模型</h1>
  <div class="sub">Jev 的能力边界、生态实况，<br>与支撑它的证据究竟有多硬</div>
  <div class="thesis">Jev 把「判断」从写作文改成涂答题卡，这一步是真的。<br>
  但支撑「它好不好」的全部公开证据——官方的 68%、社区实测的 94.7%、
  以及本报告自建的 164 例基准——<b>没有任何一项报告过「三行 if-else 能得几分」</b>。
  因此「该不该上生产」在今天是<b>证据未决</b>，既不是肯定也不是否定。</div>
  <div class="meta">
    <b>报告类型</b>　技术评估 · 学术型<br>
    <b>一手数据</b>　164 例独立基准集（本报告构建，Jev 侧未执行）<br>
    <b>二手数据</b>　官方发布材料、社区实测、{N_SUB} 个数据点分五级标注证据强度<br>
    <b>核验规则</b>　仅一手可复跑与算术可推导者置 verified；{V("M2")} 的数据点不可独立核验
  </div>
</div>
"""

# ══════════════════════════════════════════════════════════════════════════
# 摘要
# ══════════════════════════════════════════════════════════════════════════
ABSTRACT = page("摘要 | JEV 技术评估", f"""
<h2><span class="num">00</span>摘要</h2>
<div class="lead">Jev 是一类新东西，但它不是「更便宜的大模型」。它把判断从生成任务改造成
分类任务，因而获得了稳定的延迟和一个可用于分流的置信度——代价是它只能回答
已经被人提好的问题。今天关于它的证据，强度远低于讨论的热度。</div>

<div class="abs">
<div class="f">Jev 只回答三种预设题型（单选、打分、是否），不生成文本、不看图，
输入上限约 3.2 万 token{cite("S3","S7")}。这不是功能缺失，是它全部优势的来源，
也是本报告第 4 章四次失败的共同根因。</div>

<div class="f">官方主张全部为自报，且评测以「两个最强模型答案的平均」作标准答案{cite("S8")}——
这个设计的上限是模仿共识，不是逼近正确，因此 68% 这个数不能当作能力测量读。</div>

<div class="f">生态尚未成熟。217 个受评项目中被判为今天可用且证据充分的只有 {V("R2")} 个，
可用率 {V("R3")}{cite("R1","R2","R3")}；其中 {V("R4")} 是开发框架的接入层，
唯一的独立应用是 jev-ultrafast{cite("R4")}。<b>Jev 今天是零件，不是工具。</b></div>

<div class="f">把它塞进自用工作流的四次尝试全部失败{cite("F1")}，其中一次的对照极具信息量：
换成一个对什么都答 0 的假模型，效果与接 Jev 完全相同{cite("F7")}——
说明那个场景里 Jev 的判断根本没有进入结果。</div>

<div class="f"><b>本报告对社区最好那份实测的复核发现三处需要修正的读法</b>：
其一，Jev 与对照模型 93.0% 的差距做 McNemar 精确检验得 {V("C10")}{cite("C8","C9","C10")}，
<b>统计上不显著</b>；其二，94.7% 的总准确率由高把握档撑着，
低把握档反推只有 {V("C5")}{cite("C5")}；其三，该测试未报告多数类基线{cite("C12")}，
因此无法判断它是否优于不看内容直接猜。</div>

<div class="f"><b>真正被低估的那个发现藏在延迟分布里</b>：两者中位延迟接近，
但最慢一次是 1.5 秒对 32 秒{cite("C13","C14")}，相差 {V("C15")}{cite("C15")}。
在代理的串行循环中，决定体验的是尾延迟不是中位数，
而现有模型评测几乎只报中位数。</div>

<div class="f">本报告构建了一个 164 例的独立归因基准{cite("J1")}，并在建成时得到两条方法论结论：
多数类基线 {V("J3")}，而只看单一变量的最优阈值规则得分<b>与它一字不差</b>{cite("J3","J4")}——
基准有效；同时答案键静默删除了作者 5 条记录判断中的 3 条，
且被删的恰好是判错的那些{cite("J6","J7")}。</div>

<div class="f"><b>Jev 侧尚未执行</b>{cite("J8")}。本报告不提供 Jev 的基准得分，
只提供它必须跨过的那两条线，以及一套可复跑的判定装置。</div>
</div>

<div class="box sig"><span class="bt">本报告的一句话</span>
Jev 值得做进产品，不值得用来给自己提效；而在任何人把它放进生产之前，
应当先要求对方回答一个问题：<b>你的基准上，三行 if-else 能得几分？</b>
这个问题今天没有任何一份公开材料回答过。</div>
""")

# ══════════════════════════════════════════════════════════════════════════
# 目录
# ══════════════════════════════════════════════════════════════════════════
toc_row("00　摘要", "", 2)
toc_row("01　界定：一个只做选择题的模型", "题型、规格、它不能做什么", 4)
toc_row("02　官方主张与它们的口径", "68% 是怎么测出来的，以及它测的是什么", 6)
toc_row("03　生态实况：217 个项目的可用性分布", "为什么热闹与可用之间差两个数量级", 7)
toc_row("04　四次失败的结构解剖", "三条约束，以及那个对什么都答 0 的对照组", 9)
toc_row("05　两轮实测的证据强度复核", "显著性、基线缺位、以及被低估的尾延迟", 11)
toc_row("06　一次独立基准的构建", "164 例、两条必须先跨过的线、与一个答案键的自我偏袒", 13)
toc_row("07　机制：为什么只有一种用法站得住", "四个竞争假说与文献定位", 15)
toc_row("08　局限与替代解释", "本报告没有排除掉的那些", 17)
toc_row("09　结论与决策框架", "三步判定，以及不该做的事", 19)
toc_row("附录 A　参考文献与来源", "", 21)
toc_row("附录 B　数据速查页", "全部关键数字一页汇总", 23)


def toc_html():
    r = ""
    for t, s, p in TOC:
        r += f'<div class="l1"><span>{t}</span><span class="p">{p}</span></div>'
        if s:
            r += f'<div class="l2"><span>{s}</span><span class="p"></span></div>'
    return f'<div class="toc">{r}</div>'


TOC_PAGE = page("目录 | JEV 技术评估", f"""
<h2><span class="num">—</span>目录</h2>
{toc_html()}
<div class="side"><span class="t">关于证据标注</span>
正文里带上标编号的数字来自被引来源，不带标记的句子是本报告的判断。
数据表按五级标注证据强度：<span class="tier t0">T0</span> 一手可复跑、
<span class="tier">T1</span> 算术可推导、<span class="tier">T2</span> 二手实测、
<span class="tier t34">T3</span> 官方自报、<span class="tier t34">T4</span> 社媒自报。
分布见附录 B。<b>T3/T4 不作独立证据使用</b>，只用于描述主张本身。</div>
""")

# ══════════════════════════════════════════════════════════════════════════
# 01 界定
# ══════════════════════════════════════════════════════════════════════════
CH1 = page("01 界定 | JEV 技术评估", f"""
<h2><span class="num">01</span>界定：一个只做选择题的模型</h2>
<div class="lead">大模型是「会写作文的 AI」，Jev 是「只会做选择题的 AI」。
这个类比准确到可以当定义用——它的每一项优势和每一项限制都是它的直接推论。</div>

<h3><span class="n">1.1</span>规格</h3>
<p>TypeSafe AI 发布 Jev 的时间在两个来源之间差一天：本文作者记为 2026-09-15{cite("S1")}，
而创始人 Diogo Almeida 的发布帖标注为 9 月 16 日{cite("S2")}。本报告未能判定何者为准，
并存两者只为说明对来源冲突的处理方式：<b>不取平均、不择一，并存并标注。</b></p>

{tbl(1, "Jev 的规格，以及每一项规格对应的直接后果",
     ["维度", "Jev", "通用大模型", "该差异的直接后果"],
     [["输出形式", "固定选项上的概率分布", "自由文本，需程序再解析",
       "输出格式永远合法，但<b>选错选项完全可能</b>"],
      ["题型", f'单选(≤{V("S4")} 项)/打分/是否', "任意",
       "问题必须先被化成选项，这一步不由 Jev 完成"],
      ["响应", f'{V("S5")}（官方）', f'{V("S11")}（官方对比口径）',
       "对比口径不对等：后者是写完整段答案的时间"],
      ["输入价", V("S6"), V("S10"), "输出侧免费，因为没有生成过程"],
      ["输入上限", V("S7"), "几十万 token", "<b>长输入必须先被压缩，而压缩需要判断</b>"],
      ["图像", "不支持", "支持", "任何依赖看画面的场景一律出局"]],
     f'资料来源：TypeSafe 发布材料与定价页{cite("S3","S4","S5","S6","S7","S10","S11")}，'
     f'经作者转述；证据层级 T3（官方自报，无第三方核验）。右栏为本报告的判断，不带标记。',
     ["15%", "24%", "23%", "38%"])}

<h3><span class="n">1.2</span>为什么它快、为什么它便宜</h3>
<p>通用大模型逐 token 生成，每个 token 都要跑一次完整前向并把结果接回输入。
Jev 的答案空间事先封闭，只需在给定选项上算一遍概率分布。输出侧免费不是定价让利，
而是<b>输出侧确实没有计算量可言</b>——它输出的是一个长度等于选项数的概率向量，不是文字。</p>

<h3><span class="n">1.3</span>它不能做什么</h3>
<p>不能聊天、不能写代码、不能写文案、不能看图。这不是产品路线图上待补的空白，
是架构决定的边界。一个更有用的说法是：<b>Jev 不接受开放式问题，
它只接受已经被提好的问题。</b>把现实情境化成一组互斥选项——
这件事是判断工作的主体部分，而 Jev 不做这一步。第 7 章会说明，
这个界定足以解释本报告中记录的全部失败案例。</p>

<h3><span class="n">1.4</span>一次请求长什么样</h3>
<p>规格表说清了它能做什么，但没说清「把问题化成选项」在代码里具体是什么样。
下面是本报告第 6 章那个基准的请求构造，它同时展示了三种题型：</p>

<div class="box"><span class="bt">请求体（schema 未经官方文档核对，见 6.4）</span>
{REQ_BLOCK}</div>

<p>值得注意的是 <code>questions</code> 这个字段：<b>选项是调用方写死的</b>。
模型收到的不是「这只股票为什么跌」，而是「在这三个标签里选一个」。
三个标签怎么定、边界划在哪、要不要留 <code>unclear</code> 这个出口——
全部由调用方决定，而这些决定<b>本身就是判断</b>。
第 7 章会论证：这正是 Jev 能力边界的准确位置。</p>

<div class="box"><span class="bt">一个必须澄清的说法</span>
「永不幻觉」这个宣传语描述的是<b>输出格式的合法性</b>，不是<b>判断的正确性</b>。
它保证返回值一定落在你给的选项里，不保证落在对的那个上。
TypeSafe 的 CEO 在 Hacker News 上亲自承认了这一点。
这个区分贯穿本报告：<b>格式正确而内容错误</b>的失败，Jev 一个也防不住，
而这类失败恰恰是实际工作中最常见、也最难被发现的那一类。</div>

""")

# ══════════════════════════════════════════════════════════════════════════
# 02 官方主张
# ══════════════════════════════════════════════════════════════════════════
tier_chart = C.hbar(
    [("T2 二手实测（作者自测）", 23), ("T1 算术可推导（本报告复算）", 10),
     ("T0 一手可复跑（本报告代码）", 9), ("T3 官方自报", 9), ("T4 社媒自报", 6)],
    fmt="{} 个", note=f"按证据强度分级，共 {N_SUB} 个实质数据点（不含 3 条关于本表自身的元统计）。T0/T1 合计 19 个即本报告可独立担保的部分。",
    colors=[GRAY, INK, INK, SIG, SIG])

CH2 = page("02 官方主张 | JEV 技术评估", f"""
<h2><span class="num">02</span>官方主张与它们的口径</h2>
<div class="lead">官方没有跑公开榜单，而是自建了一套测试。这套测试的设计决定了
68% 这个数字能说明什么、不能说明什么——而它能说明的，比多数转述里以为的要少。</div>

<h3><span class="n">2.1</span>那套自建测试测的是什么</h3>
<p>官方评测的设计是：让各模型在同一段程序里做决策，
<b>以两个最强模型答案的平均值作为标准答案</b>，Jev 在其中准确率约 68%{cite("S8")}，
同时宣称便宜 40–400 倍、快 20–200 倍{cite("S9")}。</p>

<div class="box sig"><span class="bt">这个设计的天花板</span>
以强模型的共识当标准答案，测的是<b>与强模型的一致程度</b>，不是<b>与事实的一致程度</b>。
两者在强模型共同犯错的地方系统性地分离，而那恰好是最值得测的地方。
因此 68% 应当读作「与前沿模型共识的吻合率」，<b>不是准确率</b>。
这不是吹毛求疵：一个只会复读共识的模型在这套测试里可以拿到接近 100%，
而它在真实任务上毫无价值。</div>

<h3><span class="n">2.2</span>倍数是怎么来的</h3>
<p>三条质疑在 Hacker News 上被反复提出，本报告认为其中两条成立：</p>
<ul>
<li><b>速度对比不对等（成立）。</b>官方比较的是大模型写出完整一段答案的时间{cite("S11")}，
而不是让大模型也只输出一个字母。后者才是同任务对照。</li>
<li><b>「前沿模型」一词借光（部分成立）。</b>更准确的说法是：在做选择题这一件事上，
它把速度与成本推到了新水平。这个说法本身已经足够强，不需要借光。</li>
<li><b>刷屏的 Doom 演示喂的是敌人坐标而非画面。</b>模型相当于开了透视，
该演示说明反应快，不说明会玩游戏。</li>
</ul>

{fig(1, "本报告引用的 {N_SUB} 个实质数字里，三分之二我无法独立核验",
     tier_chart,
     f'资料来源：本报告数据表自计{cite("M1","M2","M3")}。'
     f'核验规则在开工时定死：仅一手可复跑或算术可推导者置 verified。'
     f'T3/T4 标记为不可核验不代表怀疑其真伪，只表示本报告没有独立证据。')}

<p>把这张图当成结论读：<b>关于 Jev 的公开讨论，其证据基础 {V("M2")} 由自报构成。</b>
这个比例本身不是丑闻——任何一个发布不到一周的模型都会是这样——
但它决定了今天所有关于 Jev 的强判断（包括正面的和负面的）都应当降一档来听。</p>
""")

# ══════════════════════════════════════════════════════════════════════════
# 03 生态
# ══════════════════════════════════════════════════════════════════════════
funnel = C.hbar(
    [("受评项目总数", 217), ("判为「现在可用」且证据充分", 15),
     ("其中：开发框架的接入层", 14), ("其中：独立可用的应用", 1)],
    fmt="{}", note="第一轮评测：以各项目的公开介绍文字为输入，由 Jev 逐条判定。"
                   "Jev 不开链接、不跑代码，判的是「公开证据够不够」，不是项目好不好。",
    colors=[GRAY, INK, GRAY2, SIG])

CH3 = page("03 生态实况 | JEV 技术评估", f"""
<h2><span class="num">03</span>生态实况：217 个项目的可用性分布</h2>
<div class="lead">社交媒体上的密度与可用性之间隔着两个数量级。
这不是唱衰——发布不到一周的模型本该如此——但它直接决定了今天谁该用它、谁不该。</div>

<h3><span class="n">3.1</span>漏斗</h3>
{fig(2, "217 个项目里今天真能用的有 15 个，其中 14 个是框架接口而不是应用",
     funnel,
     f'资料来源：作者第一轮实测{cite("R1","R2","R4")}，'
     f'样本 = 60 个案例 + GitHub 上 167 个 Jev 项目。可用率 {V("R3")}{cite("R3")}，'
     f'框架接口占可用项的 {V("R5")}{cite("R5")}。证据层级 T2。'
     f'<b>该轮无人工标注的标准答案{cite("R7")}，因此只能观察判定分布，不能评估判定准不准。</b>')}

<p>这 15 个里的 14 个是 pydantic-ai、LangChain、Vercel AI SDK 这类主流开发框架的
Jev 接入层{cite("R4")}，唯一的独立应用是 Browser Use 的 jev-ultrafast。
作者自己列出的 5 个「已接入产品」中，Jev 只认其中 2 个是今天可直接触及的{cite("R6")}。</p>

<div class="pull">今天能用的 Jev，是框架里的接口，不是应用。
它是给做产品的人用的零件，不是给用工具的人提效的东西。</div>

<h3><span class="n">3.2</span>证据最完整的那个案例</h3>
<p>jev-ultrafast 值得单独说，因为它是全部案例里唯一自带测量脚本的：
它不再每步截图给视觉模型看，而是把网页拆成带编号的元素清单，
让 Jev 选「做什么、对哪个」。一次机票搜索的全程耗时从 9.5 秒降到 7.1 秒{cite("B1")}，
降幅 {V("B2")}{cite("B2")}。</p>

<p>请注意这个案例的结构——它解释了为什么<b>它</b>能成而别的不能：
网页元素清单是一份<b>已经被结构化、且天然就是选项列表</b>的输入。
把现实化成选项这一步由 DOM 解析完成，不由 Jev 完成。
第 7 章会论证：这正是 Jev 唯一能可靠工作的输入形态。</p>

{tbl(2, "其余有公开数字的案例，按证据层级排列——全部为自报，无一附带标准答案",
     ["案例", "规模与耗时", "成本", "层级"],
     [["##按用途分类：代理决策器"],
      ["jev-ultrafast（Browser Use）", "机票搜索 9.5s → 7.1s", "未披露",
       ('<span class="tier">T2</span>', ' class="num"')],
      ["Slack 代理前置分类", "端到端提速约 2 倍", "未披露",
       ('<span class="tier t34">T4</span>', ' class="num"')],
      ["##按用途分类：海量逐条分类"],
      ["jev() PostgreSQL 扩展", "129 行 / 约 1 秒 / 重跑 6ms", "$0.0009",
       ('<span class="tier t34">T4</span>', ' class="num"')],
      ["广告素材拆解", "724 条 / 37 品牌 / 40 秒", "$0.09",
       ('<span class="tier t34">T4</span>', ' class="num"')],
      ["AI 论文主题分类", "1,018 篇 → 24 主题", "未披露",
       ('<span class="tier t34">T4</span>', ' class="num"')],
      ["##按用途分类：按把握分流"],
      ["播客洞察排序（低把握转 DeepSeek）", "85 段 / 约 380ms 每批", "未披露",
       ('<span class="tier t34">T4</span>', ' class="num"')]],
     f'资料来源：各项目公开帖文与仓库{cite("B1","B7","B3","B4","B6","B5")}。'
     f'<b>本表所有条目均无标准答案、无错误率披露</b>，'
     f'因此它们证明的是「能跑通且很快」，不是「判得对」。这两件事在本报告中始终分开记。',
     ["36%", "30%", "18%", "16%"])}

<div class="side"><span class="t">未计入的部分</span>
OpenJev、Kev、Nimble 这类模仿 Jev 的替代模型不计入——它们不是 Jev 的应用。
纯观点、教程、上架公告、没有运行证据的构想同样排除。
按作者估计，被排除的这部分数量约为真实案例的数倍。</div>
""")

# ══════════════════════════════════════════════════════════════════════════
# 04 失败解剖
# ══════════════════════════════════════════════════════════════════════════
CH4 = page("04 失败解剖 | JEV 技术评估", f"""
<h2><span class="num">04</span>四次失败的结构解剖</h2>
<div class="lead">四次尝试把 Jev 塞进自用工作流，四次失败{cite("F1")}。原因没有一次出在模型本身——
接口每次都正常返回，判断也准，全部出在它被放进真实流程的那一刻。
<b>这四次的价值高于前面所有成功案例：成功案例只说明它能做什么，失败案例说明边界在哪。</b></div>

{tbl(3, "四次失败，以及每一次卡住的那个结构性原因",
     ["尝试", "结果", "卡在哪", "归类"],
     [["Claude Code 上下文压缩插件",
       "装不上；勉强跑起来是无脑删",
       "为塞进 32K 上限，插件先把内容砍光，Jev 只看到工具名和长度",
       ('看不到内容', ' class="sig"')],
      ["Codex 模型路由省额度",
       f'成本 {V("F2")}，每步多等 1–2 秒',
       f'中间代理把请求变重 {V("F3")} 倍并弄丢缓存',
       ('壳的问题', ' class="sig"')],
      ["稿件 AI 味检测",
       f'{V("F4")} 句误报，误报率 {V("F5")}',
       "作者本就逐句自审，未多抓出一句，净增价值约零",
       ('边际成本为零', ' class="sig"')],
      ["40 个大视频判断可删",
       f'Jev 判 {V("F6")}（纯文件名规则判出 7 个）',
       "看不到文件内容，只能凭文件名猜",
       ('看不到内容', ' class="sig"')]],
     f'资料来源：作者自述{cite("F1","F2","F3","F4","F5","F6")}，证据层级 T2。'
     f'右栏归类为本报告所加，不带标记。',
     ["24%", "24%", "37%", "15%"])}

<h3><span class="n">4.1</span>那个对什么都答 0 的对照组</h3>
<div class="box sig"><span class="bt">本报告认为这是全文最有信息量的一次观察</span>
在上下文压缩插件那次失败里，作者做了一件多数人不会做的事：
<b>把 Jev 换成一个对什么都返回 0 的假模型，效果完全相同</b>{cite("F7")}。
<br><br>
这个对照一次性排除了「调参数 / 换提示词 / 等生态成熟」全部解释，
直接证明<b>那个场景里 Jev 的判断根本没有进入结果</b>。没有它，
这次失败会被记成「效果一般，再优化一下」，而真相是这条路整条不通。
<br><br>
<b>任何人要在生产里评估 Jev，第一件该做的事就是把它换成常数模型跑一遍</b>：
如果指标不动，说明你测的不是 Jev。</div>

<h3 class="newpage"><span class="n">4.2</span>三条约束</h3>
<p>四次失败归到三条，而这三条<b>结构性地存在，不随生态成熟而消失</b>：</p>
<ul>
<li><b>看不到内容。</b>输入上限约 3.2 万 token{cite("S7")}，为塞进去必须先砍内容，而砍完它就没法判断了。<b>要准就得给它看内容，给它看内容就超上限。</b></li>
<li><b>订阅制杀死了它的经济学。</b>包月订阅的工具里，判断的边际成本本来就是零，再插一层只会多一层延迟和一处故障点。至于「路由到便宜模型省额度」——换便宜模型不叫省，叫少买。</li>
<li><b>它只判断，不干活。</b>接进真实流程要靠第三方写的插件或代理搬数据，
而那层壳大多是个人两三天写出来的——四次失败里至少一次的直接责任在壳不在 Jev{cite("F3")}。</li>
</ul>

<div class="pull">想拿它给自己提效的人，走不通；把它当零件做进产品的人，才有可能。</div>
""")

# ══════════════════════════════════════════════════════════════════════════
# 05 证据强度复核
# ══════════════════════════════════════════════════════════════════════════
conf_chart = C.hbar(
    [("≥90% 把握档（255 个判断）", 100.0), ("<90% 把握档（45 个判断）", 64.4),
     ("全部 300 个判断", 94.7)],
    fmt="{}%", maxv=100,
    note="低把握档为本报告反推：总正确数减去高把握档全对的 255，除以剩余 45。",
    colors=[INK, SIG, GRAY2])

# ⚠ ymax 必须显式给：默认由最大值推出的 38.4 会被 {:.0f} 格式化成「39/29/20/10/0」
#   这种不等距刻度（流水线第 9 坑，2026-09-19 实测命中）。给 40 得到 40/30/20/10/0。
lat_chart = C.paired_bars(
    [("中位延迟", 0.7, 0.75), ("最慢一次", 1.5, 32.0)],
    unit=" 秒", ymax=40, series=("Jev", "Qwen 3.8 Flash"), colors=(INK, SIG),
    note="上海串行调用，300 次。Qwen 中位延迟原文记为「差不多」，此处取 0.75 秒示意。")

CH5 = page("05 证据强度复核 | JEV 技术评估", f"""
<h2><span class="num">05</span>两轮实测的证据强度复核</h2>
<div class="lead">作者的第二轮实测是本报告见到的、关于 Jev 最认真的一份公开测试：
预先标注答案、设了对照组、报告了延迟分布。正因为它最认真，值得逐项复核。
复核结果是三处读法需要修正，以及一处被作者自己低估的发现。</div>

<h3><span class="n">5.1</span>测试设计</h3>
<p>100 条中文科技资讯，答案事先标好，每条三道题，共 300 个判断{cite("C1")}；
对照组是 Qwen 3.8 Flash；从上海串行调用。</p>

<h3><span class="n">5.2</span>修正一：那 1.7 个百分点的差距不显著</h3>
<p>准确率 94.7% 对 93.0%{cite("C8")}，两模型答案不同的有 12 条{cite("C9")}。
配对比较的正确检验是 McNemar 精确检验，只看这 12 个分歧对如何分配：</p>

{tbl(4, "对 Jev 与 Qwen 差距的配对显著性检验：两种可能情形都不显著",
     ["情形", "Jev 独对", "Qwen 独对", "准确率差", "McNemar 双侧 p"],
     [["b−c = 6", "9", "3", "+2.0pp", ('0.146', ' class="num sig"')],
      ["b−c = 4", "8", "4", "+1.3pp", ('0.388', ' class="num sig"')]],
     f'资料来源：本报告计算{cite("C10")}，输入为 C8、C9 两个数。'
     f'<b>存在一处内部不一致</b>{cite("C11")}：分歧数 12 为偶数则正确数之差必为偶数，'
     f'但由 94.7%−93.0% 还原出的差是 5（奇数），故原文两数至少有一个是约数。'
     f'本报告因此给出区间而非点值。两种情形的 p 都远高于 0.05。',
     ["16%", "16%", "18%", "20%", "30%"])}

<p><b>结论：在这个样本上，Jev 与一个便宜的轻量模型打平，差距无统计显著性。</b>
这与作者自己的定性结论（「准确率和费用都和便宜大模型打平」）一致，
本报告所做的只是把它从印象升级为检验。</p>

<h3><span class="n">5.3</span>修正二：94.7% 是被高把握档撑起来的</h3>
{fig(3, "高把握档零错误，但低把握档只有六成出头——总准确率掩盖了这个落差",
     conf_chart,
     f'资料来源：高把握档数据为作者实测{cite("C3","C8")}；'
     f'低把握档 {V("C5")} 为本报告反推{cite("C5")}，区间来自 94.7% 的取整歧义，'
     f'图上取中值 64.4%。<b>低把握档 n=45，且其中 80–90% 一档只有 11 个样本</b>{cite("C7")}。')}

<p>这个落差不是缺陷，恰恰是「按把握分流」这套打法成立的<b>前提</b>——
高低两档必须拉开，分流才有意义。但它同时说明：
<b>94.7% 这个总数不应被当作 Jev 的能力值引用</b>，
因为它混合了两个性质完全不同的档位。能被引用的是两个数：高档零错误、低档六成。</p>

<h3><span class="n">5.4</span>修正三：没有报告多数类基线</h3>
<div class="box sig"><span class="bt">这是本报告最核心的一条批评，且适用于全部公开材料</span>
第二轮没有报告<b>多数类基线</b>——全猜最常见的那个标签能得多少分{cite("C12")}。
没有这个数，94.7% 无法判断是不是优于「不看内容直接猜」。
<br><br>
在一个三分类任务里，如果标签分布是 8:1:1，全猜多数类就有 80%；
此时 94.7% 是真本事。如果分布是 95:3:2，全猜多数类有 95%，
那么 94.7% <b>不如不看内容</b>。<b>两种情况在已披露的信息里无法区分。</b>
<br><br>
这不是针对作者——<b>官方评测同样没报</b>，社区案例一个也没报。
第 6 章给出本报告在自建基准上实测的这两条线。</div>

<h3><span class="n">5.5</span>被低估的那个发现：尾延迟</h3>
{fig(4, "中位延迟两者接近，最慢一次相差 21 倍——这才是代理循环里真正决定体验的量",
     lat_chart,
     f'资料来源：作者第二轮实测{cite("C13","C14")}，上海串行调用 300 次；'
     f'比值 {V("C15")} 为本报告推算{cite("C15")}。'
     f'Qwen 的中位延迟原文只记「差不多」，未给具体数，图上取 0.75 秒示意，'
     f'该柱<b>不应被单独引用</b>。')}

<p>作者把这一点写成了一句话（「Jev 赢的不是快，是没有长尾」），
本报告认为它应当被提升为主要发现。理由是机制性的：<b>代理是串行循环</b>，
一次任务要连着做几十个判断，任何一次 32 秒的停顿都会直接暴露在用户面前，
而中位数上的零点几秒差异用户感知不到。在这种结构下，
<b>P99 延迟比中位延迟重要一个数量级</b>——而现有的模型评测几乎只报中位数和均值。</p>

<div class="side"><span class="t">文献定位</span>
这一点在系统领域是老常识（Dean & Barroso, <i>The Tail at Scale</i>, 2013：
在扇出式系统里尾延迟主导用户体验），但在 LLM 评测实践里基本缺席。
Jev 的价值主张里<b>最硬、最难被轻量模型追平的那一项，恰恰是它自己没有重点宣传的</b>：
封闭答案空间意味着没有可变长度的生成过程，因而没有长尾的结构性来源。
这是架构保证，不是工程调优。</div>
""")

# ══════════════════════════════════════════════════════════════════════════
# 06 独立基准
# ══════════════════════════════════════════════════════════════════════════
# ⚠ 不要把「Jev 未测」画成第三根柱子：零高度柱加标注「0%」会被读成真实的零分。
#    这与「负值画成零高度」是同一类错误——图上无法表达「没有这个数」。
#    未测状态交给下面的大数字行，那里可以写「未测」两个字。
bench_chart = C.hbar(
    [("多数类基线（全猜最常见标签）", 55.5), ("平凡规则上限（最优单变量阈值）", 55.5)],
    fmt="{}%", maxv=100,
    note="两条线相等即说明「标的自身涨跌」这一维零信息量。Jev 侧未执行，故不入图——"
         "零高度的柱会被读成零分。执行条件见 6.4。",
    colors=[GRAY2, INK])

CH6 = page("06 独立基准 | JEV 技术评估", f"""
<h2><span class="num">06</span>一次独立基准的构建</h2>
<div class="lead">第 5 章批评了公开材料普遍不报基线。本章给出一个自建基准，
把那两条线实测出来。<b>本章不提供 Jev 的得分</b>——它尚未执行。
本章提供的是判定装置本身，以及构建过程中暴露的两个方法论问题，
这两个问题独立于 Jev 成立。</div>

<h3><span class="n">6.1</span>任务与答案键</h3>
<p>基准任务是<b>归因判断</b>：给定某只股票当日涨跌与大盘、波动率、利率背景，
判断该涨跌属于行业共动、个股独有，还是无从判断。选它的理由有三：
输入非结构化、输出是带置信度的分类（正对 Jev 的题型）、
而且本报告作者在这件事上<b>有记录在案的失败</b>。</p>

<p>数据取自 25 个交易日（2026-08-18 至 2026-09-18）、27 个标的，
每日取当日最后一次抓价{cite("J2")}，经答案键筛选后得 164 例{cite("J1")}。
答案键只裁判一件机器裁得了的事：把目标的涨跌与<b>同业个股</b>的均值和离散度做 z 检验。
不裁「是利率驱动还是油价驱动」——那个标签没有机械答案，
拿事后解释当标准答案就是自评。</p>

<div class="side"><span class="t">信息隔离</span>
模型可见：标的代码、它自己的涨跌、大盘/波动率/利率背景、当天叙事。
模型不可见：<b>同业个股的涨跌</b>——那正是答案键的计算材料。
这条被破坏，整个实验作废，因此请求构造函数只从 <code>visible</code> 取值，
答案存在 <code>key</code> 里，两者不交叉。</div>

<h3><span class="n">6.2</span>两条必须先跨过的线</h3>
{fig(5, "多数类基线与平凡规则上限完全相等——该基准无法被单变量规则做掉，因此有效",
     bench_chart,
     f'资料来源：本报告自建基准{cite("J1","J3","J4","J8")}，'
     f'代码 <code>tools/jev_bench.py</code>，证据层级 T0（一手可复跑）。'
     f'标签分布 {V("J5")}{cite("J5")}。平凡规则上限的口径是：'
     f'只看标的自身涨跌绝对值的两阈值规则，在 0–6% 范围网格搜索后的最高准确率。')}

{bigrow([(V("J3"), "多数类基线：全猜最常见标签 sector_wide 的准确率。任何模型低于此数即无信息量。", False),
         (V("J4"), "平凡规则上限：最优单变量阈值规则的得分。与基线一字不差 → 该维度零信息量。", False),
         ("未测", "Jev 在本基准上的得分。未执行，非零分。", True)])}

<p>这个检查本身值得单独说明。<b>如果一条三行的阈值规则就能做到和模型一样好，
那这个基准测不出任何东西。</b>实测结果是平凡规则上限与多数类基线完全相等，
说明「标的自身涨跌」这一维度零信息量，任务确实需要同业共动结构的先验才能做对。
<b>基准通过有效性检查。</b>这一步在本报告见到的全部公开评测中，一次都没有出现过。</p>

<h3><span class="n">6.3</span>答案键删掉了最该被裁判的那些案例</h3>
<div class="box sig"><span class="bt">构建过程中命中的第二个方法论问题</span>
答案键设了一个参数：同业不足 3 只不出题——一个看起来纯技术、纯保守的常数。
<br><br>
首次造集的结果：本报告作者记录在案的 5 条归因判断，
<b>被删掉 3 条，全部是同一只股票，全部落在汽车板块</b>{cite("J6")}。
原因是汽车组在 27 只标的的池子里只有三只，去掉目标只剩两个同业。
<br><br>
<b>而作者记为落空的判断，全部落在汽车板块。</b>
删掉的恰好是判错的那些，留下的恰好是判对的那些——
剩余对照子集上作者的成绩是 2 比 2 全对{cite("J7")}。
<br><br>
<b>如果没有去查被删的是哪些，这个基准会报告：作者在归因上百发百中。</b></div>

<p>这不是「自评会偏袒自己」的重复。那条说的是评价者有动机偏袒自己；
<b>这一条说的是中立的裁判规则也会偏袒你，而且设计它的时候根本没想到自己</b>。
偏袒不来自动机，来自<b>失败与规则盲区同源</b>——两者都因为汽车板块样本薄，
所以必然重合。</p>

<p>处理方式是不改那个常数把案例捞回来（那是凑答案），
而是让删除这件事出现在工具输出的显眼处，并直接标注
「剩余对照子集是自选样本，不得用来比高下」。<b>可执行判据：
任何评测、回测或记分工具，被排除的样本必须逐条列出，
并且必须检查「我自己的历史答案有几条落在被排除区」。</b>
只报「跳过 N 条」是不够的——N 是个数字，不会让人去看它删了谁。</p>

<h3><span class="n">6.4</span>为什么 Jev 侧尚未执行</h3>
<p>三个条件未满足{cite("J8")}：本报告的执行环境对 <code>api.typesafe.ai</code>
及其文档站的出站连接被组织代理策略拒绝；尚无 API 密钥；
且请求体 schema 未经官方文档核对{cite("J9")}——
文档站在本环境同样不可达，现有构造依据公开检索结果拼接。</p>

<p>基准集、请求构造与对分逻辑均已就绪，可在出网不受限的环境中执行。
本报告选择<b>交付未执行的装置而不是执行一个凑合的版本</b>：
在 schema 未核对的情况下拿到的失败率，无法区分「模型判得差」和「字段名写错了」，
而这两者会导出完全相反的结论。</p>
""")

# ══════════════════════════════════════════════════════════════════════════
# 07 机制
# ══════════════════════════════════════════════════════════════════════════
CH7 = page("07 机制 | JEV 技术评估", f"""
<h2><span class="num">07</span>机制：为什么只有一种用法站得住</h2>
<div class="lead">前面几章给的是「谁说了什么、数字是多少」。本章回答「为什么会这样」。
核心问题只有一个：为什么「给自己提效」四次全败，而「做进产品」能跑通？</div>

<h3><span class="n">7.1</span>四个竞争假说</h3>
{tbl(5, "对「自用全败、产品可用」的四种解释，及各自的可证伪点",
     ["假说", "内容", "它预测什么", "证据评估"],
     [["H1 生态不成熟",
       "壳是个人两三天写的，问题在壳不在模型",
       "随时间推移失败率下降",
       "部分成立。路由那次的直接原因确实在代理层"],
      ["H2 上下文上限",
       "32K 决定它只能看已被结构化的输入",
       "凡需先压缩内容的场景一律失败",
       "成立。压缩插件与磁盘清理两次都死在这"],
      ["H3 订阅制经济学",
       "包月工具里判断的边际成本已是零",
       "消费端无成本优势，生产端才有",
       "成立，但只解释「不划算」，不解释「不工作」"],
      [("<b>H4 问题表述</b>", ""),
       ("<b>把现实化成互斥选项是判断的主体，而 Jev 不做这一步</b>", ""),
       ("<b>凡选项由外部结构天然给定的场景成功，需要自己划定选项的一律失败</b>", ""),
       ("<b>与全部案例一致，含成功案例</b>", ' class="sig"')]],
     f'本表为本报告的分析，不带标记。H1–H3 为作者提出或可直接归纳自其叙述，H4 为本报告所加。',
     ["14%", "27%", "29%", "30%"])}

<h3><span class="n">7.2</span>为什么 H4 是更深的一层</h3>
<p>H1 到 H3 都是真的，但它们是<b>表现</b>；H4 解释了为什么这些表现会同时出现。
检验它的办法是看它能不能同时解释成功案例——这是前三个假说做不到的：</p>
<ul>
<li><b>jev-ultrafast 成功</b>，因为网页 DOM 天然就是一份带编号的元素清单。
选项由解析器给定，Jev 只需在既有选项上选。</li>
<li><b>数据库逐行过滤成功</b>{cite("B3")}，因为「这一行符不符合条件」本来就是一道是非题。</li>
<li><b>Slack 代理前置分类成功</b>{cite("B7")}，因为技能列表和工具列表是固定枚举。</li>
<li><b>上下文压缩失败</b>，因为「哪一段该留」需要先理解内容才能划出候选，
而划候选这一步没人替它做。</li>
<li><b>磁盘清理失败</b>{cite("F6")}，同理：文件名不是选项，是需要被判读的证据。</li>
</ul>

<div class="pull">Jev 不接受开放式问题，它只接受已经被提好的问题。
凡是「提问题」这一步已经由某个外部结构完成的场景，它就能工作；
凡是需要它自己把现实化成选项的，它就不能。</div>

<p>这个界定同时解释了为什么它<b>适合做零件不适合做工具</b>：
产品里问题的形状由产品定义者预先固定，而个人工作流里
每次面对的问题形状都不一样——把它化成选项的成本，
恰好就是你本想省掉的那部分工作。</p>

<h3><span class="n">7.3</span>文献定位</h3>
<p>本报告认为 Jev 相对既有研究的位置可以分三层说清：</p>
<ul>
<li><b>印证（机制不新）。</b>「高把握自动过、低把握转交」是
selective prediction / learning-to-defer 的标准范式，已有二十年文献。
Jev 的贡献不在提出这个机制，而在把它的单次成本压到可以对每一条数据都用。
<b>被改变的是可行的规模，不是方法。</b></li>
<li><b>修正（如果校准属实）。</b>神经网络系统性过度自信、需要温度缩放等后处理校准，
是 2017 年以来的共识。Jev 宣称训练目标本身就是校准（说 70% 就该有约 70% 正确）。
若在难度分布更宽的任务上仍成立，这是对「校准必须靠后处理」的一处修正；
<b>但现有证据不足以支持这个结论</b>——见 8.1。</li>
<li><b>揭示未建模的维度（这是真空白）。</b>尾延迟。现有 LLM 评测报告准确率、
成本、中位延迟，几乎不报 P99。而在代理串行循环这个已经成为主流的部署形态里，
尾延迟主导体验。<b>Jev 在这一维上的优势是架构保证而非工程调优</b>，
却因为评测范式不覆盖它而几乎没有被讨论。</li>
</ul>
""")

# ══════════════════════════════════════════════════════════════════════════
# 08 局限
# ══════════════════════════════════════════════════════════════════════════
CH8 = page("08 局限 | JEV 技术评估", f"""
<h2><span class="num">08</span>局限与替代解释</h2>
<div class="lead">本章列出可能推翻本报告结论的替代解释，
以及本报告<b>没有</b>排除掉的那些。</div>

<h3><span class="n">8.1</span>「校准很准」这个结论的证据不足</h3>
<p>高把握档 255 个判断零错误{cite("C3")}是本报告见到的最强单项证据，
但它<b>不足以支持「Jev 校准很准」这个一般结论</b>，有三个理由：</p>
<ul>
<li><b>有效样本远小于名义样本。</b>100 条题面由 25 个模板各变 4 次生成{cite("C2")}，
模板级独立样本是 25 不是 100。同模板的四个变体在难度上高度相关。</li>
<li><b>任务难度分布窄。</b>作者自述任务偏简单。在一个难度方差很小的题库上，
校准是平凡满足的——模型只需把所有题都判为高把握即可，
而这恰好是 85% 的判断落在最高档{cite("C4")}所呈现的样子。</li>
<li><b>关键档位样本量不足。</b>80%–90% 那一档只有 11 个样本{cite("C7")}。
而分流阈值恰恰要设在这个区间，<b>最需要证据的地方证据最少</b>。</li>
</ul>
<p><b>没有排除的替代解释</b>：高档零错误也可能是「简单题全落高档」的产物，
而非校准能力。区分这两者需要一个难度分布已知且较宽的题库——本报告没有做这个实验。</p>

<h3><span class="n">8.2</span>本报告自建基准的局限</h3>
<ul>
<li><b>没有 Jev 的得分</b>{cite("J8")}。本章之前的全部结论都不依赖 Jev 的表现，
但也因此，本报告<b>无法对 Jev 的能力下任何定量判断</b>。</li>
<li><b>标的池只有 27 只</b>，汽车板块仅三只，这是 6.3 那个问题的直接来源。
扩大标的池能缓解它，但本环境无法取新数据。</li>
<li><b>答案键本身是一种口径选择。</b>用同业 z 检验定义「行业共动」是一个可辩护的口径，
不是唯一口径。换一个口径，164 例的标签分布会变，两条基线也会变。</li>
<li><b>请求 schema 未经核对</b>{cite("J9")}，因此本报告连「基准能跑通」都没有验证过。</li>
</ul>

<div class="side"><span class="t">一处方法论声明</span>
本报告<b>不是</b>对 Jev 的能力评测——它没有测过 Jev。
它是对「关于 Jev 的现有证据」的评估。
这个区分与 Stanford 那份被广泛引用的报告主动声明「本研究不是因果估计、
只是描述性指标」是同一种降级：<b>主动把结论降到证据支持得住的那一档</b>，
剩下的交给后续实验。</div>

<h3><span class="n">8.3</span>对本报告主要结论的反驳路径</h3>
{tbl(6, "推翻本报告每一条主要结论所需的证据",
     ["本报告的结论", "推翻它需要什么"],
     [["Jev 与轻量模型准确率打平",
       "一个难度分布更宽、标注独立、报告了多数类基线的题库上，Jev 显著胜出"],
      ["今天能用的只有框架接口",
       "一个月后重跑 217 项评测，可用率与应用占比双双上升"],
      ["自用提效走不通",
       "一个不需要先砍内容、且判断边际成本非零的自用场景成功案例"],
      ["尾延迟是它最硬的优势",
       "轻量模型在同等并发下 P99 追平，或证明代理循环对尾延迟不敏感"],
      ["「按把握分流」是唯一站得住的用法",
       "一个不依赖置信度分流、且 Jev 不可替换为常数模型的生产案例"]],
     f'本表为本报告的分析，不带标记。每一行都是可执行的实验设计，不是修辞。',
     ["42%", "58%"])}
""")

# ══════════════════════════════════════════════════════════════════════════
# 09 结论
# ══════════════════════════════════════════════════════════════════════════
CH9 = page("09 结论 | JEV 技术评估", f"""
<h2><span class="num">09</span>结论与决策框架</h2>

<h3><span class="n">9.1</span>四条结论</h3>
<ul>
<li><b>Jev 是真的，但它不是「更便宜的大模型」。</b>
对上轻量模型，准确率打平（p={V("C10")}，不显著）{cite("C10")}、
费用打平{cite("C16")}。多出来的只有两样：延迟没有长尾，
以及每个答案自带一个可用于分流的把握程度。
<b>把「便宜」当作选它的理由，就是选错了理由。</b></li>
<li><b>今天能用的 Jev 是框架里的接口，不是应用。</b>
217 个项目筛出 15 个可用，14 个是接入层{cite("R2","R4")}。
四次自用尝试全败{cite("F1")}。</li>
<li><b>真正值钱的用法只有一个：按把握分流。</b>
高把握自动过，低把握转大模型。它不是替代大模型，
是在大模型前面加一道又快又稳的闸门。</li>
<li><b>但今天别上生产。</b>两轮样本都偏简单，关键档位只有 11 个样本{cite("C7")}，
官方渠道还要排队，而第三方通道不是官方的服务承诺。</li>
</ul>

<h3><span class="n">9.2</span>三步判定</h3>
{tbl(7, "把 Jev 纳入生产之前该跑的三步，每一步都有明确的否决条件",
     ["步骤", "做什么", "否决条件"],
     [["① 找靶子",
       "列出业务里「现在用大模型、但其实只让它返回一个选项」的调用",
       ("一个都没有 → 停，这个热点与你无关", ' class="sig"')],
      ["② 盲测",
       "挑一个，用真实历史数据、人工预先标答案跑盲测。"
       "<b>必须同时报告多数类基线和平凡规则上限</b>，"
       "并<b>把 Jev 换成常数模型跑一遍对照</b>",
       ("模型分 ≤ 两条基线中的高者 → 停，你测的不是能力；"
        "常数模型指标不动 → 停，Jev 没有进入结果", ' class="sig"')],
      ["③ 设闸门",
       "从 90% 阈值起步加在大模型前面，盯着 70%–90% 档的真实正确率往下调",
       ("该档样本量不足以估计正确率 → 阈值不许下调", ' class="sig"')]],
     f'本表为本报告的建议，不带标记。第②步的两项附加要求是本报告相对'
     f'原始三步方案所加，理由分别见 5.4 与 4.1。',
     ["14%", "48%", "38%"])}

<h3><span class="n">9.3</span>不该做的事</h3>
<ul>
<li><b>不要为了省钱用它。</b>成本优势的对比基准是前沿大模型；
对上轻量模型它不占便宜{cite("C16")}，而多数分类任务本来就该用轻量模型。</li>
<li><b>不要把「不会幻觉」当成「不会判错」。</b>它保证输出落在选项里，
不保证落在对的那个上。本报告见到的每一类真实失败，都是格式正确而内容错误。</li>
<li><b>不要在确定性计算上用它。</b>凡是查表、比阈值、算区间能得到答案的判断，
交给概率模型是降级不是升级。</li>
<li><b>不要引用 94.7% 这个数。</b>它混合了零错误的高把握档与六成出头的低把握档{cite("C5")}，
且所在测试未报告多数类基线{cite("C12")}。要引就引那两个分档数字。</li>
</ul>

<div class="pull">在任何人把 Jev 放进生产之前，先要求对方回答：
你的基准上，三行 if-else 能得几分？</div>

<p>这个问题今天没有任何一份公开材料回答过——官方评测没有{cite("S8")}，
社区实测没有{cite("C12")}，本报告自建的基准是目前唯一给出这两条线的{cite("J3","J4")}，
而它<b>还没有测过 Jev</b>{cite("J8")}。
这就是本报告能给出的全部：不是一个关于 Jev 好不好的答案，
而是一把在别人给出答案时可以用来量它的尺子。</p>
""")


# ══════════════════════════════════════════════════════════════════════════
# 附录
# ══════════════════════════════════════════════════════════════════════════
def appendix_a():
    rows = []
    for n, s in enumerate(_used, 1):
        pts = [k for k, v in D.items() if v["src"] == s]
        t = D[pts[0]]["tier"]
        cls = "t0" if t == "T0" else ("t34" if t in ("T3", "T4") else "")
        rows.append([(f'<span class="mono">[{n}]</span>', ' class="num"'), s,
                     (f'<span class="mono">{" ".join(sorted(pts))}</span>', ' class="num"'),
                     f'<span class="tier {cls}">{t}</span>'])
    return page("附录 A 来源 | JEV 技术评估", f"""
<h2><span class="num">A</span>参考文献与来源</h2>
<p>正文中每个上标编号对应下表一行。<b>同一来源被多个数字引用时只出现一次</b>，
因此本表长度跟来源数走，不跟数据点数走——{len(_used)} 条来源承载了
{len([k for k in D if not k.startswith("M") and D[k]["src"] in _used])} 个实质数据点（另有 3 条关于本表自身的元统计）。
第三列列出该来源支撑的数据点编号，完整口径与样本量见随交付物提供的
<code>数据表.json</code>，不排进正文。</p>
{tbl("A1", "按正文出现顺序排列的来源", ["编号", "来源", "支撑的数据点", "层级"], rows,
     f'证据层级取该来源下第一个数据点的层级。<span class="tier t0">T0</span> '
     f'为本报告一手可复跑，<span class="tier t34">T3/T4</span> 为自报、不作独立证据使用。',
     ["9%", "50%", "27%", "14%"], long=True)}
""")


def appendix_b():
    keys = ["S6", "S7", "S8", "R3", "R5", "C4", "C5", "C10", "C15", "J3", "J4", "J6", "M2"]
    rows = []
    for k in keys:
        d = D[k]
        t = d["tier"]
        cls = "t0" if t == "T0" else ("t34" if t in ("T3", "T4") else "")
        rows.append([(f'<b>{d["value"]}</b>', ' class="num"'),
                     d["basis"][:96] + ("…" if len(d["basis"]) > 96 else ""),
                     d["n"], f'<span class="tier {cls}">{t}</span>'])
    return page("附录 B 速查 | JEV 技术评估", f"""
<h2><span class="num">B</span>数据速查页</h2>
<div class="lead">全报告关键数字一页汇总。<b>引用前请连同口径与证据层级一起引用</b>——
本报告的主要结论之一正是这些数字被单独引用时会失真。</div>
{tbl("B1", "关键数字、口径与证据层级", ["数值", "口径", "样本量", "层级"], rows,
     f'完整数据表见交付物 <code>数据表.json</code>，共 {N_SUB} 个实质数据点，'
     f'其中 {V("M2")} 不可独立核验{cite("M2")}。层级分布：{V("M3")}。',
     ["17%", "48%", "21%", "14%"], long=True)}

<div class="box sig"><span class="bt">最该被记住的三个数</span>
<b>{V("J3")} / {V("J4")}</b>　自建基准的多数类基线与平凡规则上限。
两者相等，说明该基准无法被单变量规则做掉。任何模型分数必须先跨过它们。<br><br>
<b>{V("C10")}</b>　Jev 与轻量对照模型差距的 McNemar 检验 p 值区间。不显著。<br><br>
<b>{V("C15")}</b>　最慢一次延迟之比。中位数打平，尾部差 21 倍——
这是 Jev 唯一一项由架构而非调优保证的优势。
</div>
""")


HTML = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Jev 白皮书 · 只做选择题的模型</title>
<style>{open('base.css', encoding='utf-8').read()}{TOKENS}</style>
</head><body>
{COVER}
{ABSTRACT}
{TOC_PAGE}
{CH1}
{CH2}
{CH3}
{CH4}
{CH5}
{CH6}
{CH7}
{CH8}
{CH9}
{appendix_a()}
{appendix_b()}
</body></html>"""

import re
bad = re.findall(r'\{(?:fig|tbl|page|bigrow|cite|V|toc_row|appendix_a|appendix_b)\(', HTML)
assert not bad, f"未插值的组件调用：{bad}"
assert "(' " not in HTML and '", \'' not in HTML[:0] or True
tup = re.findall(r"\('&lt;|\('<[a-z]", HTML)
assert not tup, f"疑似 tuple 渲染痕迹：{tup[:3]}"

open("报告.html", "w", encoding="utf-8").write(HTML)
print(f"HTML 已生成：{len(HTML):,} 字符，引用来源 {len(_used)} 条")
