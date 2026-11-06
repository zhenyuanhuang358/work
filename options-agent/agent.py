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
只做单腿卖出；信用价差与买 put 尾部对冲两个模块已移除）：
  A buffett_csp    巴菲特式现金担保卖 put：价外、z 与价外概率达标、流动性合格
  B short_call     卖 call（2026-11-05 用户加入）：与卖 put 镜像——价外
                   （行权价高于现价）、z 与价外概率达标、流动性合格。
                   注意：裸卖 call 上行风险理论无限，保证金随标的上涨
                   急剧膨胀，同受保证金 60% 硬否决与全部风控约束
  D thorp_ev       索普式期望值过滤（叠加层）：假设真实波动率 = IV x 折扣
                   （波动率风险溢价），重算公允价，EV = bid - 公允价；
                   EV 明显为负的卖方候选直接否决

数据口径：2026-11-05 起 options_watch.json 的 right 改为 PC，期权链
rows 带 right 字段（C/P）；无 right 字段的旧链按 P 处理。put 与 call
必须分开定价（IV 反解、缓冲、保证金公式都不同），混用会出幻影信号。

财报日历（earnings.json，与 agent.py 同目录）：自选股下一次财报日期。
按 2026-11-04 用户决定，持有期跨财报日的信号直接否决（移入否决区），
与宏观事件的「只标注」不同。SLV/XLE 为 ETF 无财报。财报季后需更新日期。

事件日历（events.json，与 agent.py 同目录）：信号持有期（扫描日到到期日）
跨越的美国宏观事件（非农/CPI/PPI/FOMC/大选等）会被标注在信号上，
报告头也会列出窗口内全部事件；按 2026-11-03 用户决定，只标注提醒，
不否决、不改分数。日期需按官方日程（BLS/美联储）定期核对维护。

风控否决（任何模块都适用）：bid<=0、买卖倒挂、价差/中间价 > 50%、
卖方候选 OI < 20、索普 EV < -0.05/股；--live 模式下报价超过 30 分钟
的标的整只否决（离线/回放模式只在报告头标注过期，不否决）。

保证金仓位硬否决（2026-11-05 用户决定）：购买力取自 account.json
（与 agent.py 同目录，buying_power_usd；--bp 可覆盖）。单张 Reg-T
估算保证金超过购买力 x margin_cap_ratio（默认 0.6）的信号，在排序
截断前直接否决并由后排候补递补——2026-11-04 AMD 442.5P 保证金
几乎占满购买力，盘中逆行被券商先于止损强平（成交 7.75 vs 止损
6.90），此规则防重演。account.json 的购买力需随账户变化手动更新。

两边分开（2026-11-05 用户决定）：卖 put 与卖 call 分开排序、分开
截断，每边各自最多 top 条（默认 30），互不挤占名额；报告分「卖 Put」
「卖 Call」两区呈现，signals.json 除合并列表 signals 外另含
signals_put / signals_call 两组。

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


def call_price(s, k, sig, t):
    if sig <= 0 or t <= 0:
        return max(s - k, 0.0)
    d1 = (math.log(s / k) + 0.5 * sig * sig * t) / (sig * math.sqrt(t))
    return s * N.cdf(d1) - k * N.cdf(d1 - sig * math.sqrt(t))


def implied_vol(px, s, k, t, right="P"):
    intrinsic = max(k - s, 0.0) if right == "P" else max(s - k, 0.0)
    if px <= intrinsic:
        return None
    price = put_price if right == "P" else call_price
    lo, hi = 0.01, 5.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if price(s, k, m, t) < px else (lo, m)
    return (lo + hi) / 2


def reg_t_margin(s, k, bid):
    return max(0.2 * s - max(s - k, 0) + bid, 0.1 * k + bid) * 100


def reg_t_margin_call(s, k, bid):
    return max(0.2 * s - max(k - s, 0) + bid, 0.1 * s + bid) * 100


# ---------------- 候选行特征 ----------------

