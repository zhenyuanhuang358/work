#!/usr/bin/env python3
"""今日尾部灯色裁定（tail-risk-monitor Step 2–3 的机械部分）

为什么（2026-11-05 重跑问题 6）：灯色一直靠会话手算——取前一日收盘要翻 git 历史、常驻项要数近 20 日档位，
同一天两次扫描读数不同（VIX 23.6 → 26.5），手算易错。阈值、共振、加速度全部复用 rule_replay.py（与 SKILL.md 同步，
它有 DRIFT 检查），本脚本只补两件 rule_replay 不做的事：
  1. 常驻项剔除：近 20 个交易日 >80% 非绿档的指标降为观察项，不计共振（SKILL.md 2026-09-15 条）
  2. 用「最新一条读数」对「前一交易日收盘」算今日加速度，输出今日裁定
用法：python3 tools/tail_light.py          （先触发抓价，读工作分支最新 stock_prices.json）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rule_replay as rr  # noqa: E402

NAMES = {0: "🟢 绿灯", 1: "🟡 黄灯", 2: "🔴 红灯"}


def compute(rows, cur):
    """rows = rule_replay.load_history() 的历史读数；cur = 当前 stock_prices.json。返回裁定 dict（不打印，可测试）。"""
    t = cur.get("tail_risk") or {}
    now = {"ts": cur.get("updated_at", ""), "vix": cur.get("vix"), "vix3m": t.get("vix3m"), "skew": t.get("skew"),
           "vvix": t.get("vvix")}
    now["term_structure"] = now["vix"] / now["vix3m"] if now["vix"] and now["vix3m"] else None
    days = [d for d in rr.daily_closes(rows) if d["ts"][:10] < now["ts"][:10]]  # 前几个交易日收盘
    hist = days[-rr.RESIDENT_WINDOW:]
    resident, scores = [], {}
    for m in rr.SCORED:
        bands = [rr.band_of(m, d.get(m)) for d in hist if d.get(m) is not None]
        ng = sum(1 for b in bands if b and b >= 1) / len(bands) if bands else 0
        if ng > rr.RESIDENT_THRESHOLD:
            resident.append((m, round(ng, 3)))
        scores[m] = rr.band_of(m, now.get(m))
    res_names = {m for m, _ in resident}
    counted = {m: s for m, s in scores.items() if s is not None and m not in res_names}
    non_green = [m for m, s in counted.items() if s >= 1]
    base = max(counted[m] for m in non_green) if len(non_green) >= rr.RESONANCE_MIN else 0
    accel = []
    for lag, thr, tag in ((1, rr.ACCEL_1D, "单日"), (3, rr.ACCEL_3D, "3 日")):
        if len(days) >= lag:
            ref = days[-lag]
            for m in rr.SCORED:
                a, b = ref.get(m), now.get(m)
                if a and b and b / a - 1 > thr:
                    accel.append(f"{m} {tag} +{b / a - 1:.0%}")
    light = min(2, base + (1 if accel else 0))
    prem = now["vix3m"] / now["vix"] if now["vix"] and now["vix3m"] else None
    return {"asof": now["ts"], "ref_day": days[-1]["ts"][:10] if days else None, "readings": {m: now.get(m) for m in rr.SCORED},
            "scores": scores, "resident": resident, "non_green": non_green, "base": base, "accel": accel,
            "light": light, "light_name": NAMES[light], "term_premium": prem,
            "long_band_open": bool(prem and prem >= 1.20),
            "missing": [m for m in ("vix", "vix3m", "skew", "vvix") if now.get(m) is None]}


def main():
    rows = rr.load_history()
    if not rows:
        sys.exit("没有 tail_risk 历史（浅克隆？git fetch --unshallow）")
    r = compute(rows, json.load(open(os.path.join(rr.REPO, "stock_prices.json"))))
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
        return
    print(f"读数时间 {r['asof']}｜对比收盘日 {r['ref_day'] or '无'}")
    res_names = {m for m, _ in r["resident"]}
    for m in rr.SCORED:
        tag = "（常驻项，不计共振）" if m in res_names else ""
        print(f"  {m:15} {r['readings'][m]!s:>8}  档位 {r['scores'][m]}{tag}")
    for m, ng in r["resident"]:
        print(f"  ⚠ {m} 已降为观察项（近 {rr.RESIDENT_WINDOW} 日 {ng:.0%} 非绿档）")
    print(f"共振 {len(r['non_green'])} 项 {r['non_green']} → 基础灯 {NAMES[r['base']]}")
    print(f"加速度（只算上行）：{r['accel'] or '无'}" + ("→ 上调一级" if r["accel"] else ""))
    prem = r["term_premium"]
    print(f"裁定：{r['light_name']}｜期限溢价 VIX3M/VIX {prem:.3f}" if prem else f"裁定：{r['light_name']}｜期限溢价 缺数据",
          "→ 30–45 天档" + ("开" if r["long_band_open"] else "关（只做 20–29 天，option_quote 加 --dte-max 29）"))
    if r["missing"]:
        print("⚠ 有指标缺失：按 SKILL 原则 5 降低裁定置信度，报告里写明")


if __name__ == "__main__":
    main()
