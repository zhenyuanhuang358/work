#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分项加总校验 —— profile 1.1s 的承载物。

**1.1s 原文**：凡同表并列「总额＋分项」，自己先加一遍。
加不平就写明差额去向（或写明「余额为本表未列示项」），不要留给读者去发现。

**它为什么一直是「人工执行」**：这条规则立于 2026-09-02（绿茶 2026H1：
堂食 20.14 + 外卖 6.51 = 26.65，总额 26.75，差 0.10 亿 = 0.4%，
两个数都列了却没说差额）。立规之后三周，self_check C2 一直把它标为
「⚠ 人工执行（依赖每次自觉）」——而按 1.2a，靠自觉的规则迟早静默失效。

**这个脚本最大的风险不是漏报，是误报。**
真实报告里的表格很脏：区间值（1,200–1,350万）、「不可得」、单位混在格子里、
带注释的单元格。一个见数就加的检查器会喷出大量假警报，
然后被当成噪音关掉——**那比没有检查器更糟**（同 jev_bench 那次把 57 处
数值巧合误报成「信息泄漏」）。

所以口径刻意收窄，**只在「真的算得准」时才出结论**：
  · 必须有一行明确标着 合计/总计/总额/Total
  · 该列除总额外还要有 ≥2 个能解析成单一数字的分项
  · 区间值、百分比、「不可得/缺口/待核」、含多个数字的单元格 → 该列整列跳过
  · 差额 ≤ 各项四舍五入误差上限 → 判为「舍入可解释」，不报警
凡不满足的，输出 SKIP 并写明跳过原因——**跳过要可见，不能静默**
（同 jev_bench 的 dropped_my_calls：只报「跳过 N 条」不够，N 不会让人去看它删了谁）。

用法：
    python3 tools/sum_check.py reports/xxx.html      # 查一个文件
    python3 tools/sum_check.py --all                 # 查 reports/ 下全部 HTML
    python3 tools/sum_check.py --all --quiet         # 只输出有问题的
