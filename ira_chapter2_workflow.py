"""
IRA (Industry Research Agent) — 第二章自动化工作流
Chapter 2: 品类本质分析

用法:
    python3 ira_chapter2_workflow.py input.json
    python3 ira_chapter2_workflow.py input.json --output my_report.md

输入 JSON 格式:
    {
        "category": "火锅",
        "core_target": "海底捞 6862.HK",
        "research_depth": "标准版",
        "user_focus": "二级市场"
    }
"""

import json
import sys
import os
import argparse
from pathlib import Path
import anthropic

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

MODEL_ANALYSIS = "claude-opus-4-7"   # 主要分析任务
MODEL_WRITING = "claude-opus-4-7"    # 写作整合任务

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# AI腔黑名单（Doc 4 原文）
AI_BLACKLIST = [
    "值得注意的是", "不可否认", "毋庸置疑", "显而易见",
    "综上所述", "总的来说", "不难发现", "由此可见",
    "与此同时", "在此基础上", "从某种意义上说",
    "深度赋能", "闭环", "生态", "赋能", "底层逻辑",
    "顶层设计", "护城河（作为buzzword）", "内卷", "躺平",
    "破圈", "出圈", "降维打击", "降本增效", "弯道超车",
]

# ---------------------------------------------------------------------------
# Sub-task 1: 四象限定位
# ---------------------------------------------------------------------------

SYSTEM_QUADRANT = """你是一名资深消费行业研究员，擅长品类战略分析。

【任务】：完成品类四象限定位分析，输出结构化 JSON。

【四象限定义】
- X轴：消费频次（高频 ≥ 每月2次 / 低频 < 每月2次）
- Y轴：客单价（高客单 ≥ 200元 / 低客单 < 200元）

四个象限：
1. 高频低价（刚需日常）：便利店、快餐、早餐
2. 高频高价（习惯型享受）：星巴克、健身、轻奢餐厅
3. 低频低价（冲动偶发）：小吃、零食、街边摊
4. 低频高价（仪式型消费）：火锅、精品餐厅、节庆消费

【输出格式】严格 JSON，不含 markdown 代码块：
{
  "quadrant": "低频高价",
  "quadrant_label": "仪式型消费",
  "frequency_per_month": "1-2次",
  "avg_spend_rmb": 150,
  "frequency_data_source": "行业估算",
  "peer_brands": ["呷哺呷哺", "捞王", "巴奴"],
  "positioning_implication": "品类天花板受限于消费频次，需靠客单价和坪效驱动，复购依赖情感价值而非便利性",
  "investment_implication": "估值应更多参考翻台率与同店销售而非纯粹扩张速度",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""

def run_quadrant_analysis(category: str, core_target: str, user_focus: str) -> dict:
    print(f"  [1/4] 四象限定位分析...")
    resp = client.messages.create(
        model=MODEL_ANALYSIS,
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_QUADRANT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""品类：{category}
核心标的：{core_target}
研究视角：{user_focus}

请基于以上信息，完成四象限定位分析，严格输出 JSON。""",
            }
        ],
    )
    return _parse_json_response(resp)


# ---------------------------------------------------------------------------
# Sub-task 2: 场景拆解
# ---------------------------------------------------------------------------

