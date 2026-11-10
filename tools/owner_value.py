#!/usr/bin/env python3
"""巴菲特估值计算器（buffett-analyst Phase 2–3 的确定性部分；2026-11-07 改造）

为什么：所有者盈余、两情景 DCF、终值集中度、安全边际、估值失效条件、评分卡加总全是确定性计算，过去全靠模型心算、无人核对；
而且主文件（安全边际用下沿）与 owner-earnings-model.md（用中值）互相矛盾。用户 11/07 定：**安全边际按内在价值下沿（保守 IV）计算，
门槛 30% 不变**（路径 B 正态化估值 40%）。公式严格照 owner-earnings-model.md，改公式先改 spoke 再改这里。

输入（JSON，**每个数字都要有 src**，缺来源直接拒算——「无来源 = 不可用」）：
{
 "ticker": "KO", "market": "美股大盘股", "currency": "USD", "as_of": "2026-11-07",
 "price":  {"v": 70.1, "src": "..."},   "shares": {"v": 4.3e9, "src": "..."},
 "r":      {"v": 0.09, "src": "owner-earnings-model 折现率表：美股大盘股 9%（10Y 4.x%）"},
 "years": [  # 最近 3 个完整财年，旧 → 新；每年一个 src
   {"fy": 2023, "src": "...", "net_income": .., "da": .., "capex": .., "dwc": .., "fcf": .., "revenue": .., "ebit": .., "interest": ..,
    "adjustments": [{"item": "IRS 保证金", "amount": 6000, "src": "...", "why": "..."}]}   # 可选：一次性现金项，同时加回 FCF 与 ΔWC
 ],
 "ttm": {"period_end": "2026-07-26", "src": "...", "net_income": .., "da": .., "capex": .., "dwc": .., "fcf": ..},  # 可选：近 12 个月实际
 "base_fy_end": "2026-01-25",   # 可选：最近完整财年的结束日；超过 6 个月仍没给 ttm 会报 flag
 "maint_capex": {"method": "da_proxy | pct_of_capex | total | disclosed", "pct": 0.5, "value": null, "why": "..."},
 "revenue_prior": {"v": .., "src": "..."},   # 可选：最旧财年的前一年营收，让增速波动率有 3 个增速样本
 "moat_score": 8,
 "debt_ratio": {"v": 0.35, "src": "..."},
 "tech_disruption": false,
 "g_override": null,          # 异常增速（CAGR>50% 或 FCF 由负转正）时必须给：{"g1": .., "g2": .., "src": "共识 / FCF yield 反推"}
 "peer_p_fcf": {"v": 22, "src": "..."},   # 终值占比 > 60% 时交叉验证：(PV 前 10 年 OE + OE10 × 同行 市值/FCF ÷ (1+r)^10) ÷ 股数
 "scores": {"business": 0-30, "financial": 0-30, "management": 0-25, "price": 0-15}
}
用法：python3 tools/owner_value.py <输入.json> [--out memory/state/valuations/]
输出：屏幕摘要 + <ticker>_<as_of>.json（报告用 data-valuation 引用，report_check 核对报告数字与它一致）
"""
import json
import os
import sys

MOAT_CAPS = [(3, 4, 0.08, 0.03), (5, 6, 0.12, 0.05), (7, 8, 0.18, 0.08), (9, 10, 0.25, 0.10)]
SCORE_MAX = {"business": 30, "financial": 30, "management": 25, "price": 15}


class NoSource(Exception):
    pass


def need(obj, name):
    if not isinstance(obj, dict) or obj.get("v") is None or not str(obj.get("src", "")).strip():
        raise NoSource(f"{name} 缺数值或来源（无来源 = 不可用）")
    return obj["v"]


def caps(moat):
    for lo, hi, g1, gt in MOAT_CAPS:
        if lo <= moat <= hi:
            return g1, gt
    return None


