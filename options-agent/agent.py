#!/usr/bin/env python3
"""美股期权智能体 v1（研究信号版：只筛选、只提示、不下单）

输入：options_chain.json（与 zhenyuanhuang358/work 仓库 fetch-options 工作流
产出的格式完全一致：{updated_at, watch, tickers:{T:{source, quote_time_utc,
spot, rows:[{expiry, strike, bid, ask, delta, oi, volume, last_trade}]}}}）

口径与既有 tools/option_quote.py 保持一致：
  - IV 一律由中间价反解（Black-Scholes put，二分法，r=0），不信任数据源自带 IV
  - 定价时刻 = 该标的的 quote_time_utc（无时间戳时退用抓取时刻 updated_at）
  - 卖方收入按 bid 计；Reg-T 裸卖 put 保证金公式与 option_quote.py 相同
  - 缓冲 buffer=(S-K)/S，z = buffer / (IV*sqrt(t))，价外概率用同一对数正态公式

策略模块（2026-11-03 按用户决定收窄为单腿卖方：券商不支持组合单，
只做单腿卖出看跌；信用价差与买 put 尾部对冲两个模块已移除）：
  A buffett_csp    巴菲特式现金担保卖 put：价外、z 与价外概率达标、流动性合格
  D thorp_ev       索普式期望值过滤（叠加层）：假设真实波动率 = IV x 折扣
                   （波动率风险溢价），重算公允价，EV = bid - 公允价；
                   EV 明显为负的卖方候选直接否决

风控否决（任何模块都适用）：bid<=0、买卖倒挂、价差/中间价 > 50%、
卖方候选 OI < 20、索普 EV < -0.05/股；--live 模式下报价超过 30 分钟
的标的整只否决（离线/回放模式只在报告头标注过期，不否决）。

用法：
  python3 agent.py --file data/options_chain.sample.json --out out/
  python3 agent.py --file options_chain.json --bp 5000 --live
输出：out/signals.json + out/report.md
"""
import argparse
import json
import math
import os
from datetime import datetime, timezone
from statistics import NormalDist
from zoneinfo import ZoneInfo

N = NormalDist()
ET = ZoneInfo("America/New_York")

# ---------------- 基础定价（与 option_quote.py 同口径） ----------------

def put_price(s, k, sig, t):
    if sig <= 0 or t <= 0:
        return max(k - s, 0.0)
    d1 = (math.log(s / k) + 0.5 * sig * sig * t) / (sig * math.sqrt(t))
    return k * N.cdf(-(d1 - sig * math.sqrt(t))) - s * N.cdf(-d1)


def implied_vol(px, s, k, t):
    if px <= max(k - s, 0.0):
        return None
    lo, hi = 0.01, 5.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if put_price(s, k, m, t) < px else (lo, m)
    return (lo + hi) / 2


def reg_t_margin(s, k, bid):
    return max(0.2 * s - max(s - k, 0) + bid, 0.1 * k + bid) * 100


# ---------------- 候选行特征 ----------------

def enrich(row, s, qdt):
    """给一行原始报价补齐可裁定数字；无法定价返回 None 并在 row 里记原因。"""
    k, b, ak = row["strike"], row.get("bid") or 0, row.get("ask") or 0
    exp = datetime.fromisoformat(row["expiry"]).replace(hour=16, tzinfo=ET)
    t = (exp - qdt).total_seconds() / (365 * 86400)
    if t <= 0:
        return None
    if b <= 0 or ak < b:
        return None
    mid = (b + ak) / 2
    iv = implied_vol(mid, s, k, t)
    if iv is None:
        return None
    sig_t = iv * math.sqrt(t)
    buf = (s - k) / s
    z = buf / sig_t if sig_t > 0 else 0.0
    p_otm = N.cdf((math.log(s / k) - 0.5 * sig_t * sig_t) / sig_t) if k < s else \
        N.cdf((math.log(s / k) - 0.5 * sig_t * sig_t) / sig_t)
    return {
        "expiry": row["expiry"], "strike": k, "bid": b, "ask": ak, "mid": mid,
        "delta": row.get("delta"), "oi": row.get("oi") or 0,
        "volume": row.get("volume") or 0, "iv": iv, "t_years": t,
        "days": t * 365, "buffer": buf, "z": z, "p_otm": p_otm,
        "spread_pct": (ak - b) / mid if mid > 0 else 9.9,
        "margin": reg_t_margin(s, k, b),
    }


def thorp_ev(c, haircut=0.85):
    """卖 put 的每股期望值：用折扣后的波动率重算公允价。bid - 公允价。"""
    fair = put_price(c["_spot"], c["strike"], c["iv"] * haircut, c["t_years"])
    return c["bid"] - fair


# ---------------- 策略模块 ----------------

def mod_buffett(cands, bp):
    out = []
    for c in cands:
        if c["strike"] >= c["_spot"]:
            continue
        if c["z"] < 1.0 or c["p_otm"] < 0.80 or c["oi"] < 100 or c["bid"] < 0.05:
            continue
        if bp is not None and c["margin"] > bp:
            c.setdefault("_notes", []).append("保证金超过购买力，仅提示")
            score_bp = -5
        else:
            score_bp = 0
        cash_yield = c["bid"] / c["strike"]                       # 现金担保收益率（本期）
        ann_yield = cash_yield / c["t_years"] if c["t_years"] > 0 else 0
        score = 40 * min(ann_yield, 1.0) + 25 * min(c["z"], 2.5) / 2.5 \
            + 20 * c["p_otm"] + 15 * (1 - min(c["spread_pct"], 1.0)) + score_bp
        out.append({**base(c), "module": "buffett_csp", "action": "SELL_PUT_CSP",
                    "score": round(score, 1),
                    "why": f"z={c['z']:.2f}，价外概率 {c['p_otm']:.0%}，"
                           f"现金担保年化 {ann_yield:.0%}，每张收入 ${c['bid']*100:.0f}，"
                           f"保证金约 ${c['margin']:,.0f}"})
    return out