"""
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOTAL_WORDS = re.compile(r"合计|总计|总额|小计|Total", re.I)
# 表内或表附近出现这些词，视为「差额已说明」，不再报警
EXPLAINED = re.compile(r"差额|尾差|余额|未列示|四舍五入|舍入|不含|其中[：:]|剔除|口径差异")
# 这些单元格无法参与加总，整列跳过
UNPARSEABLE = re.compile(r"[–~至]\s*\d|不可得|缺口|待核|待补|未披露|n/?a", re.I)


def cells_of(row_html):
    return [re.sub(r"<[^>]+>", " ", c) for c in
            re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.S)]


def parse_num(s):
    """把单元格解析成 (值, 末位小数位数)；不确定就返回 None。

    ⚠ 只接受「整个单元格就是一个数」的情形。带区间、带两个数、
    带百分号的一律不接 —— 宁可跳过，不可猜。
    """
    t = re.sub(r"<[^>]+>", " ", s)
    t = t.replace(",", "").replace("，", "").strip()
    t = re.sub(r"^[¥$€£]|亿元?$|万元?$|元$|人次$|家$|个$|张$", "", t).strip()
    if not t or UNPARSEABLE.search(t):
        return None
    if "%" in t or "％" in t:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?", t)
    if len(nums) != 1:
        return None                      # 零个或多个数字 → 不确定，跳过
    # 单元格里除了这个数还有别的实质内容（注释、文字）→ 跳过
    if len(re.sub(r"-?\d+(?:\.\d+)?|[\s.．]", "", t)) > 0:
        return None
    v = float(nums[0])
    dec = len(nums[0].split(".")[1]) if "." in nums[0] else 0
    return v, dec


def check_table(tb, context):
    """返回 [(状态, 说明)]，每列一条。状态 ∈ OK / ROUND / GAP / SKIP。"""
    rows = re.findall(r"<tr.*?</tr>", tb, re.S)
    grid = [cells_of(r) for r in rows]
    grid = [g for g in grid if g]
    if len(grid) < 3:
        return [("SKIP", "行数 <3，构不成「总额＋分项」")]
    tot_idx = [i for i, g in enumerate(grid) if g and TOTAL_WORDS.search(g[0])]
    if not tot_idx:
        return []                          # 没有总额行，本表与 1.1s 无关
    ti = tot_idx[-1]
    ncol = max(len(g) for g in grid)
    out = []
    for c in range(1, ncol):
        tot = parse_num(grid[ti][c]) if c < len(grid[ti]) else None
        if tot is None:
            out.append(("SKIP", f"第{c+1}列：总额格解析不出单一数字"))
            continue
        parts, bad = [], 0
        for i, g in enumerate(grid):
            if i == ti or i == 0 or c >= len(g):
                continue
            if TOTAL_WORDS.search(g[0] if g else ""):
                continue                   # 其它小计行不算分项
            v = parse_num(g[c])
            if v is None:
                if re.sub(r"\s", "", g[c]):
                    bad += 1
            else:
                parts.append(v)
        if bad:
            out.append(("SKIP", f"第{c+1}列：{bad} 个分项格无法解析（区间/文字/缺口），整列跳过"))
            continue
        if len(parts) < 2:
            out.append(("SKIP", f"第{c+1}列：可解析分项 {len(parts)} 个 <2"))
            continue
        s = sum(v for v, _ in parts)
        diff = s - tot[0]
        # 舍入误差上限：每个数各自末位的半个单位，再加总额自己的
        tol = sum(0.5 * 10 ** (-d) for _, d in parts) + 0.5 * 10 ** (-tot[1])
        rel = abs(diff) / abs(tot[0]) if tot[0] else float("inf")
        desc = (f"第{c+1}列：分项和 {s:.10g} vs 总额 {tot[0]:.10g}"
                f"，差 {diff:+.10g}（{rel:+.2%}）")
        if abs(diff) < 1e-9:
            out.append(("OK", desc))
        elif abs(diff) <= tol:
            out.append(("ROUND", desc + f"，≤ 舍入上限 {tol:.10g}"))
        elif EXPLAINED.search(tb) or EXPLAINED.search(context):
            out.append(("ROUND", desc + "，但表内/附近已有差额说明"))
        else:
            out.append(("GAP", desc + "，**且未见差额说明** ← 1.1s 违规"))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 第二层（真正管用的那层）：数据表里**声明**的加总关系
# ══════════════════════════════════════════════════════════════════════════
# 为什么需要这一层：第一层（HTML 同表合计行）在真实产物上跑完 43 个文件
# 只加平了 2 列、跳过 30 列，**而且抓不到 1.1s 立规的那个案例**——
# 因为绿茶那次的总额与分项根本不在同一张表里（26.748 在公司对比表，
# 20.14/6.51 在收入拆分处）。**一个抓不到立规案例的检查器是装饰。**
#
# 真实的失败形态不是「同表加不平」，是「同一份交付物里我断言了总额也断言了分项」。
# 这在一般情况下需要语义才能识别，但有一个便宜且精确的解法：
# **把关系声明出来。** 数据表里给总额加一个 parts 字段，机器就能精确核。
#
# ⚠ 诚实的局限：**只查声明过的关系。忘了声明就不会触发。**
#    它把 1.1s 从「每次记得加一遍」降级为「记得声明一次」——
#    没有消灭自觉，但把自觉的次数从「每次交付」降到「每个关系一次」，
#    而且声明之后永远由机器复核（改数字也会重算）。

FIRST_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def lead_num(val):
    """取 value 字符串里的第一个数（本仓库数据表的约定是「数值 / 增速 / 占比」）。"""
    m = FIRST_NUM.search(str(val).replace(",", ""))
    return float(m.group(0)) if m else None


def check_declared(path):
    """核 数据表.json 里声明的加总关系：{"parts": ["G4","G5"]}。"""
    import json
    d = json.load(open(path, encoding="utf-8"))
    rows = d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), list) else None
    items = ({r["id"]: r for r in rows} if rows
             else {k: v for k, v in d.items() if not k.startswith("_")})
    out = []
    for tid, rec in items.items():
        parts = rec.get("parts")
        if not parts:
            continue
        tot = lead_num(rec.get("value"))
        vals, missing = [], []
        for pid in parts:
            if pid not in items:
                missing.append(pid); continue
            v = lead_num(items[pid].get("value"))
            (vals.append((pid, v)) if v is not None else missing.append(pid))
        if tot is None or missing:
            # ⚠ 声明层的「算不出来」不是 SKIP，是 GAP。
            #    HTML 那层的 SKIP 意思是「这张表本来就不该被查」；
            #    而这里我**明确声明了**一个加总关系——它算不出来，就是声明本身坏了
            #    （ID 打错、value 取不到数）。判成 SKIP 会让一个写错字的声明
            #    静默通过，整体还显示 ✓。2026-09-20 破坏性测试情形③命中。
            out.append(("GAP", f"{tid}: **声明坏了，无法核验**"
                               f"（总额取数 {tot}，取不到数的分项 {missing}）"))
            continue
        s = sum(v for _, v in vals)
        diff = s - tot
        detail = (f"{tid} = " + " + ".join(f"{pid}({v:g})" for pid, v in vals)
                  + f" → 分项和 {s:.10g} vs 总额 {tot:.10g}，差 {diff:+.10g}"
                  + (f"（{diff/tot:+.2%}）" if tot else ""))
        if abs(diff) < 1e-9:
            out.append(("OK", detail))
        elif EXPLAINED.search(str(rec.get("basis", ""))) or any(
                EXPLAINED.search(str(items[pid].get("basis", ""))) for pid, _ in vals):
            out.append(("ROUND", detail + "，已在口径里写明差额 ✓"))
        else:
            out.append(("GAP", detail + "，**口径里未见差额说明** ← 1.1s 违规"))
    return out


def check_tables(quiet=False):
    """扫 reports/ 下全部 数据表.json 的声明关系。"""
    stats = {"OK": 0, "ROUND": 0, "GAP": 0, "SKIP": 0}
    files = sorted(glob.glob(os.path.join(REPO, "reports", "**", "数据表.json"),
                             recursive=True))
    for f in files:
        res = check_declared(f)
        rel = os.path.relpath(f, REPO)
        decl = len(res)
        if not decl:
            if not quiet:
                print(f"· {rel}  未声明任何加总关系")
            continue
        for st, desc in res:
            stats[st] += 1
        bad = [d for s, d in res if s == "GAP"]
        print(f"{'❌' if bad else '✓'} {rel}  声明关系 {decl} 条"
              f"｜加平 {sum(1 for s,_ in res if s=='OK')}"
              f"｜有说明 {sum(1 for s,_ in res if s=='ROUND')}"
              f"｜**未说明 {len(bad)}**")
        for s, d in res:
            if s in ("GAP", "ROUND") or not quiet:
                print(f"     {'⛔' if s=='GAP' else '  '} {d}")
    return stats, len(files)


def check_file(path, quiet=False):
    h = open(path, encoding="utf-8", errors="ignore").read()
    gaps, stats = [], {"OK": 0, "ROUND": 0, "GAP": 0, "SKIP": 0}
    for m in re.finditer(r"<table.*?</table>", h, re.S):
        tb = m.group(0)
        ctx = h[max(0, m.start() - 700):m.end() + 700]
        for st, desc in check_table(tb, ctx):
            stats[st] += 1
            if st == "GAP":
                gaps.append(desc)
    if stats["GAP"] or not quiet:
        tag = "❌" if stats["GAP"] else ("✓" if stats["OK"] or stats["ROUND"] else "·")
        print(f"{tag} {os.path.relpath(path, REPO)}"
              f"  加平 {stats['OK']}｜舍入/已说明 {stats['ROUND']}｜"
              f"**差额未说明 {stats['GAP']}**｜跳过 {stats['SKIP']}")
        for g in gaps:
            print(f"     ⛔ {g}")
    return stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    if "--all" in sys.argv or not args:
        files = sorted(glob.glob(os.path.join(REPO, "reports", "**", "*.html"),
                                 recursive=True))
    else:
        files = args
    total = {"OK": 0, "ROUND": 0, "GAP": 0, "SKIP": 0}
    print("═══ 第一层：HTML 同表「合计行 + 分项」═══")
    for f in files:
        for k, v in check_file(f, quiet).items():
            total[k] += v
    print("\n═══ 第二层：数据表里声明的加总关系（parts 字段）═══")
    ds, nds = check_tables(quiet)
    for k, v in ds.items():
        total[k] += v
    print(f"\n共 {len(files)} 个文件｜加平 {total['OK']}｜舍入或已说明 {total['ROUND']}"
          f"｜**差额未说明 {total['GAP']}**｜跳过 {total['SKIP']}")
    if total["SKIP"]:
        print(f"  ⚠ 跳过 {total['SKIP']} 列是刻意的——口径收窄到「真的算得准」才出结论。"
              f"\n    跳过原因逐条打印（不用 --quiet 时可见），**不静默丢弃**。")
    return 1 if total["GAP"] else 0


if __name__ == "__main__":
    sys.exit(main())