def dcf(oe0, g1, ratio2, gt, r, years1=5, years2=5):
    """5 年 g1 + 5 年 g1×ratio2，第 10 年后按 gt 永续。返回 (PV 现金流合计, PV 终值, 第 10 年 OE)。"""
    pv, oe = 0.0, oe0
    for t in range(1, years1 + years2 + 1):
        oe *= 1 + (g1 if t <= years1 else g1 * ratio2)
        pv += oe / (1 + r) ** t
    tv = oe * (1 + gt) / (r - gt)
    return pv, tv / (1 + r) ** (years1 + years2), oe


def normalize(ys, out):
    """一次性现金项正态化（owner-earnings-model.md「一次性现金项正态化」）：每笔 adjustments 必须带 amount / src / why；
    同一金额同时加回 FCF 与 ΔWC（dwc 按现金口径，流出为负）。原始值留在 fcf_reported / dwc_reported。"""
    norm, res = [], []
    for y in ys:
        y = dict(y)
        adj = y.get("adjustments") or []
        tot = 0.0
        for a in adj:
            if a.get("amount") is None or not str(a.get("src", "")).strip() or not str(a.get("why", "")).strip():
                raise NoSource(f"FY{y.get('fy')} 一次性调整缺金额、来源或理由：{a.get('item')}")
            tot += a["amount"]
        if adj:
            y["fcf_reported"], y["dwc_reported"] = y["fcf"], y.get("dwc", 0)
            y["fcf"], y["dwc"] = y["fcf"] + tot, y.get("dwc", 0) + tot
            res.append({"fy": y["fy"], "fcf_reported": y["fcf_reported"], "fcf_normalized": y["fcf"],
                        "items": [{k: a.get(k) for k in ("item", "amount", "src", "why")} for a in adj]})
            out["flags"].append(f"FY{y['fy']} FCF 一次性项调整 {tot:+,.0f}：{y['fcf_reported']:,.0f} → {y['fcf']:,.0f}"
                                f"（{'；'.join(str(a.get('item')) for a in adj)}）")
        norm.append(y)
    out["normalization"] = res
    return norm