SYSTEM_SCENARIOS = """你是一名消费行业研究员，专注于消费场景与用户行为分析。

【任务】：识别品类的核心消费场景，输出结构化 JSON。

【分析框架】
每个场景需包含：
- 场景名称（4-6字）
- 触发动机（为什么这时候消费这个品类）
- 人群画像
- 平均客单价
- 对品类营收的贡献权重估算（%）
- 该场景下，头部品牌的竞争优势来自哪里

【输出格式】严格 JSON，不含 markdown 代码块：
{
  "total_scenarios": 5,
  "scenarios": [
    {
      "id": 1,
      "name": "聚会社交",
      "trigger": "朋友/家人聚会，需要"够热闹、够有仪式感"的餐厅",
      "target_group": "25-45岁城市中产，2-8人团体",
      "avg_spend_rmb": 160,
      "revenue_weight_pct": 40,
      "competitive_advantage": "大桌位设计、热闹氛围、等位文化形成社交谈资",
      "brand_examples": ["海底捞", "呷哺呷哺大店"]
    }
  ],
  "dominant_scenario": "聚会社交",
  "scenario_insight": "火锅品类本质上是社交货币，口味标准化让消费者注意力转移到"氛围体验"",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""

def run_scenario_analysis(category: str, core_target: str, quadrant_result: dict) -> dict:
    print(f"  [2/4] 消费场景拆解...")
    positioning_context = quadrant_result.get("positioning_implication", "")
    resp = client.messages.create(
        model=MODEL_ANALYSIS,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_SCENARIOS,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""品类：{category}
核心标的：{core_target}
四象限定位：{quadrant_result.get('quadrant_label', '')}（{quadrant_result.get('quadrant', '')}）
定位含义：{positioning_context}

请识别该品类的5-7个核心消费场景，按营收贡献权重从高到低排列，严格输出 JSON。""",
            }
        ],
    )
    return _parse_json_response(resp)


# ---------------------------------------------------------------------------
# Sub-task 3: 生命周期判断
# ---------------------------------------------------------------------------

SYSTEM_LIFECYCLE = """你是一名消费行业研究员，专注于行业生命周期与投资时机判断。

【任务】：判断品类所处生命周期阶段，给出估值含义。

【生命周期阶段】
1. 导入期：品类尚未普及，教育市场为主，增速不稳定
2. 成长期：快速扩张，竞争加剧，规模效应显现，给高PE
3. 成熟期：增速放缓，竞争格局固化，拼效率和品牌，给EV/EBITDA
4. 震荡期：格局未定，跑马圈地，优胜劣汰
5. 衰退期：需求萎缩，存量博弈

【五个判断指标】
1. 渗透率：与可比市场对比
2. 同店销售增长：是否由负转正/持续正增长
3. 新品牌涌现速度：是否在加速/减速
4. 价格带竞争：是否出现价格战
5. 消费频次趋势：疫后是否恢复/超越前值

【输出格式】严格 JSON，不含 markdown 代码块：
{
  "lifecycle_stage": "成熟期",
  "stage_confidence": "高",
  "indicators": {
    "penetration_rate": "中国火锅门店约50万家，渗透率高，增速放缓至个位数",
    "sssg_trend": "头部品牌同店销售2023年后逐步恢复，但尚未回到2019年峰值",
    "new_brand_velocity": "新品牌涌现放缓，区域品牌整合加速",
    "price_competition": "出现明显价格带下沉竞争（捞王、珮姐等中端扩张）",
    "frequency_recovery": "疫后翻台率恢复至2019年约80-90%水平"
  },
  "valuation_implication": "成熟期品类应以EV/EBITDA或P/FCF估值，PE估值需折价处理；重点关注坪效和翻台率改善空间",
  "key_risk": "若同店继续下滑，将进入衰退期，估值中枢将下移",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""

def run_lifecycle_analysis(category: str, core_target: str, scenario_result: dict) -> dict:
    print(f"  [3/4] 生命周期判断...")
    dominant_scenario = scenario_result.get("dominant_scenario", "")
    scenario_insight = scenario_result.get("scenario_insight", "")
    resp = client.messages.create(
        model=MODEL_ANALYSIS,
        max_tokens=1800,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_LIFECYCLE,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""品类：{category}
核心标的：{core_target}
主要消费场景：{dominant_scenario}
场景洞察：{scenario_insight}

请判断该品类当前所处的生命周期阶段，给出具体指标支撑和估值含义，严格输出 JSON。""",
            }
        ],
    )
    return _parse_json_response(resp)


# ---------------------------------------------------------------------------
# Sub-task 4: 破局点识别
# ---------------------------------------------------------------------------

