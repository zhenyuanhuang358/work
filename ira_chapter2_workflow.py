"""
IRA (Industry Research Agent) — 第二章自动化工作流
Chapter 2: 品类本质分析
驱动模型：Google Gemini 2.0 Flash（免费层）

获取免费 API Key: https://aistudio.google.com/app/apikey

用法:
    export GEMINI_API_KEY="AIza..."
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
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

MODEL = "gemini-2.0-flash"   # 免费层：1500次/天，15次/分钟

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

AI_BLACKLIST = [
    "值得注意的是", "不可否认", "毋庸置疑", "显而易见",
    "综上所述", "总的来说", "不难发现", "由此可见",
    "与此同时", "在此基础上", "从某种意义上说",
    "深度赋能", "闭环", "生态", "赋能", "底层逻辑",
    "顶层设计", "内卷", "躺平", "破圈", "出圈",
    "降维打击", "降本增效", "弯道超车",
]

# ---------------------------------------------------------------------------
# Sub-task 1: 四象限定位
# ---------------------------------------------------------------------------

SYSTEM_QUADRANT = """你是一名资深消费行业研究员，擅长品类战略分析。

【任务】：完成品类四象限定位分析，只输出 JSON，不含任何解释文字或 markdown 代码块。

【四象限定义】
- X轴：消费频次（高频 ≥ 每月2次 / 低频 < 每月2次）
- Y轴：客单价（高客单 ≥ 200元 / 低客单 < 200元）

四个象限：
1. 高频低价（刚需日常）：便利店、快餐、早餐
2. 高频高价（习惯型享受）：星巴克、健身、轻奢餐厅
3. 低频低价（冲动偶发）：小吃、零食、街边摊
4. 低频高价（仪式型消费）：火锅、精品餐厅、节庆消费

