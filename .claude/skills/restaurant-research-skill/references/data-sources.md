# 数据来源索引

按数据类型分类，快速定位应去哪里找什么数据。

---

## 第零步：检查本地缓存

**每次调研前先做这一步**，再决定是否触发 GitHub Action。

```
研究缓存路径：research_cache/[slug].json
manifest：    research_cache/_manifest.json
slug 规则：   ticker 中非字母数字替换为下划线，小写
              02255.HK → 02255_hk.json
              600519.SS → 600519_ss.json
```

**缓存命中判断**：读 `_manifest.json`，找对应 ticker 的 `updated_at`，若距今 < 24小时则直接用，否则触发刷新。

---

## 触发 GitHub Action 获取财务数据

上市公司（港股/A股/美股）可通过以下方式触发实时抓取，**绕过 sandbox egress 限制**：

```json
// 推送到 main 分支的 research_fetch_trigger.json
{
  "tickers": ["02255.HK", "9988.HK"],
  "triggered_at": "[当前ISO时间]",
  "triggered_by": "research-agent"
}
```

触发方式：用 `mcp__github__push_files` 推 `research_fetch_trigger.json` 到 main 分支。
等待方式：轮询 `research_cache/_manifest.json` 的 `updated_at` 刷新（通常 60–90 秒）。
**超时处理**：5 分钟后仍未更新 → 假设 Action 失败，走 WebSearch/聚合站降级路径，报告顶部注明"财务数据来自网络检索，非实时缓存，请核实"。

**`scripts/fetch_research_data.py` 支持的 ticker 格式：**

| 市场 | 格式示例 | 来源 |
|------|---------|------|
| 港股 | `02255.HK` / `9988.HK` | Yahoo Finance（yfinance） |
| 美股 | `NVDA` / `AAPL` | Yahoo Finance（yfinance） |
| A股 | `600519.SS` / `000858.SZ` | Yahoo Finance + 东方财富补充 |

---

## 数据冲突决策规则

遇多源数据不一致时，按以下优先级处理：

| 优先级 | 规则 |
|-------|------|
| 1 | **一手（财报/公告）> 二手（媒体/券商）** |
| 2 | **更新日期更近的来源** > 旧来源（同类） |
| 3 | 两个二手源相差 ≤15%：取均值，注明两来源 |
| 4 | 两个二手源相差 >15%：**并列呈现**，标注"数据存在分歧，建议以一手核实" |
| 禁止 | 选更高/更好看的数字掩盖争议 |

---

## 数据获取失败降级表

| 场景 | 主源 | 失败原因 | 降级路径 |
|------|------|---------|---------|
| 港股年报 | hkexnews.hk PDF | ⚠️ **PDF 体积 100–400 页，WebFetch 失败率 >70%**，不建议作为主源 | **直接走聚合站**（aastocks/雪球/futu.io）；PDF 仅在聚合站数据不全时作最后手段 |
| A股财报 | cninfo.com.cn | 403 | 先触发 GitHub Action；若失败 → 搜 `[品牌] 业绩快报 [年份]` |
| 非上市营收 | 无 | 本就不公开 | 直接走【分析预测】：人次 × 行业人均消费标准（见 industry-benchmarks.md） |
| 分部数据（各子品牌/各景区） | 财报附注 | 多数不分部披露 | 节假日公告数据 → 估算占比 → 推算全年；见 industry-benchmarks.md 估算方法 |
| 媒体深度报道 | 晚点/36氪 | 付费墙/403 | 搜同报道的微信公众号/知乎/雪球转载版本 |
| WebFetch 连续 403 | 各财经站 | sandbox 限制 | 全部改 WebSearch；搜索结果摘要中提取数字；标注【二手·媒体】 |

---

## 高成功率财务数据聚合站（优先使用）

> ⚠️ 港股年报 PDF 直接 WebFetch 失败率 >70%（体积过大+反爬）。**所有港股财务数据优先从聚合站获取**，不要先尝试 hkexnews。
>
> 这些站点将原始财报解析为 HTML，WebFetch 成功率远高于 hkexnews / cninfo。

### 港股

| 平台 | URL 模式 | 主要内容 |
|------|---------|---------|
| AAStocks | `aastocks.com/en/stocks/analysis/company-fundamental/summary?symbol=[代码不带HK]` | 营收/利润/估值摘要 |
| 富途牛牛 | `futu.io/stock/[代码]-HK/financial/income` | 财务三表 |
| ETNet | `etnet.com.hk/www/eng/stocks/realtime/quote_company_factor.php?code=[代码]` | 基础指标 |
| 雪球 | `xueqiu.com/S/[代码带HK]` | 财务+公告+讨论 |

