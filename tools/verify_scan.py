#!/usr/bin/env python3
"""扫描报告 ↔ scan.json 机器核对（2026-11-06 改造：把「报告必须……」的文字要求变成检查）

为什么：交付的报告此前没有任何检查——数字是否来自工具、每个候选是否带 📰 与跳空、首行是不是结论、
红灯 / 事件前一日是否仍写了「开」，全靠会话自觉。11/05 的验收标准（用户确认）逐条对应下面的 V 项。
主观部分（新闻鹰鸽判断是否合理、措辞）不在这里查，留人工。

用法：python3 tools/verify_scan.py <报告.md> [--scan <scan.json>]   （不给 --scan 用同名 .json 或最新一份）
退出码 0 = 全部通过；1 = 有不通过项。结果连同报告的 sha256 写回 scan.json 的 verification——
报告改了 sha 就对不上，self_check 会点名「报告改过但没重新核对」。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

CONTRACT = re.compile(r"\b([A-Z]{1,5})\s+(20\d\d-\d\d-\d\d)\s+(\d+(?:\.\d+)?)([PC])\b")


def run(report_path, scan_path=None):
    if not scan_path:
        base = os.path.splitext(report_path)[0]
        scan_path = base + ".json" if os.path.exists(base + ".json") else \
            sorted(glob.glob(os.path.join(os.path.dirname(report_path) or ".", "*.json")))[-1]
    s = json.load(open(scan_path))
    text = open(report_path).read()
    lines = [l for l in text.splitlines()]
    ok_rows = {(x["ticker"], x["expiry"], float(x["strike"]), side): x
               for side, res in s["sides"].items() for x in res["ok"]}
    res = []

    def check(vid, name, passed, evidence):
        res.append({"id": vid, "check": name, "pass": bool(passed), "evidence": evidence})

    first = next((l for l in lines if l.strip()), "")
    check("V1", "首行是结论", first.startswith("结论"), first[:80])
    says_no = "不开" in first
    check("V2", "结论与闸门一致（不能开时必须写不开）", s["can_open"] or says_no,
          f"can_open={s['can_open']} why_not={s['why_not']}｜首行：{first[:60]}")
    check("V3", "有「今日消息面」与「平台核实」两节", "今日消息面" in text and "平台核实" in text, "")
    check("V4", "没有残留【待判断】占位", "【待判断" not in text, f"残留 {text.count('【待判断')} 处")

    mentioned = []
    for i, l in enumerate(lines):
        for m in CONTRACT.finditer(l):
            mentioned.append((i, (m.group(1), m.group(2), float(m.group(3)), m.group(4))))
    unknown = sorted({f"{k[0]} {k[1]} {k[2]:g}{k[3]}" for _, k in mentioned if k not in ok_rows})
    check("V5", "报告里的合约都在工具过关行里（防编造 / 防带 ⛔ 的合约混进来）", not unknown, f"不在底稿：{unknown}")

    bad_num, no_news, no_gap, no_stop = [], [], [], []
    for i, k in mentioned:
        if k not in ok_rows:
            continue
        x = ok_rows[k]
        block = "\n".join(lines[i:i + 5])
        m = re.search(r"收入\s*\$?(\d+(?:\.\d+)?)", lines[i])
        if m and abs(float(m.group(1)) - x["income"]) > 1:
            bad_num.append(f"{k[0]} {k[2]:g}{k[3]} 报告 {m.group(1)} vs 底稿 {x['income']:.0f}")
        if "📰" not in block:
            no_news.append(f"{k[0]} {k[2]:g}{k[3]}")
        if "跳空" not in block:
            no_gap.append(f"{k[0]} {k[2]:g}{k[3]}")
        if "1/3/6" not in block and "止损亏损" not in block:
            no_stop.append(f"{k[0]} {k[2]:g}{k[3]}")
    check("V6", "合约收入与底稿一致（±$1）", not bad_num, bad_num)
    # V11（11/06 用户反馈「看不出是卖 put 还是买 put」）：每个合约附近必须写明「卖出 … put / call」，且与底稿方向一致
    no_act = []
    for i, k in mentioned:
        if k not in ok_rows:
            continue
        near = "\n".join(lines[max(0, i - 1):i + 1])
        want = "put" if k[3] == "P" else "call"
        if not re.search(rf"卖出\s*{k[0]}\s*{k[2]:g}\s*{want}", near):
            no_act.append(f"{k[0]} {k[2]:g}{k[3]}（应写「卖出 {k[0]} {k[2]:g} {want}」）")
    check("V7", "每个合约带 📰 行", not no_news, no_news)
    # V12（11/06 用户：非农抓不到不能算了）：当天公布的高影响数据，报告必须写出实际值
    miss_macro = []
    for m in s.get("macro_today", []):
        num = f"{m['actual']:g}"
        alt = {f"{m['actual'] / 10:g}", f"{m['actual'] * 1000:,.0f}", f"{m['actual']:.1f}", f"{round(m['actual'], 1):g}"}
        if m["name"] not in text or not any(x in text for x in {num} | alt):
            miss_macro.append(f"{m['name']} 实际 {num}{m['unit']}")
    check("V12", "当天公布的宏观数据写出了实际值", not miss_macro, miss_macro)
    check("V11", "每个合约写明买卖方向与 put / call（不能只写代码）", not no_act, no_act)
    check("V8", "每个合约带跳空压力", not no_gap, no_gap)
    check("V9", "每个合约带 1/3/6 张止损亏损", not no_stop, no_stop)
    f = s["freshness"]
    check("V10", "数据新鲜，或报告明说不新鲜", f["ok"] or "不新鲜" in text,
          {k: v for k, v in f.items() if k != "ok"})

    allp = all(r["pass"] for r in res)
    s["verification"] = {"report": os.path.basename(report_path),
                         "report_sha256": hashlib.sha256(text.encode()).hexdigest(), "pass": allp, "checks": res}
    json.dump(s, open(scan_path, "w"), ensure_ascii=False, indent=1, default=str)
    for r in res:
        print(f"{'✅' if r['pass'] else '❌'} {r['id']} {r['check']}" + ("" if r["pass"] else f"｜{r['evidence']}"))
    print("全部通过" if allp else "有不通过项：改报告后重跑本命令")
    return 0 if allp else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--scan")
    a = ap.parse_args()
    sys.exit(run(a.report, a.scan))
