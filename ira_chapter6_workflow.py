"""
IRA (Industry Research Agent) — 第六章自动化工作流
Chapter 6: 估值

用法:
    export GEMINI_API_KEY="AIza..."
    python3 ira_chapter6_workflow.py input.json
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

# 按优先级自动切换可用模型
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
            break  # non-quota/503 error already raised above
    raise RuntimeError("所有可用模型均无法响应，请稍后重试")


# ---------------------------------------------------------------------------
# Sub-task 1: 估值方法论选择
# ---------------------------------------------------------------------------

SYSTEM_METHODOLOGY = """你是一名资深卖方研究员，专注于消费/餐饮行业估值分析。

【任务】：为核心标的选择合适的估值方法并说明理由，只输出 JSON，不含任何解释文字或 markdown 代码块。

【常用估值方法】
- EV/EBITDA：适合重资产、有折旧摊销的连锁餐饮企业，消除资本结构差异
- P/E：适合盈利稳定的成熟期企业，直觉友好，但受会计政策影响
- P/S：适合亏损或盈利波动大的阶段，以营收作为锚定
- DCF：绝对估值，捕捉长期现金流价值，对假设高度敏感
- EV/门店数：同业横向对比，反映市场对单店价值的定价
- 不适用方法：PB（轻资产逻辑不适用重资产餐饮）

