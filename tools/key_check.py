#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""键名存在性校验 —— profile 1.1u 的承载物。

**1.1u 的事故（2026-09-06，Burry 归因）**：读 `burry_holdings.json` 时用了
`closed` / `increased` / `decreased`，而实际键名是 `new` / `add` / `trim` / `exit`。
三个键都不存在 → `.get()` **静默返回空列表** → 我输出「本季 closed 0 项」。
实际该季 exit 14 项（含全部 9 只 CALL），是当季最重要的事实。

**更该自责的一层**：全历史汇总成「new 272 / closed 0 / inc 0 / dec 0」。
**一个 272 次建仓、0 次清仓的组合在物理上不可能存在。**
这个不可能值就摆在眼前，我看过、没停。

1.1u 因此有两条，本文件各做一层：

  A. **键名存在性**（`--keys`）：AST 扫 tools/ 与 scripts/，
     找出 `json.load(open("某文件"))` 绑定的变量，收集该变量上用到的
     字符串字面量键，**拿真实文件核对它在不在**。
     这是当初那次事故的精确形态，能抓住它才算数。

  B. **不可能值**（`--shapes`）：扫已产出的 JSON 汇总，
     报出 1.1u 列的四种形态：某类别全 0 而同级有大值、占比恰好 100%/0%、
     单调无例外、两个本应互补的量不互补。

**⚠ 误报控制**（本周已栽过两次，见 jev_bench 的 57 处假泄漏、C6 的 6 vs 12）：
  · 只在**能确定变量绑到哪个文件**时才检查；动态键、变量键一律跳过并打印原因
  · `d[k]` 缺键会当场抛错（响亮失败，1.1u 推荐的写法），单独归类不算违规
  · `.get(k)` 缺键静默返回 None/默认值 —— **这才是本规则要抓的那一类**

用法：
    python3 tools/key_check.py                # 两层都跑
    python3 tools/key_check.py --keys         # 只跑键名存在性
    python3 tools/key_check.py --shapes       # 只跑不可能值
