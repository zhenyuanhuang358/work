"""Decision Mode 计算底稿：报告数字必须来自 calc.json。输入均取自 2026 中报（金额百万元）。"""
import json
out={}
# 门店
self_2025y, self_2026h1 = 1304, 1290; franch_2025y, franch_2026h1 = 79, 99
out["store_change"]={"self": self_2026h1-self_2025y, "franchise": franch_2026h1-franch_2025y,
                     "total": (self_2026h1+franch_2026h1)-(self_2025y+franch_2025y)}
# 利润率
core_2026, rev_2026 = 2513.5, 22336.9; core_2025, rev_2025 = 2408.1, 20703.3
out["margin"]={"2026h1": round(core_2026/rev_2026*100,2), "2025h1": round(core_2025/rev_2025*100,2),
               "delta_pct": round((core_2026/rev_2026-core_2025/rev_2025)*100,2)}
# 七项成本（金额，百万元）
cost={"staff":(7093.3,6988.0),"materials":(9289.2,8243.5),"rent":(224.8,216.2),"dep":(907.9,1155.9),
      "other":(1510.1,1086.9),"utilities":(728.5,700.6),"travel":(126.2,109.6)}
s26=sum(v[0] for v in cost.values()); s25=sum(v[1] for v in cost.values())
out["cost_total"]={"2026_m":round(s26,1),"2025_m":round(s25,1),"2026_pct":round(s26/rev_2026*100,2),
                   "2025_pct":round(s25/rev_2025*100,2),"delta_pct":round((s26/rev_2026-s25/rev_2025)*100,2)}
out["cost_items_pct"]={k:{"2026":round(v[0]/rev_2026*100,1),"2025":round(v[1]/rev_2025*100,1)} for k,v in cost.items()}
# 其他收益及亏损
out["other_gains"]={"2026_m":-96.5,"2025_m":235.0,"delta_m":-331.5,"pct_of_2026_rev":round(-331.5/rev_2026*100,2)}
# 门店情景（推演假设）
base=1383
out["store_scenarios"]={"2026_low":round(base*1.03),"2026_high":round(base*1.07),
                        "2027_low":round(base*1.03*1.08),"2027_high":round(base*1.07*1.12),
                        "assumption":"2026 中单位数 3–7%、2027 加快 8–12%，非公司指引"}
# 大排档情景（2026 年底 40–60 店；2027 40–90 店；单店年收入 1,000 万=H1 500 万×2）
out["dapaidang"]={str(n):{"revenue_yi":round(n*1000/10000,1),"share_of_annual_rev_pct":round(n*1000/10000/447*100,2)} for n in (40,60,90)}
out["dapaidang_delta"]={"stores_2026":"40-60","stores_2027":"40-90","delta_stores":"-20 至 +30",
                        "delta_rev_yi":"-2.0 至 +5.0","note":"配对极值：40→40=0；60→90=+30 家（+3 亿）；区间未配对时 -2 至 +5 亿"}
out["annual_rev_2026_assumption_yi"]=447
json.dump(out,open('memory/state/research/haidilao_2027_dd/calc.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False,indent=1))
