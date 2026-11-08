#!/usr/bin/env python3
"""天道 · 个人规则的确定性检查（2026-11-08）。

为什么：借款合计上限、入股本金上限、黄金占比、期权单笔 / 合计最大亏损、账户暂停线、认错线价格、仓位公式，
全是算术。让模型在对话里心算，就会出现「这笔 3000，加上之前那笔……应该没超」这种靠记忆的判断。
规则的数字只从 memory/state/tiandao/personal-rules.json 读；台账在 memory/state/tiandao/ledger.json。

用法（全部输出 JSON；"ok": false 就是违反，"violations" 写明违反哪条）：
  python3 tools/tiandao_check.py lend   --amount 3000            # 新借出前：余额合计上限
  python3 tools/tiandao_check.py equity --amount 20000           # 新入股前：未收回本金上限
  python3 tools/tiandao_check.py gold   --gold 120000 --total 500000 [--buy 20000]
  python3 tools/tiandao_check.py spread --width 5 --credit 1.2 --qty 1 [--equity 5300]
  python3 tools/tiandao_check.py long   --premium 1.5 --qty 1 [--equity 5300]
  python3 tools/tiandao_check.py size   --max-loss 2000 --stop-drop 0.08    # 单笔仓位 = 可承受亏损 ÷ 到止损的跌幅
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(REPO, "memory/state/tiandao/personal-rules.json")
LEDGER = os.path.join(REPO, "memory/state/tiandao/ledger.json")


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def lend(r, led, amount):
    cap = r["lending"]["loan_outstanding_cap"]
    out = sum(x["amount"] - x.get("repaid", 0) for x in led.get("loans", []))
    room = max(cap - out, 0)
    v = [] if out + amount <= cap else [f"资金出让第 8 条：未还借款合计 {out:,.0f} + 本笔 {amount:,.0f} > {cap:,.0f}"]
    return {"ok": not v, "outstanding": out, "cap": cap, "room": room, "max_this_loan": room, "violations": v,
            "reminders": ["第 1 条：当场只回「我考虑一下，明天回你」", "第 5 条：上限内也写借条、还款日、逾期动作",
                          "第 2 条：问第二还款来源"] + ([f"第 9 条：「借我最多借 {cap:,.0f}，更多的只能谈入股」"] if v else [])}


def equity(r, led, amount):
    cap = r["lending"]["equity_principal_cap"]
    out = sum(x["principal"] - x.get("cash_returned", 0) for x in led.get("equity", []))
    v = [] if out + amount <= cap else [f"资金出让第 11 条：未收回本金 {out:,.0f} + 本笔 {amount:,.0f} > {cap:,.0f}"]
    return {"ok": not v, "unreturned_principal": out, "cap": cap, "room": max(cap - out, 0), "violations": v,
            "reminders": ["第 10 条：书面协议、占股比例、看账的信息权；不能是改名的借款", "第 12 条：收回本金以现金到账为准"]}


def gold(r, g, total, buy=0.0):
    mx = r["gold"]["max_share"]
    share = (g + buy) / (total + buy)
    v = [] if share <= mx else [f"保值配置第 1 条：黄金占比 {share:.1%} > {mx:.0%}"]
    sell = max(g + buy - mx * (total + buy), 0)
    return {"ok": not v, "share_after": share, "cap": mx, "sell_back_to_cap": sell, "violations": v,
            "reminders": ["第 4 条：只有无杠杆、无到期的品种算保值", "第 5 条：写一句「这笔是保值，还是想赚？」"]}


def _option(r, led, max_loss, capital, equity_now):
    o = r["options"]
    open_total = sum(p["max_loss"] for p in led.get("option_positions", []) if p.get("status", "open") == "open")
    v = []
    if max_loss > o["per_trade_max_loss"]:
        v.append(f"期权第 2 条：单笔最大亏损 {max_loss:,.2f} > {o['per_trade_max_loss']}")
    if open_total + max_loss > o["open_max_loss_total"]:
        v.append(f"期权第 3 条：在手最大亏损合计 {open_total:,.2f} + {max_loss:,.2f} > {o['open_max_loss_total']}")
    if equity_now is not None and equity_now <= o["halt_equity"]:
        v.append(f"期权第 7 条：账户权益 {equity_now:,.2f} ≤ 暂停线 {o['halt_equity']}，复盘前不得开仓")
    stop = capital * o["stop_loss_share_of_capital"]
    return {"ok": not v, "max_loss": max_loss, "open_max_loss_before": open_total, "violations": v,
            "stop_loss_amount": stop,
            "reminders": [f"期权第 5 条：亏损达占用资金的 {o['stop_loss_share_of_capital']:.0%}（{stop:,.2f} 美元）平仓，开仓当下下成条件单",
                          "期权第 4 条：三问——会让我出局吗？下行封顶了吗？我凭什么比对手占优？",
                          "期权第 6 条：禁止加仓、展期、用新仓位对冲来救亏损单"]}


def spread(r, led, width, credit, qty, equity_now=None):
    if credit >= width:
        return {"ok": False, "violations": ["权利金 ≥ 价差宽度：报价有误，不计算"]}
    ml = (width - credit) * 100 * qty
    out = _option(r, led, ml, ml, equity_now)  # 信用价差的占用资金 = 最大亏损
    out["structure"] = "credit_spread"
    return out


def long_opt(r, led, premium, qty, equity_now=None):
    ml = premium * 100 * qty
    out = _option(r, led, ml, ml, equity_now)
    out["structure"] = "long_option"
    return out


def size(max_loss, stop_drop):
    if not 0 < stop_drop < 1:
        return {"ok": False, "violations": ["到止损的跌幅须在 0 和 1 之间"]}
    return {"ok": True, "position": max_loss / stop_drop, "formula": "单笔仓位 = 可承受的最大亏损 ÷ 到止损位的预期跌幅",
            "reminders": ["可承受亏损由用户给，不替用户定数字"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lend", "equity"):
        sp.add_parser(name).add_argument("--amount", type=float, required=True)
    g = sp.add_parser("gold")
    g.add_argument("--gold", type=float, required=True)
    g.add_argument("--total", type=float, required=True)
    g.add_argument("--buy", type=float, default=0.0)
    s = sp.add_parser("spread")
    s.add_argument("--width", type=float, required=True)
    s.add_argument("--credit", type=float, required=True)
    s.add_argument("--qty", type=int, default=1)
    s.add_argument("--equity", type=float)
    lo = sp.add_parser("long")
    lo.add_argument("--premium", type=float, required=True)
    lo.add_argument("--qty", type=int, default=1)
    lo.add_argument("--equity", type=float)
    z = sp.add_parser("size")
    z.add_argument("--max-loss", type=float, required=True)
    z.add_argument("--stop-drop", type=float, required=True)
    a = ap.parse_args(argv)
    r, led = load(RULES, None), load(LEDGER, {})
    if r is None:
        sys.exit(f"缺 {RULES}：个人规则未录入，不做检查")
    res = {"lend": lambda: lend(r, led, a.amount), "equity": lambda: equity(r, led, a.amount),
           "gold": lambda: gold(r, a.gold, a.total, a.buy),
           "spread": lambda: spread(r, led, a.width, a.credit, a.qty, a.equity),
           "long": lambda: long_opt(r, led, a.premium, a.qty, a.equity),
           "size": lambda: size(a.max_loss, a.stop_drop)}[a.cmd]()
    res["rules_version"] = r.get("version")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
