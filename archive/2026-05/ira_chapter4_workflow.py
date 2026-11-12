"""
IRA (Industry Research Agent) — 第四章自动化工作流
Chapter 4: 市场空间

依赖: pip install google-genai
用法:
    export GEMINI_API_KEY="AIza..."
    python3 ira_chapter4_workflow.py input.json
    python3 ira_chapter4_workflow.py input.json --ch2-dir intermediates --ch3-dir intermediates_ch3
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
# Sub-task 1: TAM / SAM / SOM 测算
# ---------------------------------------------------------------------------

SYSTEM_TAM = """你是一名消费行业研究员，专注于市场规模测算。

【任务】：采用自上而下（Top-Down）和自下而上（Bottom-Up）两种方法，测算品类的市场规模，只输出 JSON，不含任何解释文字或 markdown 代码块。

【定义】
- TAM（Total Addressable Market）：品类全国潜在总市场规模（假设100%渗透）
- SAM（Serviceable Addressable Market）：当前技术/商业模式可服务到的市场（连锁品牌可触达的部分）
- SOM（Serviceable Obtainable Market）：核心标的在合理时间内可获取的市场份额

【Top-Down方法】：从餐饮总市场出发，逐层拆解到品类
【Bottom-Up方法】：从门店数量 × 单店营收 × 渗透率出发

输出 JSON 示例（严格按此结构）：
{
  "base_year": "2023",
  "currency": "亿元人民币",
  "top_down": {
    "china_catering_total_market": 52890,
    "hotpot_share_pct": 13.5,
    "tam_estimate": 7140,
    "data_source": "国家统计局+弗若斯特沙利文估算"
  },
  "bottom_up": {
    "total_hotpot_stores_china": 500000,
    "avg_annual_revenue_per_store_wan": 120,
    "tam_estimate": 6000,
    "data_source": "美团研究院+行业协会数据估算"
  },
  "tam_consensus": 6500,
  "sam": {
    "chainable_market_share_pct": 30,
    "sam_estimate": 1950,
    "rationale": "连锁化率约30%，即可标准化复制的品牌所能触达的市场"
  },
  "som": {
    "target_brand": "海底捞",
    "current_revenue": 414.5,
    "market_share_of_sam_pct": 21.3,
    "som_ceiling_3yr": 600,
    "rationale": "在翻台率恢复和门店适度扩张假设下，3年内营收天花板估算"
  },
  "market_growth_rate_cagr_pct": 5.5,
  "growth_rate_basis": "2023-2028E，参考餐饮行业整体增速+火锅连锁化提升",
  "need_human_calibration": true,
  "calibration_reason": "TAM需以最新国家统计局餐饮数据和第三方报告交叉验证"
}"""


def run_tam_analysis(category: str, core_target: str, ch2_context: str, ch3_context: str) -> dict:
    print("  [1/4] TAM/SAM/SOM 市场规模测算...")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n\n"
        f"第二章（品类本质）摘要：\n{ch2_context}\n\n"
        f"第三章（竞争格局）摘要：\n{ch3_context}\n\n"
        "请用Top-Down和Bottom-Up两种方法测算该品类市场规模，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_TAM,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 2: 增长驱动力拆解
# ---------------------------------------------------------------------------

SYSTEM_DRIVERS = """你是一名消费行业研究员，专注于增长动力分析。

【任务】：系统识别品类市场增长的核心驱动力，并量化各驱动力的贡献，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析框架】：增长 = 量（消费频次/人口/门店数） × 价（客单价） × 新场景扩张

【五大增长驱动力】
1. 消费者基本盘扩大（人口+城镇化）
2. 消费频次提升（品类渗透率提升）
3. 客单价升级（品质化/结构升级）
4. 连锁化率提升（从散店到连锁，释放规模价值）
5. 新场景/渠道扩张（零售化/外卖/下沉市场）

