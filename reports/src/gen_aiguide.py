#!/usr/bin/env python3
"""reports/haidilao_ai_guide_Research_Report.html —— 客户提纲「海底捞调研 · AI 导购」，黄总本人受访答题准备（Merlin 模式 B）。
视角（用户 11/06 定）：架构与链路按产品方讲，体验与效果按商家方讲；第 7 题用公开行业案例，明说不是本人经历。"""
FONT = "font-family:'IM Fell English',Georgia,serif"
INK, PAPER, COPPER, GOLD, GREEN, RED, AMBER = "#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c", "#2a5c3f", "#8b2e2e", "#c47a1e"

SRC = {
    "jm": ("界面新闻：海底捞与火山引擎（小捞捞、RAG + 记忆、杨炫之访谈）", "https://www.jiemian.com/article/13556393.html"),
    "zh": ("中华网：把 AI「装」进火锅，海底捞牵手火山引擎", "https://m.tech.china.com/redian/2025/1030/102025_1756854.html"),
    "hz": ("杭州网：星语 AI 订餐员在海底捞上岗（2026-04-23）", "https://hznews.hangzhou.com.cn/jingji/content/2026-04/23/content_9210743_0.htm"),
    "yc": ("第一财经：阿里发布全新 AI 店小蜜（2026-05-11）", "https://www.yicai.com/news/103175075.html"),
    "pm1": ("人人都是产品经理：AI 智能客服落地实战——从需求调研到 ROI 评估（某电商平台，作者匿名）", "https://www.woshipm.com/ai/6232493.html"),
    "pm2": ("人人都是产品经理：AI 客服重复进线治理的 4 大底层逻辑（某金融业务线，脱敏）", "https://www.woshipm.com/ai/6378754.html"),
    "ss": ("少数派：用 Mac 打造智能化餐厅，海底捞的答案", "https://sspai.com/post/102160"),
}


def badge(level):
    c = {"高": GREEN, "中": AMBER, "低": RED}[level]
    return f'<span class="badge" style="border-color:{c};color:{c}">置信 {level}</span>'


def src(*keys):
    return '<span class="src">来源：' + "；".join(SRC[k][0].split("：")[0] for k in keys) + "</span>"


def box(can, cannot):
    return ('<div class="box"><div><b>可以说</b><ul>' + "".join(f"<li>{x}</li>" for x in can) + "</ul></div>"
            '<div><b>不能说</b><ul>' + "".join(f"<li>{x}</li>" for x in cannot) + "</ul></div></div>")


def flow_svg():
    steps = [("Orchestrator", "7 题分型"), ("Scout", "7 篇原文"), ("Analyst", "机制提炼"), ("Forensic", "口径与自述核查"),
             ("Strategist", "逐题作答"), ("Critic", "独立评审")]
    out = [f'<svg viewBox="0 0 660 110" style="{FONT};width:100%">']
    for i, (a, b) in enumerate(steps):
        x = 8 + i * 109
        out.append(f'<rect x="{x}" y="22" width="96" height="58" rx="6" fill="#fff" stroke="{COPPER}"/>')
        out.append(f'<text x="{x + 48}" y="46" text-anchor="middle" font-size="12" fill="{INK}">{a}</text>')
        out.append(f'<text x="{x + 48}" y="66" text-anchor="middle" font-size="11" fill="{COPPER}">{b}</text>')
        if i < len(steps) - 1:
            out.append(f'<path d="M{x + 98},51 l9,0" stroke="{GOLD}" stroke-width="2"/>')
    out.append(f'<text x="8" y="104" font-size="11" fill="{COPPER}">五智能体流程（Merlin 模式 B）——会话打不开的站点由 GitHub Actions 抓原文（scripts/fetch_pages.py）</text>')
    return "".join(out) + "</svg>"


