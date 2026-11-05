#!/usr/bin/env python3
"""实盘阶梯加码核对：新规则（2026-11-05 起）下的每笔真实交易 → 五项门槛 → 当前该开几张

为什么：用户 11/05 定「先证明有优势，再按证据加张数」。门槛若只写在文档里，复盘时就会靠记忆和感觉——
profile 1.2a：规则在有承载物之前不算立住。本工具就是承载物。

账本：memory/state/options-trades.jsonl（只记 2026-11-05 新规则之后的实盘；旧交易的教训在 profile 1.2r）
  开仓：python3 tools/scale_check.py open --ticker XLE --right P --strike 63 --expiry 2026-11-13 \\
            --contracts 1 --credit 0.14 --ask 0.16 --ivhv 1.45 [--date 2026-11-11]
  平仓：python3 tools/scale_check.py close --id <开仓时打印的 id> --price 0.07 --how 止盈|止损|到期|强平|手动 [--fees 1.30]
  核对：python3 tools/scale_check.py report

五项门槛（全部满足才可升一阶；任一轮不达标退一阶；连续两轮不达标停止卖方）：
  1. 本轮 ≥ 20 个独立簇（标的 × 到期日），且跨度 ≥ 6 周（单一行情阶段不算数）
  2. 扣报价差与手续费后，每 $1 收入净 ≥ +0.30（成交价已含报价差；手续费单独记）
  3. 最差一笔 ≥ −2.5 × 收入
  4. 止损按时成交率 ≥ 90%（止损成交价 ≤ 2.5 × 收入算按时；强平一律算不按时）
  5. 入场 IV ÷ HV30 平均 ≥ 1.2
阶梯：第 1 阶 1 张 → 第 2 阶 2 张 → 第 3 阶 3 张（另需保证金占用 ≤ 可取现金 50%）。
"""
import argparse
import datetime as dt
import json
import os
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(REPO, "memory", "state", "options-trades.jsonl")
ROUND = 20          # 每轮需要的独立簇数
MIN_WEEKS = 6
GATES = {"edge": 0.30, "worst": -2.5, "stop_on_time": 0.90, "ivhv": 1.2}


