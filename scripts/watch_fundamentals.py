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

ETFS = {"SLV", "XLE", "GLD", "SPY", "QQQ", "IWM", "TLT", "HYG", "USO", "XLF", "GDX", "XLP", "FXI", "EWZ",
        "KRE", "EEM", "ARKK", "XLU", "XLV", "XLI", "XLB", "XBI"}
# 银行口径申报、但没被扫描器的金融识别抓到的标的：营收科目只取到一部分（SOFI 6.2 亿），指标不可比
LENDERS = {"SOFI": "持牌银行（SoFi Bank），营收科目只取到一部分，指标不可比"}
TAX = 0.21


def main():
    watch = json.load(open("options_watch.json"))["tickers"]
    prices = json.load(open("stock_prices.json"))["prices"]
    uni = bs.build_universe()
    tickers = bs.fetch_ticker_map()
    finvals = bs.fetch_financial_values()

    # 稀释后加权平均股数（利润表科目，单一总数）。2026-11-05 修：
    #   F / HOOD / PLTR 是多类股，dei 与 us-gaap 的期末股本按类别分维度申报，frames 只收无维度事实 → 整家缺股本。
    #   加权平均股数没有类别维度、人人都报，既补期末股本的缺口，也给「股本变化」一个统一口径（今年 ÷ 去年）。
    def wavg(year):
        out = {}
        for tag in ("WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"):
            for cik, (val, _) in bs.fetch_frame(tag, year, unit="shares").items():
                out.setdefault(cik, val)
        return out
    wavg_now, wavg_prev = wavg(bs.YEAR), wavg(bs.YEAR - 1)
    cik_of = {v: k for k, v in tickers.items()}
    shares_src = {}
    for t in watch:
        cik = cik_of.get(t)
        if not cik or cik not in uni:
            continue
        e = uni[cik]
        if e.get("shares") is None and e.get("shares_gaap") is None and wavg_now.get(cik):
            e["shares"] = wavg_now[cik]
            shares_src[t] = "稀释加权平均股数（多类股补缺）"

    # 现价：缓存没有的标的在这里直接取（缓存清单已改为自动并入关注清单，这是兜底）
    for t in watch:
        if t not in prices or not prices[t].get("price"):
            try:
                import yfinance as yf
                prices[t] = {"price": float(yf.Ticker(t).fast_info["last_price"]), "src": "yfinance 兜底"}
            except Exception as ex:  # 取不到就留空，产物里会显示无现价
                print(f"  {t} 取价失败：{ex}")

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
        if t in LENDERS:
            out["tickers"][t] = {"status": "不适用", "note": LENDERS[t]}
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
                "share_change": ((wavg_now[r["cik"]] / wavg_prev[r["cik"]] - 1) if wavg_now.get(r["cik"]) and wavg_prev.get(r["cik"])
                                 else ((r["shares"] / old_shares[r["cik"]] - 1) if old_shares.get(r["cik"]) else None)),
                "shares_source": shares_src.get(t, "期末股本"),
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