SYSTEM_BREAKTHROUGH = """你是一名消费行业研究员，专注于竞争战略与品类创新分析。

【任务】：识别品类历史破局点，以及下一个潜在破局点。

【破局点定义】
破局点是指：能够打破现有竞争格局、创造新价值曲线、实现差异化胜出的关键维度。
不是"做得更好"，而是"维度创新"。

【历史破局点分类】
- 产品维度：食材/味型/健康化
- 体验维度：服务/环境/等位文化
- 效率维度：SKU精简/供应链/翻台
- 人群维度：下沉/细分/Z世代
- 场景维度：外卖/零售化/预制菜

【输出格式】严格 JSON，不含 markdown 代码块：
{
  "historical_breakthroughs": [
    {
      "year_approx": "2011-2016",
      "dimension": "体验维度",
      "description": "海底捞将"变态服务"作为核心差异点，重新定义火锅服务标准",
      "winner": "海底捞",
      "impact": "服务溢价支撑高翻台率，推动全国扩张"
    },
    {
      "year_approx": "2018-2022",
      "dimension": "产品维度",
      "description": "巴奴以"毛肚和菌汤"切入，打"产品主义"对抗服务主义",
      "winner": "巴奴",
      "impact": "成功在一二线城市建立高端定位，对海底捞形成上压"
    }
  ],
  "next_breakthrough_candidates": [
    {
      "dimension": "健康化/食材透明",
      "hypothesis": "消费者对食材来源和添加剂关注度上升，有机/可溯源食材或成新差异点",
      "probability": "中",
      "beneficiary": "有供应链能力的头部品牌"
    },
    {
      "dimension": "零售化/预制菜",
      "hypothesis": "堂食天花板下，品牌延伸至家庭消费场景，用品牌溢价卖预制底料",
      "probability": "高",
      "beneficiary": "海底捞（已布局）、巴奴"
    }
  ],
  "core_target_position": "海底捞在历史破局点上均有布局，但当前面临服务差异化被模仿、产品侧被巴奴追赶的双重压力",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""

def run_breakthrough_analysis(
    category: str,
    core_target: str,
    lifecycle_result: dict,
    scenario_result: dict,
) -> dict:
    print(f"  [4/4] 破局点识别...")
    lifecycle_stage = lifecycle_result.get("lifecycle_stage", "")
    key_risk = lifecycle_result.get("key_risk", "")
    resp = client.messages.create(
        model=MODEL_ANALYSIS,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_BREAKTHROUGH,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""品类：{category}
核心标的：{core_target}
生命周期阶段：{lifecycle_stage}
主要风险：{key_risk}

请识别该品类的历史破局点（至少2个），以及下一个潜在破局点候选（至少2个），并说明核心标的的当前定位。严格输出 JSON。""",
            }
        ],
    )
    return _parse_json_response(resp)


# ---------------------------------------------------------------------------
# 整合校验 + 写作Agent
# ---------------------------------------------------------------------------

SYSTEM_INTEGRATION = """你是一名资深卖方研究员，擅长将结构化分析数据转化为专业研报文字。

【任务】：整合四个子分析结果，撰写第二章「品类本质」完整正文。

【写作要求】
1. 文风：卖方研报体，客观专业，有论据支撑
2. 结构：按四个子任务顺序展开，共4个小节
3. 数据：引用子分析中的具体数据，不凭空编造
4. 投资视角：每节结尾给出"投资含义"1-2句
5. 长度：每小节400-600字，总计1600-2400字

【禁止使用词汇（AI腔黑名单）】
以下词汇一律禁用，一经出现即重写：
""" + "、".join(AI_BLACKLIST) + """

【输出格式】
直接输出 Markdown 正文，从 ## 2.1 开始，不含 JSON，不含代码块。

【一致性校验】
在写作前，内部核查：
- 四象限定位与生命周期判断是否自洽？
- 主要消费场景与破局点方向是否连贯？
- 如有矛盾，取证据更强的一侧，或在文中注明存在争议。"""

