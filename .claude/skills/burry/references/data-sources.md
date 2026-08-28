# 数据源、Tier 边界发现、价格管道与运行方式

> 由 SKILL.md 在需要确定 Tier 边界、排查抓数、或改动数据管道时加载。

---

## 0. 运行环境硬约束（先读这条）

**`data.sec.gov` 与 `www.sec.gov` 在本会话容器的出口策略封禁名单内。**
实测：`curl https://data.sec.gov/api/xbrl/frames/...` → `curl: (56) CONNECT tunnel failed, response 403`

**这是代理层的组织策略封禁，不是站点拒绝。按 profile 1.1b：不绕行，不重试，不改 TLS 设置。**

→ **13F 抓取与全市场扫描全部在 GitHub Actions 里跑**（Actions runner 出口不受限），
产物写回仓库，对话侧只读产物做归因。机制与 `ses-screen.yml` / `fetch-prices.yml` 完全一致。

| 任务 | 在哪跑 | 产物 |
|---|---|---|
| 13F 抓取 + Tier 边界发现 | Actions（`burry-screen.yml`） | `burry_state.json` |
| Layer 1 全市场扫描 | Actions（同上） | `burry_screen.json` |
| 四层归因分析 | **对话侧**（读上述产物） | 报告 |

**触发方式**：推 `burry_trigger.txt` 到默认分支 → Actions 跑 → 轮询产物 `updated_at` 变化。
**⚠ 读产物时读默认分支，不是 `main` 的想当然写法**（profile 1.1f：此前踩过）。

---

## 1. Tier 边界必须发现，不得写死

### 为什么
Scion Asset Management 于 **2025-11-10 终止 SEC 投顾注册**，
Michael Burry 于 **2025-11-23 上线付费 newsletter「Cassandra Unchained」**（$39/月，订阅量级约 30 万）。

**但 13F 报送义务的触发条件是「在季末持有超过 1 亿美元的 13F 证券」，
由持仓规模决定，不由投顾注册状态决定。注销投顾注册 ≠ 13F 义务自动终止。**

因此「Tier 1 截止于 2025-09-30」是一个**推测**，不是制度事实。
**把它写成常量，会在他恢复报送时静默失效，而且失效方向不可知**——
这与 2026-08-26 英伟达分析里「绝对水平阈值因基数移动而静默失效」是同一类错误。

### 怎么做
每次运行 `burry_screen.yml` 时：
```
1. 拉 https://data.sec.gov/submissions/CIK{cik}.json
2. 过滤 form == "13F-HR" 或 "13F-HR/A"
3. 取 reportDate 最大的一条 -> 这就是 Tier 1 边界
4. 写入 burry_state.json: {tier1_boundary, tier1_filed_date, tier1_accession, discovered_at}
5. 若边界较上次运行前移（出现新备案）-> 在状态报告里显式高亮
```

**CIK 必须由脚本按实体名查询后写入状态文件，不在文档里硬编码**——
硬编码的 CIK 一旦写错，后续所有归因都建立在错误主体上，且这种错误不会自己暴露。
查询端点：`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=scion&type=13F&output=atom`

### Tier 2 的结构性局限（必须写进每份报告）
- 2025-11 之后若确无强制披露，则**任何「未披露仓位」都无法证伪**
- newsletter 存在**订阅付费商业动机**：讲得动人的仓位比讲得平淡的更值得写 → **选择性偏差方向明确**
- **归因报告必须明确「已知」与「未知」的边界，不能用沉默当作证据**

---

## 2. 13F 数据的固有局限（归因前必须知道）

| 局限 | 含义 |
|---|---|
| **约 45 天滞后** | 季末后 45 天内备案，看到时持仓可能已变 |
| **只含 13F 证券** | 美股多头、ADR、部分 ETF 与期权。**不含**：空头、现金、债券、外国交易所上市股票、大宗商品 |
| **期权按名义市值披露** | 不是权利金。**与股票仓位并列排序会严重夸大期权仓位，必须单列** |
| **不含空头** | 「大空头」的空头部位在 13F 上完全不可见。**任何关于他做空什么的归因，13F 都不是证据来源** |
| **季末快照** | 季中的建仓再清仓完全不可见，换手率被系统性低估 |

