#!/usr/bin/env python3
"""Jev 基准集 — 用「归因判断」这一个靶子，把 Jev 和我自己放在同一道题上。

为什么是归因，不是灯色（2026-09-19 自我否决后重定的实验）：
  tail-risk 的灯色分档是**纯确定性计算**（读数落在哪一档，查表即得）。
  把确定性计算交给概率模型是降级不是升级，比出来的差异是噪音不是发现。
  **归因判断才是正确的靶子**，因为它同时满足三条：
    ① 输入非结构化（要读当天的叙事）
    ② 输出是带置信度的分类（正是 Jev 的 Choice 类型）
    ③ **我有记录在案的失败**（predictions.md 里 5 条落空中 1 条渠道漏、1 条方向错）

── 靶子收窄到「机器能裁判的那一个维度」 ──────────────────────────────────────
本基准只判一件事：**某只股票当天的涨跌是行业共动还是个股独有。**
不判「是利率驱动还是油价驱动」——那个标签在本数据里**没有机械答案**，
拿我自己的事后解释当标准答案就是自评（profile 1.2c：自评偏差有恒定方向）。
→ 只保留 sector_wide / stock_specific / unclear 三分类。

── 答案键必须在看结果之前定死 ────────────────────────────────────────────
KEY_Z / KEY_SD_FLOOR / KEY_SECTOR_MIN 三个常数一旦跑出结果就不许再动。
改它们来让谁的分数变好看，就是 profile 1.1p 的凑答案。
本文件被 self_check.py 视为规则承载物，改动会留在 git 里。

── 信息隔离（这条被破坏，整个实验就作废）────────────────────────────────
  模型看到的：目标股代码、它自己的涨跌、SPY/QQQ/VIX/10y、当天叙事（若有）
  模型看不到：**同业个股的涨跌**——那正是答案键的计算材料。
build_requests() 只从 case["visible"] 取值，答案在 case["key"] 里，两者不交叉。

用法：
    python3 tools/jev_bench.py --build          # 造基准集（不需要 key，可离线）
    python3 tools/jev_bench.py --stats          # 看基准集分布
    python3 tools/jev_bench.py --requests > r.json   # 导出待发请求
    python3 tools/jev_bench.py --run            # 真调 API（需 TYPESAFE_API_KEY，需可出网）
    python3 tools/jev_bench.py --score resp.json     # 对分

⚠ API 请求格式未经验证：docs.typesafe.ai / api.typesafe.ai 在本容器返回
  CONNECT tunnel failed 403（组织代理策略，按 README 只报告不绕过）。
  下面的 schema 来自公开检索结果的拼接，**跑之前必须拿真文档核一遍**。
  按 profile 1.1x：没实测就不要把它当已知——所以这里显式标注为待核。
"""
import json, os, sys, subprocess, statistics, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(REPO, "memory", "state", "jev_bench_set.json")

# ── 答案键常数（定死，不得事后调）──────────────────────────────────────────
KEY_Z          = 2.0    # |z| ≥ 2.0 判个股独有
KEY_SD_FLOOR   = 0.5    # 同业离散度下限，防止除以噪音把微小差异放大成 z=10
KEY_SECTOR_MIN = 1.0    # 同业均值 |x| < 1.0% 视为「行业没动」，该案例判 unclear
MIN_PEERS      = 3      # 同业不足 3 只不出题

# ── 行业分组（只用于算答案键，不进模型输入）────────────────────────────────
SECTORS = {
    "semis":    ["NVDA", "AMD", "MU", "SNDK", "AVGO", "INTC"],
    "autos":    ["GM", "F", "TSLA"],
    "megacap":  ["AAPL", "GOOGL", "NVDA", "AVGO"],
    "fintech":  ["SOFI", "HOOD", "UBER"],
    "metals":   ["GLD", "SLV"],
}
# 每只股票归属的「裁判组」——一只股票只能有一个答案键，否则同一案例有两个标准答案
PRIMARY = {}
for sec, members in SECTORS.items():
    for m in members:
        PRIMARY.setdefault(m, sec)

MACRO = ["SPY", "QQQ", "IWM", "TLT", "XLE", "GLD"]   # 作为背景给模型，不作同业