def arch_svg():
    layers = [("渠道接入", "小程序 / 400 电话 / 平台 IM / 点餐 iPad"), ("理解", "意图 · 槽位 · 情绪 · 跨会话记忆"),
              ("决策编排", "规则护栏 + 模型路由（快路径 / 慢路径）"), ("知识与数据", "知识库 RAG · 菜单商品 · 会员权益 · 门店实时状态"),
              ("工具执行", "订位 · 排号 · 下单 · 改单 · 开票 · 退款（授权额度内）"), ("人工协同", "带摘要转人工 · 工作台 · 高值单促单建议"),
              ("运营评估", "看板预警 · 坏例标注 · A/B · 知识保鲜")]
    out = [f'<svg viewBox="0 0 660 {40 + 40 * len(layers)}" style="{FONT};width:100%">',
           f'<text x="8" y="18" font-size="11" fill="{COPPER}">AI 导购服务链路（自上而下为一次进线；运营评估层回灌上面每一层）</text>']
    for i, (n, d) in enumerate(layers):
        y = 30 + i * 40
        out.append(f'<rect x="8" y="{y}" width="130" height="32" fill="{COPPER}"/><text x="73" y="{y + 21}" text-anchor="middle" font-size="12" fill="{PAPER}">{n}</text>')
        out.append(f'<rect x="142" y="{y}" width="510" height="32" fill="#fff" stroke="{COPPER}"/><text x="152" y="{y + 21}" font-size="12" fill="{INK}">{d}</text>')
    return "".join(out) + "</svg>"


def metric_svg():
    rows = [("试点首月", "独立解决率", 60), ("迭代三个月", "独立解决率", 80), ("实施前", "满意度 CSAT", 70), ("全量后", "满意度 CSAT", 85)]
    out = [f'<svg viewBox="0 0 660 190" style="{FONT};width:100%">',
           f'<text x="8" y="16" font-size="11" fill="{COPPER}">公开行业案例（某电商平台，作者自述）：试点 → 迭代 → 全量的关键指标（%）</text>']
    for i, (stage, m, v) in enumerate(rows):
        y = 30 + i * 38
        out.append(f'<text x="8" y="{y + 18}" font-size="12" fill="{INK}">{m}｜{stage}</text>')
        out.append(f'<rect x="190" y="{y + 4}" width="{v * 4.2:.0f}" height="20" fill="{COPPER if i % 2 == 0 else GOLD}"/>')
        out.append(f'<text x="{196 + v * 4.2:.0f}" y="{y + 19}" font-size="12" fill="{GREEN}">{v}%{"+" if (stage, m) == ("全量后", "满意度 CSAT") else ""}</text>')
    return "".join(out) + "</svg>"


CSS = f"""
:root{{--ink:{INK};--paper:{PAPER};--copper:{COPPER};--gold:{GOLD}}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:'IM Fell English','Songti SC',Georgia,serif;line-height:1.75}}
.wrap{{max-width:880px;margin:0 auto;padding:24px 18px}} section{{margin:26px 0}}
.pub{{display:flex;justify-content:space-between;font-size:12px;border-bottom:1px solid var(--copper);padding-bottom:6px;color:var(--copper)}}
h1{{font-size:28px;margin:14px 0 2px}} .h1en{{font-style:italic;color:var(--copper)}}
.section-zh{{font-size:20px;font-weight:bold}} .section-en{{font-style:italic;color:var(--copper);font-size:13px;margin-bottom:8px}}
.label-zh{{font-weight:bold;color:var(--copper)}} .label-en{{font-style:italic;font-size:12px;color:#777;margin:0 6px}}
.ans{{background:#fff;padding:14px 16px;border-top:3px solid var(--gold)}} .lead{{font-size:17px;font-weight:bold}}
.badge{{font-size:11px;padding:0 6px;border:1px solid;margin-left:6px}} .src{{display:block;font-size:12px;color:#777;margin-top:6px}}
.box{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;font-size:13px}} .box>div{{background:{PAPER};padding:8px 10px;border-left:3px solid var(--copper)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td,th{{border-bottom:1px solid #d8d2c6;padding:6px;text-align:left;vertical-align:top}}
.verdict{{background:var(--ink);color:var(--paper);padding:18px}} .verdict-en{{opacity:.6;font-style:italic}}
.note{{font-size:13px;background:#fff;padding:12px;border-left:3px solid var(--copper)}} footer{{font-size:12px;color:#777;border-top:1px solid var(--copper);padding-top:8px}}
@media(max-width:640px){{.box{{grid-template-columns:1fr}}}}
"""