def enrich(row, s, qdt):
    """给一行原始报价补齐可裁定数字；无法定价返回 None 并在 row 里记原因。"""
    k, b, ak = row["strike"], row.get("bid") or 0, row.get("ask") or 0
    right = row.get("right") or "P"
    exp = datetime.fromisoformat(row["expiry"]).replace(hour=16, tzinfo=ET)
    t = (exp - qdt).total_seconds() / (365 * 86400)
    if t <= 0:
        return None
    if b <= 0 or ak < b:
        return None
    mid = (b + ak) / 2
    iv = implied_vol(mid, s, k, t, right)
    if iv is None:
        return None
    sig_t = iv * math.sqrt(t)
    if right == "P":
        buf = (s - k) / s
        p_otm = N.cdf((math.log(s / k) - 0.5 * sig_t * sig_t) / sig_t)
        margin = reg_t_margin(s, k, b)
    else:
        buf = (k - s) / s
        p_otm = N.cdf((math.log(k / s) + 0.5 * sig_t * sig_t) / sig_t)
        margin = reg_t_margin_call(s, k, b)
    z = buf / sig_t if sig_t > 0 else 0.0
    return {
        "expiry": row["expiry"], "strike": k, "right": right,
        "bid": b, "ask": ak, "mid": mid,
        "delta": row.get("delta"), "oi": row.get("oi") or 0,
        "volume": row.get("volume") or 0, "iv": iv, "t_years": t,
        "days": t * 365, "buffer": buf, "z": z, "p_otm": p_otm,
        "spread_pct": (ak - b) / mid if mid > 0 else 9.9,
        "margin": margin,
    }


def thorp_ev(c, haircut=0.85):
    """卖方每股期望值：用折扣后的波动率重算公允价。bid - 公允价。"""
    price = put_price if c["right"] == "P" else call_price
    fair = price(c["_spot"], c["strike"], c["iv"] * haircut, c["t_years"])
    return c["bid"] - fair


# ---------------- 策略模块 ----------------

def mod_buffett(cands):
    out = []
    for c in cands:
        if c["strike"] >= c["_spot"]:
            continue
        if c["z"] < 1.0 or c["p_otm"] < 0.80 or c["oi"] < 100 or c["bid"] < 0.05:
            continue
        cash_yield = c["bid"] / c["strike"]                       # 现金担保收益率（本期）
        ann_yield = cash_yield / c["t_years"] if c["t_years"] > 0 else 0
        score = 40 * min(ann_yield, 1.0) + 25 * min(c["z"], 2.5) / 2.5 \
            + 20 * c["p_otm"] + 15 * (1 - min(c["spread_pct"], 1.0))
        out.append({**base(c), "module": "buffett_csp", "action": "SELL_PUT_CSP",
                    "score": round(score, 1),
                    "why": f"z={c['z']:.2f}，价外概率 {c['p_otm']:.0%}，"
                           f"现金担保年化 {ann_yield:.0%}，每张收入 ${c['bid']*100:.0f}，"
                           f"保证金约 ${c['margin']:,.0f}"})
    return out


def mod_short_call(cands):
    """卖 call（2026-11-05 用户加入）：与 buffett_csp 镜像的价外卖方筛选。
    门槛与卖 put 一致（z>=1.0、价外概率>=80%、OI>=100）；裸卖 call 上行
    风险无限，分数不因此加成，靠保证金硬否决与 2 倍止损纪律兜底。"""
    out = []
    for c in cands:
        if c["strike"] <= c["_spot"]:
            continue
        if c["z"] < 1.0 or c["p_otm"] < 0.80 or c["oi"] < 100 or c["bid"] < 0.05:
            continue
        cash_yield = c["bid"] / c["strike"]
        ann_yield = cash_yield / c["t_years"] if c["t_years"] > 0 else 0
        score = 40 * min(ann_yield, 1.0) + 25 * min(c["z"], 2.5) / 2.5 \
            + 20 * c["p_otm"] + 15 * (1 - min(c["spread_pct"], 1.0))
        out.append({**base(c), "module": "short_call", "action": "SELL_CALL",
                    "score": round(score, 1),
                    "why": f"z={c['z']:.2f}，价外概率 {c['p_otm']:.0%}，"
                           f"年化 {ann_yield:.0%}，每张收入 ${c['bid']*100:.0f}，"
                           f"保证金约 ${c['margin']:,.0f}（裸卖 call，上行风险无限）"})
    return out


