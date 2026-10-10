import random, statistics as st, math
random.seed(7)
def tri(lo,mode,hi): return random.triangular(lo,hi,mode)
GZ_ZH_ROOMS = 3000 + (1888+2000+730+1250)   # 广州 长隆酒店1500+熊猫1500；珠海 横琴湾/企鹅/马戏/海洋科学(飞船)
QY_ROOMS = 1253
D26, QY25 = 212, 188   # 2026 1-7月天数；清远 2025-01-25 试营业起至 7/31
def central():
    rn = GZ_ZH_ROOMS*D26*.75 + 0; q = QY_ROOMS*D26*.55
    return (rn*.70*.25*1600 + q*.70*.25*1200)/1e8
lv, yo = [], []
for _ in range(200000):
    occ=tri(.65,.75,.85); occq=tri(.40,.55,.70); pk=tri(.60,.70,.80); ct=tri(.15,.25,.35)
    asp=tri(1300,1600,2000); aspq=tri(950,1200,1500)
    v26 = GZ_ZH_ROOMS*D26*occ*pk*ct*asp + QY_ROOMS*D26*occq*pk*ct*aspq
    lv.append(v26/1e8)
    # YoY：同口径增长因子（不由两个水平值相减，避免噪声）
    demand=tri(.00,.06,.12)           # 长隆需求/房价综合增长
    share=tri(-.10,-.03,.03)          # 携程在长隆渠道份额相对变化（反垄断调查 1 月、罚单 7/25）
    qy_share = QY_ROOMS*occq*aspq/(GZ_ZH_ROOMS*occ*asp+QY_ROOMS*occq*aspq)
    base = (1-qy_share) + qy_share*QY25/D26   # 2025 清远只有 188 天
    yo.append(((1+demand)*(1+share))/base - 1)
q=lambda a,p: sorted(a)[int(p*len(a))]
print("中心测算 %.2f 亿元"%central())
print("水平 P10/P50/P90: %.2f / %.2f / %.2f 亿元"%(q(lv,.1),q(lv,.5),q(lv,.9)))
print("YoY  P10/P50/P90: %+.1f%% / %+.1f%% / %+.1f%%"%(100*q(yo,.1),100*q(yo,.5),100*q(yo,.9)))
print("2025 同期隐含 P50: %.2f 亿元"%(q(lv,.5)/(1+q(yo,.5))))
print("房晚(中心):", round(GZ_ZH_ROOMS*D26*.75+QY_ROOMS*D26*.55), "携程套餐房晚:", round((GZ_ZH_ROOMS*D26*.75+QY_ROOMS*D26*.55)*.7*.25))