def auto_scores(inp, sf, out, ys, revs, dr, cover):
    """评分卡里能查表的 8 项由工具算（berkshire-score.md；2026-11-10）。
    为什么：KO、NVDA 两份报告共 8 轮 Critic，反复退回的就是查表查错、敏感性底稿抄旧分数。3A / 3B / 3C 是判断，仍由分析师给（带理由）。
    score_facts: {"gross_margin": [三年], "roe": [三年], "roic": [三年，可选], "cash": .., "debt": .., "ev_fcf": .., "peer_ev_fcf": ..,
                  "management": {"3A": {"v": .., "why": ..}, "3B": {...}, "3C": {...}}}
    2B 与 4B 一律用报告值 FCF（一次性项只用于估值）。"""
    d, why = {}, {}
    moat = inp["moat_score"]
    d["1A"] = 5 if moat <= 4 else 8 if moat <= 6 else 12 if moat <= 8 else 15
    why["1A"] = f"护城河 {moat} 分"
    grs = [revs[i] / revs[i - 1] - 1 for i in range(len(revs) - len(ys) + 1, len(revs))] or [0.0]
    cagr = (ys[-1]["revenue"] / ys[0]["revenue"]) ** (1 / (len(ys) - 1)) - 1
    neg = sum(1 for g in grs if g < 0)
    d["1B"] = (8 if cagr > 0.20 and neg == 0 else 6 if 0.10 <= cagr <= 0.20 and neg <= 1 else 4 if 0.05 <= cagr < 0.10 and neg == 0
               else 2 if (0.05 <= cagr < 0.10 and neg == 1) or (0 <= cagr < 0.05 and neg == 0) else 0)
    why["1B"] = f"营收复合增速 {cagr:.1%}，负增长 {neg} 年"
    gm = sf["gross_margin"]
    d["1C"] = 7 if min(gm) > 0.50 else 5 if min(gm) >= 0.35 else 3 if min(gm) >= 0.20 and gm[-1] >= gm[0] - 0.05 else 1
    why["1C"] = "毛利率 " + " / ".join(f"{g:.1%}" for g in gm)
    roe = sum(sf["roe"]) / len(sf["roe"])
    tiers = [12, 9, 6, 3, 0]
    i = 0 if roe > 0.25 else 1 if roe >= 0.18 else 2 if roe >= 0.12 else 3 if roe >= 0.08 else 4
    note = ""
    if dr > 0.40:
        if not sf.get("roic"):
            raise NoSource("负债率 > 40%：2A 需要 ROIC 复核（score_facts.roic）")
        if min(sf["roic"]) < 0.12:
            i, note = min(i + 2, 4), "；ROIC < 12%，降两档"
        else:
            note = "；负债率 > 40%，ROIC 复核均 ≥ 12%，不降档"
    d["2A"] = tiers[i]
    why["2A"] = f"ROE 三年均值 {roe:.1%}{note}"
    fr = [y.get("fcf_reported", y["fcf"]) for y in ys]
    ratios = [f / y["net_income"] for f, y in zip(fr, ys) if y["net_income"] > 0]
    pos = sum(1 for f in fr if f > 0)
    d["2B"] = (0 if pos <= 1 else 5 if pos == 2 else 10 if ratios and min(ratios) > 0.80 else 7 if ratios and min(ratios) >= 0.60 else 2)
    why["2B"] = "报告值 FCF / 净利润 " + " / ".join(f"{r:.0%}" for r in ratios) + "（按三年最低值查表）"
    last = ys[-1]
    d["2C"] = (0 if last["ebit"] < 0 else 8 if sf["cash"] > sf["debt"] else 6 if dr < 0.20 and cover > 10 else 4 if dr <= 0.40 and cover > 5
               else 0 if dr > 0.60 or cover < 3 else 2)
    why["2C"] = f"现金 {sf['cash']:,.0f}，有息负债 {sf['debt']:,.0f}，负债率 {dr:.0%}，利息覆盖 {cover:.1f}x"
    mv = out["margin_of_safety"]["value"]
    d["4A"] = 10 if mv >= 0.40 else 8 if mv >= 0.30 else 5 if mv >= 0.20 else 3 if mv >= 0.10 else 0
    why["4A"] = f"安全边际 {mv:.1%}"
    rel = sf["ev_fcf"] / sf["peer_ev_fcf"] - 1
    d["4B"] = 5 if rel <= -0.20 else 3 if rel <= 0.20 else 1
    why["4B"] = f"EV/FCF {sf['ev_fcf']:.1f}x，同行均值 {sf['peer_ev_fcf']:.1f}x（{rel:+.0%}）"
    for k in ("3A", "3B", "3C"):
        m = (sf.get("management") or {}).get(k) or {}
        if m.get("v") is None or not str(m.get("why", "")).strip():
            raise NoSource(f"评分 {k} 是判断项：需给分数和理由（score_facts.management.{k}）")
        d[k], why[k] = m["v"], m["why"]
    sc = {"business": d["1A"] + d["1B"] + d["1C"], "financial": d["2A"] + d["2B"] + d["2C"],
          "management": d["3A"] + d["3B"] + d["3C"], "price": d["4A"] + d["4B"]}
    return sc, d, why