# ── 我在这 5 天留下的、有据可查的归因判断 ──────────────────────────────────
# 出处：memory/state/predictions.md + 当日期权扫描结论。
# reading 一栏标注读数口径（登记规范第 9 条）——9/18 那条是盘中，不是收盘。
MY_CALLS = [
    {"date": "2026-09-11", "ticker": "GM",   "my_answer": "sector_wide",
     "my_note": "高 CPI 日车价推动 → 偏好 GM。事后记 ❌（渠道漏：框架缺油价）",
     "source": "predictions.md 2026-09-11 GM 在高 CPI 日的净效应"},
    {"date": "2026-09-14", "ticker": "AMD",  "my_answer": "sector_wide",
     "my_note": "半导体下跌是叙事非基本面（Amodei 发文 + Altman 表态 + 特朗普反对）",
     "source": "predictions.md 2026-09-14，记 ✅"},
    {"date": "2026-09-15", "ticker": "GM",   "my_answer": "sector_wide",
     "my_note": "当日 XLE +2.17%，油价上行压制皮卡/SUV 利润池",
     "source": "2026-09-15 扫描结论（油价渠道已于 9/14 补为第三渠道）"},
    {"date": "2026-09-17", "ticker": "MU",   "my_answer": "sector_wide",
     "my_note": "FOMC 次日波动率释放，VIX −11.52%，风险资产普涨",
     "source": "predictions.md 2026-09-17 期限溢价条目的同日记录"},
    {"date": "2026-09-18", "ticker": "GM",   "my_answer": "stock_specific",
     "my_note": "GM 盘中低点 $81.62 跌破 $82 价格条件，触发腿部重估",
     "source": "2026-09-18 扫描：GM 价格条件触发"},
]


# ── 取数 ───────────────────────────────────────────────────────────────────
def load_daily_closes():
    """每个交易日取当天最后一次抓价。返回 [(date, basis, payload)]。

    basis: "close" 若最后一次抓价在 20:00Z 之后（美股收盘后），否则 "intraday HH:MMZ"。
    这个区分不是装饰——9/18 只有 15:53Z 的盘中读数，
    把它当收盘用就是 predictions.md 第 9 条要防的「挑读数」。
    """
    log = subprocess.run(["git", "log", "--format=%H %cI", "--reverse",
                          "--", "stock_prices.json"],
                         capture_output=True, text=True, cwd=REPO).stdout.strip().split("\n")
    by_day = collections.OrderedDict()
    for line in log:
        if not line.strip():
            continue
        commit, ts = line.split()
        by_day.setdefault(ts[:10], []).append((ts, commit))

    rows = []
    for day, entries in by_day.items():
        ts, commit = entries[-1]
        raw = subprocess.run(["git", "show", f"{commit}:stock_prices.json"],
                             capture_output=True, text=True, cwd=REPO).stdout
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if not payload.get("prices"):
            continue
        hhmm = ts[11:16]
        basis = "close" if ts[11:19] >= "20:00:00" else f"intraday {hhmm}Z"
        rows.append((day, basis, payload))
    return rows


def pct(prices, ticker):
    row = prices.get(ticker) or {}
    v = row.get("changePct")
    return None if v is None else float(v)


# ── 答案键 ─────────────────────────────────────────────────────────────────
def adjudicate(target, prices):
    """只用同业个股涨跌裁判。返回 (label, 证据) 或 (None, 原因)。"""
    sector = PRIMARY.get(target)
    if not sector:
        return None, "无归属行业组"
    peers = [t for t in SECTORS[sector] if t != target]
    vals = [pct(prices, t) for t in peers]
    pairs = [(t, v) for t, v in zip(peers, vals) if v is not None]
    if len(pairs) < MIN_PEERS:
        return None, f"同业有效样本 {len(pairs)} < {MIN_PEERS}"
    tv = pct(prices, target)
    if tv is None:
        return None, "目标无读数"

    peer_vals = [v for _, v in pairs]
    mean = statistics.fmean(peer_vals)
    sd = statistics.pstdev(peer_vals)
    z = (tv - mean) / max(sd, KEY_SD_FLOOR)

    evidence = {"sector": sector, "target_pct": tv, "peer_mean": round(mean, 3),
                "peer_sd": round(sd, 3), "z": round(z, 2), "n_peers": len(pairs),
                "peers": {t: v for t, v in pairs}}

    if abs(z) >= KEY_Z:
        return "stock_specific", evidence
    if abs(mean) >= KEY_SECTOR_MIN:
        return "sector_wide", evidence
    # 行业本身没动，且目标也没显著偏离 → 这天这只股票没什么可归因的
    return "unclear", evidence