def run_integration_writing(
    category: str,
    core_target: str,
    research_depth: str,
    user_focus: str,
    quadrant: dict,
    scenarios: dict,
    lifecycle: dict,
    breakthrough: dict,
) -> str:
    print(f"  [整合] 写作整合Agent...")

    analysis_bundle = {
        "四象限定位": quadrant,
        "消费场景拆解": scenarios,
        "生命周期判断": lifecycle,
        "破局点识别": breakthrough,
    }

    resp = client.messages.create(
        model=MODEL_WRITING,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_INTEGRATION,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""研究标的：{core_target}（品类：{category}）
研究深度：{research_depth}
读者视角：{user_focus}

以下是四个子分析的结构化结果（JSON），请据此撰写第二章正文：

{json.dumps(analysis_bundle, ensure_ascii=False, indent=2)}

请直接输出 Markdown，从"## 2.1 品类四象限定位"开始。""",
            }
        ],
    )

    for block in resp.content:
        if block.type == "text":
            return block.text
    return ""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _parse_json_response(resp) -> dict:
    for block in resp.content:
        if block.type == "text":
            text = block.text.strip()
            # 去除可能的 markdown 代码块
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # 尝试找第一个 { 到最后一个 }
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        return json.loads(text[start:end])
                    except json.JSONDecodeError:
                        pass
                print(f"  [警告] JSON解析失败，返回原始文本")
                return {"raw_text": text, "parse_error": True}
    return {"error": "no text block in response"}


def save_intermediate(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 中间结果已保存: {path}")


def build_chapter2_markdown(
    category: str,
    core_target: str,
    chapter_body: str,
    all_results: dict,
) -> str:
    header = f"""# 第二章　品类本质

> **研究标的**：{core_target}　｜　**品类**：{category}
> **生成方式**：IRA 自动化工作流 v0.1

---

"""
    calibration_warnings = []
    for key, result in all_results.items():
        if isinstance(result, dict) and result.get("need_human_calibration"):
            calibration_warnings.append(f"- **{key}**：{result.get('calibration_reason', '需人工核查')}")

    if calibration_warnings:
        warning_block = "\n> ⚠️ **人工核查提示**\n>\n" + "\n".join(f"> {w}" for w in calibration_warnings) + "\n\n"
    else:
        warning_block = ""

    return header + warning_block + chapter_body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第二章自动化工作流")
    parser.add_argument("input", help="输入 JSON 文件路径")
    parser.add_argument("--output", default="output_chapter2.md", help="输出 Markdown 文件路径")
    parser.add_argument("--intermediates-dir", default="intermediates", help="中间结果保存目录")
    args = parser.parse_args()

    # 读取输入
    with open(args.input, "r", encoding="utf-8") as f:
        inp = json.load(f)

    category = inp["category"]
    core_target = inp["core_target"]
    research_depth = inp.get("research_depth", "标准版")
    user_focus = inp.get("user_focus", "二级市场")

    print(f"\n{'='*60}")
    print(f"IRA 第二章工作流启动")
    print(f"品类: {category}　标的: {core_target}")
    print(f"深度: {research_depth}　视角: {user_focus}")
    print(f"{'='*60}\n")

    # 创建中间结果目录
    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    # Step 1: 四象限定位
    quadrant = run_quadrant_analysis(category, core_target, user_focus)
    save_intermediate(quadrant, str(inter_dir / "s1_quadrant.json"))

    # Step 2: 场景拆解
    scenarios = run_scenario_analysis(category, core_target, quadrant)
    save_intermediate(scenarios, str(inter_dir / "s2_scenarios.json"))

    # Step 3: 生命周期判断
    lifecycle = run_lifecycle_analysis(category, core_target, scenarios)
    save_intermediate(lifecycle, str(inter_dir / "s3_lifecycle.json"))

    # Step 4: 破局点识别
    breakthrough = run_breakthrough_analysis(category, core_target, lifecycle, scenarios)
    save_intermediate(breakthrough, str(inter_dir / "s4_breakthrough.json"))

    # Step 5: 整合写作
    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        quadrant, scenarios, lifecycle, breakthrough,
    )

    # 组装最终文档
    all_results = {
        "四象限定位": quadrant,
        "消费场景拆解": scenarios,
        "生命周期判断": lifecycle,
        "破局点识别": breakthrough,
    }
    final_md = build_chapter2_markdown(category, core_target, chapter_body, all_results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n{'='*60}")
    print(f"✓ 完成！输出文件: {output_path}")
    print(f"✓ 中间结果目录: {inter_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