def q(n, zh, en, lead, body, level, keys, can, cannot):
    return (f'<section><div class="section-zh">Q{n} · {zh}</div><div class="section-en">{en}</div><div class="ans">'
            f'<p class="lead">{lead}{badge(level)}</p>{body}{src(*keys)}{box(can, cannot)}</div></section>')


def build():
    P = []
    P.append('<section><div class="pub"><span>Merlin · 客户提纲研究 · 受访答题准备</span><span>2026-11-06 · 仅公开口径</span></div>'
             '<h1>海底捞调研 · 商家 AI 导购：七问答题准备</h1><div class="h1en">Merchant AI Shopping Guide — Interview Prep, 7 Questions</div></section>')
    P.append('<section><div class="section-zh">一页结论</div><div class="section-en">Bottom Line</div><div class="ans">'
             '<p class="lead">AI 导购和传统客服的根本区别，是考核从「答了多少」变成「解决了多少、成交了多少」——它能主动问、记得住、还能直接办事。</p>'
             '<p><span class="label-zh">三句话主线</span><span class="label-en">Storyline</span>'
             '① 区别不在会不会聊天，在于有没有记忆、有没有办事权限（海底捞「小捞捞」用 RAG + 记忆解决「每换一个服务员都要重说一遍需求」）；'
             '② 平衡三方收益的办法是排序而不是折中：体验底线 → 商家授权边界内的收益 → 平台转化；'
             '③「问题真正解决」要看行为证据——同一诉求 48 小时内不再进线、业务状态真的改变（订位核销、退款到账），满意度邀评只作辅助。</p>'
             '<p><span class="label-zh">开场口径</span><span class="label-en">Opening</span>「我讲的都是公开信息和行业通行做法，加上我做门店运营的经验判断；海底捞、绿茶的内部数据和合作细节我不展开。」</p></div></section>')
    P.append('<section><div class="section-zh">研究流程</div><div class="section-en">Five-Agent Workflow</div>' + flow_svg() + '</section>')

    P.append(q(1, "AI 导购与传统客服 / 人工导购的最大区别", "AI Guide vs. Traditional Service",
               "最大区别是目标函数变了：传统客服按接单量考核、只求答完；人工导购会主动推荐但规模化不了；AI 导购同时做到主动、可规模化、能办事，考核对象变成「解决率 + 转化率」。",
               '<p><span class="label-zh">三个可观测差异</span><span class="label-en">Evidence</span>'
               '① 会反问澄清：星语 AI 热线客服（海底捞 AI 订餐员的供应商）遇到「有单人的锅吗」，会反问是一个人用餐还是要一人一锅，刚培训完的人工客服未必反应得过来；同一家的 AI 订餐员在海底捞接订位电话，能答生日布置、最低消费、蛋糕寄存，并完成查询、下单、通知门店（杭州网）；'
               '② 记得住：老顾客反馈每次换服务员都要重复需求，海底捞的应对是让「小捞捞」带记忆、用 RAG 调取历史（界面新闻，杨炫之）；'
               '③ 有手有脚：阿里把新版店小蜜定位为「具备售前售后办事能力的客服 agent」，能直接改地址、退差价（第一财经）。</p>'
               '<p><span class="label-zh">我的判断</span><span class="label-en">My Take</span>餐饮场景里最值钱的不是「回答」，是「把需求记下来并传到门店」——订位时的生日布置、安静角落，过去靠人工备注——海底捞店长侯永平公开说过，这些需求备注「难免会有遗漏」（界面新闻）。</p>',
               "高", ("hz", "jm", "yc"),
               ["行业公开案例（海底捞小捞捞、AI 订餐员、店小蜜）", "海底捞店长侯永平的公开原话：订位个性化需求靠备注「难免会有遗漏」"],
               ["海底捞 / 绿茶内部客服量、人效、成本数据", "绿茶当前在评估或签约的 AI 供应商"]))

    P.append(q(2, "如何平衡用户体验、商家收益和平台转化", "Balancing UX, Merchant Revenue, Platform Conversion",
               "按优先级排序而不是平均用力：先守体验底线，再在商家授权的边界内争收益，平台转化是前两者做好之后的结果。",
               '<p><span class="label-zh">底线</span><span class="label-en">Floor</span>不推与需求无关的东西、营销内容标清楚、同一用户有推送频控；过敏、未成年、酒类这类约束优先于任何主推。</p>'
               '<p><span class="label-zh">商家边界</span><span class="label-en">Merchant Guardrails</span>收益动作必须有授权额度：店小蜜的赔付「严格控制在商家授权额度内」，挽单只给换尺码、换款、补发这类可替代方案，测试商家退款挽单成功率超过 20%（第一财经，阿里自述）。</p>'
               '<p><span class="label-zh">反直觉的一招</span><span class="label-en">Counter-intuitive</span>海底捞的账单问答会主动教顾客怎么组合用券最省、哪些权益快到期——短期少收一点，换的是信任和复购（界面新闻）。</p>'
               '<p><span class="label-zh">平台转化</span><span class="label-en">Platform</span>高值订单不全交给 AI：店小蜜对高值单给人工提供决策信息和促单建议，「AI + 人」询单转化全时段超过纯人工（第一财经，阿里自述）。</p>',
               "中", ("yc", "jm"),
               ["排序框架：体验底线 → 授权边界内的商家收益 → 平台转化", "用券最优解这类「替顾客省钱」的设计能换信任"],
               ["海底捞在美团 / 抖音的具体费率、补贴、流量协议", "任何门店级客单、毛利数字"]))

    P.append(q(3, "整体产品架构与服务链路", "Architecture & Service Chain",
               "七层链路：渠道接入 → 理解 → 决策编排 → 知识与数据 → 工具执行 → 人工协同 → 运营评估，最后一层持续回灌前六层。",
               arch_svg() +
               '<p><span class="label-zh">海底捞的对应</span><span class="label-en">Haidilao Mapping</span>渠道覆盖小程序订位排号、账单页问答、点餐 iPad 推荐、400 电话；底座是火山引擎 HiAgent 智能体工作站 + 豆包大模型，会员与营销数据经 VeCDP / DataFinder 整合，营销动作用 DataTester 做 A/B（界面新闻、中华网）。</p>'
               '<p><span class="label-zh">设计要点</span><span class="label-en">Design Points</span>决策编排层必须独立于模型：规则管「不能做什么」（授权、合规、敏感场景直转人工），模型管「怎么说、怎么理解」。</p>',
               "中", ("jm", "zh", "hz"),
               ["七层链路框架与各层职责", "海底捞公开披露的合作方与产品名（HiAgent、豆包、VeCDP 等）"],
               ["海底捞系统内部架构细节、接口与数据表结构", "供应商合同、报价、上线排期"]))

    P.append(q(4, "AI 导购推荐时应基于哪些信息", "Signals for Recommendation",
               "五类信息按可信度排序：用户当下的明确诉求 > 实时上下文 > 历史与会员 > 商家经营规则 > 平台规则与合规约束（合规是一票否决，排最后不代表权重最低）。",
               '<table><tr><th>信息</th><th>餐饮里的例子</th></tr>'
               '<tr><td>当下诉求</td><td>人数、场合（生日、带娃、健身）、口味与忌口</td></tr>'
               '<tr><td>实时上下文</td><td>位置、到店时间、附近门店排队与空台、缺货沽清</td></tr>'
               '<tr><td>历史与会员</td><td>常点锅底与菜品、可用券与快到期权益（海底捞会员超 2 亿，2025 年中报口径）</td></tr>'
               '<tr><td>商家经营规则</td><td>主推新品、套餐、库存与出品能力（高峰期少推慢出品菜）</td></tr>'
               '<tr><td>平台与合规</td><td>过敏原、酒类与未成年、营销标识、价格承诺</td></tr></table>'
               '<p><span class="label-zh">公开例子</span><span class="label-en">Example</span>选「健身」推低脂高蛋白、带小孩推儿童餐；登录后点餐 iPad 直接弹出历史偏好菜品（界面新闻，海底捞店长侯永平、杨炫之）。</p>',
               "中", ("jm",),
               ["五类信息框架与排序逻辑", "海底捞公开的推荐场景（健身、儿童、历史偏好）"],
               ["海底捞推荐算法的特征、权重与效果数据", "会员分层与圈选规则"]))

    P.append(q(5, "从开通配置到转人工的完整流程与分工", "End-to-End Flow & Responsibilities",
               "一条主干、两条快慢路径：开通配置 → 进线 → 诉求识别 → 多轮处理 → 业务执行 → 转人工；简单诉求走知识库快路径秒级回答，复杂诉求走模型加工具编排的慢路径，任何一步失败都有降级和人工兜底。",
               '<p><span class="label-zh">流程</span><span class="label-en">Flow</span>'
               '① 开通配置：商家导入菜单 / 商品、门店信息、活动与券规则，设定授权额度（可赔多少、可改什么）与转人工规则；'
               '② 进线：小程序、电话、平台 IM 统一身份，带上会员与历史订单；'
               '③ 诉求识别：意图 + 槽位 + 情绪，含糊就反问（星语的「单人锅」例）；'
               '④ 多轮处理：跨会话记忆，第二次进线不重复上一次的话术，直接下钻到卡点（金融热线案例的「首次预判—二次下钻—三次收敛」）；'
               '⑤ 业务执行：调用订位、排号、下单、改单、开票、退款等工具，先校验授权再执行，执行结果回写并通知门店；'
               '⑥ 转人工：带上诉求、已尝试步骤和用户情绪交接，人工不必让用户重说一遍。</p>'
               '<p><span class="label-zh">复杂诉求走一遍</span><span class="label-en">Complex Case</span>顾客在小程序投诉「上错菜还多收了钱」：模型识别为投诉 + 退款、情绪偏高 → 规则判定属「必须留痕」意图 → 工具查该桌订单与出品记录、核对差额 → 在商家授权额度内直接退差价并补一张券 → 同步门店当班经理工单 → 情绪仍高或超出额度时，带完整摘要转人工回电。这是我的设计，不是海底捞的实际流程。</p>'
               '<table><tr><th>组件</th><th>职责</th></tr>'
               '<tr><td>模型</td><td>理解与表达：意图、澄清、话术、情绪安抚</td></tr>'
               '<tr><td>规则</td><td>护栏与路由：授权额度、合规禁区、哪些意图必须直转人工</td></tr>'
               '<tr><td>知识库</td><td>事实来源：菜单、门店、活动、售后政策，定期保鲜防过期答案</td></tr>'
               '<tr><td>工具</td><td>办事：查询与写入业务系统，保证可重试、不重复下单</td></tr>'
               '<tr><td>业务方案</td><td>把一类诉求的最优解设计好（如挽单只给可替代方案），模型照方案执行</td></tr></table>'
               '<p><span class="label-zh">时延与异常</span><span class="label-en">Latency &amp; Exceptions</span>语音场景一秒的延迟就会让人出戏（星语 CTO 赵俊）：流式输出、先说确认语再并行查系统；工具超时先重试一次，再降级为「已登记，X 分钟内回电」，最后人工兜底。'
               '金融热线案例里，按「N 次来电直转人工」兜底规则转进来的通话占全部重复来电的 40%，其中不少是查余额这类 AI 能解决的请求（「24 小时内打 4 次直转人工」是作者举的典型做法）——转人工规则要按意图分白名单 / 黑名单，而不是按次数。</p>',
               "中", ("hz", "pm2", "pm1", "yc"),
               ["六步流程与五个组件的职责划分", "快慢路径、降级与人工兜底设计", "公开案例：转人工规则按意图而不是按次数"],
               ["海底捞 / 绿茶的转人工率、时延、工单量等运营数据", "具体系统名与对接方式之外的内部实现"]))

    P.append(q(6, "如何衡量效果并形成持续优化闭环", "Metrics & Optimization Loop",
               "用四层指标树衡量，用「看板预警 → 坏例标注 → 归因 → 迭代 → A/B → 上线」六步形成闭环；只看满意度会被选择性偏差骗。",
               '<table><tr><th>层</th><th>指标</th></tr>'
               '<tr><td>体验</td><td>首响时长、整体时长、满意度（邀评）</td></tr>'
               '<tr><td>解决</td><td>独立解决率、转人工率、48 小时同诉求再进线率、工单重开率</td></tr>'
               '<tr><td>业务</td><td>询单转化率、订位到店核销率、客单与券核销、挽单率</td></tr>'
               '<tr><td>成本</td><td>人工替代量、单次服务成本</td></tr></table>'
               '<p><span class="label-zh">闭环怎么转</span><span class="label-en">Loop</span>人工客服在工作台的反馈入口标记 AI 的「精彩表现 / 翻车现场」，配合定期用户回访，是迭代的主要燃料；指标设预警阈值，解决率骤降时运营和技术当天排查（电商平台案例）。海底捞营销侧已用 DataTester 做 A/B 验证（界面新闻）。</p>',
               "中", ("pm1", "jm"),
               ["四层指标树与六步闭环", "满意度邀评有选择性偏差：不满意的人往往不评"],
               ["海底捞 / 绿茶实际的指标数值与目标值"]))

    P.append(q(7, "「问题真正解决」如何判定：一次完整优化（公开行业案例）", "Defining True Resolution — A Public Case",
               "「真正解决」= 三个行为证据同时成立：同一诉求 48 小时内没有再进线、没有转人工或投诉、诉求对应的业务状态真的改变（订位核销、退款到账、改单完成）；邀评满意度只作辅助。",
               '<p><span class="label-zh">先声明</span><span class="label-en">Disclosure</span>下面是公开的行业案例，不是我本人经历；我会讲它的方法，再讲换到餐饮我会怎么做。</p>'
               '<p><span class="label-zh">问题发现</span><span class="label-en">Discovery</span>某电商平台调半年工单：近 80% 咨询集中在不到 10 类基础问题，高峰平均响应 5 分钟，超过 30% 的用户等 3 分钟后放弃（人人都是产品经理，作者匿名）。</p>'
               '<p><span class="label-zh">诊断归因</span><span class="label-en">Diagnosis</span>不只看报表，产品、技术、客服运营和一线组长组成混编小组去客服中心「蹲点」，访谈 + 工单 + 用户问卷三路印证。'
               '另一个金融热线案例的归因更典型：单月 3,000 多名客户打了 2 万通电话，按「N 次来电直转人工」兜底规则转进来的通话占重复来电的 40%，其中不少是查余额、查明细这类 AI 本可解决的请求——一部分问题出在规则，不在模型。</p>'
               '<p><span class="label-zh">团队分工</span><span class="label-en">Roles</span>原文：产品、技术、客服运营骨干和一线客服组长组成混编小组；金牌客服做「AI 教练」，参与数据清洗、标注和话术优化。我的拆法：产品定场景与转人工策略，算法做意图识别与多轮，客服运营管知识库保鲜。</p>'
               '<p><span class="label-zh">上线验证</span><span class="label-en">Validation</span>先选 3C 数码和日用品两个标准化品类试点，「AI 优先、解决不了无缝转人工」；首月独立解决约 60%、响应从 5 分钟降到 15 秒内，迭代三个月升到约 80%，再全量推广。</p>'
               + metric_svg() +
               '<p><span class="label-zh">收益评估</span><span class="label-en">ROI</span>作者自述：会话后购买转化约 +15%，承担约 75% 重复咨询，年省人力约 300 万元，满意度从约 70% 升到 85% 以上，首个完整年度 ROI 超过 150%（未经审计）。</p>'
               '<p><span class="label-zh">换到餐饮我会怎么做</span><span class="label-en">My Version</span>以订位为例：「真正解决」看订位成功且顾客按时到店核销、备注的生日布置在门店工单里出现；48 小时内为同一订单再来电算未解决。优化先找再进线最多的诉求，按「规则问题 / 知识缺失 / 模型理解 / 工具失败」四类归因，再分给对应的人。</p>',
               "中", ("pm1", "pm2"),
               ["「真正解决」的三条行为证据判定", "公开案例的完整过程（明确说明是行业案例）", "餐饮订位场景的判定与归因思路"],
               ["把公开案例说成自己的经历", "海底捞 / 绿茶的任何优化项目、团队与收益数据"]))

    P.append('<section><div class="section-zh">风险信号</div><div class="section-en">Risk Signals</div><table>'
             '<tr><th>信号</th><th>为什么要小心</th></tr>'
             '<tr><td>店小蜜转人工率 −45%、转化 +10%、挽单 20%</td><td>阿里自述测试数据，样本与口径未公开；引用时说「阿里公布」</td></tr>'
             '<tr><td>电商案例 ROI 150%、年省 300 万</td><td>匿名作者自述、未审计；只讲方法，数字点到为止</td></tr>'
             '<tr><td>星语「意图识别与执行完成率 99.9%」</td><td>供应商宣传口径，未独立核实；本报告未采用</td></tr>'
             '<tr><td>对方追问海底捞 / 绿茶具体数字</td><td>按开场口径回到公开信息与方法论</td></tr></table></section>')
    P.append('<section><div class="verdict"><b>评审裁定：</b>综合置信 7 / 10 · 高 1 / 中 6 / 低 0。七题答案均以结论开头，第 7 题明确为公开行业案例；事实均对照原文核过，数字为来源方自述口径。'
             '<div class="verdict-en">Interview prep for an AI shopping-guide discussion; public sources only.</div>'
             '<div style="margin-top:6px;font-size:12px">反馈：<a style="color:#c9a84c" href="https://spontaneous-youtiao-b9cde9.netlify.app?product=merlin&report=haidilao_ai_guide">https://spontaneous-youtiao-b9cde9.netlify.app?product=merlin&report=haidilao_ai_guide</a></div></div></section>')
    P.append('<section><div class="note"><div class="section-zh">分析师附注</div><div class="section-en">Analyst\'s Note</div>'
             '<p>来源性质：海底捞相关事实来自界面新闻、中华网（火山引擎合作报道，含海底捞信息科技部杨炫之、店长侯永平原话）与杭州网（供应商星语创始人访谈），均属合作方宣传语境；店小蜜数据为阿里自述；第 7 题两个案例来自人人都是产品经理，作者匿名、数据脱敏。</p>'
             '<p>获取方式：上述站点不在会话网络白名单内，原文由 GitHub Actions 抓取（scripts/fetch_pages.py，pages/ 目录）；北京商报一篇 403 未取得，其内容与第一财经重合。美团技术团队未找到公开的智能客服实践文章，未引用。</p>'
             '<p>置信度总表：Q1 高（三个差异均有原话）；Q2–Q7 中（Q4 的例子有海底捞原话，排序框架是分析师判断；其余为行业通行做法 + 分析师判断，数字为自述口径）。</p>'
             '<p>合规：本报告不使用海底捞、绿茶任何未公开经营数据；「48 小时」是我设的观察窗，金融案例里举的是 24 小时，应按业务周期定（订位类看到店核销日），不是任何公司的内部标准。</p>'
             '<div class="section-zh" style="font-size:16px;margin-top:10px">来源索引</div><div class="section-en">Sources</div><ol>'
             + "".join(f'<li>{n}：<a href="{u}">{u}</a></li>' for n, u in SRC.values()) + '</ol></div>'
             '<footer>Merlin · 仅供受访准备使用 · 2026-11-06</footer></section>')
    return ('<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>海底捞调研 · AI 导购答题准备</title><style>{CSS}</style></head><body><div class="wrap">' + "".join(P) + "</div></body></html>")


if __name__ == "__main__":
    import sys
    open(sys.argv[1], "w", encoding="utf-8").write(build())
