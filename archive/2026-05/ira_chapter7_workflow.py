"""
IRA (Industry Research Agent) — 第七章自动化工作流
Chapter 7: 风险提示

用法:
    export GEMINI_API_KEY="AIza..."
    python3 ira_chapter7_workflow.py input.json
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

MODELS = [
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-001",
]

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

AI_BLACKLIST = [
    "值得注意的是", "不可否认", "毋庸置疑", "显而易见",
    "综上所述", "总的来说", "不难发现", "由此可见",
    "与此同时", "在此基础上", "从某种意义上说",
    "深度赋能", "闭环", "生态", "赋能", "底层逻辑",
    "顶层设计", "内卷", "躺平", "破圈", "出圈",
    "降维打击", "降本增效", "弯道超车",
]

_active_model = None


def _generate(contents: str, config: types.GenerateContentConfig, retries: int = 5) -> str:
    global _active_model
    seen = set()
    models_to_try = []
    for m in ([_active_model] if _active_model else []) + MODELS:
        if m not in seen:
            seen.add(m)
            models_to_try.append(m)

    for model in models_to_try:
        delay = 15
        switched = False
        for attempt in range(retries):
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=config)
                if _active_model != model:
                    print(f"  [模型] 使用 {model}")
                    _active_model = model
                return resp.text
            except (genai_errors.ServerError, genai_errors.ClientError) as e:
                code = getattr(e, "status_code", 0)
                if code == 503 and attempt < retries - 1:
                    print(f"  [重试] {model} 繁忙，等待 {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                elif code in (429, 503):
                    print(f"  [切换] {model} 不可用（{code}），尝试下一模型...")
                    switched = True
                    break
                else:
                    raise
        if not switched:
            break
    raise RuntimeError("所有可用模型均无法响应，请稍后重试")


# ---------------------------------------------------------------------------
# Sub-task 1: 宏观与行业风险
# ---------------------------------------------------------------------------

SYSTEM_MACRO = """你是一名资深卖方研究员，专注于消费行业风险评估。

【任务】：识别宏观经济和行业层面的核心风险，只输出 JSON，不含任何解释文字或 markdown 代码块。

【风险评估维度】
- 概率：高/中/低
- 冲击烈度：高/中/低（对公司业绩和估值的潜在冲击幅度）
- 发生时间窗口：短期（0-12个月）/ 中期（1-3年）/ 长期（3年+）
- 估值影响：触发该风险后目标价的下修幅度

