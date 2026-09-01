"""
burry_13f.py — 13F-HR 持仓抓取与逐季变动计算

补上 Burry 智能体缺失的另一半：扫描器（burry_screener.py）已跑通，
但归因模块此前没有数据源，`Burry 归因/持仓/校验` 三个命令无法运行。

产物 burry_holdings.json：
  quarters: {报告期: {holdings: [...], total_value, n_positions, filed, accession}}
  changes:  {报告期: {new/add/trim/exit: [...]}}   相对上一报告期
  meta:     CIK、Tier 1 边界、口径声明

⚠ 运行环境：sec.gov 在会话容器出口策略封禁名单内，本脚本在 GitHub Actions 跑。

⚠⚠ 最大的口径陷阱（会静默污染全部结论）：
   13F infotable 的 <value> 字段在 2023-01-03 之前以**千美元**申报，之后以**美元**申报。
   混用会让 2022 及更早的持仓市值被低估 1000 倍，而这个错误不会报错、不会崩、
   只会让「他历史上仓位很小」这种荒谬结论看起来很正常。本脚本按备案日期切换单位。
"""

import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Personal Research zhenyuanhuang358@gmail.com"}
CACHE_DIR = os.environ.get("BURRY_13F_CACHE", ".burry_13f")
OUT_FILE = "burry_holdings.json"
STATE_FILE = "burry_state.json"

# <value> 单位切换日：此日期（含）之后备案的以美元申报，之前以千美元申报
VALUE_DOLLARS_FROM = "2023-01-03"


def _get(url, timeout=90, raw=False):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if raw else json.loads(data)


def _cached(name, fetch, raw=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path):
        mode = "rb" if raw else "r"
        with open(path, mode) as f:
            return f.read() if raw else json.load(f)
    val = fetch()
    mode = "wb" if raw else "w"
    with open(path, mode) as f:
        f.write(val) if raw else json.dump(val, f)
    time.sleep(0.15)
    return val


def load_state():
    if not os.path.exists(STATE_FILE):
        raise SystemExit("burry_state.json 不存在——先跑 burry_screener.py 做 Tier 边界发现")
    with open(STATE_FILE) as f:
        return json.load(f)


def find_infotable_url(cik, accession):
    """从 filing index 里找 infotable XML。文件名不固定，必须查索引而不是猜。"""
    acc = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
    try:
        idx = _cached(f"idx_{acc}.json", lambda: _get(f"{base}/index.json"))
    except Exception as e:
        print(f"    index 拉取失败 {accession}: {type(e).__name__}")
        return None
    items = idx.get("directory", {}).get("item", [])
    # 优先带 infotable 字样的 xml；否则取非 primary_doc 的 xml
    cands = [i["name"] for i in items if i["name"].lower().endswith(".xml")]
    for n in cands:
        if "infotable" in n.lower() or "info_table" in n.lower():
            return f"{base}/{n}"
    for n in cands:
        if "primary_doc" not in n.lower() and not n.lower().startswith("form13f"):
            return f"{base}/{n}"
    return None