输出 JSON 示例（严格按此结构）：
{
  "growth_framework": "量价双轮+连锁化率提升",
  "drivers": [
    {
      "name": "城镇化与中产扩容",
      "type": "量",
      "contribution_to_growth_pct": 15,
      "current_status": "城镇化率66%，仍有5-8个百分点提升空间，新增城镇人口是火锅消费增量的核心来源",
      "upside_scenario": "三四线城市火锅连锁渗透率持续提升",
      "risk": "城镇化速度放缓，人口负增长压制长期总量"
    },
    {
      "name": "连锁化率提升",
      "type": "结构",
      "contribution_to_growth_pct": 35,
      "current_status": "火锅连锁化率约30%，低于全国餐饮连锁化率均值，提升空间大",
      "upside_scenario": "连锁化率提升至40-45%将释放约1500亿元市场规模",
      "risk": "连锁扩张过快导致单店质量下降，品牌价值受损"
    },
    {
      "name": "零售化与外卖渠道",
      "type": "新场景",
      "contribution_to_growth_pct": 20,
      "current_status": "火锅外卖渗透率约8%，预制火锅底料零售市场年增速>20%",
      "upside_scenario": "海底捞颐海国际零售端持续放量，非堂食贡献度提升",
      "risk": "外卖火锅体验折损，预制菜教育成本高"
    }
  ],
  "growth_inhibitors": [
    {
      "name": "消费降级压力",
      "description": "宏观经济压力下，消费者向更低价格带迁移，中高端火锅客流承压",
      "severity": "高"
    },
    {
      "name": "同质化竞争",
      "description": "品类创新放缓，差异化难度加大，价格战侵蚀行业整体利润率",
      "severity": "中"
    }
  ],
  "net_growth_outlook": "中性偏乐观：品类总量增速放缓至个位数，但连锁化率提升带来的结构性机会支撑头部品牌跑赢行业",
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_drivers_analysis(category: str, core_target: str, tam: dict) -> dict:
    print("  [2/4] 增长驱动力拆解...")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"市场规模（TAM）：{tam.get('tam_consensus', '')}亿元，CAGR：{tam.get('market_growth_rate_cagr_pct', '')}%\n"
        f"连锁化市场（SAM）：{tam.get('sam', {}).get('sam_estimate', '')}亿元\n\n"
        "请识别并量化该品类的核心增长驱动力，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_DRIVERS,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 3: 渗透率与天花板分析
# ---------------------------------------------------------------------------

SYSTEM_PENETRATION = """你是一名消费行业研究员，专注于市场渗透率与增长天花板分析。

【任务】：从多个维度评估品类的渗透率现状与增长天花板，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析维度】
1. 地理维度：一二三四线城市的渗透率对比
2. 人群维度：不同年龄/收入层的消费频次差异
3. 参照系：与可比海外市场（日本/美国）对比，判断成熟状态
4. 天花板测算：门店数量上限（基于人口/购买力/竞争密度）

输出 JSON 示例（严格按此结构）：
{
  "penetration_overview": "中国火锅市场渗透率较高，但区域和城市级别间存在显著差异",
  "by_city_tier": [
    {"tier": "一线城市", "penetration_level": "高", "chain_ratio_pct": 45, "growth_potential": "低", "note": "市场饱和，竞争激烈，增量来自存量品牌替换"},
    {"tier": "新一线/二线", "penetration_level": "中高", "chain_ratio_pct": 35, "growth_potential": "中", "note": "核心增量市场，连锁品牌加速渗透"},
    {"tier": "三线城市", "penetration_level": "中", "chain_ratio_pct": 20, "growth_potential": "高", "note": "消费升级明显，品牌火锅接受度快速提升"},
    {"tier": "四线及以下", "penetration_level": "低", "chain_ratio_pct": 10, "growth_potential": "高", "note": "长期白地，但客单价和盈利模型需适配"}
  ],
  "international_benchmarks": [
    {
      "country": "日本",
      "metric": "餐饮连锁化率",
      "value_pct": 55,
      "implication": "中国连锁化率仍有约20个百分点的长期提升空间"
    },
    {
      "country": "美国",
      "metric": "人均餐饮支出占可支配收入比",
      "value_pct": 6.5,
      "implication": "中国约4.5%，提升空间约2个百分点，对应约数千亿增量市场"
    }
  ],
  "store_count_ceiling": {
    "current_chain_stores_hotpot": 150000,
    "estimated_ceiling": 250000,
    "ceiling_basis": "基于日本连锁餐饮密度（每万人约15家连锁店）对标中国人口规模",
    "years_to_ceiling": "8-12年"
  },
  "core_target_ceiling": {
    "brand": "海底捞",
    "current_stores": 1374,
    "estimated_store_ceiling": 2200,
    "ceiling_basis": "参照麦当劳/肯德基在中国的门店密度模型，结合火锅品类特性",
    "revenue_at_ceiling_cny_bn": 650,
    "key_constraint": "优质点位供给有限，人均消费天花板约120-130元"
  },
  "need_human_calibration": true,
  "calibration_reason": "天花板估算高度依赖假设，需结合公司管理层指引和三方测算交叉验证"
}"""


def run_penetration_analysis(category: str, core_target: str, tam: dict, drivers: dict) -> dict:
    print("  [3/4] 渗透率与天花板分析...")
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"市场规模：{tam.get('tam_consensus', '')}亿元\n"
        f"增长主驱动力：{drivers.get('growth_framework', '')}\n"
        f"增长展望：{drivers.get('net_growth_outlook', '')}\n\n"
        "请从地理维度、人群维度、国际对标三个角度分析该品类的渗透率现状与天花板，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PENETRATION,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return _parse_json(text)


# ---------------------------------------------------------------------------
# Sub-task 4: 区域扩张机会图
# ---------------------------------------------------------------------------

SYSTEM_REGIONAL = """你是一名消费行业研究员，专注于区域市场分析与扩张策略。

【任务】：识别核心标的的区域扩张白地，给出优先级排序与进入策略建议，只输出 JSON，不含任何解释文字或 markdown 代码块。

【分析框架】
- 机会地图：哪些城市/区域是"高吸引力 × 低渗透率"的白地？
- 进入优先级：A级（立即进入）/ B级（中期布局）/ C级（长期观望）
- 单店经济模型适配性：下沉市场能否维持盈利模型？

输出 JSON 示例（严格按此结构）：
{
  "expansion_whitespace_summary": "海底捞门店主要集中于一二线城市，三线及以下城市仍有明显白地，但需适配更低客单价的门店模型",
  "opportunity_map": [
    {
      "region": "华东三四线城市（苏北/浙南/皖北等）",
      "priority": "A",
      "rationale": "人口密度高、消费升级快、品牌认知度高但门店密度低",
      "estimated_whitespace_stores": 150,
      "risk": "人均客单价可能低于一线门店，坪效承压"
    },
    {
      "region": "中西部省会城市及周边（成都/重庆外溢）",
      "priority": "A",
      "rationale": "火锅文化根基深、客单价接受度高、竞争相对分散",
      "estimated_whitespace_stores": 80,
      "risk": "川渝本地品牌竞争激烈，海底捞无地域优势"
    },
    {
      "region": "华南三四线城市（粤东/粤西）",
      "priority": "B",
      "rationale": "消费能力强，但本地特色餐饮（粤菜/潮汕）占主导，火锅渗透需时间",
      "estimated_whitespace_stores": 60,
      "risk": "本地饮食文化强，品类接受度低于平均水平"
    },
    {
      "region": "东北及西北低线城市",
      "priority": "C",
      "rationale": "市场潜力有限，人均消费低，门店盈利模型难以匹配",
      "estimated_whitespace_stores": 30,
      "risk": "客单价天花板低，运营成本高，回收期长"
    }
  ],
  "overseas_expansion": {
    "current_status": "海底捞已在新加坡、英国、美国等地布局，海外门店约110家",
    "near_term_priority": "东南亚（新马泰）：华人聚集、火锅接受度高、扩张成本可控",
    "upside": "海外业务贡献约5-8%营收，长期看具备独立增长价值",
    "risk": "海外本地化难度大，食材供应链需重建"
  },
  "store_model_adaptation": {
    "tier1_model": "大店（400-600㎡），翻台率4次+，人均120-130元",
    "tier3_model": "中店（250-350㎡），翻台率3次+，人均90-100元，需精简菜单",
    "profitability_threshold": "三四线门店需翻台率≥3次/天方可覆盖运营成本"
  },
  "need_human_calibration": false,
  "calibration_reason": ""
}"""


def run_regional_analysis(
    category: str, core_target: str, penetration: dict, tam: dict
) -> dict:
    print("  [4/4] 区域扩张机会图...")
    ceiling = penetration.get("core_target_ceiling", {})
    prompt = (
        f"品类：{category}\n核心标的：{core_target}\n"
        f"当前门店数：{ceiling.get('current_stores', '')}家，"
        f"天花板估算：{ceiling.get('estimated_store_ceiling', '')}家\n"
        f"城市渗透率概况：一线（高）→ 三四线（低）\n"
        f"市场总规模：{tam.get('tam_consensus', '')}亿元\n\n"
        "请识别核心标的的区域扩张白地，给出优先级排序和进入策略，只输出 JSON。"
    )
    text = _generate(
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_REGIONAL,
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
    "1. 文风：卖方研报体，客观专业，数据驱动\n"
    "2. 结构：四个小节——4.1市场规模测算、4.2增长驱动力、4.3渗透率与天花板、4.4区域扩张机会\n"
    "3. 数据：引用子分析中的具体数字（亿元、%、门店数等），不凭空编造\n"
    "4. 投资视角：每节结尾给出1-2句投资含义\n"
    "5. 长度：每小节400-600字，总计1600-2400字\n"
    "6. 直接输出 Markdown，从 ## 4.1 开始，不含 JSON，不含代码块\n\n"
    "【禁止使用词汇（一律不得出现）】\n"
    + "、".join(AI_BLACKLIST)
)


def run_integration_writing(
    category: str, core_target: str, research_depth: str, user_focus: str,
    tam: dict, drivers: dict, penetration: dict, regional: dict,
) -> str:
    print("  [整合] 写作整合 Agent...")
    bundle = {
        "市场规模测算": tam,
        "增长驱动力": drivers,
        "渗透率与天花板": penetration,
        "区域扩张机会": regional,
    }
    prompt = (
        f"研究标的：{core_target}（品类：{category}）\n"
        f"研究深度：{research_depth}\n"
        f"读者视角：{user_focus}\n\n"
        f"以下是四个子分析的结构化结果：\n\n"
        f"{json.dumps(bundle, ensure_ascii=False, indent=2)}\n\n"
        "请据此撰写第四章正文，直接从 ## 4.1 市场规模测算 开始。"
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


def load_context(ch2_dir: str, ch3_dir: str) -> tuple[str, str]:
    """从前两章提取摘要作为上下文。"""

    def _read(d: str, fname: str) -> dict:
        p = Path(d) / fname
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # 第二章摘要
    q = _read(ch2_dir, "s1_quadrant.json")
    lc = _read(ch2_dir, "s3_lifecycle.json")
    bt = _read(ch2_dir, "s4_breakthrough.json")
    ch2 = "\n".join(filter(None, [
        f"四象限：{q.get('quadrant_label','')}，人均{q.get('avg_spend_rmb','')}元" if q else "",
        f"生命周期：{lc.get('lifecycle_stage','')}，{lc.get('valuation_implication','')}" if lc else "",
        f"标的定位：{bt.get('core_target_position','')}" if bt else "",
    ])) or "（无第二章上下文）"

    # 第三章摘要
    conc = _read(ch3_dir, "s1_concentration.json")
    moat = _read(ch3_dir, "s3_moat.json")
    ch3 = "\n".join(filter(None, [
        f"市场格局：{conc.get('structure_type','')}，{conc.get('concentration_trend','')}" if conc else "",
        f"护城河：{moat.get('moat_rating','')}（{moat.get('total_score','')}/{moat.get('max_score','')}分），最大风险：{moat.get('biggest_moat_risk','')}" if moat else "",
    ])) or "（无第三章上下文）"

    return ch2, ch3


def build_final_md(category: str, core_target: str, chapter_body: str, all_results: dict) -> str:
    warnings = [
        f"- **{k}**：{v.get('calibration_reason', '需人工核查')}"
        for k, v in all_results.items()
        if isinstance(v, dict) and v.get("need_human_calibration")
    ]
    header = (
        f"# 第四章　市场空间\n\n"
        f"> **研究标的**：{core_target}　｜　**品类**：{category}\n\n---\n\n"
    )
    warning_block = (
        "\n> ⚠️ **人工核查提示**\n>\n"
        + "\n".join(f"> {w}" for w in warnings) + "\n\n"
        if warnings else ""
    )
    return header + warning_block + chapter_body


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IRA 第四章自动化工作流")
    parser.add_argument("input", help="输入 JSON 文件路径")
    parser.add_argument("--output", default="output_chapter4.md")
    parser.add_argument("--intermediates-dir", default="intermediates_ch4")
    parser.add_argument("--ch2-dir", default="intermediates")
    parser.add_argument("--ch3-dir", default="intermediates_ch3")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("错误：请先设置环境变量 GEMINI_API_KEY")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        inp = json.load(f)

    category       = inp["category"]
    core_target    = inp["core_target"]
    research_depth = inp.get("research_depth", "标准版")
    user_focus     = inp.get("user_focus", "二级市场")

    print(f"\n{'='*60}")
    print(f"IRA 第四章工作流：市场空间")
    print(f"品类: {category}　标的: {core_target}")
    print(f"{'='*60}\n")

    inter_dir = Path(args.intermediates_dir)
    inter_dir.mkdir(exist_ok=True)

    ch2_context, ch3_context = load_context(args.ch2_dir, args.ch3_dir)
    loaded = sum([ch2_context != "（无第二章上下文）", ch3_context != "（无第三章上下文）"])
    if loaded:
        print(f"  [✓] 已加载第二、三章上下文（{loaded}/2）")

    def _load_or_run(path: str, fn):
        p = Path(path)
        if p.exists():
            print(f"  [跳过] 加载已有结果: {path}")
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        result = fn()
        save_intermediate(result, path)
        return result

    tam = _load_or_run(
        str(inter_dir / "s1_tam.json"),
        lambda: run_tam_analysis(category, core_target, ch2_context, ch3_context),
    )
    drivers = _load_or_run(
        str(inter_dir / "s2_drivers.json"),
        lambda: run_drivers_analysis(category, core_target, tam),
    )
    penetration = _load_or_run(
        str(inter_dir / "s3_penetration.json"),
        lambda: run_penetration_analysis(category, core_target, tam, drivers),
    )
    regional = _load_or_run(
        str(inter_dir / "s4_regional.json"),
        lambda: run_regional_analysis(category, core_target, penetration, tam),
    )

    chapter_body = run_integration_writing(
        category, core_target, research_depth, user_focus,
        tam, drivers, penetration, regional,
    )

    all_results = {
        "市场规模测算": tam,
        "增长驱动力": drivers,
        "渗透率与天花板": penetration,
        "区域扩张机会": regional,
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