输出 JSON 示例（严格按此结构）：
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
    resp = client.models.generate_content(
        model=MODEL,
        contents=f"品类：{category}\n核心标的：{core_target}\n研究视角：{user_focus}\n\n请完成四象限定位分析，只输出 JSON。",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_QUADRANT,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(resp.text)


# ---------------------------------------------------------------------------
# Sub-task 2: 场景拆解
# ---------------------------------------------------------------------------

SYSTEM_SCENARIOS = """你是一名消费行业研究员，专注于消费场景与用户行为分析。

【任务】：识别品类的核心消费场景，只输出 JSON，不含任何解释文字或 markdown 代码块。

每个场景包含：
- 场景名称（4-6字）
- 触发动机
- 人群画像
- 平均客单价（元）
- 对品类营收的贡献权重估算（%）
- 该场景下头部品牌的竞争优势

输出 JSON 示例（严格按此结构）：
{
  "total_scenarios": 5,
  "scenarios": [
    {
      "id": 1,
      "name": "聚会社交",
      "trigger": "朋友/家人聚会，需要够热闹、够有仪式感的餐厅",
      "target_group": "25-45岁城市中产，2-8人团体",
      "avg_spend_rmb": 160,
      "revenue_weight_pct": 40,
      "competitive_advantage": "大桌位设计、热闹氛围、等位文化形成社交谈资",
      "brand_examples": ["海底捞", "呷哺呷哺大店"]
    }
  ],
  "dominant_scenario": "聚会社交",
  "scenario_insight": "火锅品类本质上是社交货币，口味标准化让消费者注意力转移到氛围体验",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_scenario_analysis(category: str, core_target: str, quadrant: dict) -> dict:
    print(f"  [2/4] 消费场景拆解...")
    context = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"四象限定位：{quadrant.get('quadrant_label', '')}（{quadrant.get('quadrant', '')}）\n"
        f"定位含义：{quadrant.get('positioning_implication', '')}\n\n"
        "请识别该品类的5-7个核心消费场景，按营收贡献权重从高到低排列，只输出 JSON。"
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=context,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_SCENARIOS,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(resp.text)


# ---------------------------------------------------------------------------
# Sub-task 3: 生命周期判断
# ---------------------------------------------------------------------------

SYSTEM_LIFECYCLE = """你是一名消费行业研究员，专注于行业生命周期与投资时机判断。

【任务】：判断品类所处生命周期阶段，只输出 JSON，不含任何解释文字或 markdown 代码块。

生命周期阶段：导入期、成长期、成熟期、震荡期、衰退期

五个判断指标：
1. 渗透率（与可比市场对比）
2. 同店销售增长趋势
3. 新品牌涌现速度
4. 价格带竞争（是否出现价格战）
5. 消费频次趋势

输出 JSON 示例（严格按此结构）：
{
  "lifecycle_stage": "成熟期",
  "stage_confidence": "高",
  "indicators": {
    "penetration_rate": "中国火锅门店约50万家，渗透率高，增速放缓至个位数",
    "sssg_trend": "头部品牌同店销售2023年后逐步恢复，但尚未回到2019年峰值",
    "new_brand_velocity": "新品牌涌现放缓，区域品牌整合加速",
    "price_competition": "出现明显价格带下沉竞争",
    "frequency_recovery": "疫后翻台率恢复至2019年约80-90%水平"
  },
  "valuation_implication": "成熟期品类应以EV/EBITDA或P/FCF估值，PE估值需折价处理；重点关注坪效和翻台率改善空间",
  "key_risk": "若同店继续下滑，将进入衰退期，估值中枢将下移",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_lifecycle_analysis(category: str, core_target: str, scenarios: dict) -> dict:
    print(f"  [3/4] 生命周期判断...")
    context = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"主要消费场景：{scenarios.get('dominant_scenario', '')}\n"
        f"场景洞察：{scenarios.get('scenario_insight', '')}\n\n"
        "请判断该品类当前所处的生命周期阶段，给出具体指标支撑和估值含义，只输出 JSON。"
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=context,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_LIFECYCLE,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(resp.text)


# ---------------------------------------------------------------------------
# Sub-task 4: 破局点识别
# ---------------------------------------------------------------------------

SYSTEM_BREAKTHROUGH = """你是一名消费行业研究员，专注于竞争战略与品类创新分析。

【任务】：识别品类历史破局点及下一个潜在破局点，只输出 JSON，不含任何解释文字或 markdown 代码块。

破局点定义：能打破现有竞争格局、创造新价值曲线、实现差异化胜出的关键维度。
不是"做得更好"，而是"维度创新"。

历史破局点分类：产品维度、体验维度、效率维度、人群维度、场景维度

输出 JSON 示例（严格按此结构）：
{
  "historical_breakthroughs": [
    {
      "year_approx": "2011-2016",
      "dimension": "体验维度",
      "description": "海底捞将变态服务作为核心差异点，重新定义火锅服务标准",
      "winner": "海底捞",
      "impact": "服务溢价支撑高翻台率，推动全国扩张"
    }
  ],
  "next_breakthrough_candidates": [
    {
      "dimension": "零售化/预制菜",
      "hypothesis": "堂食天花板下，品牌延伸至家庭消费场景",
      "probability": "高",
      "beneficiary": "海底捞（已布局）、巴奴"
    }
  ],
  "core_target_position": "海底捞在历史破局点上均有布局，但当前面临服务差异化被模仿、产品侧被巴奴追赶的双重压力",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_breakthrough_analysis(category: str, core_target: str, lifecycle: dict, scenarios: dict) -> dict:
    print(f"  [4/4] 破局点识别...")
    context = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"生命周期阶段：{lifecycle.get('lifecycle_stage', '')}\n"
        f"主要风险：{lifecycle.get('key_risk', '')}\n\n"
        "请识别该品类的历史破局点（至少2个），以及下一个潜在破局点候选（至少2个），只输出 JSON。"
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=context,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_BREAKTHROUGH,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(resp.text)


# ---------------------------------------------------------------------------
# 整合写作 Agent
# ---------------------------------------------------------------------------

SYSTEM_INTEGRATION = (
    "你是一名资深卖方研究员，擅长将结构化分析数据转化为专业研报文字。\n\n"
    "【写作要求】\n"
    "1. 文风：卖方研报体，客观专业，有论据支撑\n"
    "2. 结构：四个小节——2.1四象限定位、2.2消费场景拆解、2.3生命周期判断、2.4破局点识别\n"
    "3. 数据：引用子分析中的具体数据，不凭空编造\n"
    "4. 投资视角：每节结尾给出投资含义1-2句\n"
    "5. 长度：每小节400-600字，总计1600-2400字\n"
    "6. 直接输出 Markdown，从 ## 2.1 开始，不含 JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    quadrant: dict, scenarios: dict, lifecycle: dict, breakthrough: dict,
) -> str:
    print(f"  [整合] 写作整合 Agent...")
    bundle = {
        "四象限定位": quadrant,
        "消费场景拆解": scenarios,
        "生命周期判断": lifecycle,
        "破局点识别": breakthrough,
    }
    prompt = (
        f"研究标的：{core_target}（品类：{category}）\n"
        f"研究深度：{research_depth}\n"
        f"读者视角：{user_focus}\n\n"
        f"以下是四个子分析的结构化结果：\n\n"
        f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
        "请据此撰写第二章正文，直接从 ## 2.1 品类四象限定位 开始。"
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INTEGRATION,
            temperature=0.5,
            max_output_tokens=4096,
        ),
    )
    return resp.text


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        print(f"  [警告] JSON 解析失败，保留原始文本")
        return {"raw_text": text, "parse_error": True}


def save_intermediate(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 已保存: {path}")


def build_final_md(category: str, core_target: str, chapter_body: str, all_results: dict) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason', '需人工核查')}"
        for k, v in all_results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = f"# 第二章　品类本质\n\n> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    warning_block = (
        "\n> ⚠️ **人工核查提示**\n>\n" + "\n".join(f"> {w}" for w in warnings) + "\n\n"
        if warnings else ""
    )
    return header + warning_block + chapter_body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第二章自动化工作流（Gemini 免费版）")
    parser.add_argument("input", help="输入 JSON 文件路径")
    parser.add_argument("--output", default="output_chapter2.md", help="输出 Markdown 文件路径")
    parser.add_argument("--intermediates-dir", default="intermediates", help="中间结果目录")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误：请先设置环境变量 GEMINI_API_KEY")
        print("  获取免费 Key：https://aistudio.google.com/app/apikey")
        print("  设置方法：export GEMINI_API_KEY='AIza...'")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        inp = json.load(f)

    category      = inp["category"]
    core_target   = inp["core_target"]
    research_depth = inp.get("research_depth", "标准版")
    user_focus    = inp.get("user_focus", "二级市场")

    print(f"\n{'='*60}")
    print(f"IRA 第二章工作流（Gemini 免费版）")
    print(f"品类: {category}　标的: {core_target}")
    print(f"深度: {research_depth}　视角: {user_focus}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    quadrant    = run_quadrant_analysis(category, core_target, user_focus)
    save_intermediate(quadrant, str(inter_dir / "s1_quadrant.json"))

    scenarios   = run_scenario_analysis(category, core_target, quadrant)
    save_intermediate(scenarios, str(inter_dir / "s2_scenarios.json"))

    lifecycle   = run_lifecycle_analysis(category, core_target, scenarios)
    save_intermediate(lifecycle, str(inter_dir / "s3_lifecycle.json"))

    breakthrough = run_breakthrough_analysis(category, core_target, lifecycle, scenarios)
    save_intermediate(breakthrough, str(inter_dir / "s4_breakthrough.json"))

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        quadrant, scenarios, lifecycle, breakthrough,
    )

    all_results = {
        "四象限定位": quadrant, "消费场景拆解": scenarios,
        "生命周期判断": lifecycle, "破局点识别": breakthrough,
    }
    final_md = build_final_md(category, core_target, chapter_body, all_results)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n{'='*60}")
    print(f"完成！输出文件: {out}")
    print(f"中间结果目录: {inter_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
