#!/usr/bin/env python3
"""按公司取 10-K 年报关键科目（SEC companyfacts），写 financials/<ticker>.json——巴菲特估值的带来源原始数据

为什么（2026-11-07 buffett-analyst 实测）：owner_value 要求每个数字带来源；10-K 原文在会话容器打不开，
companyfacts 是 SEC 官方 XBRL（每个值带 accession 号与报送日期，就是可追溯的来源）。复用 ses_screener 的抓取与缓存。
请求：financials_request.json {"tickers": ["KO"], "years": 3}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ses_screener as ss  # noqa: E402

# 科目：按优先级取第一个有数的标签
TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "ebit": ["OperatingIncomeLoss"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PurchasesRelatedToPropertyAndEquipmentAndIntangibleAssets"],  # 11/09：NVDA 只报这个
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "interest": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "dwc_increase": ["IncreaseDecreaseInOperatingCapital"],  # 营运资本增加为正 → OE 里取负
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
    "debt_st": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    "commercial_paper": ["CommercialPaper", "ShortTermBorrowings"],
    # 11/07 KO 实测补：护城河（毛利率对比同行）、管理层（回购 / 分红 / 股数）、负债率（少数股东权益）
    "gross_profit": ["GrossProfit"],
    "cogs": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "buyback": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "nci": ["MinorityInterest"],
    "equity_total": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "tax": ["IncomeTaxExpenseBenefit"],  # 11/07 Critic：ROIC 按各年实际税率，不套一个预估税率
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
}

DEBT_HINT = ("Debt", "Borrowings", "CommercialPaper", "Notes")
CAPEX_HINT = ("PropertyPlantAndEquipment", "PropertyAndEquipment", "ProductiveAssets")  # 11/09 NVDA capex 标签找不到时供人工挑


def annual(facts, tags):
    """返回 {fy: {"v", "tag", "accn", "filed", "end"}}，只取 10-K 的 FY 值，同 FY 取最新报送。"""
    # 11/09 NVDA：capex 用公司自建扩展标签（不在 us-gaap 里），只查 us-gaap 会静默缺失 → us-gaap 优先，再查其他分类
    ns = facts.get("facts", {})
    gaap = dict(ns.get("us-gaap", {}))
    for k, v in ns.items():
        if k not in ("us-gaap", "dei"):
            for t, val in v.items():
                gaap.setdefault(t, val)
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {})
        rows = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        out = {}
        for r in rows:
            if r.get("form") == "10-K" and r.get("fp") == "FY" and r.get("fy"):
                # 同一 10-K 会带前两年对比值：用 end 年份对应真实财年
                fy = int(r["end"][:4])
                if fy not in out or r["filed"] > out[fy]["filed"]:
                    if "start" in r and int(r["end"][:4]) - int(r["start"][:4]) > 1:
                        continue
                    out[fy] = {"v": r["val"], "tag": tag, "accn": r["accn"], "filed": r["filed"], "end": r["end"]}
        if out:
            return out
    return {}


def main():
    req = json.load(open("financials_request.json"))
    os.makedirs("financials", exist_ok=True)
    for t in req["tickers"]:
        cik = ss.get_cik(t)
        facts = ss.fetch_company_facts(cik)
        data = {k: annual(facts, tags) for k, tags in TAGS.items()}
        shares = facts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
        latest_sh = max(shares, key=lambda r: r["filed"]) if shares else None
        yrs = sorted({fy for d in data.values() for fy in d})[-int(req.get("years", 3)) - 1:]
        out = {"ticker": t, "cik": cik, "entity": facts.get("entityName"),
               "source": f"SEC EDGAR companyfacts https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
               "shares_outstanding": latest_sh and {"v": latest_sh["val"], "accn": latest_sh["accn"], "filed": latest_sh["filed"]},
               "years": {fy: {k: d.get(fy) for k, d in data.items()} for fy in yrs},
               "missing": {fy: [k for k, d in data.items() if fy not in d] for fy in yrs}}
        # 债务标签各家各年不同（KO 2024 起 LongTermDebtNoncurrent 缺）：列出所有含 Debt 的标签最近 10-K 值，供人工挑口径
        gaap = facts.get("facts", {}).get("us-gaap", {})
        out["debt_tags"] = {tag: {fy: v["v"] for fy, v in annual(facts, [tag]).items() if fy in yrs}
                            for tag in gaap if any(h in tag for h in DEBT_HINT) and "Repayments" not in tag and "Proceeds" not in tag}
        out["debt_tags"] = {k: v for k, v in out["debt_tags"].items() if v}
        allns = {t for v in facts.get("facts", {}).values() for t in v}
        out["capex_tags"] = {f"{tag}": {fy: v["v"] for fy, v in annual(facts, [tag]).items() if fy in yrs}
                             for tag in sorted(allns) if any(h in tag for h in CAPEX_HINT) and ("Payment" in tag or "Purchase" in tag)}
        try:
            import yfinance as yf
            h = yf.Ticker(t).history(period="5d")
            out["price"] = {"v": round(float(h["Close"].iloc[-1]), 2), "date": str(h.index[-1].date()),
                            "src": "Yahoo Finance 日收盘（yfinance，Actions 抓取）"}
        except Exception as e:  # 价格只是辅助，失败不挡财报数据
            out["price"] = {"v": None, "error": str(e)[:200]}
        json.dump(out, open(f"financials/{t.lower()}.json", "w"), ensure_ascii=False, indent=1)
        print(t, out["entity"], "年份", yrs, "缺", out["missing"])


if __name__ == "__main__":
    main()
