"""绿茶 UE/增长计算（输入取自 2025 年报金额与 2026H1 媒体口径）。"""
import json
rev25, rev26h1 = 4762967.0, 2674754.0
stores25, stores26h1 = 609, 733
out={}
out["revenue_per_store_2025_wan"]=round(rev25/1000/stores25,1)
out["revenue_per_store_2026h1_wan"]=round(rev26h1/1000/stores26h1,1)
out["revenue_per_store_annualized_2026_wan"]=round(rev26h1/1000/stores26h1*2,1)
out["store_growth_pct"]=round((stores26h1/stores25-1)*100,1)
out["rev_growth_2026h1_pct"]=16.8
cost={"raw":1508430,"staff":1242539,"rent_rou_dep":242298,"dep_other":238873,"util":169764,"delivery":202707,"other":464564}
out["cost_ratio_2025_pct"]={k:round(v/rev25*100,2) for k,v in cost.items()}
eat=1203970.0
out["delivery_share_2025_pct"]=round(eat/rev25*100,1)
out["delivery_share_2026h1_pct"]=24.3
out["ue_sanity"]={"capex_wan":[210,350],"payback_m":12.5,"implied_annual_cash_wan":[round(c/(12.5/12),1) for c in (210,350)]}
out["store_scenarios_2027"]={"2026_new_200":609+200,"2027_new_213":733+69+213,"if_2026_160":609+160,"if_2027_180":609+160+180}
json.dump(out,open('memory/state/research/greentea_2026_dd/calc.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False,indent=1))