def load():
    if not os.path.exists(BOOK):
        return []
    with open(BOOK, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save(rows):
    with open(BOOK, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_open(a):
    rows = load()
    spread = (a.ask - a.credit) / a.credit if a.ask else None
    r = {"id": uuid.uuid4().hex[:6], "date": a.date or dt.date.today().isoformat(), "ticker": a.ticker.upper(),
         "right": a.right, "strike": a.strike, "expiry": a.expiry, "contracts": a.contracts, "credit": a.credit,
         "ask": a.ask, "spread": spread, "ivhv": a.ivhv, "exit": None, "how": None, "fees": 0.0, "closed": None}
    rows.append(r)
    save(rows)
    warn = []
    if spread is not None and spread > 0.10:
        warn.append(f"报价差 {spread:.0%} > 10%（违反第 7 条）")
    if a.ivhv is not None and a.ivhv < 1.1:
        warn.append(f"IV/HV {a.ivhv:.2f} < 1.1（违反第 14 条）")
    stage = report(quiet=True)
    if a.contracts > stage:
        warn.append(f"张数 {a.contracts} > 当前阶段允许的 {stage} 张")
    print(f"已记开仓 id={r['id']} {r['ticker']} {a.strike}{a.right} {a.expiry} ×{a.contracts} @{a.credit}"
          + ("｜⚠ " + "；".join(warn) if warn else ""))


def cmd_close(a):
    rows = load()
    hit = [r for r in rows if r["id"] == a.id]
    if not hit:
        raise SystemExit(f"找不到 id={a.id}")
    r = hit[0]
    r.update(exit=a.price, how=a.how, fees=a.fees or 0.0, closed=a.date or dt.date.today().isoformat())
    save(rows)
    pnl = ((r["credit"] - a.price) * 100 * r["contracts"]) - r["fees"]
    print(f"已记平仓 {r['ticker']} {r['strike']}{r['right']}｜{a.how} @{a.price}｜净 {pnl:+.0f} 美元"
          f"（{(r['credit'] - a.price) / r['credit']:+.2f} × 收入）")


def metrics(rows):
    closed = [r for r in rows if r["exit"] is not None]
    if not closed:
        return None
    cr = sum(r["credit"] * 100 * r["contracts"] for r in closed)
    pnl = sum((r["credit"] - r["exit"]) * 100 * r["contracts"] - r["fees"] for r in closed)
    worst = min((r["credit"] - r["exit"]) / r["credit"] for r in closed)
    stops = [r for r in closed if r["how"] in ("止损", "强平")]
    on_time = sum(1 for r in stops if r["how"] == "止损" and r["exit"] <= 2.5 * r["credit"])
    ivs = [r["ivhv"] for r in closed if r.get("ivhv")]
    days = sorted(r["date"] for r in closed)
    weeks = (dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days / 7
    return {
        "n": len(closed), "clusters": len({(r["ticker"], r["expiry"]) for r in closed}), "weeks": weeks,
        "edge": pnl / cr, "pnl": pnl, "worst": worst,
        "stop_on_time": (on_time / len(stops)) if stops else None, "n_stops": len(stops),
        "ivhv": (sum(ivs) / len(ivs)) if ivs else None,
    }


def passed(m):
    return {
        "簇 ≥ 20 且跨度 ≥ 6 周": m["clusters"] >= ROUND and m["weeks"] >= MIN_WEEKS,
        f"每 $1 收入净 ≥ +{GATES['edge']:.2f}": m["edge"] >= GATES["edge"],
        f"最差一笔 ≥ {GATES['worst']}× 收入": m["worst"] >= GATES["worst"],
        "止损按时 ≥ 90%": m["stop_on_time"] is None or m["stop_on_time"] >= GATES["stop_on_time"],
        "入场 IV/HV 均值 ≥ 1.2": m["ivhv"] is not None and m["ivhv"] >= GATES["ivhv"],
    }


def report(quiet=False):
    """按「轮」（每 20 簇一轮）逐轮判定，返回当前允许的张数。"""
    rows = sorted([r for r in load() if r["exit"] is not None], key=lambda r: r["closed"])
    stage, fails, rounds, cur, seen = 1, 0, [], [], set()
    for r in rows:
        cur.append(r)
        seen.add((r["ticker"], r["expiry"]))
        if len(seen) >= ROUND:
            rounds.append(cur)
            cur, seen = [], set()
    for rd in rounds:
        ok = all(passed(metrics(rd)).values())
        if ok:
            stage, fails = min(stage + 1, 3), 0
        else:
            stage, fails = max(stage - 1, 1), fails + 1
        if fails >= 2:
            stage = 0
            break
    if not quiet:
        print(f"实盘账本 {len(load())} 笔（已平 {len(rows)}）｜已完成 {len(rounds)} 轮｜当前阶段：" +
              ("⛔ 连续两轮不达标 → 停止卖方" if stage == 0 else f"每笔 {stage} 张"))
        m = metrics(cur or (rounds[-1] if rounds else []))
        if m:
            print(f"本轮进度：{m['clusters']}/{ROUND} 簇｜跨度 {m['weeks']:.1f} 周｜每 $1 收入净 {m['edge']:+.2f}"
                  f"（净 {m['pnl']:+.0f} 美元）｜最差 {m['worst']:+.1f}× 收入｜止损 {m['n_stops']} 次，按时 "
                  f"{'—' if m['stop_on_time'] is None else format(m['stop_on_time'], '.0%')}｜IV/HV 均值 "
                  f"{'—' if m['ivhv'] is None else format(m['ivhv'], '.2f')}")
            for k, v in passed(m).items():
                print(f"  {'✅' if v else '❌'} {k}")
        else:
            print("本轮还没有已平仓的交易。")
    return stage


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("open")
    for k in ("--ticker", "--expiry"):
        o.add_argument(k, required=True)
    o.add_argument("--right", choices=["P", "C"], required=True)
    o.add_argument("--strike", type=float, required=True)
    o.add_argument("--contracts", type=int, default=1)
    o.add_argument("--credit", type=float, required=True, help="实际成交的卖出价")
    o.add_argument("--ask", type=float, help="开仓时的卖价（算买卖报价差）")
    o.add_argument("--ivhv", type=float)
    o.add_argument("--date")
    c = sp.add_parser("close")
    c.add_argument("--id", required=True)
    c.add_argument("--price", type=float, required=True, help="实际成交的买回价（到期作废填 0）")
    c.add_argument("--how", choices=["止盈", "止损", "到期", "强平", "手动"], required=True)
    c.add_argument("--fees", type=float)
    c.add_argument("--date")
    sp.add_parser("report")
    a = ap.parse_args()
    {"open": cmd_open, "close": cmd_close, "report": lambda _: report()}[a.cmd](a)


if __name__ == "__main__":
    main()