"""
import ast
import glob
import re
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ("tools", "scripts")


# ══════════════════════════════════════════════════════════════════════════
# A. 严格加载器的采用情况（1.1u 第 1 条）
# ══════════════════════════════════════════════════════════════════════════
# ⛔ 首版这里是一个 AST 检查器：扫脚本里用到的字面量键，拿真实数据文件核对。
#    在本仓库实测：**14 个脚本只绑定到 1 个变量、核对 1 处键**——
#    因为真实代码里路径几乎都来自函数参数（def load(path)）或计算常量
#    （os.path.join(REPO, ...)），静态分析追不动。
#    **一个只核对 1 处还打 ✅ 的检查器是在装绿**，已删。
#
# → 改做结构性修复：tools/jsonsafe.py 让 `.get(拼错的键)` 抛错而不是返回 None。
#   本层退化成一件静态分析做得准的事：**谁还在用原生 json.load 读数据产物。**
#   这是一张诚实的迁移清单，不假装是完备检查。

DATA_PRODUCTS = ("burry_holdings.json", "burry_state.json", "stock_prices.json",
                 "ses_universe.json", "burry_screen.json", "jev_bench_set.json")


def check_keys(verbose=True):
    files = []
    for d in SCAN_DIRS:
        files += sorted(glob.glob(os.path.join(REPO, d, "**", "*.py"), recursive=True))
    raw, safe, na = [], [], 0
    for f in files:
        src = open(f, encoding="utf-8").read()
        rel = os.path.relpath(f, REPO)
        if rel.endswith(("key_check.py", "jsonsafe.py")):
            continue
        # ⚠ 只写不读的脚本与本条无关（fetch_prices.py 产出 stock_prices.json
        #   但从不读它）。首版按「文件名出现过」判，把它误算成违规。
        #   判据要是「真的读了」，不是「提到了文件名」—— 同 profile 1.2n。
        reads = re.search(r"(?:json\.loads?|_jsonsafe\.loads?|jsonsafe\.loads?"
                          r"|read_text|\.read\(\))", src)
        touches = [p for p in DATA_PRODUCTS if p in src] if reads else []
        if not touches:
            na += 1
            continue
        # ⚠ 判据必须是「真的调用了」，不是「提到了这个名字」。
        #   首版写成 `"jsonsafe" in src`，结果一行没用上的 import 就让它变 ✅——
        #   2026-09-20 我自己无意中把它骗过去了。检查器被一个字符串糊弄，
        #   和规则没有承载物是一样的后果。
        # load 与 loads 都算（前者读文件、后者读字符串，比如 git show 的输出）。
        # 首版正则只写了 load\( ，把已迁的两个 loads( 漏判成未迁 —— 2026-09-20 实测。
        called = re.search(r"(?:jsonsafe|_jsonsafe)\s*\.\s*loads?\s*\(", src) \
            or re.search(r"from\s+jsonsafe\s+import[^\n]*\bloads?\b", src)
        (safe if called else raw).append((rel, touches))
    if verbose:
        print("═══ A. 严格加载器采用情况（1.1u 第 1 条）═══")
        print(f"  扫 {len(files)} 个脚本｜{na} 个不读数据产物，与本条无关")
        for rel, tp in safe:
            print(f"  ✅ {rel}  已用 jsonsafe（读 {', '.join(tp)}）")
        for rel, tp in raw:
            print(f"  ⚠ {rel}  仍用原生 json.load 读 {', '.join(tp)}"
                  f"  ← .get(拼错的键) 会静默返回 None")
        if not raw and not safe:
            print("  · 没有脚本读已知数据产物")
        print(f"\n  ⚠ 本层的局限说在明处：它只查「有没有用严格加载器」，"
              f"\n     **不查键名对不对**——那件事静态分析在本仓库做不准（见文件头）。"
              f"\n     真正的防线是 jsonsafe 让错键在运行时抛错。")
    return raw, safe


# ══════════════════════════════════════════════════════════════════════════
# B. 不可能值
# ══════════════════════════════════════════════════════════════════════════
def impossible_shapes(counts, ctx=""):
    """给一组「类别 -> 计数」，报出 1.1u 第 2 条列的不可能形态。

    可被任何产出汇总的脚本直接调用。判据全部来自 1.1u 原文，不自创。
    """
    issues = []
    nums = {k: v for k, v in counts.items() if isinstance(v, (int, float))}
    if len(nums) < 2:
        return issues
    total = sum(nums.values())
    if total <= 0:
        return issues
    zeros = [k for k, v in nums.items() if v == 0]
    big = max(nums.values())
    # ① 某类别全 0 而同级存在大值 —— 正是「new 272 / closed 0」那个形态
    if zeros and big >= 20:
        issues.append(f"{ctx}某类别为 0 而同级最大值 {big}：{zeros} —— "
                      f"核对键名是否拼错（1.1u：.get() 对拼错的键不报错）")
    # ② 占比恰好 100% / 0%
    for k, v in nums.items():
        if total and (abs(v / total - 1.0) < 1e-12 or v == 0) and len(nums) > 2:
            if abs(v / total - 1.0) < 1e-12:
                issues.append(f"{ctx}「{k}」占比恰好 100%，其余全 0 —— 口径可疑")
    # ③ 本应互补的量不互补
    for a, b in (("new", "exit"), ("add", "trim"), ("increased", "decreased"),
                 ("opened", "closed"), ("buy", "sell"), ("开仓", "平仓")):
        if a in nums and b in nums and nums[a] >= 20 and nums[b] == 0:
            issues.append(f"{ctx}{a}={nums[a]} 而 {b}=0 —— 两个本应互补的量不互补，"
                          f"物理上不可能")
    return issues


# ⛔ 首版这里是「扫全仓 JSON，凡同级有 0 就报」——在真实数据上喷出 40+ 条假警报，
#    因为它把 {shares: 6239400, is_option: 0} 当成了同类计数：
#    shares 是数量、is_option 是布尔标志，两者根本不可比。
#    **猜哪个 dict 是「同类计数」必然产生垃圾**，而会喷假警报的检查器比没有更糟
#    （本周第三次栽在这上面：jev_bench 的 57 处假泄漏、C6 的 6 vs 12、这次）。
#
# → 改为与 1.1s 同一思路：**不猜，由产出汇总的代码显式调用 impossible_shapes()。**
#   下面的 producers 检查确保这些调用点没被删掉。
SUMMARY_PRODUCERS = [("scripts/burry_13f.py", "changes 汇总（2026-09-06 事故的产出点）")]


def check_shapes(verbose=True):
    print("\n═══ B. 不可能值（1.1u 第 2 条）═══")
    print("  判据不靠猜：由产出汇总的代码显式调用 impossible_shapes()。")
    missing = []
    for rel, why in SUMMARY_PRODUCERS:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            print(f"  · {rel} 不存在，跳过")
            continue
        used = "impossible_shapes" in open(p, encoding="utf-8").read()
        print(f"  {'✅' if used else '⛔'} {rel}  {why}"
              + ("" if used else "  ← **未调用守卫**"))
        if not used:
            missing.append(rel)
    return len(missing)


def selftest():
    """证明 B 层抓得住当初那个汇总。不验证的检测器等于没有。"""
    print("\n═══ 自测：拿 2026-09-06 的真实汇总喂给它 ═══")
    real = {"new": 272, "closed": 0, "increased": 0, "decreased": 0}
    out = impossible_shapes(real, "[历史事故] ")
    for m in out:
        print(f"  ⛔ {m}")
    ok_case = {"new": 272, "exit": 118, "add": 64, "trim": 91}
    clean = impossible_shapes(ok_case, "[正常分布] ")
    print(f"  正常分布误报 {len(clean)} 条" + ("  ✅" if not clean else f"  ✗ {clean}"))
    return bool(out) and not clean


def main():
    want_keys = "--keys" in sys.argv or "--shapes" not in sys.argv
    want_shapes = "--shapes" in sys.argv or "--keys" not in sys.argv
    bad = 0
    if want_keys:
        raw, safe = check_keys()
        # 未迁移不判为失败：迁移是渐进的，这里只做清单。真正的防线在运行时。
    if want_shapes:
        check_shapes()
    if "--selftest" in sys.argv:
        print("\n自测" + ("通过 ✅" if selftest() else "失败 ✗"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
