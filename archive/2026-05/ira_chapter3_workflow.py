"""
IRA (Industry Research Agent) — 第三章自动化工作流
Chapter 3: 竞争格局分析

依赖: pip install google-genai
用法:
    export GEMINI_API_KEY="AIza..."
    python3 ira_chapter3_workflow.py input.json
    python3 ira_chapter3_workflow.py input.json --output my_ch3.md --ch2-dir intermediates

输入 JSON 格式:
    {
        "category": "火锅",
        "core_target": "海底捞 6862.HK",
        "research_depth": "标准版",
        "user_focus": "二级市场"
    }

--ch2-dir 指向第二章的 intermediates 目录，用于加载第二章分析结论作为上下文。
"""

import json
import sys
import os
import time
import argparse
from pathlib import Path
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

MODEL = "gemini-2.5-flash"

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

AI_BLACKLIST = [
    "值得注意的是", "不可否认", "毋庸置疑", "显而易见",
    "综上所述", "总的来说", "不难发现", "由此可见",
    "与此同时", "在此基础上", "从某种意义上说",
    "深度赋能", "闭环", "生态", "赋能", "底层逻辑",
    "顶层设计", "内卷", "躺平", "破圈", "出圈",
    "降维打击", "降本增效", "弯道超车",
]


def _generate(contents: str, config: types.GenerateContentConfig, retries: int = 5) -> str:
    delay = 15
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents, config=config)
            return resp.text
        except (genai_errors.ServerError, genai_errors.ClientError) as e:
            code = getattr(e, "status_code", 0)
            if code in (429, 503) and attempt < retries - 1:
                print(f"  [重试 {attempt+1}/{retries-1}] 服务繁忙，等待 {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise


# ---------------------------------------------------------------------------
# Sub-task 1: 市场集中度分析
# ---------------------------------------------------------------------------

SYSTEM_CONCENTRATION = """你是一名资深消费行业研究员，专注于产业竞争格局分析。

【任务】：评估品类的市场集中度，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析维度】
- CR3/CR5：头部3家/5家品牌的合计市场份额（按门店数或营收估算）
- HHI 指数：赫芬达尔指数（0-10000），越高越集中
  - < 1000：高度分散（完全竞争）
  - 1000-2500：中等集中
  - > 2500：高度集中（寡头）
- 格局类型：分散型 / 区域寡头型 / 全国寡头型 / 垄断型
- 集中度趋势：是否在加速集中（头部吃掉份额）或继续分散

输出 JSON 示例（严格按此结构）：
{
  "market_share_basis": "按门店数估算",
  "top_players": [
    {"rank": 1, "brand": "海底捞", "market_share_pct": 3.5, "store_count_approx": 1350},
    {"rank": 2, "brand": "呷哺呷哺", "market_share_pct": 1.2, "store_count_approx": 500},
    {"rank": 3, "brand": "捞王", "market_share_pct": 0.3, "store_count_approx": 120},
    {"rank": 4, "brand": "巴奴", "market_share_pct": 0.2, "store_count_approx": 90},
    {"rank": 5, "brand": "珮姐", "market_share_pct": 0.15, "store_count_approx": 60}
  ],
  "cr3_pct": 5.0,
  "cr5_pct": 5.35,
  "hhi_estimate": 150,
  "structure_type": "高度分散",
  "concentration_trend": "缓慢集中：头部连锁扩张，但区域品牌仍大量存在，品类天然不易集中",
  "fragmentation_reason": "火锅门槛较低，口味偏好地域差异大，本地小店长期占据大部分份额",
  "investment_implication": "高分散格局意味着头部品牌市占率提升空间大，但整合速度慢；龙头应以单店盈利为先，而非激进扩张",
  "need_human_calibration": true,
  "calibration_reason": "市场份额数据需参照弗若斯特沙利文/欧睿等第三方报告核实"
}"""


def run_concentration_analysis(
    category: str, core_target: str, ch2_context: str
) -> dict:
    print("  [1/4] 市场集中度分析...")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n\n"
        f"第二章背景（品类本质摘要）：\n{ch2_context}\n\n"
        "请评估该品类的市场集中度，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_CONCENTRATION,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 2: 主要玩家竞争力对比
# ---------------------------------------------------------------------------

SYSTEM_PLAYERS = """你是一名消费行业研究员，专注于竞争对手分析。

【任务】：对品类内主要竞争者进行多维度横向对比，只输出 JSON，不含任何解释文字或 markdown 代码块。

【对比维度】（每个玩家）
1. 定位：价格带 + 人群定位
2. 规模：门店数量（近似值）
3. 单店经济模型：平均客单价（元）、翻台率（次/天）、坪效（元/㎡/月）
4. 核心差异化：1句话说清楚该品牌凭什么胜出
5. 短板：最主要的竞争弱点

输出 JSON 示例（严格按此结构）：
{
  "comparison_basis": "2023-2024年公开资料综合估算",
  "players": [
    {
      "brand": "海底捞",
      "ticker": "6862.HK",
      "positioning": "中高端，全客群，主打极致服务",
      "price_band_rmb": "人均150-200元",
      "store_count": 1350,
      "avg_table_turns_per_day": 3.5,
      "avg_spend_per_head_rmb": 105,
      "estimated_revenue_cny_bn": 41.5,
      "core_differentiation": "服务体系标准化输出，等位文化形成品牌护城河",
      "key_weakness": "服务溢价被逐步模仿，客单价下行压力下翻台率承压"
    },
    {
      "brand": "呷哺呷哺",
      "ticker": "0520.HK",
      "positioning": "中端，个人/小团体，性价比火锅",
      "price_band_rmb": "人均60-90元",
      "store_count": 500,
      "avg_table_turns_per_day": 2.8,
      "avg_spend_per_head_rmb": 65,
      "estimated_revenue_cny_bn": 5.5,
      "core_differentiation": "小火锅形态适合单人/双人就餐，翻台效率高",
      "key_weakness": "定位模糊，凑凑子品牌拖累整体，同店销售持续下滑"
    }
  ],
  "core_target_competitive_summary": "海底捞在规模和服务标准化上领先全行业，但单店盈利恢复进程和客单价下行是短期核心矛盾",
  "need_human_calibration": true,
  "calibration_reason": "翻台率、坪效等运营数据需以最新财报数据核实"
}"""


def run_players_analysis(
    category: str, core_target: str, concentration: dict
) -> dict:
    print("  [2/4] 主要玩家竞争力对比...")
    top_brands = [p["brand"] for p in concentration.get("top_players", [])]
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"主要竞争品牌：{', '.join(top_brands)}\n"
        f"市场格局类型：{concentration.get('structure_type', '')}\n\n"
        "请对以上品牌进行多维度竞争力横向对比，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PLAYERS,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 3: 核心标的护城河评估
# ---------------------------------------------------------------------------

SYSTEM_MOAT = """你是一名消费行业研究员，专注于企业竞争优势与护城河分析。

【任务】：评估核心标的在六大护城河维度上的强度，只输出 JSON，不含任何解释文字或 markdown 代码块。

【六大护城河维度】
1. 品牌溢价：消费者是否愿意为品牌多付钱，品牌认知度
2. 供应链壁垒：自建供应链的成本优势、食材品质控制能力
3. 服务体系：服务SOP可复制性、员工激励机制的差异化
4. 选址网络：优质点位的先占优势，开店速度与密度
5. 数据与会员：用户数据积累、会员体系转化率
6. 网络效应：规模带来的强化效应（口碑、供应商议价）

每个维度评分：
- 强（3分）：明显领先同行，竞争对手难以复制
- 中（2分）：行业平均水平，有优势但可被模仿
- 弱（1分）：低于同行或存在明显短板

输出 JSON 示例（严格按此结构）：
{
  "target": "海底捞",
  "moat_scores": [
    {
      "dimension": "品牌溢价",
      "score": 3,
      "rating": "强",
      "evidence": "海底捞品牌在全国范围内具备高认知度，消费者接受10-20%的价格溢价",
      "threat": "竞争品牌持续侵蚀，年轻消费者对性价比诉求上升"
    },
    {
      "dimension": "供应链壁垒",
      "score": 3,
      "rating": "强",
      "evidence": "颐海国际（3097.HK）独立上市，底料供应链自控，食材集采规模优势显著",
      "threat": "供应商依赖度高，关联交易占比需持续关注"
    },
    {
      "dimension": "服务体系",
      "score": 3,
      "rating": "强",
      "evidence": "服务SOP体系全行业最成熟，师徒制文化形成独特激励机制",
      "threat": "人力成本上升，竞争对手持续学习模仿，差异化空间收窄"
    },
    {
      "dimension": "选址网络",
      "score": 2,
      "rating": "中",
      "evidence": "全国1350+门店，覆盖主要城市核心商圈",
      "threat": "扩张后部分点位质量下降，关店调整仍在进行"
    },
    {
      "dimension": "数据与会员",
      "score": 2,
      "rating": "中",
      "evidence": "拥有海量会员数据，但数据变现和精准营销能力尚待提升",
      "threat": "同行加速补课，美团等平台掌握更多用户数据"
    },
    {
      "dimension": "网络效应",
      "score": 2,
      "rating": "中",
      "evidence": "规模带来供应商议价优势，口碑传播具备一定网络效应",
      "threat": "餐饮本质属地化，网络效应不如互联网行业显著"
    }
  ],
  "total_score": 15,
  "max_score": 18,
  "moat_rating": "宽护城河",
  "moat_summary": "海底捞在品牌、供应链、服务三大核心维度构建了行业内最强的护城河组合，但护城河宽度正面临收窄压力",
  "biggest_moat_risk": "服务差异化被模仿导致品牌溢价下降，客单价承压将直接冲击翻台率和单店利润",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_moat_analysis(
    category: str, core_target: str, players: dict, ch2_context: str
) -> dict:
    print("  [3/4] 护城河评估...")
    summary = players.get("core_target_competitive_summary", "")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"竞争地位摘要：{summary}\n"
        f"第二章品类背景：\n{ch2_context}\n\n"
        "请对核心标的进行六大护城河维度评估，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_MOAT,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 4: 竞争态势预判
# ---------------------------------------------------------------------------

SYSTEM_OUTLOOK = """你是一名消费行业研究员，专注于行业竞争动态预测。

【任务】：预判品类未来2-3年的竞争态势演变，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析框架】
1. 格局演变方向：集中度会提升/维持/分散？驱动力是什么？
2. 竞争主战场：未来竞争将在哪个维度展开（价格/产品/效率/渠道）？
3. 潜在搅局者：来自哪里？（跨界/区域扩张/新模式）
4. 核心标的2-3年内的竞争地位变化预测：升/维持/降？原因？

输出 JSON 示例（严格按此结构）：
{
  "outlook_horizon": "2024-2026年",
  "concentration_direction": "缓慢提升",
  "concentration_driver": "头部品牌供应链和品牌优势形成规模门槛，中小品牌在成本压力下加速淘汰",
  "competition_battleground": [
    {
      "dimension": "价格带",
      "description": "中端价格带（人均80-120元）竞争最激烈，多品牌争夺性价比用户"
    },
    {
      "dimension": "供应链效率",
      "description": "食材透明化和预制菜延伸成为新竞争点，供应链能力决定成本优势"
    }
  ],
  "potential_disruptors": [
    {
      "type": "区域品牌全国化",
      "example": "珮姐老火锅、朱光玉等重庆系品牌加速向一线渗透",
      "threat_level": "中",
      "threat_to_target": "分流海底捞中端客群，尤其在非核心城市"
    },
    {
      "type": "新模式创新",
      "example": "预制火锅套餐、家庭火锅零售化扩大非堂食市场",
      "threat_level": "低",
      "threat_to_target": "海底捞已提前布局零售端（颐海国际），新模式反而是机会"
    }
  ],
  "core_target_outlook": {
    "position_change": "维持",
    "rationale": "海底捞规模和品牌壁垒短期内难以被超越，但盈利恢复进度和客单价走势是关键变量",
    "bull_case": "翻台率持续回升至4.0+，同店销售正增长，利润弹性充分释放",
    "bear_case": "消费降级持续，客单价下压，门店盈利能力难以回到2019年水平"
  },
  "key_watch_indicators": [
    "海底捞季度翻台率趋势",
    "头部品牌新开店速度与关店率",
    "中端价格带新品牌融资动态"
  ],
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_outlook_analysis(
    category: str, core_target: str, concentration: dict, moat: dict
) -> dict:
    print("  [4/4] 竞争态势预判...")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"当前格局类型：{concentration.get('structure_type', '')}\n"
        f"集中度趋势：{concentration.get('concentration_trend', '')}\n"
        f"核心标的护城河评级：{moat.get('moat_rating', '')}（{moat.get('total_score', '')}/{moat.get('max_score', '')}分）\n"
        f"最大护城河风险：{moat.get('biggest_moat_risk', '')}\n\n"
        "请预判该品类未来2-3年的竞争态势演变，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_OUTLOOK,
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# 整合写作 Agent
# ---------------------------------------------------------------------------

SYSTEM_INTEGRATION = (
    "你是一名资深卖方研究员，擅长将结构化分析数据转化为专业研报文字。\n\n"
    "【写作要求】\n"
    "1. 文风：卖方研报体，客观专业，有论据支撑\n"
    "2. 结构：四个小节——3.1市场集中度、3.2主要玩家对比、3.3护城河评估、3.4竞争态势预判\n"
    "3. 数据：引用子分析中的具体数据和评分，不凭空编造\n"
    "4. 投资视角：每节结尾给出投资含义1-2句\n"
    "5. 长度：每小节400-600字，总计1600-2400字\n"
    "6. 直接输出 Markdown，从 ## 3.1 开始，不含 JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    concentration: dict, players: dict, moat: dict, outlook: dict,
) -> str:
    print("  [整合] 写作整合 Agent...")
    bundle = {
        "市场集中度": concentration,
        "主要玩家对比": players,
        "护城河评估": moat,
        "竞争态势预判": outlook,
    }
    prompt = (
        f"研究标的：{core_target}（品类：{category}）\n"
        f"研究深度：{research_depth}\n"
        f"读者视角：{user_focus}\n\n"
        f"以下是四个子分析的结构化结果：\n\n"
        f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
        "请据此撰写第三章正文，直接从 ## 3.1 市场集中度 开始。"
    )
    return _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INTEGRATION,
            temperature=0.5,
            max_output_tokens=4096,
        ),
    )


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
        print("  [警告] JSON 解析失败，保留原始文本")
        return {"raw_text": text, "parse_error": True}


