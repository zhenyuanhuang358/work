import json,statistics as st
def load(t): return json.load(open(f"history/{t}.json"))["rows"]
def tr_series(rows, keep=1.0):
    """总回报净值：分红按 keep 比例到手后当日收盘再投。"""
    v, out = 1.0, []
    prev=None
    for r in rows:
        if prev is not None:
            v *= (r["c"] + r["div"]*keep) / prev
        out.append((r["d"], v)); prev = r["c"]
    return out
def maxdd(series):
    peak, pd_, worst = -1, None, (0,None,None,None)
    for d,v in series:
        if v>peak: peak, pd_ = v, d
        dd=v/peak-1
        if dd<worst[0]: worst=(dd,pd_,d,None)
    # 回本日
    rec=None
    for d,v in series:
        if d>worst[2] and v>=[x for dd_,x in series if dd_==worst[1]][0]: rec=d; break
    return worst[0],worst[1],worst[2],rec
def window(series,a,b):
    s=[v for d,v in series if a<=d<=b]; return s[-1]/s[0]-1, min(s)/s[0]-1 if s else None
def ann(series):
    y=(len(series)-1)/252; return (series[-1][1]/series[0][1])**(1/y)-1
R={t:load(t) for t in ("spyi","spy","jepi")}
start=max(R[t][0]["d"] for t in R); 
for t in R: R[t]=[r for r in R[t] if r["d"]>=start]
print("区间",start,"→",R["spyi"][-1]["d"],"交易日",len(R["spyi"]))
for t in R:
    px=[(r["d"],r["c"]) for r in R[t]]; tr=tr_series(R[t])
    d1=maxdd(px); d2=maxdd(tr)
    rets=[tr[i][1]/tr[i-1][1]-1 for i in range(1,len(tr))]
    print(f"{t.upper():5} 年化总回报 {ann(tr):.1%}｜价格年化 {ann(px):.1%}｜波动率 {st.pstdev(rets)*252**.5:.1%}｜最大回撤(总回报) {d2[0]:.1%} {d2[1]}→{d2[2]} 回本 {d2[3]}｜最大回撤(价格) {d1[0]:.1%} {d1[1]}→{d1[2]} 回本 {d1[3]}")
# 各次下跌段：SPY 回撤超过 8% 的区间里 SPYI 跌多少
spy=tr_series(R["spy"]); spyi=tr_series(R["spyi"]); jepi=tr_series(R["jepi"])
eps=[]; peak=-1;pd_=None;trough=None;low=0
for d,v in spy:
    if v>peak:
        if low<=-0.08: eps.append((pd_,trough,low))
        peak,pd_,low,trough=v,d,0,None
    elif v/peak-1<low: low,trough=v/peak-1,d
if low<=-0.08: eps.append((pd_,trough,low))
print("SPY 回撤 ≥8% 的区间：")
for a,b,l in eps:
    f=lambda s:[v for d,v in s if d==b][0]/[v for d,v in s if d==a][0]-1
    print(f"  {a}→{b} SPY {l:.1%}｜SPYI {f(spyi):.1%}（承受 {f(spyi)/l:.0%}）｜JEPI {f(jepi):.1%}")
# 月度上/下行捕获
def monthly(s):
    m={}
    for d,v in s: m[d[:7]]=v
    k=sorted(m); return {k[i]:m[k[i]]/m[k[i-1]]-1 for i in range(1,len(k))}
ms,mi=monthly(spy),monthly(spyi)
up=[k for k in ms if ms[k]>0]; dn=[k for k in ms if ms[k]<0]
print(f"月度：上涨月 {len(up)} 个，SPYI 平均涨 {st.mean(mi[k] for k in up):.2%} vs SPY {st.mean(ms[k] for k in up):.2%}（捕获 {sum(mi[k] for k in up)/sum(ms[k] for k in up):.0%}）；下跌月 {len(dn)} 个，SPYI {st.mean(mi[k] for k in dn):.2%} vs SPY {st.mean(ms[k] for k in dn):.2%}（捕获 {sum(mi[k] for k in dn)/sum(ms[k] for k in dn):.0%}）")
# 税后情景
last=R["spyi"][-1]; one=[r for r in R["spyi"] if r["d"]>"2025-11-10"]
div12=sum(r["div"] for r in one); print(f"近 12 个月分配 ${div12:.4f}，现价 {last['c']}，分配率 {div12/last['c']:.2%}")
for name,keep in (("不预扣",1.0),("预扣 10%（中美税收协定股息税率）",0.9),("预扣 30%（无协定默认）",0.7)):
    tr=tr_series(R["spyi"],keep); tr1=tr_series(one,keep)
    print(f"  {name}：成立以来年化 {ann(tr):.1%}｜近 12 个月 {tr1[-1][1]/tr1[0][1]-1:.1%}｜到手分配率 {div12*keep/last['c']:.2%}｜$5,469 一年到手现金 ${5469*div12*keep/last['c']:.0f}")
# 只花分配、不再投：价格本金变化
px=[(r["d"],r["c"]) for r in R["spyi"]]; print(f"不再投：价格 {px[0][1]} → {px[-1][1]}（{px[-1][1]/px[0][1]-1:+.1%}），累计分配 ${sum(r['div'] for r in R['spyi']):.2f}/股")