输出 JSON 示例（严格按此结构）：
{
  "primary_methods": [
    {
      "method": "EV/EBITDA",
      "rationale": "连锁餐饮标准估值方法，消除租赁会计（IFRS 16）折旧差异，便于跨市场横向对比",
      "weight_pct": 40,
      "applicable_scenario": "当前阶段最核心的估值锚"
    },
    {
      "method": "DCF",
      "rationale": "捕捉翻台率恢复、门店扩张和利润率改善的长期价值，适合判断内在价值是否被低估",
      "weight_pct": 40,
      "applicable_scenario": "判断安全边际和长期持有价值"
    },
    {
      "method": "P/E",
      "rationale": "辅助参考，盈利恢复后PE估值回归合理区间，可与历史估值带对比",
      "weight_pct": 20,
      "applicable_scenario": "辅助验证，当净利润率稳定后更有效"
    }
  ],
  "excluded_methods": [
    {
      "method": "P/B",
      "reason": "重资产直营模式导致账面净资产受租赁负债影响大，PB估值对餐饮企业不具参考价值"
    },
    {
      "method": "P/S",
      "reason": "当前海底捞已实现稳定盈利，PS估值意义有限，更适合盈利不稳定阶段"
    }
  ],
  "key_valuation_driver": "翻台率恢复进度是核心变量，每提升0.1次/天对应约5-8%的估值上修空间",
  "valuation_challenge": "IFRS 16租赁负债导致EBITDA和EV口径需统一处理，否则跨市场比较失真",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_methodology(category: str, core_target: str, prior_context: str) -> dict:
    print("  [1/4] 估值方法论选择...")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n\n"
            f"前置章节摘要：\n{prior_context}\n\n"
            "请为该公司选择合适的估值方法并说明理由，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_METHODOLOGY,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 2: 相对估值（可比公司法）
# ---------------------------------------------------------------------------

SYSTEM_COMPS = """你是一名资深卖方研究员，专注于可比公司估值分析（Comparable Company Analysis）。

【任务】：构建可比公司估值矩阵，得出核心标的的相对估值区间，只输出 JSON，不含任何解释文字或 markdown 代码块。

【可比公司选择标准】
1. 同品类或同类型连锁餐饮（火锅/中式连锁）
2. 港股/A股/美股上市
3. 规模和成熟度具备可比性

【关键倍数】
- EV/EBITDA（2024E）：核心
- P/E（2024E）：辅助
- EV/门店数：验证单店市值

输出 JSON 示例（严格按此结构）：
{
  "comp_set": [
    {
      "company": "海底捞",
      "ticker": "6862.HK",
      "role": "核心标的",
      "market_cap_hkd_bn": 180,
      "ev_hkd_bn": 165,
      "ebitda_2024e_cny_bn": 85,
      "ev_ebitda_2024e": 13.5,
      "pe_2024e": 18.0,
      "store_count": 1374,
      "ev_per_store_hkd_mn": 120,
      "revenue_growth_2024e_pct": 10,
      "note": "核心标的，估值相对同业仍有折价"
    },
    {
      "company": "呷哺呷哺",
      "ticker": "0520.HK",
      "role": "同业对标",
      "market_cap_hkd_bn": 15,
      "ev_hkd_bn": 18,
      "ebitda_2024e_cny_bn": 8,
      "ev_ebitda_2024e": 9.5,
      "pe_2024e": null,
      "store_count": 800,
      "ev_per_store_hkd_mn": 22,
      "revenue_growth_2024e_pct": 5,
      "note": "中低端，盈利能力弱，折价合理"
    },
    {
      "company": "捞王",
      "ticker": "9622.HK",
      "role": "同业对标",
      "market_cap_hkd_bn": 5,
      "ev_hkd_bn": 4.5,
      "ebitda_2024e_cny_bn": 2.5,
      "ev_ebitda_2024e": 8.0,
      "pe_2024e": 12.0,
      "store_count": 180,
      "ev_per_store_hkd_mn": 25,
      "revenue_growth_2024e_pct": 8,
      "note": "细分赛道，规模小，流动性折价"
    },
    {
      "company": "百胜中国",
      "ticker": "9987.HK",
      "role": "跨品类参考",
      "market_cap_hkd_bn": 190,
      "ev_hkd_bn": 185,
      "ebitda_2024e_cny_bn": 120,
      "ev_ebitda_2024e": 10.5,
      "pe_2024e": 22.0,
      "store_count": 13000,
      "ev_per_store_hkd_mn": 14,
      "revenue_growth_2024e_pct": 6,
      "note": "西式快餐龙头，护城河更强，估值溢价合理"
    },
    {
      "company": "九毛九",
      "ticker": "9922.HK",
      "role": "同业对标",
      "market_cap_hkd_bn": 12,
      "ev_hkd_bn": 10,
      "ebitda_2024e_cny_bn": 6,
      "ev_ebitda_2024e": 7.5,
      "pe_2024e": 14.0,
      "store_count": 550,
      "ev_per_store_hkd_mn": 18,
      "revenue_growth_2024e_pct": 12,
      "note": "太二酸菜鱼差异化定位，增速更快"
    }
  ],
  "peer_median": {
    "ev_ebitda": 9.0,
    "pe": 14.5,
    "ev_per_store_hkd_mn": 21
  },
  "target_justified_multiples": {
    "ev_ebitda_justified": 13.0,
    "pe_justified": 20.0,
    "premium_rationale": "海底捞护城河最强（宽护城河评级）、规模最大、翻台率恢复弹性最大，理应享有同业溢价30-50%"
  },
  "implied_price_range_hkd": {
    "low": 16.0,
    "mid": 19.5,
    "high": 23.0,
    "basis": "EV/EBITDA 11-15x区间对应目标价范围"
  },
  "need_human_calibration": true,
  "calibration_reason": "市值、EV和EBITDA数据需以最新财报和Wind/Bloomberg共识预测核实"
}"""


def run_comps(category: str, core_target: str, methodology: dict, prior_context: str) -> dict:
    print("  [2/4] 相对估值——可比公司法...")
    primary = methodology.get("primary_methods", [])
    driver = methodology.get("key_valuation_driver", "")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"主要估值方法：{', '.join(m['method'] for m in primary)}\n"
            f"核心估值驱动：{driver}\n\n"
            f"前置章节摘要：\n{prior_context}\n\n"
            "请构建可比公司估值矩阵，得出相对估值区间，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_COMPS,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 3: DCF 绝对估值
# ---------------------------------------------------------------------------

SYSTEM_DCF = """你是一名资深卖方研究员，专注于餐饮企业DCF估值建模。

【任务】：构建核心标的的DCF估值模型，给出关键假设和目标价，只输出 JSON，不含任何解释文字或 markdown 代码块。

【DCF框架】
- 预测期：5年（2024E-2028E）显式预测
- 终值：采用永续增长法（Gordon Growth Model）
- 折现率：WACC（加权平均资本成本）
- 自由现金流：FCFF = EBIT×(1-税率) + 折旧摊销 - 资本支出 - 营运资本变化

【三情景分析】：牛市/基准/熊市

输出 JSON 示例（严格按此结构）：
{
  "model_currency": "港元（HKD），以人民币财务数据按汇率0.88换算",
  "wacc_assumptions": {
    "risk_free_rate_pct": 4.0,
    "equity_risk_premium_pct": 6.5,
    "beta": 0.95,
    "cost_of_equity_pct": 10.2,
    "cost_of_debt_pct": 3.5,
    "tax_rate_pct": 15,
    "target_debt_ratio_pct": 10,
    "wacc_pct": 9.6
  },
  "scenarios": [
    {
      "name": "牛市情景",
      "probability_pct": 25,
      "key_assumptions": {
        "revenue_cagr_2024_2028_pct": 12,
        "terminal_ebit_margin_pct": 14,
        "terminal_growth_rate_pct": 3.0,
        "table_turn_2026e": 4.2,
        "new_stores_per_year": 100
      },
      "fcff_2024e_cny_bn": 55,
      "fcff_2028e_cny_bn": 80,
      "terminal_value_hkd_bn": 320,
      "equity_value_hkd_bn": 280,
      "shares_outstanding_bn": 11.5,
      "intrinsic_value_per_share_hkd": 24.3,
      "scenario_description": "翻台率快速恢复至4.2次+，同店销售正增长，海外扩张超预期"
    },
    {
      "name": "基准情景",
      "probability_pct": 50,
      "key_assumptions": {
        "revenue_cagr_2024_2028_pct": 8,
        "terminal_ebit_margin_pct": 11,
        "terminal_growth_rate_pct": 2.5,
        "table_turn_2026e": 3.8,
        "new_stores_per_year": 50
      },
      "fcff_2024e_cny_bn": 48,
      "fcff_2028e_cny_bn": 62,
      "terminal_value_hkd_bn": 230,
      "equity_value_hkd_bn": 200,
      "shares_outstanding_bn": 11.5,
      "intrinsic_value_per_share_hkd": 17.4,
      "scenario_description": "翻台率稳健恢复至3.8-4.0，门店适度扩张，利润率小幅改善"
    },
    {
      "name": "熊市情景",
      "probability_pct": 25,
      "key_assumptions": {
        "revenue_cagr_2024_2028_pct": 3,
        "terminal_ebit_margin_pct": 7,
        "terminal_growth_rate_pct": 1.5,
        "table_turn_2026e": 3.2,
        "new_stores_per_year": 10
      },
      "fcff_2024e_cny_bn": 38,
      "fcff_2028e_cny_bn": 42,
      "terminal_value_hkd_bn": 130,
      "equity_value_hkd_bn": 110,
      "shares_outstanding_bn": 11.5,
      "intrinsic_value_per_share_hkd": 9.6,
      "scenario_description": "消费降级持续，翻台率无法回升，客单价承压，盈利能力受损"
    }
  ],
  "probability_weighted_value_hkd": 17.2,
  "sensitivity_table": {
    "description": "WACC vs. 终值增长率的目标价敏感性（基准情景）",
    "wacc_range": [8.5, 9.0, 9.6, 10.0, 10.5],
    "tgr_range": [1.5, 2.0, 2.5, 3.0, 3.5],
    "note": "WACC每+1%，内在价值约下降12-15%；终值增长率每+0.5%，内在价值约上升6-8%"
  },
  "need_human_calibration": true,
  "calibration_reason": "WACC、FCFF和股本数量需以最新数据校正；终值增长率假设对结果影响显著"
}"""


def run_dcf(category: str, core_target: str, comps: dict, prior_context: str) -> dict:
    print("  [3/4] DCF 绝对估值...")
    comp_mid = comps.get("implied_price_range_hkd", {}).get("mid", "")
    premium = comps.get("target_justified_multiples", {}).get("premium_rationale", "")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"相对估值中枢：HKD {comp_mid}\n"
            f"溢价理由：{premium}\n\n"
            f"前置章节摘要：\n{prior_context}\n\n"
            "请构建三情景DCF估值模型，给出内在价值区间，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_DCF,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 4: 目标价测算与投资评级
# ---------------------------------------------------------------------------

SYSTEM_RATING = """你是一名资深卖方研究员，负责出具最终投资评级和目标价。

【任务】：综合相对估值和DCF估值，给出目标价区间、12个月目标价和投资评级，只输出 JSON，不含任何解释文字或 markdown 代码块。

【评级标准】
- 买入（Buy）：12个月预期总回报 > 15%（含股息）
- 增持（Outperform）：12个月预期总回报 10-15%
- 中性（Neutral）：12个月预期总回报 0-10%
- 减持（Underperform）：12个月预期总回报 < 0%

【目标价确定方法】
- 相对估值结果权重40%
- DCF基准情景结果权重40%
- DCF概率加权结果权重20%
- 取加权平均后四舍五入至0.5港元

输出 JSON 示例（严格按此结构）：
{
  "current_price_hkd": 14.5,
  "price_date": "2024年估算",
  "valuation_summary": [
    {"method": "相对估值（EV/EBITDA中枢）", "weight_pct": 40, "implied_value_hkd": 19.5},
    {"method": "DCF基准情景", "weight_pct": 40, "implied_value_hkd": 17.4},
    {"method": "DCF概率加权", "weight_pct": 20, "implied_value_hkd": 17.2}
  ],
  "weighted_target_price_hkd": 18.5,
  "target_price_range_hkd": {"low": 16.0, "mid": 18.5, "high": 22.0},
  "upside_pct": 27.6,
  "dividend_yield_pct": 2.5,
  "total_return_pct": 30.1,
  "rating": "买入",
  "rating_rationale": "翻台率恢复路径清晰，2023年盈利大幅改善验证运营韧性，护城河完整，当前估值相对内在价值仍有折价，安全边际充足",
  "key_catalysts": [
    "季度翻台率持续超预期（>4.0次/天）",
    "2024年H2新开店数量超市场预期",
    "颐海国际零售端放量带动估值重估",
    "管理层宣布提升分红比例或加大回购"
  ],
  "key_risks_to_rating": [
    "消费降级持续，翻台率无法回升至4.0以上，目标价下修至16港元",
    "竞争加剧导致客单价承压，利润率改善受阻",
    "海外扩张失利，产生大额减值"
  ],
  "rating_change": "首次覆盖",
  "need_human_calibration": true,
  "calibration_reason": "当前股价需以实时行情核实；目标价应结合最新一致预期EPS/EBITDA更新"
}"""


def run_rating(
    category: str, core_target: str, comps: dict, dcf: dict
) -> dict:
    print("  [4/4] 目标价测算与投资评级...")
    comp_range = comps.get("implied_price_range_hkd", {})
    dcf_base = next(
        (s for s in dcf.get("scenarios", []) if "基准" in s.get("name", "")), {}
    )
    dcf_pw = dcf.get("probability_weighted_value_hkd", "")
    text = _generate(
        contents=(
            f"品类：{category}\n核心标的：{core_target}\n"
            f"相对估值区间：HKD {comp_range.get('low','')} - {comp_range.get('high','')}\n"
            f"DCF基准情景内在价值：HKD {dcf_base.get('intrinsic_value_per_share_hkd','')}\n"
            f"DCF概率加权价值：HKD {dcf_pw}\n\n"
            "请综合以上两种估值方法，给出目标价和投资评级，只输出 JSON。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_RATING,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# 整合写作 Agent
# ---------------------------------------------------------------------------

SYSTEM_INTEGRATION = (
    "你是一名资深卖方研究员，将结构化估值数据转化为专业研报文字。\n\n"
    "【写作要求】\n"
    "1. 文风：卖方研报体，逻辑严谨，数据驱动\n"
    "2. 结构：四个小节——6.1估值方法论、6.2相对估值、6.3DCF绝对估值、6.4目标价与评级\n"
    "3. 数据：引用具体数字（港元、倍数、%），不凭空编造\n"
    "4. 6.4节必须明确写出：目标价 HKD XX、评级：买入/中性/减持\n"
    "5. 长度：每小节400-600字，总计1600-2400字\n"
    "6. 直接输出Markdown，从 ## 6.1 开始，不含JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    methodology: dict, comps: dict, dcf: dict, rating: dict,
) -> str:
    print("  [整合] 写作整合 Agent...")
    bundle = {
        "估值方法论": methodology,
        "相对估值（可比公司法）": comps,
        "DCF绝对估值": dcf,
        "目标价与评级": rating,
    }
    return _generate(
        contents=(
            f"研究标的：{core_target}（品类：{category}）\n"
            f"研究深度：{research_depth}\n读者视角：{user_focus}\n\n"
            f"以下是四个子分析的结构化结果：\n\n"
            f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
            "请据此撰写第六章完整正文，直接从 ## 6.1 估值方法论 开始。"
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


def load_prior_context(ch2: str, ch3: str, ch4: str, ch5: str) -> str:
    parts = []

    def _r(d: str, f: str) -> dict:
        p = Path(d) / f
        return json.load(open(p, encoding="utf-8")) if p.exists() else {}

    lc  = _r(ch2, "s3_lifecycle.json")
    moat = _r(ch3, "s3_moat.json")
    tam  = _r(ch4, "s1_tam.json")
    fin  = _r(ch5, "s3_financials.json")
    strat = _r(ch5, "s4_strategy.json")

    if lc:
        parts.append(f"生命周期：{lc.get('lifecycle_stage','')}，{lc.get('valuation_implication','')}")
    if moat:
        parts.append(f"护城河：{moat.get('moat_rating','')}（{moat.get('total_score','')}/{moat.get('max_score','')}分）")
    if tam:
        parts.append(f"SOM天花板：{tam.get('som',{}).get('som_ceiling_3yr','')}亿元")
    if fin:
        data = fin.get("annual_data", [])
        last = data[-1] if data else {}
        parts.append(
            f"最新财年（{last.get('year','')}）：营收{last.get('revenue','')}亿，净利润率{last.get('net_margin_pct','')}%，翻台率{last.get('table_turns_avg','')}次"
        )
    if strat:
        parts.append(f"战略评级：{strat.get('overall_strategy_rating','')}，{strat.get('rating_rationale','')}")

    return "\n".join(parts) or "（无前置章节上下文）"


def build_final_md(category: str, core_target: str, body: str, results: dict) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason','需人工核查')}"
        for k, v in results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = f"# 第六章　估值\n\n> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    warn = (
        "\n> ⚠️ **人工核查提示**\n>\n" + "\n".join(f"> {w}" for w in warnings) + "\n\n"
        if warnings else ""
    )
    return header + warn + body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第六章自动化工作流")
    parser.add_argument("input")
    parser.add_argument("--output", default="output_chapter6.md")
    parser.add_argument("--intermediates-dir", default="intermediates_ch6")
    parser.add_argument("--ch2-dir", default="intermediates")
    parser.add_argument("--ch3-dir", default="intermediates_ch3")
    parser.add_argument("--ch4-dir", default="intermediates_ch4")
    parser.add_argument("--ch5-dir", default="intermediates_ch5")
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
    print(f"IRA 第六章工作流：估值")
    print(f"品类: {category}　标的: {core_target}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    prior = load_prior_context(args.ch2_dir, args.ch3_dir, args.ch4_dir, args.ch5_dir)
    if prior != "（无前置章节上下文）":
        print("  [✓] 已加载前置章节上下文（2-5章）")

    def _load_or_run(path: str, fn):
        p = Path(path)
        if p.exists():
            print(f"  [跳过] 加载已有结果: {path}")
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        result = fn()
        save_intermediate(result, path)
        return result

    methodology = _load_or_run(
        str(inter_dir / "s1_methodology.json"),
        lambda: run_methodology(category, core_target, prior),
    )
    comps = _load_or_run(
        str(inter_dir / "s2_comps.json"),
        lambda: run_comps(category, core_target, methodology, prior),
    )
    dcf = _load_or_run(
        str(inter_dir / "s3_dcf.json"),
        lambda: run_dcf(category, core_target, comps, prior),
    )
    rating = _load_or_run(
        str(inter_dir / "s4_rating.json"),
        lambda: run_rating(category, core_target, comps, dcf),
    )

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        methodology, comps, dcf, rating,
    )

    all_results = {
        "估值方法论": methodology, "相对估值": comps,
        "DCF估值": dcf, "目标价与评级": rating,
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