# ── 造集 ───────────────────────────────────────────────────────────────────
def build():
    rows = load_daily_closes()
    my_index = {(c["date"], c["ticker"]): c for c in MY_CALLS}
    cases, skipped = [], collections.Counter()

    for day, basis, payload in rows:
        prices = payload["prices"]
        macro = {t: pct(prices, t) for t in MACRO if pct(prices, t) is not None}
        macro["VIX"] = payload.get("vix")
        macro["UST10Y"] = payload.get("treasury_10y")

        for target in sorted(PRIMARY):
            label, ev = adjudicate(target, prices)
            if label is None:
                skipped[ev] += 1
                continue
            mine = my_index.get((day, target))
            cases.append({
                "id": f"{day}:{target}",
                "date": day,
                "basis": basis,
                # ── 模型可见（**不含同业个股**）──
                "visible": {
                    "ticker": target,
                    "change_pct": ev["target_pct"],
                    "market": macro,
                    "narrative": (mine or {}).get("my_note"),
                },
                # ── 答案键（模型不可见）──
                "key": {"label": label, "evidence": ev},
                # ── 我的记录答案（仅 5 例有）──
                "mine": ({"answer": mine["my_answer"], "source": mine["source"]}
                         if mine else None),
            })

    # ⚠ 关键自检：MY_CALLS 里有没有案例被答案键静默丢掉？
    # 2026-09-19 首次造集即命中——MIN_PEERS=3 把 3 条 GM 全删了，
    # 而那 3 条正是我唯一记 ❌ 的那个方向（汽车组只有 GM/F/TSLA，去掉目标只剩 2 个同业）。
    # **被删掉的恰好是我判错的那些，留下的恰好是我判对的那些。**
    # 不改常数来把它们捞回来（那是 1.1p 凑答案），而是让这件事出现在输出里。
    built = {c["id"] for c in cases}
    dropped_calls = []
    for call in MY_CALLS:
        cid = f"{call['date']}:{call['ticker']}"
        if cid not in built:
            day_payload = next((p for d, _, p in rows if d == call["date"]), None)
            reason = adjudicate(call["ticker"], day_payload["prices"])[1] if day_payload else "该日无抓价"
            dropped_calls.append({"id": cid, "my_answer": call["my_answer"],
                                  "reason": reason})

    out = {
        "built_at_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                       capture_output=True, text=True).stdout.strip(),
        "dropped_my_calls": dropped_calls,
        "key_constants": {"KEY_Z": KEY_Z, "KEY_SD_FLOOR": KEY_SD_FLOOR,
                          "KEY_SECTOR_MIN": KEY_SECTOR_MIN, "MIN_PEERS": MIN_PEERS},
        "task": "给定某只股票当日涨跌与大盘/波动率/利率背景（不给同业个股），"
                "判断该涨跌是行业共动(sector_wide)、个股独有(stock_specific)还是无从判断(unclear)。",
        "n_cases": len(cases),
        "skipped": dict(skipped),
        "cases": cases,
    }
    os.makedirs(os.path.dirname(BENCH), exist_ok=True)
    with open(BENCH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def load_bench():
    if not os.path.exists(BENCH):
        return build()
    with open(BENCH) as f:
        return json.load(f)


# ── 请求构造（schema 待核）─────────────────────────────────────────────────
CHOICES = ["sector_wide", "stock_specific", "unclear"]

def build_requests(bench):
    """按公开检索到的 Jev API 形状构造请求。

    ⚠ 本函数的 schema **未经真实文档验证**（docs 站点在本容器 403）。
    跑之前拿官方文档核对 state / questions 的字段名与取值形式。
    """
    reqs = []
    for c in bench["cases"]:
        v = c["visible"]
        state = {
            "ticker": v["ticker"],
            "ticker_change_pct": v["change_pct"],
            **{f"market_{k}": val for k, val in v["market"].items()},
        }
        if v.get("narrative"):
            state["narrative"] = v["narrative"]
        reqs.append({
            "case_id": c["id"],
            "body": {
                "model": "jev-latest",
                "state": state,
                "questions": {
                    "driver": CHOICES,                 # Choice 型
                    "confidence_sufficient": "bool",   # Bool 型
                    "peer_divergence": ["score", 0, 10],  # Score 型
                },
            },
        })
    return reqs


def run():
    """真调 API。需要 TYPESAFE_API_KEY 且所在环境可出网到 api.typesafe.ai。

    本容器出不去（代理 403），所以这条路只在 GitHub Actions 里走得通。
    """
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        print("TYPESAFE_API_KEY 未设置 —— 无法调用。", file=sys.stderr)
        print("获取路径：typesafe.ai 排队 → console.typesafe.ai/settings/keys → "
              "存为 GitHub secret TYPESAFE_API_KEY。", file=sys.stderr)
        return 2
    import urllib.request, urllib.error
    bench = load_bench()
    results = []
    for r in build_requests(bench):
        req = urllib.request.Request(
            "https://api.typesafe.ai/v1/systemone",
            data=json.dumps(r["body"]).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                results.append({"case_id": r["case_id"],
                                "response": json.loads(resp.read().decode())})
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            print(f"[{r['case_id']}] HTTP {e.code}: {body}", file=sys.stderr)
            results.append({"case_id": r["case_id"],
                            "error": f"HTTP {e.code}", "body": body})
        except Exception as e:
            print(f"[{r['case_id']}] {type(e).__name__}: {e}", file=sys.stderr)
            results.append({"case_id": r["case_id"], "error": f"{type(e).__name__}: {e}"})
    json.dump(results, sys.stdout, ensure_ascii=False, indent=1)
    return 0


# ── 对分 ───────────────────────────────────────────────────────────────────
def extract_answer(resp):
    """从响应里挖出 driver 标签。形状未核实，所以多路兜底 + 挖不到就明说。"""
    if not isinstance(resp, dict):
        return None
    for path in (("answers", "driver"), ("questions", "driver"), ("driver",),
                 ("result", "driver"), ("output", "driver")):
        node = resp
        for p in path:
            node = node.get(p) if isinstance(node, dict) else None
            if node is None:
                break
        if node is None:
            continue
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            for k in ("value", "choice", "label", "answer"):
                if isinstance(node.get(k), str):
                    return node[k]
            # 概率分布形式：取 argmax
            probs = {k: v for k, v in node.items() if isinstance(v, (int, float))}
            if probs:
                return max(probs, key=probs.get)
    return None


def score(resp_path):
    bench = load_bench()
    keys = {c["id"]: c for c in bench["cases"]}
    with open(resp_path) as f:
        responses = json.load(f)

    hit = miss = unparsed = 0
    confusion = collections.Counter()
    head_to_head = []
    for r in responses:
        c = keys.get(r["case_id"])
        if not c:
            continue
        got = extract_answer(r.get("response"))
        if got is None:
            unparsed += 1
            continue
        truth = c["key"]["label"]
        confusion[(truth, got)] += 1
        if got == truth:
            hit += 1
        else:
            miss += 1
        if c.get("mine"):
            head_to_head.append({"id": c["id"], "truth": truth,
                                 "jev": got, "mine": c["mine"]["answer"]})

    total = hit + miss
    print(f"基准集 {bench['n_cases']} 例 | 有效应答 {total} | 解析失败 {unparsed}")
    if total:
        print(f"Jev 准确率 {hit}/{total} = {hit/total:.1%}")
    print("\n混淆矩阵（真值 → 判定）:")
    for (t, g), n in sorted(confusion.items()):
        mark = " " if t == g else "✗"
        print(f"  {mark} {t:>15} → {g:<15} {n}")

    if head_to_head:
        print(f"\n── 同题对照（我 vs Jev），n={len(head_to_head)} ──")
        print("  ⚠ n 这么小只能看出大破绽，看不出高下。不要用它下结论。")
        mine_hit = sum(1 for h in head_to_head if h["mine"] == h["truth"])
        jev_hit = sum(1 for h in head_to_head if h["jev"] == h["truth"])
        for h in head_to_head:
            print(f"  {h['id']:<18} 真值 {h['truth']:<15} "
                  f"我 {h['mine']:<15} Jev {h['jev']}")
        print(f"  我 {mine_hit}/{len(head_to_head)} | Jev {jev_hit}/{len(head_to_head)}")
    return 0


def trivial_ceiling(cases):
    """平凡规则上限：只看目标自身 |涨跌| 的两阈值规则，网格搜到最优。

    为什么必须算这个（2026-09-19 立）：
      我刚刚才因为「把确定性计算交给概率模型」否决过一版实验设计。
      同一个错误在基准集这一层会换个样子出现——
      **如果一条三行的阈值规则就能做到和模型一样好，那这个基准测不出任何东西。**
      首次实测：平凡规则上限 54.9%，与多数类基线一字不差 → 该维度零信息量，
      任务确实需要「同业共动结构」的先验才能做对。基准通过。
    """
    best = (0, None, None)
    grid = [x / 4 for x in range(0, 25)]
    for lo, hi in ((l, h) for l in grid for h in grid if h > l):
        ok = sum((("unclear" if abs(c["visible"]["change_pct"]) < lo else
                   "sector_wide" if abs(c["visible"]["change_pct"]) < hi else
                   "stock_specific") == c["key"]["label"]) for c in cases)
        if ok > best[0]:
            best = (ok, lo, hi)
    return best


def stats():
    bench = load_bench()
    print(f"基准集：{bench['n_cases']} 例，建于 {bench['built_at_utc']}")
    print(f"答案键常数：{bench['key_constants']}")
    dist = collections.Counter(c["key"]["label"] for c in bench["cases"])
    for label, n in dist.most_common():
        print(f"  {label:<15} {n:>4}  ({n/bench['n_cases']:.0%})")
    base = dist.most_common(1)[0]
    n = bench["n_cases"]
    triv, lo, hi = trivial_ceiling(bench["cases"])
    print(f"\n── 两条必须先跨过的线 ──")
    print(f"  多数类基线    全猜 {base[0]}：{base[1]/n:.1%}")
    print(f"  平凡规则上限  只看自身 |涨跌| 的最优两阈值规则：{triv/n:.1%} (lo={lo} hi={hi})")
    print(f"  **打不过这两个数就是没有信息量**——这是判据，不是参考。")
    if triv <= base[1]:
        print(f"  ✓ 平凡规则 = 多数类基线 → 自身涨跌这一维零信息量，"
              f"任务确实需要同业共动的先验，基准有效。")
    else:
        print(f"  ⚠ 平凡规则已超基线 {(triv-base[1])/n:+.1%} → "
              f"这个基准有一部分能被三行代码做掉，评分时要扣掉这部分再谈模型价值。")
    if bench.get("skipped"):
        print(f"\n未出题：{bench['skipped']}")

    dropped = bench.get("dropped_my_calls") or []
    if dropped:
        print(f"\n⛔ 我的记录判断里有 {len(dropped)}/{len(MY_CALLS)} 条被答案键判为不可裁：")
        for d in dropped:
            print(f"     {d['id']:<18} 我判 {d['my_answer']:<15} 不可裁因：{d['reason']}")
        print("   **这不是技术细节，是这个基准的硬边界**：汽车组在 27 只票的池子里"
              "\n   只有 GM/F/TSLA，去掉目标只剩 2 个同业，同业均值/离散度都不成立。"
              "\n   而我记 ❌ 的判断全部落在汽车组 —— "
              "\n   **答案键删掉的恰好是我判错的，留下的恰好是我判对的。**"
              "\n   → 下面那个对照子集因此是自选样本，**不得用来比高下**。")

    mine = [c for c in bench["cases"] if c.get("mine")]
    print(f"\n── 有我记录答案的对照子集：{len(mine)} 例（自选样本，见上）──")
    ok = 0
    for c in mine:
        truth, ans = c["key"]["label"], c["mine"]["answer"]
        ok += truth == ans
        flag = "对" if truth == ans else "错"
        ev = c["key"]["evidence"]
        print(f"  {c['id']:<18} [{c['basis']}] 我判 {ans:<15} 真值 {truth:<15} {flag}")
        print(f"      z={ev['z']} 同业均值 {ev['peer_mean']}% 目标 {ev['target_pct']}% "
              f"同业 {ev['peers']}")
    print(f"  我在对照子集上：{ok}/{len(mine)}")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--stats"
    if arg == "--build":
        out = build()
        print(f"已写 {BENCH}：{out['n_cases']} 例")
    elif arg == "--stats":
        sys.exit(stats())
    elif arg == "--requests":
        json.dump(build_requests(load_bench()), sys.stdout, ensure_ascii=False, indent=1)
    elif arg == "--run":
        sys.exit(run())
    elif arg == "--score":
        sys.exit(score(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)