def base(c):
    return {"ticker": c["_ticker"], "expiry": c["expiry"], "strike": c["strike"],
            "bid": c["bid"], "ask": c["ask"], "mid": round(c["mid"], 3),
            "iv": round(c["iv"], 4), "z": round(c["z"], 2),
            "p_otm": round(c["p_otm"], 3), "oi": c["oi"],
            "spread_pct": round(c["spread_pct"], 3)}


# ---------------- 风控 + 主流程 ----------------

def run(path, bp=None, live=False, haircut=0.85, top=30):
    j = json.load(open(path))
    updated = j.get("updated_at")
    signals, vetoes, stale_notes = [], [], []
    for tkr, r in sorted(j["tickers"].items()):
        rows = r.get("rows") or []
        if not rows:
            continue
        s = r["spot"]
        qt = r.get("quote_time_utc")
        qdt = (datetime.fromisoformat(qt).replace(tzinfo=timezone.utc) if qt
               else datetime.fromisoformat(updated))
        age_min = (datetime.now(timezone.utc) - qdt).total_seconds() / 60
        if age_min > 30:
            stale_notes.append(f"{tkr} 报价距今 {age_min/60:.1f} 小时"
                                 + ("（live 模式：整只否决）" if live else "（回放模式：仍出信号，仅供研究）"))
            if live:
                continue
        cands = []
        for row in rows:
            c = enrich(row, s, qdt)
            if c is None:
                continue
            c["_spot"], c["_ticker"] = s, tkr
            # 全局风控否决
            if c["spread_pct"] > 0.5:
                vetoes.append({"ticker": tkr, **base(c), "reason": "买卖价差超过中间价 50%，流动性不合格"})
                continue
            cands.append(c)
        # 索普 EV：卖方候选的叠加否决/加分依据
        ev_map = {}
        for c in cands:
            ev = thorp_ev(c, haircut)
            ev_map[id(c)] = ev
        sellable = []
        for c in cands:
            if c["strike"] < s and ev_map[id(c)] < -0.05:
                vetoes.append({"ticker": tkr, **base(c),
                               "reason": f"索普 EV {ev_map[id(c)]:+.2f}/股（真实波动率按 IVx{haircut} 估），卖方期望值为负"})
            else:
                sellable.append(c)
        sig = mod_buffett(sellable, bp)
        for sg in sig:
            sg["thorp_ev"] = round(ev_map.get(id(next(
                c for c in cands if c["expiry"] == sg["expiry"] and c["strike"] == sg["strike"])), 0.0), 3)
        signals.extend(sig)
    signals.sort(key=lambda x: -x["score"])
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_file": os.path.basename(path), "chain_updated_at": updated,
            "mode": "live" if live else "replay", "bp": bp, "ev_haircut": haircut,
            "stale_notes": stale_notes, "signals": signals[:top], "vetoes": vetoes}


def render_md(res):
    lines = [f"# 期权信号日报（研究版，不构成下单指令）",
             f"- 生成：{res['generated_at']}｜模式：{res['mode']}｜期权链更新：{res['chain_updated_at']}"]
    if res["bp"]:
        lines.append(f"- 购买力硬过滤参考：${res['bp']:,.0f}（Reg-T 估算，平台预览为准）")
    for n in res["stale_notes"]:
        lines.append(f"- ⚠️ {n}")
    lines += ["", f"## 信号（共 {len(res['signals'])} 条，按分数排序）", ""]
    if not res["signals"]:
        lines.append("今日无通过风控的信号。")
    for sg in res["signals"]:
        lines.append(f"### {sg['ticker']} {sg['expiry']} {sg['strike']:g}P — {sg['action']}（{sg['module']}，{sg['score']} 分）")
        lines.append(f"- bid/ask {sg['bid']:.2f}/{sg['ask']:.2f}，IV {sg['iv']:.0%}，z {sg['z']}，价外概率 {sg['p_otm']:.0%}，OI {sg['oi']:.0f}，价差占比 {sg['spread_pct']:.0%}")
        lines.append(f"- 理由：{sg['why']}")
        lines.append("")
    lines += [f"## 被风控否决（{len(res['vetoes'])} 条，仅列前 15）", ""]
    for v in res["vetoes"][:15]:
        lines.append(f"- {v['ticker']} {v['expiry']} {v['strike']:g}P：{v['reason']}")
    lines += ["", "> 口径：IV 由中间价反解；卖方收入按 bid 计；EV 假设真实波动率 = IV x "
              f"{res['ev_haircut']}。信号只用于研究筛选，下单前必须以交易平台实时报价复核。"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--bp", type=float, help="可取现金（美元），做保证金可执行性标注")
    ap.add_argument("--live", action="store_true", help="实盘时段模式：报价超 30 分钟整只否决")
    ap.add_argument("--ev-haircut", type=float, default=0.85)
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args()
    res = run(a.file, a.bp, a.live, a.ev_haircut, a.top)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "signals.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(a.out, "report.md"), "w").write(render_md(res))
    print(f"信号 {len(res['signals'])} 条，否决 {len(res['vetoes'])} 条 -> {a.out}/report.md")


if __name__ == "__main__":
    main()
