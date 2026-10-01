#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""期权候选全量登记 + 到期结算 —— 让「缓冲÷1σ 排序到底有没有用」可以被检验。

**为什么要有它**（2026-10-01，借鉴 github.com/dominickkubica/options-scanner）：
  us-options-agent 从 7 月起每次扫描都在 journal 里写「候选与裁定」，但写的是散文，
  **从来没有一条被结算过**——推荐的那几个后来跌没跌破行权价、被否决的那几个呢？
  不知道。于是「缓冲÷1σ ≥ X 才做」这条核心规则，至今是信念，不是被验证过的结论。

  options-scanner 的三条做法直接搬过来：
  1. **全量登记，不只登记推荐的。** 只记推荐项的研究无法检验评分——
     你不知道被否决的那些如果做了会怎样。否决项必须带理由一起记。
  2. **只追加，不改写。** 登记的分数和事后结算都不能覆盖。结算不落盘，
     每次从价格历史现算——同一份历史永远算出同一个结果。
  3. **独立单位是 (标的, 到期日) 簇，不是行。** 同一次扫描同一条链出的几个行权价
     一起涨跌，算成 5 个样本是自欺。**不满 20 簇，report 拒绝下结论。**

**1σ 的口径服从 profile 1.1x / 1.2q**：只有 iv_src = 平台反解 才算 z = 缓冲÷1σ；
  没有实测 IV 的候选照样登记（它的结果仍然有用），但 z 留空，不参与分桶。

**结算的局限（每次 report 都会打印）**：
  - 价格来自 stock_prices.json 的 git 历史（抓价日的 close/low），只覆盖被抓价的 27 个标的；
    池外标的记为「无价源」，不猜。
  - 「触及」用抓价日的 low 判断，缺抓价的交易日看不到 → 触及率是**下限**。
  - 到期日当天没有收盘读数 → 记「缺收盘」，**不拿前一天或盘中读数代替**（predictions 第 9 条）。
  - 按持有到期结算是反事实：多数仓位会提前平仓。用它是因为 PoP 本来就是按到期定义的，
    而且到期是更坏的那条尾巴。

用法：
  python3 tools/candidate_ledger.py add --ticker HOOD --right P --strike 82.5 \\
      --expiry 2026-10-16 --spot 97.46 --verdict 推荐 --reason "缓冲17%，IV实测" \\
      [--iv 0.65 --iv-src 平台反解] [--bid 1.70]
  python3 tools/candidate_ledger.py report
