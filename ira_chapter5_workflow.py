"""
IRA (Industry Research Agent) — 第五章自动化工作流
Chapter 5: 公司深度分析

用法:
    export GEMINI_API_KEY="AIza..."
    python3 ira_chapter5_workflow.py input.json
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

MODEL = "gemini-flash-lite-latest"
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
# Sub-task 1: 商业模式解析
# ---------------------------------------------------------------------------

SYSTEM_BIZ_MODEL = """你是一名资深消费行业研究员，专注于餐饮企业商业模式分析。

【任务】：解析核心标的的商业模式，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析维度】
1. 收入结构：各业务线收入拆分及占比
2. 盈利逻辑：核心利润来源，边际成本结构
3. 飞轮机制：哪些要素相互增强形成正向循环
4. 关联方价值链：上下游关联实体对主体的价值贡献
5. 轻重资产属性：资本密集度，扩张所需投入

输出 JSON 示例（严格按此结构）：
{
  "company": "海底捞",
  "business_model_type": "直营连锁餐饮 + 供应链协同",
  "revenue_breakdown": [
    {"segment": "餐厅经营收入", "share_pct": 96.2, "note": "堂食为核心，外卖占比较小"},
    {"segment": "外卖业务", "share_pct": 2.3, "note": "疫情期间快速增长，现占比趋稳"},
    {"segment": "调味品及食材零售", "share_pct": 1.5, "note": "通过颐海国际间接获益，主体收入占比低"}
  ],
  "profit_logic": {
    "core_driver": "翻台率 × 客单价 × 门店数",
    "margin_structure": "食材成本约40%，员工成本约35%，租金约10%，四墙利润率约10-15%",
    "leverage_point": "翻台率每提升0.5次/天，单店年利润增量约30-50万元"
  },
  "flywheel": [
    "极致服务 → 口碑传播 → 更高翻台率 → 更多利润 → 更好激励员工 → 更好服务",
    "门店规模 → 供应链议价 → 食材成本下降 → 利润提升 → 更多扩张资金"
  ],
  "related_party_value": [
    {
      "entity": "颐海国际（3097.HK）",
      "relationship": "底料及食材核心供应商，海底捞持股约36%",
      "strategic_value": "供应链成本可控，食材品质稳定，且向外部B端销售形成独立盈利"
    },
    {
      "entity": "蜀海集团",
      "relationship": "食材供应链管理平台（非上市）",
      "strategic_value": "负责全链路食材采购、加工、冷链配送，是海底捞扩张的后勤保障"
    }
  ],
  "asset_intensity": {
    "model": "重资产直营",
    "capex_per_new_store_wan": 800,
    "payback_period_years": 2.5,
    "asset_turnover_comment": "高翻台率是提升资产周转效率的核心"
  },
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_biz_model(category: str, core_target: str, prior_context: str) -> dict:
    print("  [1/4] 商业模式解析...")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n\n"
            f"前置章节摘要：\n{prior_context}\n\n"
            "请解析该公司的商业模式，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_BIZ_MODEL,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 2: 单店经济模型
# ---------------------------------------------------------------------------

SYSTEM_UNIT_ECON = """你是一名消费行业研究员，专注于餐饮企业单店经济模型分析（Unit Economics）。

【任务】：拆解核心标的的单店经济模型，只输出 JSON，不含任何解释文字或 markdown 代码块。

【单店P&L结构】（以标准大店为基准）
- 收入端：翻台率 × 桌数 × 人均消费 × 营业天数
- 成本端：食材（原材料）+ 员工（人力）+ 租金（物业）+ 其他（水电/折旧/营销）
- 四墙利润（Restaurant-Level Profit）= 收入 - 以上直接成本
- 注意：四墙利润未扣除总部费用分摊

【对比基准】
- 2019年（巅峰）vs 2022年（谷底）vs 2023-2024年（恢复期）

输出 JSON 示例（严格按此结构）：
{
  "model_basis": "标准直营大店（400㎡，约30-35桌）",
  "scenarios": [
    {
      "period": "2019年（峰值）",
      "table_turns_per_day": 4.8,
      "avg_spend_per_head_rmb": 105,
      "annual_revenue_wan": 1580,
      "cost_breakdown_pct": {
        "food_cost": 40.2,
        "labor_cost": 30.5,
        "rent": 8.1,
        "other": 7.2
      },
      "restaurant_level_margin_pct": 14.0,
      "restaurant_level_profit_wan": 221
    },
    {
      "period": "2022年（谷底）",
      "table_turns_per_day": 2.9,
      "avg_spend_per_head_rmb": 104,
      "annual_revenue_wan": 960,
      "cost_breakdown_pct": {
        "food_cost": 42.0,
        "labor_cost": 36.0,
        "rent": 11.0,
        "other": 8.5
      },
      "restaurant_level_margin_pct": 2.5,
      "restaurant_level_profit_wan": 24
    },
    {
      "period": "2023-2024年（恢复期）",
      "table_turns_per_day": 3.8,
      "avg_spend_per_head_rmb": 99,
      "annual_revenue_wan": 1260,
      "cost_breakdown_pct": {
        "food_cost": 41.0,
        "labor_cost": 33.0,
        "rent": 9.0,
        "other": 7.5
      },
      "restaurant_level_margin_pct": 9.5,
      "restaurant_level_profit_wan": 120
    }
  ],
  "sensitivity": {
    "table_turn_impact": "翻台率每+0.1次/天，单店四墙利润约+8-12万元/年",
    "asp_impact": "人均消费每+5元，单店四墙利润约+15-20万元/年",
    "key_bottleneck": "当前翻台率恢复至3.5-4.0区间是利润弹性释放的关键"
  },
  "new_store_economics": {
    "capex_wan": 800,
    "breakeven_table_turns": 3.2,
    "irr_at_current_turns_pct": 18,
    "target_irr_pct": 25
  },
  "need_human_calibration": true,
  "calibration_reason": "单店数据需以海底捞最新财报披露的餐厅层面数据核实"
}"""


def run_unit_economics(category: str, core_target: str, biz_model: dict) -> dict:
    print("  [2/4] 单店经济模型拆解...")
    margin = biz_model.get("profit_logic", {}).get("margin_structure", "")
    leverage = biz_model.get("profit_logic", {}).get("leverage_point", "")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"利润率结构：{margin}\n"
            f"利润杠杆点：{leverage}\n\n"
            "请拆解该公司的单店经济模型，对比峰值/谷底/恢复期三个时期，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_UNIT_ECON,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 3: 历史财务复盘
# ---------------------------------------------------------------------------

SYSTEM_FINANCIALS = """你是一名消费行业分析师，专注于餐饮企业财务分析。

【任务】：复盘核心标的近3-4年的财务表现，识别关键趋势，只输出 JSON，不含任何解释文字或 markdown 代码块。

【关注指标】
- 营收增速及驱动拆分（量/价/门店数）
- 毛利率、经营利润率、净利润率趋势
- 自由现金流生成能力
- 资产负债表健康度（净现金/净负债）
- 分红/回购政策

输出 JSON 示例（严格按此结构）：
{
  "company": "海底捞",
  "currency": "亿元人民币（港股上市，以人民币报告）",
  "annual_data": [
    {
      "year": "2020",
      "revenue": 286.1,
      "revenue_yoy_pct": -11.5,
      "gross_profit_margin_pct": 57.1,
      "operating_profit": -11.9,
      "operating_margin_pct": -4.2,
      "net_profit": -18.3,
      "net_margin_pct": -6.4,
      "free_cash_flow": -25.0,
      "store_count_eoy": 1298,
      "table_turns_avg": 3.5,
      "key_event": "疫情冲击，门店受限，全年净亏损"
    },
    {
      "year": "2021",
      "revenue": 411.1,
      "revenue_yoy_pct": 43.7,
      "gross_profit_margin_pct": 57.7,
      "operating_profit": -20.3,
      "operating_margin_pct": -4.9,
      "net_profit": -41.6,
      "net_margin_pct": -10.1,
      "free_cash_flow": -40.0,
      "store_count_eoy": 1443,
      "table_turns_avg": 3.0,
      "key_event": "激进扩张（啄木鸟前），新开门店摊薄盈利，人力成本激增"
    },
    {
      "year": "2022",
      "revenue": 347.4,
      "revenue_yoy_pct": -15.5,
      "gross_profit_margin_pct": 56.4,
      "operating_profit": 18.8,
      "operating_margin_pct": 5.4,
      "net_profit": 13.7,
      "net_margin_pct": 3.9,
      "free_cash_flow": 30.0,
      "store_count_eoy": 1374,
      "table_turns_avg": 2.9,
      "key_event": "啄木鸟计划关店300+，精简提效，利润率回正"
    },
    {
      "year": "2023",
      "revenue": 414.5,
      "revenue_yoy_pct": 19.3,
      "gross_profit_margin_pct": 57.1,
      "operating_profit": 50.0,
      "operating_margin_pct": 12.1,
      "net_profit": 44.9,
      "net_margin_pct": 10.8,
      "free_cash_flow": 55.0,
      "store_count_eoy": 1374,
      "table_turns_avg": 3.8,
      "key_event": "翻台率快速恢复，规模效应重现，利润大幅反弹"
    }
  ],
  "balance_sheet_snapshot": {
    "as_of": "2023年末",
    "cash_and_equivalents_cny_bn": 57.5,
    "total_debt_cny_bn": 22.0,
    "net_cash_position_cny_bn": 35.5,
    "leverage_comment": "净现金状态，资产负债表健康，具备回购/分红能力"
  },
  "dividend_policy": {
    "history": "2023年首次派发特别股息，体现盈利恢复信心",
    "payout_ratio_pct": 30,
    "buyback_activity": "2023-2024年启动股份回购计划"
  },
  "financial_quality_flags": [
    "现金流质量高：经营活动现金流持续强劲，资本支出管控改善",
    "警惕：使用权资产（租赁负债）规模较大，需关注租约续签风险",
    "警惕：关联方交易（颐海）占采购比例较高，需关注定价公允性"
  ],
  "need_human_calibration": true,
  "calibration_reason": "财务数据以最新年报为准，2024年数据需补充披露后更新"
}"""


def run_financials(category: str, core_target: str, unit_econ: dict) -> dict:
    print("  [3/4] 历史财务复盘...")
    sensitivity = unit_econ.get("sensitivity", {})
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"单店经济模型摘要：\n"
            f"- 翻台率敏感性：{sensitivity.get('table_turn_impact', '')}\n"
            f"- 当前瓶颈：{sensitivity.get('key_bottleneck', '')}\n\n"
            "请复盘该公司2020-2023年的财务表现，分析关键趋势和质量指标，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_FINANCIALS,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 4: 战略与管理层评估
# ---------------------------------------------------------------------------

SYSTEM_STRATEGY = """你是一名消费行业研究员，专注于企业战略和管理层评估。

【任务】：评估核心标的的战略清晰度与管理层执行力，只输出 JSON，不含任何解释文字或 markdown 代码块。

【评估框架】
1. 核心战略举措（3-5个，近2年的重大战略动作）
2. 战略执行情况（承诺 vs. 实际结果）
3. 管理层评估（稳定性、激励机制、决策质量）
4. 未来战略重点（公司指引的下一步）
5. 战略风险（执行失败的可能性和影响）

输出 JSON 示例（严格按此结构）：
{
  "company": "海底捞",
  "strategic_initiatives": [
    {
      "name": "啄木鸟计划（2021-2022）",
      "description": "主动关闭约300家盈利不达标门店，优化门店网络质量",
      "execution_score": "高",
      "result": "单店翻台率从2.9回升至3.8，四墙利润率从接近0恢复至10%+",
      "lesson": "证明管理层具备自我纠错能力，愿意在规模和盈利间取得平衡"
    },
    {
      "name": "硬骨头计划（2023-）",
      "description": "重开部分此前关闭但潜力尚在的门店，选择性扩张",
      "execution_score": "中",
      "result": "谨慎重开约20-30家，未出现大规模激进扩张，节奏可控",
      "lesson": "扩张纪律有所改善，但市场对再次扩张过快仍有顾虑"
    },
    {
      "name": "特色服务与产品迭代",
      "description": "持续升级服务项目，推出主题门店、新品菜式",
      "execution_score": "中",
      "result": "服务维度仍领先同业，但产品侧与巴奴等对手的差距有所收窄",
      "lesson": "服务护城河依然成立，但需加大产品研发投入以防侧翼被突破"
    }
  ],
  "management_assessment": {
    "ceo": "杨利娟（2022年接任，前任张勇淡出）",
    "stability": "高：核心管理层稳定，内部提拔文化保持延续性",
    "incentive_alignment": "中：高管持股比例适中，师徒制对一线员工激励强",
    "decision_quality": "近年显著改善：啄木鸟计划证明管理层愿意承认错误并纠偏",
    "key_risk": "创始人张勇淡出后，企业家精神和文化传承是潜在挑战"
  },
  "strategic_priorities_next2yr": [
    "单店盈利能力持续提升（翻台率目标4.0+）",
    "海外市场选择性扩张（东南亚为主）",
    "零售和预制菜业务放量（通过颐海国际）",
    "数字化运营降本（智能点餐、供应链数字化）"
  ],
  "strategy_risk_matrix": [
    {
      "risk": "扩张纪律再次失守",
      "probability": "低",
      "impact": "高",
      "mitigation": "管理层已建立更严格的开店标准，需持续跟踪新开店表现"
    },
    {
      "risk": "服务差异化持续弱化",
      "probability": "中",
      "impact": "高",
      "mitigation": "加大产品研发，向巴奴的产品主义学习，构建双轮驱动"
    }
  ],
  "overall_strategy_rating": "B+",
  "rating_rationale": "战略方向清晰，执行力相比2021年有明显改善，但产品侧短板和海外扩张不确定性制约评级上限",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_strategy(category: str, core_target: str, financials: dict, biz_model: dict) -> dict:
    print("  [4/4] 战略与管理层评估...")
    flags = financials.get("financial_quality_flags", [])
    dividend = financials.get("dividend_policy", {})
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"财务质量观察：{'; '.join(flags[:2])}\n"
            f"分红/回购情况：{dividend.get('history', '')}\n"
            f"商业模式核心驱动：{biz_model.get('profit_logic', {}).get('core_driver', '')}\n\n"
            "请评估该公司的战略清晰度、核心举措执行情况和管理层质量，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_STRATEGY,
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
    "1. 文风：卖方研报体，客观专业，有数据支撑\n"
    "2. 结构：四个小节——5.1商业模式、5.2单店经济模型、5.3财务复盘、5.4战略与管理层\n"
    "3. 数据：引用具体数字（%、亿元、次/天等），不凭空编造\n"
    "4. 投资视角：每节结尾给出1-2句投资含义\n"
    "5. 长度：每小节400-600字，总计1600-2400字\n"
    "6. 直接输出 Markdown，从 ## 5.1 开始，不含 JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    biz_model: dict, unit_econ: dict, financials: dict, strategy: dict,
) -> str:
    print("  [整合] 写作整合 Agent...")
    bundle = {
        "商业模式": biz_model,
        "单店经济模型": unit_econ,
        "历史财务复盘": financials,
        "战略与管理层": strategy,
    }
    return _generate(
        contents=(
            f"研究标的：{core_target}（品类：{category}）\n"
            f"研究深度：{research_depth}\n读者视角：{user_focus}\n\n"
            f"以下是四个子分析的结构化结果：\n\n"
            f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
            "请据此撰写第五章正文，直接从 ## 5.1 商业模式 开始。"
        ),
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
        text = "\n".join(text.split("\n")[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e])
            except json.JSONDecodeError:
                pass
        print("  [警告] JSON 解析失败，保留原始文本")
        return {"raw_text": text, "parse_error": True}


def save_intermediate(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 已保存: {path}")


def load_prior_context(ch2: str, ch3: str, ch4: str) -> str:
    parts = []

    def _r(d: str, f: str) -> dict:
        p = Path(d) / f
        return json.load(open(p, encoding="utf-8")) if p.exists() else {}

    lc = _r(ch2, "s3_lifecycle.json")
    bt = _r(ch2, "s4_breakthrough.json")
    moat = _r(ch3, "s3_moat.json")
    out = _r(ch3, "s4_outlook.json")
    tam = _r(ch4, "s1_tam.json")

    if lc:
        parts.append(f"生命周期：{lc.get('lifecycle_stage','')}，{lc.get('valuation_implication','')}")
    if bt:
        parts.append(f"标的定位：{bt.get('core_target_position','')}")
    if moat:
        parts.append(f"护城河：{moat.get('moat_rating','')}，最大风险：{moat.get('biggest_moat_risk','')}")
    if out:
        tgt = out.get("core_target_outlook", {})
        parts.append(f"竞争展望：{tgt.get('position_change','')}，{tgt.get('rationale','')}")
    if tam:
        parts.append(f"SOM天花板：{tam.get('som',{}).get('som_ceiling_3yr','')}亿元")

    return "\n".join(parts) or "（无前置章节上下文）"


def build_final_md(category: str, core_target: str, body: str, results: dict) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason','需人工核查')}"
        for k, v in results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = f"# 第五章　公司深度分析\n\n> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    warn = (
        "\n> ⚠️ **人工核查提示**\n>\n" + "\n".join(f"> {w}" for w in warnings) + "\n\n"
        if warnings else ""
    )
    return header + warn + body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第五章自动化工作流")
    parser.add_argument("input")
    parser.add_argument("--output", default="output_chapter5.md")
    parser.add_argument("--intermediates-dir", default="intermediates_ch5")
    parser.add_argument("--ch2-dir", default="intermediates")
    parser.add_argument("--ch3-dir", default="intermediates_ch3")
    parser.add_argument("--ch4-dir", default="intermediates_ch4")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("错误：请先设置 GEMINI_API_KEY")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        inp = json.load(f)

    category       = inp["category"]
    core_target    = inp["core_target"]
    research_depth = inp.get("research_depth", "标准版")
    user_focus     = inp.get("user_focus", "二级市场")

    print(f"\n{'='*60}")
    print(f"IRA 第五章工作流：公司深度分析")
    print(f"品类: {category}　标的: {core_target}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    prior_context = load_prior_context(args.ch2_dir, args.ch3_dir, args.ch4_dir)
    if prior_context != "（无前置章节上下文）":
        print("  [✓] 已加载前置章节上下文")

    def _load_or_run(path: str, fn):
        p = Path(path)
        if p.exists():
            print(f"  [跳过] 加载已有结果: {path}")
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        result = fn()
        save_intermediate(result, path)
        return result

    biz_model = _load_or_run(
        str(inter_dir / "s1_biz_model.json"),
        lambda: run_biz_model(category, core_target, prior_context),
    )
    unit_econ = _load_or_run(
        str(inter_dir / "s2_unit_econ.json"),
        lambda: run_unit_economics(category, core_target, biz_model),
    )
    financials = _load_or_run(
        str(inter_dir / "s3_financials.json"),
        lambda: run_financials(category, core_target, unit_econ),
    )
    strategy = _load_or_run(
        str(inter_dir / "s4_strategy.json"),
        lambda: run_strategy(category, core_target, financials, biz_model),
    )

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        biz_model, unit_econ, financials, strategy,
    )

    all_results = {
        "商业模式": biz_model, "单店经济模型": unit_econ,
        "历史财务复盘": financials, "战略与管理层": strategy,
    }
    final_md = build_final_md(category, core_target, chapter_body, all_results)

    out = Path(args.output)
    with open(out, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n{'='*60}")
    print(f"完成！输出文件: {out}")
    print(f"中间结果目录: {inter_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