输出 JSON 示例（严格按此结构）：
{
  "risk_category": "宏观与行业风险",
  "risks": [
    {
      "id": "M1",
      "name": "消费降级持续",
      "description": "宏观经济增速放缓，居民可支配收入增速下降，消费者向更低价格带迁移，中高端餐饮客单价承压",
      "probability": "中",
      "impact_severity": "高",
      "time_horizon": "短期",
      "trigger_indicator": "社会零售总额连续同比负增长，CPI中餐饮分项持续下滑",
      "business_impact": "翻台率和客单价双双承压，预计影响营收5-10%，净利润率下降2-3个百分点",
      "target_price_downside_pct": 20,
      "mitigation": "海底捞已推出更多低价套餐，但服务溢价逻辑在消费降级环境下存在挑战"
    },
    {
      "id": "M2",
      "name": "食品安全监管趋严",
      "description": "政府加强餐饮食品安全抽查和处罚力度，行业合规成本上升，门店整改可能导致短期关店",
      "probability": "中",
      "impact_severity": "中",
      "time_horizon": "短期",
      "trigger_indicator": "监管部门专项整治行动，媒体曝光食品安全事件",
      "business_impact": "若出现食品安全负面事件，短期客流下降20-30%，品牌修复需6-12个月",
      "target_price_downside_pct": 15,
      "mitigation": "海底捞供应链自控能力较强，历史食品安全记录相对良好"
    },
    {
      "id": "M3",
      "name": "火锅品类竞争加剧",
      "description": "区域品牌全国化扩张，新品牌通过差异化定位分流海底捞客群，价格战侵蚀行业利润率",
      "probability": "高",
      "impact_severity": "中",
      "time_horizon": "中期",
      "trigger_indicator": "同类品牌融资加速，海底捞同店销售增速转负",
      "business_impact": "市场份额流失1-2个百分点，客单价被迫下调3-5元",
      "target_price_downside_pct": 12,
      "mitigation": "海底捞护城河宽度仍领先，短期内市场地位难以被撼动"
    },
    {
      "id": "M4",
      "name": "劳动力成本上升",
      "description": "最低工资标准持续上调，服务型餐饮人力密集，用工成本刚性上升，压缩四墙利润率",
      "probability": "高",
      "impact_severity": "中",
      "time_horizon": "中期",
      "trigger_indicator": "各省市最低工资标准年均涨幅超5%",
      "business_impact": "员工成本占比每上升1个百分点，净利润率下降约0.8个百分点",
      "target_price_downside_pct": 8,
      "mitigation": "数字化运营和智能化设备投入可部分对冲，但短期效果有限"
    }
  ],
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_macro_risks(category: str, core_target: str, prior_context: str) -> dict:
    print("  [1/4] 宏观与行业风险...")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n\n"
            f"前置章节摘要：\n{prior_context}\n\n"
            "请识别该公司面临的宏观经济和行业层面风险，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_MACRO,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 2: 公司经营风险
# ---------------------------------------------------------------------------

SYSTEM_OPERATIONAL = """你是一名资深卖方研究员，专注于公司层面经营风险分析。

【任务】：识别核心标的在运营、战略和财务层面的特定风险，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析框架】
- 运营风险：门店执行、供应链、服务质量维持
- 战略风险：扩张节奏、多元化失败、管理层变动
- 财务风险：现金流、负债、汇率（海外业务）

输出 JSON 示例（严格按此结构）：
{
  "risk_category": "公司经营风险",
  "risks": [
    {
      "id": "O1",
      "name": "扩张纪律再次失守",
      "description": "公司在盈利修复后可能重复2021年激进开店的错误，新店质量参差不齐拉低整体翻台率",
      "probability": "低",
      "impact_severity": "高",
      "time_horizon": "中期",
      "trigger_indicator": "单季度新开店>100家，或新店翻台率低于3.0次/天",
      "business_impact": "大规模开店摊薄每股盈利，重演2021年亏损周期",
      "target_price_downside_pct": 25,
      "mitigation": "管理层已建立更严格的开店审批标准，啄木鸟计划的教训应有约束效果"
    },
    {
      "id": "O2",
      "name": "服务体系质量下滑",
      "description": "随着员工规模扩大和新生代员工价值观变化，维持极致服务SOP的难度上升，口碑护城河面临侵蚀",
      "probability": "中",
      "impact_severity": "中",
      "time_horizon": "中期",
      "trigger_indicator": "大众点评/美团评分持续下滑，社交媒体负面评价增加",
      "business_impact": "品牌溢价收窄，客单价下行压力加大",
      "target_price_downside_pct": 12,
      "mitigation": "师徒制激励机制和区域化管理有助于维持服务一致性"
    },
    {
      "id": "O3",
      "name": "关联方风险（颐海国际）",
      "description": "海底捞与颐海国际（3097.HK）之间的关联交易定价公允性存疑，若颐海向外部扩张影响海底捞的供应链优先级",
      "probability": "低",
      "impact_severity": "中",
      "time_horizon": "长期",
      "trigger_indicator": "颐海国际第三方客户收入占比超过40%，对海底捞供货条款发生变化",
      "business_impact": "食材成本上升，供应链稳定性受损",
      "target_price_downside_pct": 8,
      "mitigation": "蜀海集团作为备用供应链，颐海国际目前仍以海底捞需求为优先"
    },
    {
      "id": "O4",
      "name": "海外业务亏损扩大",
      "description": "海外门店本地化难度大，食材供应链重建成本高，文化适应周期长，持续亏损可能拖累整体业绩",
      "probability": "中",
      "impact_severity": "低",
      "time_horizon": "中期",
      "trigger_indicator": "海外门店亏损超过3亿元人民币，关店率超过10%",
      "business_impact": "海外业务占比约5-8%，亏损扩大对EPS影响有限，但影响市场对全球化预期的定价",
      "target_price_downside_pct": 5,
      "mitigation": "海外扩张集中在华人聚居地区，文化适配难度相对较低"
    },
    {
      "id": "O5",
      "name": "创始人退出后的文化传承风险",
      "description": "张勇淡出管理层后，海底捞独特的企业文化和服务基因能否在新管理层领导下得到传承，存在不确定性",
      "probability": "中",
      "impact_severity": "中",
      "time_horizon": "长期",
      "trigger_indicator": "关键管理层流失，员工满意度调查显著下滑",
      "business_impact": "文化稀释将逐步影响服务质量和品牌定位",
      "target_price_downside_pct": 10,
      "mitigation": "杨利娟接任后运营表现良好，内部晋升机制保障文化延续性"
    }
  ],
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_operational_risks(category: str, core_target: str, macro_risks: dict) -> dict:
    print("  [2/4] 公司经营风险...")
    top_macro = [r["name"] for r in macro_risks.get("risks", [])[:2]]
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"主要宏观风险（已识别）：{', '.join(top_macro)}\n\n"
            "请识别该公司在运营、战略和财务层面的特定风险，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_OPERATIONAL,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 3: 估值与评级下行风险
# ---------------------------------------------------------------------------

SYSTEM_VALUATION_RISK = """你是一名资深卖方研究员，专注于投资评级下行风险场景分析。

【任务】：量化分析可能导致目标价下修或评级降级的情景，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析框架】
- 定义2-3个悲观情景（Bear Case Scenarios）
- 每个情景对应的触发条件、对盈利预测的影响、目标价修正幅度
- 分析当前估值是否已充分反映风险溢价

输出 JSON 示例（严格按此结构）：
{
  "risk_category": "估值与评级下行风险",
  "base_target_price_hkd": 21.5,
  "base_rating": "买入",
  "downside_scenarios": [
    {
      "scenario_name": "温和熊市",
      "trigger": "翻台率无法超越3.5次/天，客单价同比下降3-5%，宏观消费持续疲软",
      "probability_pct": 30,
      "revenue_impact_pct": -8,
      "eps_impact_pct": -20,
      "revised_target_price_hkd": 16.5,
      "revised_rating": "中性",
      "key_metric_to_watch": "季度翻台率是否维持在3.5次以上"
    },
    {
      "scenario_name": "深度熊市",
      "trigger": "食品安全重大事件+消费降级双重打击，翻台率跌破3.0次/天，管理层出现重大不稳定",
      "probability_pct": 10,
      "revenue_impact_pct": -20,
      "eps_impact_pct": -50,
      "revised_target_price_hkd": 10.0,
      "revised_rating": "减持",
      "key_metric_to_watch": "食品安全相关新闻，管理层人事变动公告"
    }
  ],
  "valuation_support_analysis": {
    "current_price_hkd": 16.8,
    "downside_to_book_value_pct": -15,
    "implied_floor_price_hkd": 12.0,
    "floor_basis": "基于2023年净现金35.5亿元+门店资产清算价值的资产支撑底",
    "risk_reward_ratio": "当前风险回报比约3:1（上涨28% vs 下跌最大约25%）",
    "valuation_risk_comment": "估值已在一定程度上反映经营修复预期，安全边际尚可"
  },
  "rating_change_triggers": {
    "upgrade_to_strong_buy": "翻台率连续两季度超过4.2次/天，且同店销售增长超10%",
    "downgrade_to_neutral": "翻台率连续两季度低于3.3次/天，或客单价同比降幅超5%",
    "downgrade_to_sell": "出现重大食品安全事件，或管理层宣布大规模激进扩张计划"
  },
  "need_human_calibration": true,
  "calibration_reason": "目标价和当前股价需以最新市场数据更新"
}"""


def run_valuation_risks(
    category: str, core_target: str, macro_risks: dict, operational_risks: dict
) -> dict:
    print("  [3/4] 估值与评级下行风险...")
    # 取所有风险中冲击最大的两个
    all_risks = macro_risks.get("risks", []) + operational_risks.get("risks", [])
    top_risks = sorted(all_risks, key=lambda r: r.get("target_price_downside_pct", 0), reverse=True)[:3]
    top_names = [r["name"] for r in top_risks]
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"最大风险项（按目标价冲击排序）：{', '.join(top_names)}\n"
            f"当前目标价：HKD 21.5（买入评级）\n\n"
            "请构建悲观情景分析，量化目标价下修幅度和评级降级触发条件，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_VALUATION_RISK,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 4: 风险矩阵汇总
# ---------------------------------------------------------------------------

SYSTEM_MATRIX = """你是一名资深卖方研究员，负责汇总风险评估并给出综合结论。

【任务】：将所有已识别风险汇总为风险矩阵，给出综合风险等级和监控指标清单，只输出 JSON，不含任何解释文字或 markdown 代码块。

【风险矩阵定义】
- 横轴：概率（低/中/高）
- 纵轴：冲击烈度（低/中/高）
- 综合风险等级：
  - 高概率×高冲击 = 关键风险（Red）
  - 中概率×高冲击 或 高概率×中冲击 = 重要风险（Amber）
  - 其余 = 一般风险（Green）

输出 JSON 示例（严格按此结构）：
{
  "overall_risk_level": "中等",
  "risk_matrix": [
    {"id": "M1", "name": "消费降级持续", "probability": "中", "impact": "高", "level": "Amber"},
    {"id": "M2", "name": "食品安全事件", "probability": "中", "impact": "高", "level": "Amber"},
    {"id": "M3", "name": "竞争加剧", "probability": "高", "impact": "中", "level": "Amber"},
    {"id": "M4", "name": "劳动力成本上升", "probability": "高", "impact": "中", "level": "Amber"},
    {"id": "O1", "name": "扩张纪律失守", "probability": "低", "impact": "高", "level": "Green"},
    {"id": "O2", "name": "服务质量下滑", "probability": "中", "impact": "中", "level": "Green"},
    {"id": "O3", "name": "关联方风险", "probability": "低", "impact": "中", "level": "Green"},
    {"id": "O4", "name": "海外亏损扩大", "probability": "中", "impact": "低", "level": "Green"},
    {"id": "O5", "name": "文化传承风险", "probability": "中", "impact": "中", "level": "Green"}
  ],
  "key_monitoring_indicators": [
    {
      "indicator": "季度平均翻台率",
      "frequency": "季报",
      "bull_threshold": ">4.0次/天",
      "bear_threshold": "<3.3次/天",
      "action": "低于3.3次触发评级下调至中性"
    },
    {
      "indicator": "同店销售增长（SSSG）",
      "frequency": "季报",
      "bull_threshold": ">5%",
      "bear_threshold": "<-3%",
      "action": "连续两季度负增长触发模型复核"
    },
    {
      "indicator": "客单价同比变化",
      "frequency": "半年报/年报",
      "bull_threshold": "持平或正增长",
      "bear_threshold": "<-5%",
      "action": "降幅超5%下修盈利预测"
    },
    {
      "indicator": "新开门店数量及质量",
      "frequency": "季报",
      "bull_threshold": "新店翻台率>3.5次",
      "bear_threshold": "单季新开>80家或新店翻台<3.0次",
      "action": "触发扩张纪律风险预警"
    },
    {
      "indicator": "食品安全事件",
      "frequency": "实时监控",
      "bull_threshold": "无重大事件",
      "bear_threshold": "任何涉及海底捞的重大食品安全媒体报道",
      "action": "立即启动风险评估，必要时暂停买入建议"
    }
  ],
  "risk_conclusion": "综合来看，海底捞当前面临的主要风险集中在宏观消费环境和竞争格局层面，公司自身经营风险在管理层调整后有所下降。核心投资逻辑（翻台率恢复+盈利弹性）尚未受到系统性威胁，买入评级维持，但需密切跟踪翻台率和客单价的季度数据。",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_risk_matrix(
    category: str, core_target: str,
    macro_risks: dict, operational_risks: dict, valuation_risks: dict
) -> dict:
    print("  [4/4] 风险矩阵汇总...")
    # 整合所有风险ID和名称
    all_risks = macro_risks.get("risks", []) + operational_risks.get("risks", [])
    risk_list = [f"{r['id']} {r['name']}（概率：{r['probability']}，冲击：{r['impact_severity']}）"
                 for r in all_risks]
    downside = valuation_risks.get("downside_scenarios", [])
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n\n"
            f"已识别风险清单：\n" + "\n".join(risk_list) + "\n\n"
            f"悲观情景：{', '.join(s['scenario_name'] for s in downside)}\n\n"
            "请汇总风险矩阵，给出每项风险的综合等级（Red/Amber/Green）和监控指标清单，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_MATRIX,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# 整合写作 Agent
# ---------------------------------------------------------------------------

SYSTEM_INTEGRATION = (
    "你是一名资深卖方研究员，将风险分析数据转化为专业研报文字。\n\n"
    "【写作要求】\n"
    "1. 文风：卖方研报体，客观，不过度悲观也不轻描淡写\n"
    "2. 结构：四个小节——7.1宏观与行业风险、7.2公司经营风险、7.3估值下行情景、7.4风险监控指标\n"
    "3. 数据：引用具体的冲击幅度（%）和触发指标\n"
    "4. 7.3节必须包含：温和熊市和深度熊市的修正目标价和评级\n"
    "5. 长度：每小节350-500字，总计1400-2000字\n"
    "6. 直接输出Markdown，从 ## 7.1 开始，不含JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    macro_risks: dict, operational_risks: dict, valuation_risks: dict, risk_matrix: dict,
) -> str:
    print("  [整合] 写作整合 Agent...")
    bundle = {
        "宏观与行业风险": macro_risks,
        "公司经营风险": operational_risks,
        "估值下行情景": valuation_risks,
        "风险矩阵": risk_matrix,
    }
    return _generate(
        contents=(
            f"研究标的：{core_target}（品类：{category}）\n"
            f"研究深度：{research_depth}\n读者视角：{user_focus}\n\n"
            f"以下是四个子分析的结构化结果：\n\n"
            f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
            "请据此撰写第七章完整正文，直接从 ## 7.1 宏观与行业风险 开始。"
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


def load_prior_context(ch3: str, ch5: str, ch6: str) -> str:
    parts = []

    def _r(d: str, f: str) -> dict:
        p = Path(d) / f
        return json.load(open(p, encoding="utf-8")) if p.exists() else {}

    moat  = _r(ch3, "s3_moat.json")
    strat = _r(ch5, "s4_strategy.json")
    rating = _r(ch6, "s4_rating.json")

    if moat:
        parts.append(f"护城河：{moat.get('moat_rating','')}，最大风险：{moat.get('biggest_moat_risk','')}")
    if strat:
        risks = strat.get("strategy_risk_matrix", [])
        if risks:
            parts.append(f"战略风险：{'; '.join(r['risk'] for r in risks[:2])}")
    if rating:
        parts.append(
            f"目标价：HKD {rating.get('weighted_target_price_hkd','')}，"
            f"评级：{rating.get('rating','')}，"
            f"风险因素：{'; '.join(rating.get('key_risks_to_rating', [])[:2])}"
        )
    return "\n".join(parts) or "（无前置章节上下文）"


def build_final_md(category: str, core_target: str, body: str, results: dict) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason','需人工核查')}"
        for k, v in results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = f"# 第七章　风险提示\n\n> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    warn = (
        "\n> ⚠️ **人工核查提示**\n>\n" + "\n".join(f"> {w}" for w in warnings) + "\n\n"
        if warnings else ""
    )
    return header + warn + body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第七章自动化工作流")
    parser.add_argument("input")
    parser.add_argument("--output", default="output_chapter7.md")
    parser.add_argument("--intermediates-dir", default="intermediates_ch7")
    parser.add_argument("--ch3-dir", default="intermediates_ch3")
    parser.add_argument("--ch5-dir", default="intermediates_ch5")
    parser.add_argument("--ch6-dir", default="intermediates_ch6")
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
    print(f"IRA 第七章工作流：风险提示")
    print(f"品类: {category}　标的: {core_target}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    prior = load_prior_context(args.ch3_dir, args.ch5_dir, args.ch6_dir)
    if prior != "（无前置章节上下文）":
        print("  [✓] 已加载前置章节上下文（3/5/6章）")

    def _load_or_run(path: str, fn):
        p = Path(path)
        if p.exists():
            print(f"  [跳过] 加载已有结果: {path}")
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        result = fn()
        save_intermediate(result, path)
        return result

    macro_risks = _load_or_run(
        str(inter_dir / "s1_macro.json"),
        lambda: run_macro_risks(category, core_target, prior),
    )
    operational_risks = _load_or_run(
        str(inter_dir / "s2_operational.json"),
        lambda: run_operational_risks(category, core_target, macro_risks),
    )
    valuation_risks = _load_or_run(
        str(inter_dir / "s3_valuation_risk.json"),
        lambda: run_valuation_risks(category, core_target, macro_risks, operational_risks),
    )
    risk_matrix = _load_or_run(
        str(inter_dir / "s4_matrix.json"),
        lambda: run_risk_matrix(category, core_target, macro_risks, operational_risks, valuation_risks),
    )

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        macro_risks, operational_risks, valuation_risks, risk_matrix,
    )

    all_results = {
        "宏观风险": macro_risks, "经营风险": operational_risks,
        "估值风险": valuation_risks, "风险矩阵": risk_matrix,
    }
    final_md = build_final_md(category, core_target, chapter_body, all_results)

    out = Path(args.output)
    with open(out, "w", encoding="utf-8") as f:
        f.write(final_md)

    print(f"\n{'='*60}")
    print(f"完成！输出文件: {out}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