**⚠ 最后两条合起来的含义**：13F 能回答「他季末持有什么多头」，
**不能回答「他这季做了什么」**。归因报告的标题措辞必须与这个边界一致。

---

## 3. Layer 1 扫描器的数据源与缺口

### 基本面：SEC EDGAR XBRL
- **Frames API**（全市场横截面，首选）：
  `https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/CY{year}[Q{n}][I].json`
  一次拿全市场某科目某期的所有值，几十个请求覆盖全部报送人。
  （`I` 后缀 = instantaneous，用于资产负债表时点科目）
- **Company Facts**（单公司全科目，用于复核）：
  `https://data.sec.gov/api/xbrl/companyfacts/CIK{10位}.json`，单文件可达 10MB+，**只用于抽查，不用于扫描**

**请求礼仪**：`User-Agent` 必须含真实联系方式；限速 ≤10 req/s；跨 run 缓存 frames 结果。

### ⭐ 缺口比原规格估计的小一半
原规格写「EDGAR 没有市值和股价」。**准确说法是：EDGAR 没有股价，但有股数。**

`dei:EntityCommonStockSharesOutstanding`（10-K/10-Q 封面页流通股数）在 XBRL 里可取。
**因此缺的只有价格一项，市值 = 该股数 × 价格。**

### 价格管道：两段式，把瓶颈从五千支压到数百支
全市场约 5,000+ 报送人，免费价格 API 普遍限速（Finnhub 免费档 60 req/min ≈ 83 分钟）。
**解法不是找更快的 API，是少问几支：**

```
Stage A（纯 EDGAR，零价格请求）
  算：EBITDA、净负债、净负债/EBITDA、SBC/营收、账面净资产、FCF
  过滤：低杠杆 + 低 SBC + 数据完整度
  预期输出：数百家

Stage B（只对 Stage A 幸存者取价格）
  取价 -> 市值 = 股数 × 价格 -> EV = 市值 + 净负债
  算：EV/EBITDA、P/B、FCF yield -> 按分位数排序
```

**本仓库已有价格管道**：`scripts/fetch_prices.py`（Finnhub + yfinance，跑在 Actions）。
Burry 扫描器**复用其取价函数**，不新建一套。若 Stage A 幸存者超过 800 家，收紧 Stage A 门槛而不是加大取价量。

### 覆盖范围的诚实声明（必须出现在每次扫描输出的抬头）
> EDGAR 仅覆盖向 SEC 报送的主体，**扫描范围为美股**。
> 伯里本人选股不限国别（历史上做过波兰、英国、墨西哥小盘股）。
> **本扫描器的范围小于他的真实选股范围——这是数据源带来的收窄，不是选股标准的收窄。**

---

## 4. 交叉验证材料（Tier 2 及以下）

| 来源 | Tier | 用法 |
|---|---|---|
| Cassandra Unchained newsletter | Tier 2 | 补充细节、调节置信度。**不可单独支撑结论** |
| 公开采访、X/Twitter 历史发言 | Tier 2− | 仅用于 L4 标注。**历史上多次言行脱节，不得当作仓位证据** |
| 媒体转述的持仓消息 | **不采信** | 二手源期间错标高发（本会话已遇三次）。**必须回到 13F 原文** |

**⚠ 二手源的判别法（已验证有效三次）：用台账里已有的独立事实去戳它。**
若二手源给出的数字与已确认事实倒推不一致，**以可对账者为准，直接弃用该来源**。

---

## 5. 产物文件约定

| 文件 | 内容 |
|---|---|
| `burry_state.json` | Tier 边界发现结果、CIK、最新 13F 期间与备案日、上次运行时间 |
| `burry_holdings.json` | 逐季持仓明细（标的、CUSIP、市值、股数、类型：股票/期权） |
| `burry_screen.json` | Layer 1 扫描输出：通过项、具体数值、分位、行业、数据完整度标注 |
| `burry_trigger.txt` | 触发文件，推送即触发 Actions |

**所有产物必须带 `updated_at`（UTC ISO8601）与 `source_boundary`（本次使用的 Tier 1 边界）。**
读产物时先看这两个字段，**陈旧产物不得直接用于出报告**。