def base(c):
    return {"ticker": c["_ticker"], "expiry": c["expiry"], "strike": c["strike"],
            "right": c["right"],
            "bid": c["bid"], "ask": c["ask"], "mid": round(c["mid"], 3),
            "iv": round(c["iv"], 4), "z": round(c["z"], 2),
            "p_otm": round(c["p_otm"], 3), "oi": c["oi"],
            "spread_pct": round(c["spread_pct"], 3),
            "margin": round(c["margin"])}


# ---------------- 风控 + 主流程 ----------------

def load_events(explicit=None):
    """加载事件日历：显式路径优先，否则用 agent.py 同目录的 events.json。"""
    cands = [explicit] if explicit else []
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.json"))
    for p in cands:
        if p and os.path.exists(p):
            try:
                return json.load(open(p)).get("events", [])
            except Exception:
                return []
    return []


def load_earnings(explicit=None):
    """加载财报日历：显式路径优先，否则用 agent.py 同目录的 earnings.json。"""
    cands = [explicit] if explicit else []
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "earnings.json"))
    for p in cands:
        if p and os.path.exists(p):
            try:
                return json.load(open(p)).get("earnings", {})
            except Exception:
                return {}
    return {}


def load_account(explicit=None):
    """加载账户参数：显式路径优先，否则用 agent.py 同目录的 account.json。
    返回 (buying_power_usd, margin_cap_ratio)；文件缺失时 (None, 0.6)。"""
    cands = [explicit] if explicit else []
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "account.json"))
    for p in cands:
        if p and os.path.exists(p):
            try:
                j = json.load(open(p))
                return j.get("buying_power_usd"), float(j.get("margin_cap_ratio", 0.6))
            except Exception:
                return None, 0.6
    return None, 0.6


