import sys, math, datetime as dt
sys.path.insert(0, '/home/user/work/tools')
import put_backtest as pb
dates, days = pb.load()
def spot_on(t, d):
    ds = [x for x in dates if x <= d and t in days[x]['prices']]
    return days[ds[-1]]['prices'][t]['price'] if ds and ds[-1] == d else None
def iv_from(px, S, K, T):
    lo, hi = 0.01, 5.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if pb.put(S, K, m, T) < px else (lo, m)
    return (lo + hi) / 2
# 名称, 标的, 行权, 到期, 开仓日, 开仓股价(None=取缓存), 收入, 原张数, 原实际盈亏, 有据可查的过滤理由
T = [
 ('PLTR 110P','PLTR',110,'2026-07-24','2026-06-24',None,2.13,1,166,None),
 ('SPCX 130P','SPCX',130,'2026-07-24','2026-06-22',None,3.05,1,-304,None),
 ('GOOGL 290P','GOOGL',290,'2026-08-21','2026-07-23',330.76,2.75,1,206,None),
 ('VRT 200P','VRT',200,'2026-08-21','2026-07-30',223.04,5.40,1,405,None),
 ('HOOD 80P','HOOD',80,'2026-09-04','2026-08-04',None,2.81,1,211,None),
 ('UBER 62P','UBER',62,'2026-09-11','2026-08-06',None,0.50,6,258,None),
 ('INTC 85P','INTC',85,'2026-09-18','2026-08-12',None,2.26,2,376,None),
 ('HOOD 82P','HOOD',82,'2026-09-25','2026-08-14',None,2.00,2,305,None),
 ('NVDA 190P','NVDA',190,'2026-10-02','2026-08-26',None,3.00,1,220,'财报 8/27 在持有期内'),
 ('SGI 55P','SGI',55,'2026-10-16','2026-08-31',None,0.77,3,89,None),
 ('GM 79P','GM',79,'2026-10-09','2026-09-10',None,0.96,4,-448,None),
 ('INTC 104P','INTC',104,'2026-10-16','2026-10-01',None,0.81,5,-5150,'刚宣布 150 亿增发（事件压力）'),
 ('UBER 63P','UBER',63,'2026-10-30','2026-10-21',None,0.18,5,89,'报价差 58%'),
 ('XLE 63P','XLE',63,'2026-11-13','2026-11-02',None,0.18,6,-288,'报价差 14%'),
 ('AMD 442.5P','AMD',442.5,'2026-11-13','2026-11-04',None,4.00,1,-375,'报价差 12.5%；CPI 前高估值成长股'),
]
rows = []
for name,t,K,exp,entry,S0,cr,n,act,why in T:
    S = S0 or spot_on(t, entry)
    if S is None:
        rows.append((name,act,n,None,None,'无价格数据，保留原结果',act,act)); continue
    T0 = (dt.date.fromisoformat(exp)-dt.date.fromisoformat(entry)).days/365
    iv = iv_from(cr, S, K, T0); hv = pb.hv(dates, days, t, entry)
    ratio = iv/hv if hv else None
    e = dt.date.fromisoformat(exp); res=None; how=None
    for d in [x for x in dates if entry < x <= exp and t in days[x]['prices']]:
        q = days[d]['prices'][t]; Tr = max((e-dt.date.fromisoformat(d)).days,0)/365
        lo, hi = q.get('low') or q['price'], q.get('high') or q['price']
        if pb.put(lo, K, iv, Tr) >= 2*cr: res, how = -cr, f'止损 {d}'; break
        if pb.put(hi, K, iv, Tr) <= 0.5*cr: res, how = 0.5*cr, f'止盈 {d}'; break
    after = [x for x in dates if entry < x <= exp and t in days[x]['prices']]
    if res is None and not after:  # 开仓后没有任何价格数据：用真实结局（按 1 张折算）
        sim = round(act / n); flt = why or (f'IV/HV {ratio:.2f} < 1.1' if ratio and ratio < 1.1 else None)
        rows.append((name,act,n,ratio,'无后续数据，用真实结局',flt or '通过',sim,0 if flt else sim)); continue
    if res is None:
        last = [x for x in dates if x <= exp and t in days[x]['prices']][-1]
        px = days[last]['prices'][t]['price']
        res, how = cr - max(K-px,0), ('到期' if last == exp else f'持有中（{last}）')
    sim = round(res*100)
    flt = why or (f'IV/HV {ratio:.2f} < 1.1' if ratio and ratio < 1.1 else None)
    new = 0 if flt else sim
    rows.append((name,act,n,ratio,how,flt or '通过',sim,new))
print(f"{'交易':<12}{'原张数':>4}{'原实际':>8}{'IV/HV':>7}  {'新规则 1 张怎么走':<22}{'1 张结果':>8}  {'过滤':<26}{'新规则最终':>8}")
for name,act,n,ratio,how,flt,sim,new in rows:
    print(f"{name:<12}{n:>4}{act:>+8}{(f'{ratio:.2f}' if ratio else '—'):>7}  {(how or '—'):<22}{sim:>+8}  {flt:<26}{new:>+8}")
A=sum(r[1] for r in rows); S1=sum(r[6] for r in rows); N=sum(r[7] for r in rows)
print(f"\n合计：原实际 {A:+}｜新规则 1 张（不过滤）{S1:+}｜新规则（1 张 + 过滤）{N:+}")
print('最大单笔亏损：原',min(r[1] for r in rows),'｜新',min(r[7] for r in rows))
print('亏损合计：原',sum(r[1] for r in rows if r[1]<0),'｜新',sum(r[7] for r in rows if r[7]<0))
w=[r[7] for r in rows if r[7]!=0]; print('新规则实际做的笔数',len(w),'｜赚钱',sum(1 for x in w if x>0))