### A股

| 平台 | URL 模式 | 主要内容 |
|------|---------|---------|
| 东方财富 | `quote.eastmoney.com/[sh/sz][代码].html` | 行情+基本面 |
| 同花顺 | `basic.10jqka.com.cn/[代码]/finance.html` | 财务三表 |
| 新浪财经 | `finance.sina.com.cn/realstock/company/[sh/sz代码]/nc.shtml` | 行情+公告 |
| 雪球 | `xueqiu.com/S/[SH/SZ代码]` | 财务+讨论 |

### 搜索查询模板（已优化，直接复用）

```
# 找港股年报关键数字
[公司名] OR [股票代码] 年报 营收 净利润 [年份] site:aastocks.com OR site:xueqiu.com OR site:futu.io

# 找A股业绩
[公司名] 业绩快报 营收 净利润 [年份] site:eastmoney.com OR site:xueqiu.com OR site:10jqka.com.cn

# 找非上市品牌规模数据
[品牌名] 门店数 营收 估值 融资 [年份] site:36kr.com OR site:late.cn OR site:huxiu.com

# 找主题公园/文旅数据
[景区名] 游客人次 接待量 [年份] site:traveldaily.cn OR site:21jingji.com OR site:our-themepark.com
```

---

## 一手财报数据（上市公司原始源）

| 市场 | 平台 | 说明 |
|------|------|------|
| 港股 | 港交所披露易 hkexnews.hk | 年报、中报、季报、公告原文 ⚠️ PDF直接WebFetch失败率>70%，优先用同花顺/东方财富获取财务数据，hkexnews仅用于公告原文 |
| A股 | 巨潮资讯 cninfo.com.cn | 年报、季报、临时公告 |
| 美股 | SEC EDGAR sec.gov | 20-F（年报）、6-K（半年报） |

---

## 主题乐园 / 文旅行业专项数据源

| 来源 | 主要内容 | 搜索方式 |
|------|---------|---------|
| TEA/AECOM 年度报告 | 全球前25主题公园游客量，每年5–6月发布 | `TEA AECOM theme park attendance report [年份]` |
| 各地文旅局统计公报 | 城市/景区年度接待人次 | `[城市] 文旅局 旅游统计 [年份] 公报` |
| 中国主题公园研究院 | 竞争力评价报告、行业白皮书 | `our-themepark.com [年份] 竞争力报告` |
| 景区官方承载量公告 | 最大日接待量（推算年上限） | `[景区名] 最大承载量 公告` |
| 节假日旅游简报 | 黄金周/春节各景区接待数据 | `[景区名] 五一 春节 接待人次 [年份]` |
| 环球旅讯 traveldaily.cn | 主题公园行业深度分析 | `site:traveldaily.cn [品牌] [年份]` |

---

## 餐饮行业专项数据源

| 来源 | 主要内容 |
|------|---------|
| 国家统计局 | 全国餐饮收入月度数据 |
| 中国连锁餐饮协会 | 年度行业报告、百强榜 |
| 美团研究院 | 外卖/到店餐饮数据（报告摘要免费） |
| 艾瑞咨询 | 消费行业分析（摘要免费） |
| 窄播（Jelly） | 餐饮细分赛道深度 |
| 红餐网 | 行业动态、品牌案例 |
| 餐饮O2O | 连锁动态、火锅专题 |

---

## 权威财经媒体

| 媒体 | 擅长内容 | 搜索域名 |
|------|---------|---------|
| 晚点LatePost | 商业模式深度、管理层决策 | late.cn |
| 36氪 | 融资动态、战略解读 | 36kr.com |
| 财新 | 宏观、监管、财务调查 | caixin.com |
| 第一财经 | 上市公司、资本市场 | yicai.com |
| 21经济网 | 上市公司、行业数据 | 21jingji.com |
| 虎嗅 | 商业模式分析 | huxiu.com |
| 环球旅讯 | 文旅/主题公园 | traveldaily.cn |

---

## 企业信息查询

| 平台 | 主要用途 |
|------|---------|
| 企查查 qcc.com | 工商信息、股权结构、融资记录 |
| 天眼查 tianyancha.com | 同上，部分数据有差异 |
| IT桔子 itjuzi.com | 融资信息最全，含未披露轮次 |

---

## 社媒/消费者端信号

| 平台 | 信号类型 |
|------|---------|
| 大众点评 | 门店分布、评分趋势、用户评价 |
| 小红书 | 品牌热度、产品口碑、新品反应 |
| 抖音/微博 | 话题热度、营销事件传播 |
| 微信指数 | 品牌搜索热度趋势（免费） |