def parse_infotable(xml_bytes, value_in_dollars):
    """解析 infoTable。返回持仓列表。
    value_in_dollars=False 时把千美元换算成美元。"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"    XML 解析失败: {e}")
        return []
    rows = []
    for it in root.iter():
        if not it.tag.endswith("infoTable"):
            continue
        g = {}
        for ch in it:
            tag = ch.tag.split("}")[-1]
            if tag == "shrsOrPrnAmt":
                for sub in ch:
                    g[sub.tag.split("}")[-1]] = (sub.text or "").strip()
            else:
                g[tag] = (ch.text or "").strip()
        try:
            val = float(g.get("value", 0) or 0)
        except ValueError:
            val = 0.0
        if not value_in_dollars:
            val *= 1000.0                      # 千美元 -> 美元
        try:
            shares = float(g.get("sshPrnamt", 0) or 0)
        except ValueError:
            shares = 0.0
        put_call = (g.get("putCall") or "").strip() or None
        rows.append({
            "issuer": g.get("nameOfIssuer", ""),
            "cusip": g.get("cusip", ""),
            "class": g.get("titleOfClass", ""),
            "value": val,
            "shares": shares,
            "share_type": g.get("sshPrnamtType", ""),
            # ⚠ 13F 对期权披露的是标的名义市值，不是权利金。
            #   与股票并列排序会严重夸大期权仓位，故打标记供下游单列。
            "put_call": put_call,
            "is_option": put_call is not None,
        })
    return rows


def merge_same_security(rows):
    """同一 CUSIP 可能因不同 discretion/manager 拆成多行，需合并。
    期权与股票即使同 CUSIP 也不合并——它们是不同工具。

    ⚠ 排序时股票在前、期权在后，两组各自按市值降序，**不混排**。
      期权披露的是标的名义市值而非权利金，混排会让期权占据榜首位置，
      任何 holdings[:N] 的下游读法都会被误导（本文件 F5 明令禁止的事）。"""
    agg = {}
    for r in rows:
        key = (r["cusip"], r["put_call"] or "STOCK")
        if key in agg:
            agg[key]["value"] += r["value"]
            agg[key]["shares"] += r["shares"]
        else:
            agg[key] = dict(r)
    vals = list(agg.values())
    stocks = sorted((r for r in vals if not r["is_option"]), key=lambda r: -r["value"])
    opts = sorted((r for r in vals if r["is_option"]), key=lambda r: -r["value"])
    return stocks + opts


def compute_changes(prev, cur):
    """相对上一报告期的变动。按 (cusip, 工具类型) 配对。"""
    pk = {(r["cusip"], r["put_call"] or "STOCK"): r for r in prev}
    ck = {(r["cusip"], r["put_call"] or "STOCK"): r for r in cur}
    new, add, trim, exit_ = [], [], [], []
    for k, r in ck.items():
        if k not in pk:
            new.append({**r, "prev_shares": 0})
        else:
            ps = pk[k]["shares"]
            if r["shares"] > ps * 1.02:
                add.append({**r, "prev_shares": ps,
                            "share_chg_pct": (r["shares"] / ps - 1) if ps else None})
            elif r["shares"] < ps * 0.98:
                trim.append({**r, "prev_shares": ps,
                             "share_chg_pct": (r["shares"] / ps - 1) if ps else None})
    for k, r in pk.items():
        if k not in ck:
            exit_.append({**r, "prev_shares": r["shares"], "shares": 0})
    key = lambda x: -x["value"]
    return {"new": sorted(new, key=key), "add": sorted(add, key=key),
            "trim": sorted(trim, key=key), "exit": sorted(exit_, key=lambda x: -x["value"])}


def concentration(rows):
    """集中度指标。⚠ 期权按名义市值披露，必须单独算，不与股票同池排序。"""
    stocks = [r for r in rows if not r["is_option"]]
    opts = [r for r in rows if r["is_option"]]
    tv = sum(r["value"] for r in stocks)
    if tv <= 0:
        return {"stock_total": 0, "n_stock": len(stocks), "n_option": len(opts)}
    w = sorted((r["value"] / tv for r in stocks), reverse=True)
    return {
        "stock_total": tv,
        "option_notional": sum(r["value"] for r in opts),
        "n_stock": len(stocks), "n_option": len(opts),
        "top1": w[0] if w else 0,
        "top5": sum(w[:5]),
        "top10": sum(w[:10]),
        # 有效持仓数（HHI 倒数）：比「持仓家数」更能反映真实分散度
        "effective_n": (1.0 / sum(x * x for x in w)) if w else 0,
    }


def pick_latest_per_period(filings):
    """同一 report_date 可能有原件(13F-HR)与修订(13F-HR/A)多份。

    ⚠ P0 修复（2026-09-01 审计发现）：原实现是
        for f in sorted(filings, key=report_date): quarters[rd] = ...
      同键之间「后处理的覆盖先处理的」，而 sorted 只按 report_date 排、
      同键保持原顺序——**留下哪一份完全由列表顺序偶然决定，不是设计**。
      实测 2023-12-31 保留了原件、丢弃了修订件。
      **修订件之所以存在就是因为原件有错，保留原件等于保留了错的那份。**

    规则：同一 report_date 取「备案日最晚」的那份；备案日相同则 /A 优先。
    """
    best = {}
    for f in filings:
        rd = f.get("report_date")
        if not rd:
            continue
        cur = best.get(rd)
        if cur is None:
            best[rd] = f
            continue
        key = lambda x: ((x.get("filing_date") or ""), 1 if x.get("form", "").endswith("/A") else 0)
        if key(f) > key(cur):
            best[rd] = f
    return [best[k] for k in sorted(best)]


def main():
    st = load_state()
    cik = st.get("cik")
    filings = ((st.get("tier1") or {}).get("all")) or []
    if not cik or not filings:
        raise SystemExit("burry_state.json 里没有 CIK 或 13F 备案列表")
    print(f"CIK {cik}｜13F-HR 备案 {len(filings)} 份（state 中保留最近 {len(filings)} 份）")

    selected = pick_latest_per_period(filings)
    amended = [f for f in selected if f.get("form", "").endswith("/A")]
    print(f"  去重后 {len(selected)} 个报告期（其中 {len(amended)} 个取自修订件 13F-HR/A）")

    quarters = {}
    skipped = []          # ⚠ P0 修复：抓取失败必须落库，否则产物看不出漏了几期
    for f in selected:
        rd, fd, acc = f["report_date"], f["filing_date"], f["accession"]
        url = find_infotable_url(cik, acc)
        if not url:
            print(f"  {rd}  ✗ 未找到 infotable")
            skipped.append({"report_date": rd, "accession": acc, "reason": "未找到 infotable XML"})
            continue
        try:
            xb = _cached(f"it_{acc.replace('-','')}.xml",
                         lambda: _get(url, raw=True), raw=True)
        except Exception as e:
            print(f"  {rd}  ✗ 下载失败 {type(e).__name__}")
            skipped.append({"report_date": rd, "accession": acc,
                            "reason": f"下载失败 {type(e).__name__}"})
            continue
        in_dollars = (fd or "9999") >= VALUE_DOLLARS_FROM
        rows = merge_same_security(parse_infotable(xb, in_dollars))
        conc = concentration(rows)
        quarters[rd] = {
            "report_date": rd, "filing_date": fd, "accession": acc, "form": f["form"],
            "value_unit_source": "USD" if in_dollars else "USD(由千美元换算)",
            "n_positions": len(rows),
            "total_value": sum(r["value"] for r in rows),
            "concentration": conc,
            "holdings": rows,
        }
        print(f"  {rd}  {len(rows):>3} 持仓  股票合计 ${conc.get('stock_total',0)/1e6:>9,.1f}M"
              f"  期权名义 ${conc.get('option_notional',0)/1e6:>8,.1f}M"
              f"  top1 {conc.get('top1',0)*100:>5.1f}%  有效持仓 {conc.get('effective_n',0):>4.1f}"
              f"  [{'USD' if in_dollars else '千USD→USD'}]")

    # 逐季变动
    keys = sorted(quarters)
    changes = {}
    for i in range(1, len(keys)):
        changes[keys[i]] = compute_changes(quarters[keys[i-1]]["holdings"],
                                           quarters[keys[i]]["holdings"])
    # 浓仓位阈值：用该管理人自身历史 top1 分布的 80% 分位，不写死 15%
    top1s = sorted(q["concentration"].get("top1", 0) for q in quarters.values())
    conc_threshold = top1s[min(int(0.80 * (len(top1s) - 1)), len(top1s) - 1)] if top1s else None

    out = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cik": cik,
        "entity_name": (st.get("tier1") or {}).get("entity_name"),
        "tier1_boundary": ((st.get("tier1") or {}).get("latest") or {}).get("report_date"),
        "periods_available": len(selected),
        "quarters_parsed": len(quarters),
        # ⚠ 抓取失败的期间显式落库。为空是结论，不为空是必须交代的缺口。
        "skipped": skipped,
        "amended_periods": [f["report_date"] for f in amended],
        "concentration_threshold_top1": conc_threshold,
        "caliber_notes": [
            "13F <value> 字段 2023-01-03 前为千美元、之后为美元，本文件已统一换算为美元。",
            "期权按标的名义市值披露，非权利金；is_option=true 者必须与股票分列，不同表排序。",
            "13F 仅含多头 13F 证券：不含空头、现金、债券、外国交易所上市股票。",
            "季末快照，季中建仓再清仓不可见，换手率被系统性低估。",
            "浓仓位阈值取该管理人自身历史 top1 分布的 80% 分位，非固定 15%。",
            "同一报告期有原件与修订(13F-HR/A)时取修订件——修订件存在即说明原件有错。",
        ],
        "quarters": quarters,
        "changes": changes,
    }
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n写出 {OUT_FILE}：{len(quarters)}/{len(selected)} 个报告期，{len(changes)} 组变动")
    if skipped:
        print(f"⚠ 跳过 {len(skipped)} 期，已落库到 skipped 字段：")
        for sk in skipped:
            print(f"    {sk['report_date']}  {sk['reason']}")
    if conc_threshold is not None:
        print(f"浓仓位阈值（历史 top1 的 80% 分位）= {conc_threshold*100:.1f}%")


if __name__ == "__main__":
    main()
