#!/usr/bin/env python3
"""关注标的的基本面体检（期权基本面反向名单的月度复核数据源，position-discipline 第 17 条）

为什么（2026-11-05）：名单首版只用了仓库已有事实；复核要用巴菲特（护城河 / 资本回报 / 稀释）和伯里（估值 / 负债 / 泡沫）的口径，
而 SEC 数据在会话容器里打不开，所以在 Actions 里跑，复用 burry_screener 的 frames 抓取与缓存。
产出 watch_fundamentals.json：每个关注标的的指标 + 在全市场完整样本中的分位。
口径说明：
  - 指标基准年 = burry_screener 的 YEAR（最近完整财年，CY 口径）；股本变化用最近季度末 vs 约一年前季度末。
  - ROE 为近似：经营利润 × (1 − 21%) ÷ 净资产（frames 不统一提供归母净利）。
  - 估值用仓库价格缓存 stock_prices.json 的现价 × 最新股本。
  - ETF（SLV、XLE 等）不适用，标「ETF」。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import burry_screener as bs  # noqa: E402

ETFS = {"SLV", "XLE", "GLD", "SPY", "QQQ", "IWM", "TLT"}
TAX = 0.21


def main():
    watch = json.load(open("options_watch.json"))["tickers"]
    prices = json.load(open("stock_prices.json"))["prices"]
    uni = bs.build_universe()
    tickers = bs.fetch_ticker_map()
    finvals = bs.fetch_financial_values()
    full, missing, na = bs.stage_a(uni, tickers, finvals)

    # 上一财年营收（增速）与约一年前的股本（稀释）
    prev_rev = {}
    for tag in bs.CONCEPTS["revenue"]:
        for cik, (val, _) in bs.fetch_frame(tag, bs.YEAR - 1).items():
            prev_rev.setdefault(cik, val)
    old_period = bs.INSTANT_PERIODS[-1]  # 最旧的季度末，约一年前
    old_shares = {}
    for tag, tax, unit in (("EntityCommonStockSharesOutstanding", "dei", "shares"),
                           ("CommonStockSharesOutstanding", "us-gaap", "shares")):
        for cik, (val, _) in bs.fetch_frame(tag, bs.YEAR, taxonomy=tax, unit=unit, period=old_period).items():
            old_shares.setdefault(cik, val)

    # 全市场完整样本的分位基准（与伯里扫描器同一口径）
    def mk_val(r, key):
        p = prices.get(r.get("ticker") or "", {}).get("price")
        if not p:
            return None
        mcap = p * r["shares"]
        return {"ev_ebitda": (mcap + r["net_debt"]) / r["ebitda"], "fcf_yield": r["fcf"] / mcap,
                "pb": mcap / r["equity"]}[key]
    base = {k: [mk_val(r, k) for r in full] for k in ("ev_ebitda", "fcf_yield", "pb")}
    base["sbc_ratio"] = [r["sbc_ratio"] for r in full]
    base["net_debt_ebitda"] = [r["net_debt_ebitda"] for r in full]

    by_ticker = {}
    for group, label in ((full, "完整"), (missing, "数据缺失"), (na, "不适用")):
        for r in group:
            if r.get("ticker"):
                by_ticker.setdefault(r["ticker"], (r, label))

    out = {"year": bs.YEAR, "shares_old_period": old_period, "universe_complete": len(full), "tickers": {}}
    for t in watch:
        if t in ETFS:
            out["tickers"][t] = {"status": "ETF", "note": "ETF 不适用公司基本面"}
            continue
        hit = by_ticker.get(t)
        if not hit:
            out["tickers"][t] = {"status": "未找到", "note": "SEC frames 无该 ticker 映射"}
            continue
        r, label = hit
        e = uni.get(r["cik"], {})
        rec = {"status": label, "name": r.get("name"), "reason": r.get("reason"), "missing": r.get("missing")}
        if label == "完整":
            p = prices.get(t, {}).get("price")
            mcap = p * r["shares"] if p else None
            opi = e.get("operating_income")
            rec.update({
                "revenue": r["revenue"], "op_margin": opi / r["revenue"] if opi else None,
                "rev_growth": (r["revenue"] / prev_rev[r["cik"]] - 1) if prev_rev.get(r["cik"]) else None,
                "roe_approx": (opi * (1 - TAX) / r["equity"]) if opi else None,
                "fcf_margin": r["fcf"] / r["revenue"],
                "net_debt_ebitda": r["net_debt_ebitda"], "sbc_ratio": r["sbc_ratio"],
                "share_change": (r["shares"] / old_shares[r["cik"]] - 1) if old_shares.get(r["cik"]) else None,
                "price": p,
                "ev_ebitda": (mcap + r["net_debt"]) / r["ebitda"] if mcap else None,
                "fcf_yield": r["fcf"] / mcap if mcap else None,
                "pb": mcap / r["equity"] if mcap else None,
            })
            rec["pct"] = {k: bs.rank_pct(base[k], rec.get(k)) for k in base}
        out["tickers"][t] = rec
    with open("watch_fundamentals.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for t, r in out["tickers"].items():
        print(t, r.get("status"), {k: (round(v, 3) if isinstance(v, float) else v)
                                   for k, v in r.items() if k in ("ev_ebitda", "fcf_yield", "roe_approx", "share_change", "rev_growth")})


if __name__ == "__main__":
    main()