def run(path, bp=None, live=False, haircut=0.85, top=30, events=None, earnings=None,
        cap_ratio=0.6):
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
            is_otm = (c["strike"] < s) if c["right"] == "P" else (c["strike"] > s)
            if is_otm and ev_map[id(c)] < -0.05:
                vetoes.append({"ticker": tkr, **base(c),
                               "reason": f"索普 EV {ev_map[id(c)]:+.2f}/股（真实波动率按 IVx{haircut} 估），卖方期望值为负"})
            else:
                sellable.append(c)
        sig = mod_buffett([c for c in sellable if c["right"] == "P"])
        sig += mod_short_call([c for c in sellable if c["right"] == "C"])
        for sg in sig:
            sg["thorp_ev"] = round(ev_map.get(id(next(
                c for c in cands if c["expiry"] == sg["expiry"] and c["strike"] == sg["strike"]
                and c["right"] == sg["right"])), 0.0), 3)
        signals.extend(sig)
    # 财报否决（2026-11-04 用户决定）：持有期跨财报日的信号直接否决，
    # 移入否决区，不进信号列表；否决在排序截断之前执行，后排候补自动递补。
    scan_date = None
    if updated:
        scan_date = datetime.fromisoformat(updated).astimezone(ET).date()
    earn = earnings or {}
    earnings_vetoes = []
    if scan_date:
        kept = []
        for sg in signals:
            e = earn.get(sg["ticker"])
            if e and e.get("date") and scan_date.isoformat() <= e["date"] <= sg["expiry"]:
                timing = {"AMC": "盘后", "BMO": "盘前"}.get(e.get("timing") or "", "")
                tag = f"{e['date'][5:]} {sg['ticker']} 财报" + (f"（{timing}）" if timing else "")
                vetoes.append({"ticker": sg["ticker"], "expiry": sg["expiry"],
                               "strike": sg["strike"], "right": sg.get("right", "P"),
                               "module": sg["module"],
                               "reason": f"跨财报否决：持有期跨 {tag}，按纪律不跨财报持有"})
                if tag not in earnings_vetoes:
                    earnings_vetoes.append(tag)
            else:
                kept.append(sg)
        signals = kept
    # 保证金仓位硬否决（2026-11-05 用户决定）：单张估算保证金超过
    # 购买力 x cap_ratio 的信号在排序截断前否决，后排候补自动递补。
    margin_cap = bp * cap_ratio if bp else None
    margin_vetoes = []
    if margin_cap:
        kept = []
        for sg in signals:
            if sg.get("margin") and sg["margin"] > margin_cap:
                pct = sg["margin"] / bp
                vetoes.append({"ticker": sg["ticker"], "expiry": sg["expiry"],
                               "strike": sg["strike"], "right": sg.get("right", "P"),
                               "module": sg["module"],
                               "reason": f"仓位过重否决：保证金约 ${sg['margin']:,.0f}，"
                                         f"占购买力 {pct:.0%}，超过 {cap_ratio:.0%} 上限"})
                tag = sg["ticker"]
                if tag not in margin_vetoes:
                    margin_vetoes.append(tag)
            else:
                kept.append(sg)
        signals = kept
    # 两边分开（2026-11-05 用户决定）：put / call 各自按分数排序、
    # 各自截断 top 条，互不挤占；合并列表仅作兼容保留。
    signals.sort(key=lambda x: -x["score"])
    signals_put = [sg for sg in signals if sg.get("right", "P") == "P"][:top]
    signals_call = [sg for sg in signals if sg.get("right", "P") == "C"][:top]
    signals = signals_put + signals_call
    # 宏观事件标注：持有期 = [扫描日（期权链更新时刻的美东日期）, 到期日]，只提醒不否决
    evs = events or []
    window_events = []
    if scan_date and signals:
        max_exp = max(sg["expiry"] for sg in signals)
        window_events = [e for e in evs
                         if scan_date.isoformat() <= e["date"] <= max_exp]
        for sg in signals:
            sg["events"] = [f"{e['date'][5:]} {e['name']}" for e in evs
                            if scan_date.isoformat() <= e["date"] <= sg["expiry"]]
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_file": os.path.basename(path), "chain_updated_at": updated,
            "mode": "live" if live else "replay", "bp": bp, "ev_haircut": haircut,
            "margin_cap_ratio": cap_ratio, "margin_cap": margin_cap,
            "stale_notes": stale_notes, "window_events": window_events,
            "earnings_vetoes": earnings_vetoes, "margin_vetoes": margin_vetoes,
            "signals_put": signals_put, "signals_call": signals_call,
            "signals": signals, "vetoes": vetoes}


