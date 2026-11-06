#!/usr/bin/env python3
"""筛选器产物不变量检查（2026-11-06 改造推广到第二档：burry / sleeper）

为什么：burry_screener / ses_screener 在 Actions 上跑、结果被期权基本面名单与研究引用，但「输出对不对」没有任何程序检查。
profile 1.1u 的事故（一个吞掉的异常让 37 天数据静默变成 0 天）说明：筛选器最危险的不是算错，是悄悄算空、算偏。
这里只用产物里已存的原始量重算派生指标、核对计数与阈值——不联网、不依赖 SEC 缓存，Actions 跑完后与 self_check 都能跑。

用法：python3 tools/screen_check.py [burry_screen.json] [ses_screen.json] [--json]
退出码：0 = 无 FAIL。
"""
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def close(a, b, rel=1e-6):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=rel, abs_tol=1e-9)


def check_burry(d):
    res = []

    def chk(cid, level, name, ok, ev=""):
        res.append({"id": cid, "level": level, "check": name, "pass": bool(ok), "evidence": ev})

    s = d["sample"]
    chk("B1", "FAIL", "样本计数闭合：完整 + 缺失 + 不适用 = 全集", s["complete"] + s["missing_data"] + s["not_applicable"] == s["universe"],
        f"{s['complete']}+{s['missing_data']}+{s['not_applicable']} vs {s['universe']}")
    mr = s["missing_data"] / max(s["complete"] + s["missing_data"], 1)  # 口径：缺失 /（完整 + 缺失），「不适用」不算覆盖问题
    chk("B2", "FAIL", "缺失率 = 缺失 /（完整 + 缺失）与记录一致，且 >30% 时有警告（F11 分位数样本偏差）",
        close(mr, s["missing_ratio"], 1e-3) and (mr <= 0.3 or any("缺失率" in w for w in d["warnings"])), f"缺失率 {mr:.1%}")
    chk("B3", "FAIL", "结果非空（防静默算空，profile 1.1u）", len(d["results"]) > 0 and s["stage_a_survivors"] > 0,
        f"results {len(d['results'])}，Stage A 幸存 {s['stage_a_survivors']}")
    bad_derived, bad_thr, impossible = [], [], []
    th = d["thresholds"]
    for r in d["results"]:
        t = r.get("ticker") or r["cik"]
        if r.get("price") and r.get("shares"):
            if not close(r["mktcap"], r["price"] * r["shares"], 1e-4):
                bad_derived.append(f"{t} 市值")
            if not close(r["ev"], r["mktcap"] + r["net_debt"], 1e-4):
                bad_derived.append(f"{t} EV")
            if r.get("ev_ebitda") is not None and not close(r["ev_ebitda"], r["ev"] / r["ebitda"], 1e-4):
                bad_derived.append(f"{t} EV/EBITDA")
            # burry 口径 FCF ÷ EV（screener 第 536 行）；注意 watch_fundamentals 的同名字段是 FCF ÷ 市值，口径不同
            if r.get("fcf_yield") is not None and not close(r["fcf_yield"], r["fcf"] / r["ev"], 1e-4):
                bad_derived.append(f"{t} FCF 收益率")
            if r.get("pb") is not None and not close(r["pb"], r["mktcap"] / r["equity"], 1e-4):
                bad_derived.append(f"{t} P/B")
        if not close(r["net_debt_ebitda"], r["net_debt"] / r["ebitda"], 1e-6):
            bad_derived.append(f"{t} 净负债/EBITDA")
        if r["ebitda"] <= 0 or r["equity"] <= 0 or r["revenue"] <= 0 or r["shares"] <= 0:
            impossible.append(f"{t} 非正分母进了完整组")
        if r.get("sbc_ratio") is not None and not (0 <= r["sbc_ratio"] < 1):
            impossible.append(f"{t} SBC 占营收 {r['sbc_ratio']:.2f}")
        if r.get("passed") is True:  # 声称通过的必须真满足两条预登记阈值
            if r["net_debt_ebitda"] > th["net_debt_ebitda_cut"] + 1e-12:
                bad_thr.append(f"{t} 净负债/EBITDA {r['net_debt_ebitda']:.2f} > {th['net_debt_ebitda_cut']:.2f}")
            if r.get("sbc_ratio") is not None and r["sbc_ratio"] > th["sbc_ratio_cut"] + 1e-12:
                bad_thr.append(f"{t} SBC {r['sbc_ratio']:.3f} > {th['sbc_ratio_cut']:.3f}")
    chk("B4", "FAIL", "派生指标可由原始量重算（市值 / EV / 倍数 / 收益率）", not bad_derived, bad_derived[:5])
    chk("B5", "FAIL", "标为通过的确实满足预登记阈值", not bad_thr, bad_thr[:5])
    chk("B6", "FAIL", "无不可能值（非正分母、SBC ≥ 100%）", not impossible, impossible[:5])
    no_t = [r["cik"] for r in d["results"] if not r.get("ticker")]
    chk("B7", "WARN", "结果都有 ticker（无 ticker 无法取价、无法交易）", not no_t, no_t[:5])
    return res


def check_ses(d):
    res = []

    def chk(cid, level, name, ok, ev=""):
        res.append({"id": cid, "level": level, "check": name, "pass": bool(ok), "evidence": ev})

    rs = d.get("results", [])
    chk("S1", "FAIL", "结果非空", len(rs) > 0, f"{len(rs)} 条")
    bad_gm, bad_win, bad_flag = [], [], []
    for r in rs:
        sg = r.get("signals") or {}
        ser = sg.get("gross_margin_series") or []
        if any(not (-1 < v < 1) for _, v in ser):
            bad_gm.append(r["ticker"])
        if sg.get("window_years") and abs(sg["window_years"] - d["window_years"]) > 0.6:
            bad_win.append(f"{r['ticker']} {sg['window_years']}")
        if r.get("flag") not in ("绿", "黄", "红", "灰", "—", "⚑分部", "抓取失败", None):
            bad_flag.append(f"{r['ticker']} {r.get('flag')}")
    chk("S2", "FAIL", "毛利率序列在 (−100%, 100%) 内（防单位 / 口径错）", not bad_gm, bad_gm)
    chk("S3", "FAIL", "每家窗口长度与配置一致（F10 基期污染防线：窗口不能悄悄变短）", not bad_win, bad_win)
    chk("S4", "FAIL", "判别旗标在允许集合内", not bad_flag, bad_flag)
    failed = [r["ticker"] for r in rs if r.get("flag") == "抓取失败"]
    chk("S6", "WARN", "无抓取失败的标的", not failed, failed)
    no_reason = [r["ticker"] for r in rs if not r.get("reason") and r.get("flag") != "抓取失败"]
    chk("S5", "WARN", "每条判别都写了理由", not no_reason, no_reason)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    bp = args[0] if args else os.path.join(REPO, "burry_screen.json")
    sp = args[1] if len(args) > 1 else os.path.join(REPO, "ses_screen.json")
    out = {}
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    for name, p, fn in (("burry", bp, check_burry), ("ses", sp, check_ses)):
        if (only is None or only == name) and os.path.exists(p):
            out[name] = fn(json.load(open(p, encoding="utf-8")))
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for name, rs in out.items():
            print(f"== {name}")
            for c in rs:
                m = "✅" if c["pass"] else ("❌" if c["level"] == "FAIL" else "⚠️")
                print(f"  {m} {c['id']} {c['check']}" + ("" if c["pass"] else f"｜{c['evidence']}"))
    fails = [c for rs in out.values() for c in rs if not c["pass"] and c["level"] == "FAIL"]
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
