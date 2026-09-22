#!/usr/bin/env python3
"""HV20 计算器 —— 承载 profile 1.2q / 1.2r

为什么需要它（两个真实事故，都发生在 2026-09-21）：

1.2q  σ 的窗口必须等于合约剩余天数。候选表按 39 天算 σ，结论却配 25 天到期，
      行权价照搬 → 偏保守 $2.5。本工具只输出年化 HV，**不输出行权价**，
      强制调用方自己写明 T。

1.2r  重建的收盘序列比现实晚一天。序列由「第二天快照里的 prevClose」重建，
      所以当日那根收益率要到明天才进窗口。2026-09-21 INTC +11.97% 当天，
      我拿不含这根的 HV20=60.2% 去和实测 IV=69.4% 比，得出「IV 溢价 9.2pct，
      这是卖方的边」——补上那根后 HV=69.0%，**真实溢价 +0.4pct，边约等于零。**
      → 本工具默认补当日收益率，并在当日绝对涨跌 >5% 时显式警告。

另一个已修的坑：**同一交易日内 prevClose 会是陈旧值**
（实测 2026-08-31 14:37Z 仍写 92.09，19:22Z 才更正为 89.47）。
→ 每日必须取**最后一个**快照的 prevClose，不能取第一个。取错会让 INTC 的
  HV20 从 60.2% 变成 88.6%。
"""
import subprocess, json, math, statistics, sys

BRANCH = "claude/install-claude-hud-d51E6"   # ⚠ 本仓库默认分支不是 main（profile 1.1f）
WINDOW = 20                                   # 与 skill 中「HV20」一一对应（1.2f：窗口要对齐）
TRADING_DAYS = 252
BIG_MOVE = 0.05                               # 当日绝对涨跌超过此值 → IV/HV 对比需警告


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def load_snapshots(branch=BRANCH):
    shas = _git("log", "--format=%H", f"origin/{branch}", "--", "stock_prices.json").split()
    snaps = []
    for s in shas:                            # git log 是新→旧，保持这个顺序
        try:
            snaps.append(json.loads(_git("show", f"{s}:stock_prices.json")))
        except json.JSONDecodeError:
            continue                          # 窄 except：只吞解析失败（profile 1.2o）
    if not snaps:
        sys.exit("没有读到任何 stock_prices.json 快照——先确认 origin 已 fetch")
    return snaps


def close_series(snaps):
    """date -> ticker -> prevClose，取每日**最后**一个快照（见模块 docstring）。"""
    byday = {}
    for d in snaps:                           # 新→旧，setdefault 保留最先遇到的 = 当日最晚
        rec = byday.setdefault(d["updated_at"][:10], {})
        for t, v in d.get("prices", {}).items():
            if v.get("prevClose"):
                rec.setdefault(t, v["prevClose"])
    return byday


def hv(snaps=None, window=WINDOW):
    snaps = snaps or load_snapshots()
    byday = close_series(snaps)
    latest = snaps[0]
    out = {}
    for t, cur in latest["prices"].items():
        closes = []
        for day in sorted(byday):
            pc = byday[day].get(t)
            if pc and (not closes or pc != closes[-1]):
                closes.append(pc)
        if len(closes) < 8:
            continue
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        today = None
        if cur.get("prevClose") and cur.get("price"):
            today = math.log(cur["price"] / cur["prevClose"])
            rets = rets + [today]             # ← 1.2r 的修复
        use = rets[-window:]
        out[t] = {
            "hv": statistics.pstdev(use) * math.sqrt(TRADING_DAYS),
            "n": len(use),
            "today_ret": today,
            "stale_warning": today is not None and abs(math.exp(today) - 1) > BIG_MOVE,
        }
    return latest["updated_at"], out


def sigma(price, hv_annual, days_to_expiry):
    """1σ over the contract's own remaining days. T 必须由调用方传，不得继承（1.2q）。"""
    return price * hv_annual * math.sqrt(days_to_expiry / 365)


if __name__ == "__main__":
    asof, res = hv()
    print(f"as of {asof}  窗口 {WINDOW} 根收益率（已含当日）")
    print(f"{'T':6s}{'HV20':>8s}{'n':>4s}{'当日%':>9s}")
    for t in sorted(res):
        v = res[t]
        chg = (math.exp(v["today_ret"]) - 1) * 100 if v["today_ret"] is not None else 0.0
        flag = "  ⚠ 当日大幅波动：IV/HV 对比在今天不可信" if v["stale_warning"] else ""
        print(f"{t:6s}{v['hv']*100:7.1f}%{v['n']:4d}{chg:+8.2f}%{flag}")