"""
import argparse
import datetime as dt
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "memory", "state", "options-candidates.jsonl")
sys.path.insert(0, os.path.join(REPO, "tools"))

MIN_CLUSTERS = 20
VERDICTS = ("推荐", "否决")


def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    rows = []
    with open(LEDGER, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"⛔ {LEDGER} 第 {n} 行不是合法 JSON：{e}——账本只追加，坏行要人工看，不跳过")
    return rows


def z_score(row):
    """缓冲÷1σ。只在 IV 是平台反解时给数，否则 None。"""
    if row["iv_src"] != "平台反解" or not row["iv"]:
        return None
    dte = (dt.date.fromisoformat(row["expiry"]) - dt.date.fromisoformat(row["logged"][:10])).days
    if dte <= 0:
        return None
    sigma = row["iv"] * math.sqrt(dte / 365)
    return round(row["buffer"] / sigma, 2)


def add(a):
    if a.verdict not in VERDICTS:
        sys.exit(f"--verdict 只能是 {VERDICTS}")
    if a.verdict == "否决" and not a.reason:
        sys.exit("否决项必须写理由——不带理由的否决，事后无法分辨是规则挡住的还是嫌麻烦")
    if a.iv is not None and a.iv_src != "平台反解":
        sys.exit("给了 --iv 却不是平台反解：按 1.1x，估出来的 IV 不登记（否则 z 会被污染）")
    right = a.right.upper()
    buffer = (a.spot - a.strike) / a.spot if right == "P" else (a.strike - a.spot) / a.spot
    row = {
        "logged": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "ticker": a.ticker.upper(), "right": right, "strike": a.strike,
        "expiry": a.expiry, "spot": a.spot, "buffer": round(buffer, 4),
        "iv": a.iv, "iv_src": a.iv_src or "无", "bid": a.bid,
        "verdict": a.verdict, "reason": a.reason or "",
    }
    row["z"] = z_score(row)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    z = "—（无实测 IV）" if row["z"] is None else row["z"]
    print(f"已登记 {row['ticker']} {right}{a.strike} {a.expiry}｜{a.verdict}｜缓冲 {buffer:.1%}｜z {z}")


def settle(row, closes):
    """返回 (状态, 是否触及)。状态：未到期 / 无价源 / 缺收盘 / 价内 / 价外。"""
    today = dt.date.today().isoformat()
    if row["expiry"] >= today:
        return "未到期", None
    start = row["logged"][:10]
    window = [(d, b, p) for d, b, p in closes if start < d <= row["expiry"]]
    if not any(row["ticker"] in p["prices"] for _, _, p in window):
        return "无价源", None
    touched = False
    for _, _, p in window:
        q = p["prices"].get(row["ticker"])
        if not q:
            continue
        extreme = q.get("low") if row["right"] == "P" else q.get("high")
        if extreme is not None and (extreme <= row["strike"] if row["right"] == "P" else extreme >= row["strike"]):
            touched = True
    last = [x for x in window if x[0] == row["expiry"]]
    if not last or last[0][1] != "close" or row["ticker"] not in last[0][2]["prices"]:
        return "缺收盘", touched
    px = last[0][2]["prices"][row["ticker"]]["price"]
    itm = px < row["strike"] if row["right"] == "P" else px > row["strike"]
    return ("价内" if itm else "价外"), touched


def bucket(z):
    if z is None:
        return "z 无（无实测 IV）"
    return "z < 1.0" if z < 1.0 else ("1.0 ≤ z < 1.5" if z < 1.5 else "z ≥ 1.5")


def report():
    rows = read_ledger()
    if not rows:
        print(f"账本为空：{LEDGER}\n从下一次扫描开始，每个候选（含否决项）都用 add 登记。")
        return
    from jev_bench import load_daily_closes
    closes = load_daily_closes()
    settled = []
    status_count = {}
    for r in rows:
        st, touched = settle(r, closes)
        status_count[st] = status_count.get(st, 0) + 1
        if st in ("价内", "价外"):
            settled.append((r, st, touched))
    clusters = {(r["ticker"], r["expiry"]) for r, _, _ in settled}
    print(f"登记 {len(rows)} 条｜" + "｜".join(f"{k} {v}" for k, v in sorted(status_count.items())))
    print(f"已结算 {len(settled)} 条，独立簇 (标的, 到期日) {len(clusters)} 个")
    if len(clusters) < MIN_CLUSTERS:
        print(f"\n⛔ 不足 {MIN_CLUSTERS} 簇，不下任何结论。"
              f"\n   不到门槛就说「推荐的都没破」是拿噪声当发现——同 predictions 规则 10 的样本门槛。")
    else:
        for label, key in (("按裁定", lambda r: r["verdict"]), ("按 z 分桶", lambda r: bucket(r["z"]))):
            print(f"\n{label}：")
            groups = {}
            for r, st, touched in settled:
                g = groups.setdefault(key(r), {"n": 0, "itm": 0, "touch": 0, "cl": set()})
                g["n"] += 1
                g["itm"] += st == "价内"
                g["touch"] += bool(touched)
                g["cl"].add((r["ticker"], r["expiry"]))
            for k in sorted(groups):
                g = groups[k]
                print(f"  {k:<18} 行 {g['n']:>3}｜簇 {len(g['cl']):>3}｜到期价内 {g['itm']/g['n']:.0%}"
                      f"｜期间触及 ≥{g['touch']/g['n']:.0%}")
    print("\n局限：只覆盖抓价的 27 个标的；触及按抓价日 low 判断，是下限；"
          "按持有到期结算是反事实（多数仓位会提前平）。")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--ticker", required=True)
    p.add_argument("--right", default="P", choices=["P", "C", "p", "c"])
    p.add_argument("--strike", type=float, required=True)
    p.add_argument("--expiry", required=True, help="YYYY-MM-DD")
    p.add_argument("--spot", type=float, required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--iv", type=float, help="小数，如 0.65；仅限平台实价反解")
    p.add_argument("--iv-src", dest="iv_src")
    p.add_argument("--bid", type=float, help="卖方腿的 bid（成交按 bid 记，不按 mid）")
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "add":
        dt.date.fromisoformat(a.expiry)
        add(a)
    else:
        report()


if __name__ == "__main__":
    main()
