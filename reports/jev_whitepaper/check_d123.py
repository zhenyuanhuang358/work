#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""huashu-report 交付前的 D1/D2/D3b 三项检查。

**为什么需要这个文件**：CLAUDE.md 规定 huashu-report 不走 Critic（它交付 PDF 不是 HTML，
且自带两层自检），但「D1 数据来源 / D2 内部数字一致性 / D3b 答案前置 仍然适用，
交付前手工过这三项」。**「手工过」是一条没有承载物的规则**——profile 1.2a 说过，
没有承载物的规则等于不存在。这个脚本就是它的承载物。

本次实跑抓到的两类问题，都不是眼睛能看出来的：
  1. 元统计把自己算进了分母（自指）→ 封面写 59、数据表实为 57，而且不报错
  2. 检查脚本自己的口径与正文不一致 → 第一版报 T0+T1=22 而正文写 19，
     实际是脚本数了 M* 元统计。**检查器的口径也要对**，否则它制造假警报。

用法：python3 check_d123.py
"""
import collections
import json
import re
import subprocess
import sys
from math import comb

TABLE, PDF, HTML = "数据表.json", "报告.pdf", "报告.html"

# 正文里手写（而非由 V() 插值）的关键数字 → 它在数据表里的编号。
# 凡手写就有漂的可能，这张表就是漂移检测的靶子。
MANUAL = {"164": "J1", "55.5%": "J3/J4", "217": "R1", "300": "C1", "255": "C3",
          "32 秒": "C14", "21.3 倍": "C15", "66.7%": "M2", "94.7%": "C8",
          "93.0%": "C8", "6.9%": "R3"}


def mcnemar(b, c):
    n, k = b + c, max(b, c)
    return min(2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n, 1.0)


def main():
    d = json.load(open(TABLE, encoding="utf-8"))
    # ⚠ 口径：实质数据点不含 M* 元统计。统计自己会形成自指，
    #    而且会让分母比正文大 3，制造一个看起来像真事的假不一致。
    sub = {k: v for k, v in d.items() if not k.startswith(("_", "M"))}
    allp = {k: v for k, v in d.items() if not k.startswith("_")}
    pdf = subprocess.run(["pdftotext", PDF, "-"], capture_output=True, text=True).stdout
    tiers = collections.Counter(v["tier"] for v in sub.values())
    bad = []

    print("═══ D1 数据来源 ═══")
    miss = [k for k, v in allp.items()
            if not all(v.get(f) for f in ("value", "basis", "n", "src", "tier"))]
    print(f"  字段完整：{'✓ %d 条全有 value/basis/n/src/tier' % len(allp) if not miss else '✗ ' + str(miss)}")
    bad += miss
    thin = [k for k, v in allp.items() if len(v["basis"]) < 20]
    print(f"  口径够不够一句话：{'✓' if not thin else '⚠ 偏短 ' + str(thin)}")
    print(f"  层级分布：{dict(sorted(tiers.items()))}")
    nver = sum(1 for v in sub.values() if not v["verified"])
    print(f"  不可独立核验：{nver}/{len(sub)} = {nver/len(sub):.1%}")

    print("\n═══ D2 内部数字一致性 ═══")
    m1_den = int(allp["M1"]["value"].split("/")[1])
    m3_want = " / ".join(f"{t}:{tiers[t]}" for t in sorted(tiers))
    for name, got, want in [
            ("M1 分母 == 实质数据点数", m1_den, len(sub)),
            ("M1 分子 == 实算不可核验数", int(allp["M1"]["value"].split("/")[0]), nver),
            ("M2 == 分子/分母", allp["M2"]["value"], f"{nver/len(sub):.1%}"),
            ("M3 == 实算层级分布", allp["M3"]["value"], m3_want)]:
        ok = got == want
        print(f"  {name}：{got} {'✓' if ok else '✗ 期望 ' + str(want)}")
        if not ok:
            bad.append(name)

    for s, who in MANUAL.items():
        if s not in pdf:
            print(f"  ✗ 手写数 {s}（{who}）在 PDF 中找不到——多半是改了数据表没改正文")
            bad.append(s)
    print(f"  手写数字对照：{'✓ %d 个关键数全部出现在 PDF 中' % len(MANUAL) if not bad else ''}")

    for b, c, want in [(9, 3, 0.146), (8, 4, 0.388)]:
        got = mcnemar(b, c)
        ok = abs(got - want) < 1e-3
        print(f"  McNemar b={b},c={c} → {got:.3f} {'✓' if ok else '✗'}")
        if not ok:
            bad.append("McNemar")
    lo = (284 - 255) / 45
    print(f"  低把握档反推 (284−255)/45 = {lo:.1%} "
          f"{'✓ 落在 C5 区间内' if 0.622 <= lo <= 0.667 else '✗ 超出 C5 区间'}")

    print("\n═══ D3b 答案前置 ═══")
    for name, cond in [("摘要编号事实 F1–F8 渲染出来", all(f"F{i}" in pdf for i in range(1, 9))),
                       ("封面第 1 页即给出论点", "证据未决" in pdf[:1200]),
                       ("「一句话」结论在摘要页", "三行 if-else 能得几分" in pdf[:4000])]:
        print(f"  {name}：{'✓' if cond else '✗'}")
        if not cond:
            bad.append(name)

    print("\n" + ("✓ D1/D2/D3b 全部通过" if not bad else "✗ 仍有问题：" + "; ".join(map(str, bad))))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