def save_intermediate(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 已保存: {path}")


def load_ch2_context(ch2_dir: str) -> str:
    """从第二章中间结果提取关键摘要作为上下文。"""
    summary_parts = []
    files = {
        "四象限": "s1_quadrant.json",
        "生命周期": "s3_lifecycle.json",
        "破局点":   "s4_breakthrough.json",
    }
    for label, fname in files.items():
        p = Path(ch2_dir) / fname
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if label == "四象限":
                summary_parts.append(
                    f"四象限定位：{data.get('quadrant_label', '')}，"
                    f"月均消费频次{data.get('frequency_per_month', '')}，"
                    f"人均消费{data.get('avg_spend_rmb', '')}元"
                )
            elif label == "生命周期":
                summary_parts.append(f"生命周期：{data.get('lifecycle_stage', '')}，{data.get('valuation_implication', '')}")
            elif label == "破局点":
                summary_parts.append(f"核心标的竞争定位：{data.get('core_target_position', '')}")
    return "\n".join(summary_parts) if summary_parts else "（无第二章上下文）"


def build_final_md(
    category: str, core_target: str, chapter_body: str, all_results: dict
) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason', '需人工核查')}"
        for k, v in all_results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = (
        f"# 第三章　竞争格局\n\n"
        f"> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    )
    warning_block = (
        "\n> ⚠️ **人工核查提示**\n>\n"
        + "\n".join(f"> {w}" for w in warnings)
        + "\n\n"
        if warnings else ""
    )
    return header + warning_block + chapter_body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第三章自动化工作流")
    parser.add_argument("input", help="输入 JSON 文件路径")
    parser.add_argument("--output", default="output_chapter3.md", help="输出 Markdown 文件路径")
    parser.add_argument("--intermediates-dir", default="intermediates_ch3", help="中间结果保存目录")
    parser.add_argument("--ch2-dir", default="intermediates", help="第二章中间结果目录（用于上下文）")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误：请先设置环境变量 GEMINI_API_KEY")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        inp = json.load(f)

    category       = inp["category"]
    core_target    = inp["core_target"]
    research_depth = inp.get("research_depth", "标准版")
    user_focus     = inp.get("user_focus", "二级市场")

    print(f"\n{'='*60}")
    print(f"IRA 第三章工作流：竞争格局")
    print(f"品类: {category}　标的: {core_target}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    ch2_context = load_ch2_context(args.ch2_dir)
    if ch2_context != "（无第二章上下文）":
        print(f"  [✓] 已加载第二章上下文")

    def _load_or_run(path: str, fn):
        p = Path(path)
        if p.exists():
            print(f"  [跳过] 加载已有结果: {path}")
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        result = fn()
        save_intermediate(result, path)
        return result

    concentration = _load_or_run(
        str(inter_dir / "s1_concentration.json"),
        lambda: run_concentration_analysis(category, core_target, ch2_context),
    )
    players = _load_or_run(
        str(inter_dir / "s2_players.json"),
        lambda: run_players_analysis(category, core_target, concentration),
    )
    moat = _load_or_run(
        str(inter_dir / "s3_moat.json"),
        lambda: run_moat_analysis(category, core_target, players, ch2_context),
    )
    outlook = _load_or_run(
        str(inter_dir / "s4_outlook.json"),
        lambda: run_outlook_analysis(category, core_target, concentration, moat),
    )

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        concentration, players, moat, outlook,
    )

    all_results = {
        "市场集中度": concentration,
        "主要玩家对比": players,
        "护城河评估": moat,
        "竞争态势预判": outlook,
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
