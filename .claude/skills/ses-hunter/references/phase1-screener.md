# Phase 1 · 量化预筛：口径、陷阱与运行方式

本文件由 SKILL.md 的 Phase 1 加载。脚本实体在 `scripts/ses_screener.py`。

---

## 0 · 运行环境（先读这条，否则会白折腾）

**`data.sec.gov` 与 `www.sec.gov` 在本仓库会话环境的出口策略封禁名单内。**
本地 `curl` / `urllib` 会返回 `CONNECT tunnel failed, response 403`——
这是**代理层封禁**，不是站点拒绝，按 `memory/profile.md` 1.1b 的规定**不得绕行**。

**因此 Phase 1 不在会话环境里跑，走 GitHub Actions（出口不受限，与价格缓存同一套机制）：**

```
1. 触发：push 任意内容到 main 的 ses_screen_trigger.txt
   （或在 Actions 页面手动 workflow_dispatch）
2. 产物：main 分支的 ses_screen.json
3. 读取：git show origin/main:ses_screen.json
```

**判定新鲜度**：读 `generated_at`。SEC 数据按年报更新，缓存 7 天内均可用；
但**改了候选池或阈值后必须重跑**，不得用旧产物。

---

## 1 · XBRL 三个必须知道的陷阱

### 陷阱 A（最致命）：`fy` 字段不是数据的会计年度

`companyfacts` 里每条 fact 的 `fy` / `fp` 描述的是**该数字出现在哪一份报送里**，
不是这个数字本身属于哪一年。一份 FY2024 的 10-K 会同时包含 FY2024 / FY2023 / FY2022
三年的利润表数据，**三条记录的 `fy` 全部是 2024、`fp` 全部是 `FY`**。

所以下面这种写法会静默串年：

```python
seen = {}
for v in annual:
    seen[v["fy"]] = v["val"]     # ❌ 同一 fy 下多条不同期间，后写覆盖先写
```

**正确做法：用 `start` / `end` 识别期间，用 `end` 去重，用 `filed` 取最新修订。**

```python
dur = (date(end) - date(start)).days
if 300 <= dur <= 400:            # 年度期间
    key = v["end"]
    if key not in seen or v["filed"] > seen[key]["filed"]:
        seen[key] = v
```

**这个 bug 的危害是它不报错**——CAGR 照样算得出来，只是错的。

### 陷阱 B：`units` 不能按位置取

`list(units.values())[0]` 在多币种或含非货币单位时会取错。**显式取 `"USD"`**，
取不到再按优先级回退，并把实际使用的单位写进产物，便于事后核对。

### 陷阱 C：外国私人发行人不报 10-K

`form == "10-K"` 会让 MELI 之外的拉美/东南亚标的静默返回空序列。
**必须接受 `10-K` / `20-F` / `40-F` 三种。**
候选池里 SE、NU 属此类；只筛 10-K 时它们会显示「数据不足」，
**这是筛选器的问题，不是标的的问题，不得据此出局。**

---

## 2 · 标签优先级（按顺序回退）

| 概念 | 标签优先级 |
|------|-----------|
| 收入 | `RevenueFromContractWithCustomerExcludingAssessedTax` → `Revenues` → `RevenueFromContractWithCustomerIncludingAssessedTax` → `SalesRevenueNet` |
| 毛利 | `GrossProfit` → **收入 − `CostOfRevenue`** → 收入 − `CostOfGoodsAndServicesSold` |
| SG&A | `SellingGeneralAndAdministrativeExpense` → `GeneralAndAdministrativeExpense` + `SellingAndMarketingExpense` |
| 营业利润 | `OperatingIncomeLoss` |

**亚马逊等公司不单独 tag `GrossProfit`，必须走「收入 − 成本」的推导路径**，
否则会返回「数据不足」而漏检。推导得到的毛利要在产物里标记 `derived: true`。

---

## 3 · 窗口对齐（第二常见的错）

四个科目的可得年数往往不同。**必须先求交集年份，再在交集上计算所有趋势。**

用 5 年 CAGR 配 10 年毛利率变化，会得到一个没有意义的比较——
毛利率的变化里有一半发生在 CAGR 窗口之外。产物里必须写明 `window_years` 与 `window_end`。

---

## 4 · 判别器阈值（可调，但要记录为什么调）

```
必要条件：  revenue_cagr >= 0.08          规模确实在扩，否则谈不上规模反哺
判别输入：  gm_trend      毛利率(期末−期初)
           opm_trend     营业利润率(期末−期初)      ← 核心，原始版本缺这一项
           sga_trend     SG&A/收入(期末−期初)

🟢 绿   cagr>=8%  且  gm_trend<=0     且  opm_trend>=-0.01
🟡 黄   cagr>=8%  且  gm_trend<=0     且  -0.03<=opm_trend<-0.01
🔴 红   gm_trend<=-0.03  且  opm_trend<-0.03  且  sga_trend>=0
⚪ 灰   gm_trend>0，或以上均不满足
```

**为什么 `opm_trend` 是核心**：毛利率下降本身**不含信息**——主动让利与被动侵蚀都会让它下降。
只有配上「营业利润率有没有跟着塌」才有分辨力：
- 毛利让出去了但经营利润稳住 → 说明成本侧的规模收益真实存在且被传导
- 毛利和经营利润一起塌 → 说明根本没有规模收益，只是在被迫降价

**原始版本计算了 `sga_ratio_trend` 却没有把它接进判定函数**，只在黄灯文案里打印出来。
这等于放弃了唯一的判别维度。本版把它接进红灯条件。

---

## 5 · 产物结构

```json
{
  "generated_at": "ISO8601",
  "window_years": 5,
  "results": [{
    "ticker": "COST", "cik": "0000909832", "flag": "green",
    "revenue_cagr": 0.093, "gm_trend": -0.004, "opm_trend": 0.002, "sga_trend": -0.006,
    "window": {"start_fy_end": "2020-08-30", "end_fy_end": "2025-08-31"},
    "gross_profit_derived": false,
    "series": {"revenue": [...], "gross_margin": [...], "operating_margin": [...]},
    "notes": ["..."]
  }]
}
```

**`series` 必须保留**——Phase 2 要看的是形状（是平滑下移还是某一年断崖），
只给首尾两个点的趋势值会把「一次性会计变更」误读成「持续让利」。

---

## 6 · 候选池维护原则

候选池是**人工策展**的，不是全市场扫描。理由：
SES 是一种**管理层意图**，意图不在财务数据里，只能先由人从阅读中提出假设，再由筛选器证伪。

加入候选池的最低门槛（满足其一）：
- 管理层公开表述过「把成本节省交给客户」类的经营原则
- 存在结构性的第二利润腿（会员费 / 订阅 / 广告 / 浮存金 / 抽佣）
- 长期毛利率显著低于同业却持续抢占份额

**不要因为「便宜」或「跌了很多」把标的放进池子——那是另一个策略的入口。**