def run(inp):
    price, shares, r = need(inp.get("price"), "现价"), need(inp.get("shares"), "股数"), need(inp.get("r"), "折现率")
    ys = inp["years"]
    if len(ys) < 3:
        raise NoSource("需要最近 3 个完整财年")
    for y in ys:
        if not str(y.get("src", "")).strip():
            raise NoSource(f"FY{y.get('fy')} 财务数据缺来源")
    out = {"ticker": inp["ticker"], "as_of": inp.get("as_of"), "currency": inp.get("currency"), "flags": [], "route": "标准 DCF"}
    ys = normalize(ys, out)
    last = ys[-1]

    # 估值失效条件（hub Phase 2）
    fcfs = [y["fcf"] for y in ys]
    revs = ([inp["revenue_prior"]["v"]] if inp.get("revenue_prior") else []) + [y["revenue"] for y in ys]
    fail = []
    if all(f < 0 for f in fcfs):
        fail.append("FCF 三年连负")
    # 营收增速波动率 = 各年营收增速的样本标准差（用户 2026-11-09 定）。原实现用「最高 ÷ 最低 − 1」，
    # 会把任何持续高增长误判为波动（NVDA +126% / +114% / +65% 被判 254% 失效）；高增长另由异常增速路径处理。
    import statistics
    grs = [revs[i] / revs[i - 1] - 1 for i in range(1, len(revs))]
    vol = statistics.stdev(grs) if len(grs) >= 2 else 0.0
    out["revenue_growth"] = {"rates": grs, "stdev": vol}
    if vol > 0.5:
        fail.append(f"营收增速波动率（标准差）{vol * 100:.0f} 个百分点 > 50")
    dr = need(inp.get("debt_ratio"), "负债率")
    cover = last["ebit"] / last["interest"] if last.get("interest") else float("inf")
    if dr > 0.5 and cover < 3:
        fail.append(f"负债率 {dr:.0%} > 50% 且 EBIT / 利息 {cover:.1f}x < 3")
    if inp.get("tech_disruption"):
        fail.append("技术颠覆期（分析师判断）")
    out["failure_conditions"] = fail

    # 护城河门槛
    moat = inp["moat_score"]
    if moat < 3:
        out.update(verdict="终止：护城河 < 3，不进入估值（心智模型 1）")
        return out
    g1cap, gtcap = caps(moat)

    # 所有者盈余基数：最近完整财年；结束超过 6 个月且有季报时用近 12 个月（TTM）实际值（用户 2026-11-09 定）。
    # 只用已发生的现金流，不用预测。NVDA：FY2026 已过 9 个月，上半年 FCF 同比 +77%，用完整财年会把已实现的增长截掉。
    import datetime as _dt
    base = last
    out["base"] = {"kind": "最近完整财年", "fy": last.get("fy")}
    if inp.get("ttm"):
        t = inp["ttm"]
        if not str(t.get("src", "")).strip():
            raise NoSource("TTM 基数缺来源")
        base = dict(t)
        out["base"] = {"kind": "近 12 个月（TTM）", "period_end": t.get("period_end"), "src": t["src"]}
    elif inp.get("base_fy_end") and inp.get("as_of"):
        age = (_dt.date.fromisoformat(inp["as_of"][:10]) - _dt.date.fromisoformat(inp["base_fy_end"])).days
        if age > 183:
            out["flags"].append(f"最近完整财年已结束 {age} 天（> 6 个月）：规则要求改用 TTM 实际值作基数（给 ttm 输入）")
    m = inp["maint_capex"]
    meth = m["method"]
    mc = {"da_proxy": base["da"], "total": base["capex"], "disclosed": m.get("value"),
          "pct_of_capex": base["capex"] * (m.get("pct") or 0.5)}[meth]
    if mc is None:
        raise NoSource("维护性资本支出：method=disclosed 但没给 value")
    oe = base["net_income"] + base["da"] - mc + base.get("dwc", 0)
    out["owner_earnings"] = {"value": oe, "maint_capex": mc, "method": meth, "why": m.get("why")}
    if oe <= 0:
        fail.append("所有者盈余 ≤ 0（靠外部资本维持运营）")

    # 增速：近 3 年 FCF CAGR（两段：最旧 → 最新）
    anomaly = fcfs[0] <= 0 or (fcfs[-1] > 0 and (fcfs[-1] / fcfs[0]) ** 0.5 - 1 > 0.5)
    cagr = (fcfs[-1] / fcfs[0]) ** 0.5 - 1 if fcfs[0] > 0 and fcfs[-1] > 0 else None
    out["fcf_cagr"] = cagr
    if anomaly:
        go = inp.get("g_override")
        if not go or not str(go.get("src", "")).strip():
            raise NoSource("异常增速（CAGR>50% 或 FCF 由负转正）：必须给 g_override {g1, g2, src}（共识锚定 / FCF yield 反推）")
        g_cons, g_base = min(go["g1"], g1cap), min(go["g2"], g1cap)
        out["flags"].append("历史增速异常，DCF 基于正态化增速，可信度中等")
        out["route"] = "正态化增速 DCF（路径 B）"
    else:
        g_cons, g_base = min(max(cagr, 0) * 0.60, g1cap), min(max(cagr, 0) * 0.85, g1cap)

    # 终端增长率：上限的 60% / 80%，且分别不超过 2.5% / 4%，并硬性 ≤ r − 2%
    gt_cons = min(gtcap * 0.6, 0.025, r - 0.02)
    gt_base = min(gtcap * 0.8, 0.03, r - 0.02)  # 用户 11/07 定：封顶 3%（与全球 GDP 参考值统一）
    res = {}
    for name, g, ratio2, gt in (("conservative", g_cons, 0.5, gt_cons), ("base", g_base, 0.6, gt_base)):
        pv, pvtv, oe10 = dcf(oe, g, ratio2, gt, r)
        iv = (pv + pvtv) / shares
        res[name] = {"g1": g, "g2": g * ratio2, "g_terminal": gt, "pv_cash": pv, "pv_terminal": pvtv,
                     "terminal_share": pvtv / (pv + pvtv), "oe_year10": oe10, "iv_per_share": iv}
        if pvtv / (pv + pvtv) > 0.6:
            peer = inp.get("peer_p_fcf")
            if peer:  # 股权口径（用户 11/07 定）：前 10 年 OE 现值 + 第 10 年 OE × 同行 P/FCF 折现
                cross = (pv + oe10 * need(peer, "同行 P/FCF") / (1 + r) ** 10) / shares
                res[name]["exit_multiple_iv"] = cross
                if abs(cross - iv) / iv > 0.3:
                    res[name]["iv_per_share"] = min(cross, iv)
                    out["flags"].append(f"{name} 终值占比 > 60% 且出口倍数法差 > 30%：取较低值")
            else:
                out["flags"].append(f"{name} 终值占比 {pvtv / (pv + pvtv):.0%} > 60%：需同行 P/FCF 交叉验证（未给 peer_p_fcf）")
    out["scenarios"] = res

    # 敏感性（以保守情景 = 安全边际基准为底）与逆向验证（现价隐含的阶段 1 增速，基准情景结构、不设护城河上限）
    def iv_of(g, ratio2, gt, rr):
        a, b, _ = dcf(oe, g, ratio2, min(gt, rr - 0.02), rr)
        return (a + b) / shares
    c = res["conservative"]
    base_iv = iv_of(c["g1"], 0.5, c["g_terminal"], r)
    sens = []
    for var, d, args in (("r", +0.01, (c["g1"], 0.5, c["g_terminal"], r + 0.01)), ("r", -0.01, (c["g1"], 0.5, c["g_terminal"], r - 0.01)),
                         ("g1", +0.03, (c["g1"] + 0.03, 0.5, c["g_terminal"], r)), ("g1", -0.03, (c["g1"] - 0.03, 0.5, c["g_terminal"], r)),
                         ("g_terminal", +0.005, (c["g1"], 0.5, c["g_terminal"] + 0.005, r))):
        v = iv_of(*args)
        sens.append({"var": var, "delta": d, "iv_per_share": v, "change": v / base_iv - 1})
    out["sensitivity"] = {"basis": "保守情景", "rows": sens}
    lo_g, hi_g = -0.5, 2.0
    if iv_of(lo_g, 0.6, res["base"]["g_terminal"], r) < price < iv_of(hi_g, 0.6, res["base"]["g_terminal"], r):
        for _ in range(200):
            mid = (lo_g + hi_g) / 2
            lo_g, hi_g = (mid, hi_g) if iv_of(mid, 0.6, res["base"]["g_terminal"], r) < price else (lo_g, mid)
        out["implied_g1"] = {"g1": lo_g, "g2": lo_g * 0.6, "g_terminal": res["base"]["g_terminal"], "moat_cap": g1cap,
                             "exceeds_cap": lo_g > g1cap, "fcf_cagr": cagr}
    lo, hi = res["conservative"]["iv_per_share"], res["base"]["iv_per_share"]
    out["iv_range"] = [lo, hi]
    out["iv_mid_reference"] = (lo + hi) / 2

    # 安全边际：按下沿（用户 11/07 定）
    mos = (lo - price) / lo
    hurdle = 0.40 if out["route"].startswith("正态化") else 0.30
    out["margin_of_safety"] = {"basis": "内在价值下沿（保守情景）", "value": mos, "hurdle": hurdle, "price": price}
    zone = "买入区间" if mos >= hurdle else ("观察区间" if mos >= 0.15 else "高估区间（不买）")
    out["zone"] = zone if not fail else f"估值失效（{'；'.join(fail)}）→ 按替代估值顺序，不出买入结论"

    # 三个检验（可算的部分）
    out["checks"] = {"fcf_conversion": [y["fcf"] / y["net_income"] if y["net_income"] else None for y in ys],
                     "interest_cover": cover}

    # 不调一次性项时的对照（spoke：报告须说明「不调」时结论是否改变）
    if out["normalization"] and not inp.get("_no_adj"):
        raw = dict(inp, _no_adj=True, years=[{k: v for k, v in y.items() if k != "adjustments"} for y in inp["years"]])
        try:
            ro = run(raw)
            out["without_adjustments"] = {"iv_range": ro.get("iv_range"), "fcf_cagr": ro.get("fcf_cagr"),
                                          "margin_of_safety": ro.get("margin_of_safety", {}).get("value"), "zone": ro.get("zone")}
        except NoSource as e:  # 例如不调后 FCF 由正转负触发 g_override 要求
            out["without_adjustments"] = {"error": str(e)}

    # 评分卡：给了 score_facts 就由工具查表（3A–3C 除外），并覆盖手填分数
    if inp.get("score_facts"):
        asc, asd, awhy = auto_scores(inp, inp["score_facts"], out, ys, revs, dr, cover)
        inp["scores"], inp["scores_detail"] = asc, asd
        out["scorecard_detail"] = {k: {"score": asd[k], "why": awhy[k]} for k in asd}
    sc = inp.get("scores") or {}
    bad = [k for k, mx in SCORE_MAX.items() if not (0 <= sc.get(k, -1) <= mx)]
    if bad:
        raise NoSource(f"评分卡维度缺失或越界：{bad}（满分 {SCORE_MAX}）")
    out["scorecard"] = dict(sc, total=sum(sc[k] for k in SCORE_MAX))
    # 4A 由安全边际机械决定（berkshire-score 4A 表）：11/09 NVDA 护城河 9 分对照底稿复制了主底稿的 4A = 0，
    # 实际安全边际 34% 应得 8，总分错 8 分。给了 scores_detail 就核对，对不上直接拒算。
    sd = inp.get("scores_detail") or {}
    if "4A" in sd and "iv_range" in out:
        mv = out["margin_of_safety"]["value"]
        exp4a = 10 if mv >= 0.40 else 8 if mv >= 0.30 else 5 if mv >= 0.20 else 3 if mv >= 0.10 else 0
        if sd["4A"] != exp4a:
            raise NoSource(f"评分卡 4A = {sd['4A']} 与安全边际 {mv:.1%} 不符（应为 {exp4a}，berkshire-score 4A 表）")
        if "4B" in sd and sc.get("price") != sd["4A"] + sd["4B"]:
            raise NoSource(f"price = {sc.get('price')} ≠ 4A {sd['4A']} + 4B {sd['4B']}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    od = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), "memory/state/valuations")
    inp = json.load(open(args[0], encoding="utf-8"))
    try:
        out = run(inp)
    except NoSource as e:
        sys.exit(f"拒算：{e}")
    os.makedirs(od, exist_ok=True)
    fp = os.path.join(od, f"{out['ticker'].lower()}_{out.get('as_of') or 'na'}.json")
    out["input"] = inp
    json.dump(out, open(fp, "w"), ensure_ascii=False, indent=1)
    if "iv_range" in out:
        lo, hi = out["iv_range"]
        m = out["margin_of_safety"]
        print(f"{out['ticker']}：内在价值 {lo:.2f}–{hi:.2f}（中值 {out['iv_mid_reference']:.2f} 仅参考）｜现价 {m['price']}｜"
              f"安全边际（下沿）{m['value']:.1%}，门槛 {m['hurdle']:.0%} → {out['zone']}｜评分 {out['scorecard']['total']}/100")
    else:
        print(out.get("verdict"))
    for f in out["flags"]:
        print("  ⚠", f)
    print("→", fp)


if __name__ == "__main__":
    main()