def render_md(res):
    lines = [f"# 期权信号日报（研究版，不构成下单指令）",
             f"- 生成：{res['generated_at']}｜模式：{res['mode']}｜期权链更新：{res['chain_updated_at']}"]
    if res["bp"]:
        lines.append(f"- 购买力 ${res['bp']:,.0f}，单张保证金上限 ${res['margin_cap']:,.0f}"
                     f"（购买力 x {res['margin_cap_ratio']:.0%}，仓位过重硬否决；Reg-T 估算，平台预览为准）")
    for n in res["stale_notes"]:
        lines.append(f"- ⚠️ {n}")
    if res.get("window_events"):
        ev_txt = "；".join(f"{e['date']} {e['name']}" for e in res["window_events"])
        lines.append(f"- 🗓️ 本批信号持有期内的宏观事件：{ev_txt}（仅标注提醒，不否决）")
    if res.get("earnings_vetoes"):
        lines.append(f"- 🔴 财报否决：跨 {'；'.join(res['earnings_vetoes'])} 的信号已直接否决（见否决区）")
    if res.get("margin_vetoes"):
        lines.append(f"- 🔴 保证金否决：{'、'.join(res['margin_vetoes'])} 的信号因单张保证金超过购买力 "
                     f"{res['margin_cap_ratio']:.0%} 已直接否决（见否决区）")
    puts = res.get("signals_put")
    calls = res.get("signals_call")
    if puts is None or calls is None:
        # 兼容旧结果结构：按 right 现场拆分
        puts = [sg for sg in res["signals"] if sg.get("right", "P") == "P"]
        calls = [sg for sg in res["signals"] if sg.get("right", "P") == "C"]
    lines += ["", f"## 信号（共 {len(res['signals'])} 条：卖 Put {len(puts)} 条 + 卖 Call {len(calls)} 条，两边分开、各自按分数排序）", ""]
    if not res["signals"]:
        lines.append("今日无通过风控的信号。")
    for title, group in [(f"### 卖 Put 信号（{len(puts)} 条）", puts),
                         (f"### 卖 Call 信号（{len(calls)} 条）", calls)]:
        lines.append(title)
        lines.append("")
        if not group:
            lines.append("本边今日无通过风控的信号。")
            lines.append("")
            continue
        for sg in group:
            lines.append(f"#### {sg['ticker']} {sg['expiry']} {sg['strike']:g}{sg.get('right', 'P')} — {sg['action']}（{sg['module']}，{sg['score']} 分）")
            lines.append(f"- bid/ask {sg['bid']:.2f}/{sg['ask']:.2f}，IV {sg['iv']:.0%}，z {sg['z']}，价外概率 {sg['p_otm']:.0%}，OI {sg['oi']:.0f}，价差占比 {sg['spread_pct']:.0%}")
            lines.append(f"- 理由：{sg['why']}")
            if sg.get("events"):
                lines.append(f"- ⚠️ 事件窗口：持有期跨 {'、'.join(sg['events'])}")
            lines.append("")
    lines += [f"## 被风控否决（{len(res['vetoes'])} 条，仅列前 15）", ""]
    for v in res["vetoes"][:15]:
        lines.append(f"- {v['ticker']} {v['expiry']} {v['strike']:g}{v.get('right', 'P')}：{v['reason']}")
    lines += ["", "> 口径：IV 由中间价反解；卖方收入按 bid 计；EV 假设真实波动率 = IV x "
              f"{res['ev_haircut']}。信号只用于研究筛选，下单前必须以交易平台实时报价复核。"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--bp", type=float, help="购买力（美元），覆盖 account.json 的 buying_power_usd")
    ap.add_argument("--account", help="账户参数 JSON 路径（默认 agent.py 同目录 account.json）")
    ap.add_argument("--live", action="store_true", help="实盘时段模式：报价超 30 分钟整只否决")
    ap.add_argument("--ev-haircut", type=float, default=0.85)
    ap.add_argument("--top", type=int, default=30, help="每边（put/call 各自）最多保留条数，默认 30")
    ap.add_argument("--events", help="事件日历 JSON 路径（默认 agent.py 同目录 events.json）")
    ap.add_argument("--earnings", help="财报日历 JSON 路径（默认 agent.py 同目录 earnings.json）")
    a = ap.parse_args()
    acct_bp, cap_ratio = load_account(a.account)
    bp = a.bp if a.bp is not None else acct_bp
    res = run(a.file, bp, a.live, a.ev_haircut, a.top,
              events=load_events(a.events), earnings=load_earnings(a.earnings),
              cap_ratio=cap_ratio)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "signals.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(a.out, "report.md"), "w").write(render_md(res))
    print(f"信号 {len(res['signals'])} 条（卖 Put {len(res['signals_put'])} + 卖 Call {len(res['signals_call'])}），否决 {len(res['vetoes'])} 条 -> {a.out}/report.md")


if __name__ == "__main__":
    main()
