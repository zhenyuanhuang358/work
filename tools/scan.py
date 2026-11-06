#!/usr/bin/env python3
"""期权日常扫描统一入口（2026-11-06 改造：把流水线里确定性的步骤从「会话手工拼」变成一条命令）

为什么：11/05 四次扫描，问题集中在会话手工拼接——等错了数据（链到了价格没到）、灯色手算、逐只调 120 次、
主因被闸门盖住、HOOD 靠手工否决、报告里的数字与工具对不上没人查。确定性的部分全部在这里做完并落盘，
会话只负责两件需要判断的事：新闻标注（读标题判断鹰鸽 / 利好利空）和写结论；写完用 verify 机器核对。

子命令：
  fetch                    写触发文件 → commit → push → 等 链 / 价格 / 新闻 / 美联储讲话 四份产物的 trigger 都等于本次 → merge
  run  --bp <可取现金>     灯色 + 事件闸门 + P/C 全清单筛选 + 跳空压力 + 新闻素材 → memory/state/scans/<id>.json + <id>.draft.md
  verify <报告.md> [--scan <id>.json]   报告与 scan.json 逐项核对（tools/verify_scan.py），结果写回 scan.json

产物 memory/state/scans/<id>.json 是本次扫描的「事实底稿」：报告里的每个数字都应能在这里找到。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
BRANCH = "claude/install-claude-hud-d51E6"
ARTIFACTS = ["options_chain.json", "stock_prices.json", "news.json", "fed_speak.json"]
SCANS = os.path.join(REPO, "memory", "state", "scans")
# position-discipline 第 4 条「事件压力」（增发 / 大股东减持 / 指引下调 / 监管处罚）的标题初筛——只标 ⚠ 交人工判断，不自动否决
PRESSURE_RE = re.compile(r"offering|secondary|dilut|insider sell|stake sale|sells? .*stake|cuts? (?:guidance|outlook|forecast)|"
                         r"lowers? (?:guidance|outlook|forecast)|downgrade|SEC (?:probe|charges)|investigation|fine[sd]? ", re.I)
EVENT_RE = re.compile(r"Non-Farm|CPI|PPI|FOMC|Federal Funds|Fed Chair .* Testifies", re.I)


def sh(*cmd, check=True):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"命令失败：{' '.join(cmd)}\n{r.stderr[-500:]}")
    return r.stdout


def remote_trigger(path):
    out = subprocess.run(["git", "show", f"FETCH_HEAD:{path}"], cwd=REPO, capture_output=True, text=True).stdout
    try:
        return json.loads(out).get("trigger")
    except ValueError:
        return None


def cmd_fetch(a):
    trig = f"scan-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    with open(os.path.join(REPO, "price_fetch_trigger.txt"), "w") as f:
        f.write(trig + "\n")
    sh("git", "add", "price_fetch_trigger.txt")
    sh("git", "commit", "-qm", f"chore: trigger scan fetch {trig}")
    for i in range(5):  # Actions 并发提交会让推送被拒：fetch+merge 后重试
        sh("git", "fetch", "-q", "origin", BRANCH)
        sh("git", "merge", "-q", "--no-edit", "FETCH_HEAD")
        if subprocess.run(["git", "push", "-q", "origin", BRANCH], cwd=REPO).returncode == 0:
            break
        time.sleep(2 ** (i + 1))
    else:
        raise SystemExit("推送触发失败 5 次")
    t0 = time.time()
    while True:
        sh("git", "fetch", "-q", "origin", BRANCH)
        got = {p: remote_trigger(p) == trig for p in ARTIFACTS}
        if all(got.values()):
            break
        if time.time() - t0 > a.timeout:
            raise SystemExit(f"等待超时 {a.timeout}s，未就绪：{[p for p, ok in got.items() if not ok]}")
        time.sleep(15)
    sh("git", "merge", "-q", "--no-edit", "FETCH_HEAD")
    print(f"四份产物就绪（trigger {trig}），用时 {time.time() - t0:.0f}s")


def next_trading_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def cmd_run(a):
    import option_quote as oq
    import gap_stress as gs
    import tail_light as tl
    import rule_replay as rr

    for k in ("history", "out"):  # 先转绝对路径再切目录（11/06 试跑：相对路径在 --root 下找不到）
        if getattr(a, k):
            setattr(a, k, os.path.abspath(getattr(a, k)))
    os.chdir(REPO if not a.root else a.root)
    now = datetime.fromisoformat(a.asof).replace(tzinfo=timezone.utc) if a.asof else datetime.now(timezone.utc)
    oq.NOW = now if a.asof else None
    load = lambda p: json.load(open(p))  # noqa: E731
    chain, prices = load("options_chain.json"), load("stock_prices.json")
    news = load("news.json") if os.path.exists("news.json") else {}
    fed = load("fed_speak.json") if os.path.exists("fed_speak.json") else {}
    trig = open("price_fetch_trigger.txt").read().strip() if os.path.exists("price_fetch_trigger.txt") else None

    # 1 新鲜度：四份产物是不是同一次触发、报价多老
    fresh = {p: {"trigger_ok": (d.get("trigger") == trig) if d else False, "updated_at": d.get("updated_at") if d else None}
             for p, d in (("options_chain.json", chain), ("stock_prices.json", prices), ("news.json", news),
                          ("fed_speak.json", fed))}
    qts = [r.get("quote_time_utc") for r in chain["tickers"].values() if r.get("quote_time_utc")]
    newest = max(qts) if qts else chain["updated_at"][:19].replace("T", " ")
    age = (now - datetime.fromisoformat(newest.replace(" ", "T")).replace(tzinfo=timezone.utc)).total_seconds() / 60
    fresh["quote_age_min"] = round(age, 1)
    fresh["ok"] = all(v["trigger_ok"] for k, v in fresh.items() if isinstance(v, dict)) and age <= a.max_age

    # 2 灯色
    light = tl.compute(rr.load_history() if not a.history else load(a.history), prices)

    # 3 事件闸门：下一个交易日有高影响美国数据 / FOMC → 今日不新开
    today = now.astimezone(timezone(timedelta(hours=-5))).date()
    ntd = next_trading_day(today)
    events = [e for e in fed.get("usd_high", []) if EVENT_RE.search(e["title"])]
    eve = [e for e in events if e["time"][:10] == ntd.isoformat()]
    can_open = light["light"] < 2 and not eve and fresh["ok"]
    why_not = ([f"尾部灯 {light['light_name']}"] if light["light"] >= 2 else []) + \
              ([f"明日（{ntd}）{'、'.join(sorted({e['title'] for e in eve}))}，事件前一交易日不新开"] if eve else []) + \
              ([f"数据不新鲜：" + "、".join([f"{k} 不是本次触发" for k, v in fresh.items() if isinstance(v, dict) and not v["trigger_ok"]]
                                       + ([f"报价已 {age:.0f} 分钟（上限 {a.max_age:g}）"] if age > a.max_age else []))]
               if not fresh["ok"] else [])

    # 4 全清单筛选（P / C），30–45 天档按期限溢价
    sides = {}
    for right in ("P", "C"):
        ns = argparse.Namespace(right=right, bp=a.bp, z_min=a.z_min, max_age=a.max_age if not a.asof else 10 ** 9,
                                dte_max=None if light["long_band_open"] else 29, strikes=None, json=False)
        res = oq.collect(ns, chain)
        for x in res["ok"]:
            x["gap"] = gs.stress(x["right"], x["spot"], x["strike"], x["t"], x["iv"], x["bid"], x["hv30"], x["move"])
            x["stop_loss_1_3_6"] = [round(x["bid"] * 100 * n) for n in (1, 3, 6)]  # 2× 止损成交 = 亏 1× 收入 × 张数
            x["assign_1"] = round(x["strike"] * 100)  # R5 接货金额（每张）：只提示，profile 1.1t
            x["pressure"] = [n.get("headline") for n in news.get("tickers", {}).get(x["ticker"], [])
                             if PRESSURE_RE.search(n.get("headline") or "")]
            tn = news.get("tickers", {}).get(x["ticker"], [])[:3]
            x["news"] = [{k: n.get(k) for k in ("time_utc", "source", "headline")} for n in tn]
        sides[right] = res

    scale = sh("python3", os.path.join(HERE, "scale_check.py"), "report", check=False).strip().splitlines()[:1]
    sid = now.strftime("%Y-%m-%d_%H%MZ")
    out = {"id": sid, "asof": now.isoformat(timespec="seconds"), "bp": a.bp, "freshness": fresh, "light": light,
           "events_next": [e for e in events if today.isoformat() <= e["time"][:10] <= (today + timedelta(days=7)).isoformat()],
           "event_eve": eve, "can_open": can_open, "why_not": why_not, "scale": scale,
           "fed": {"schedule": fed.get("schedule", []), "headlines": fed.get("headlines", [])[:8], "errors": fed.get("errors")},
           "market_news": news.get("market", [])[:8], "sides": sides, "verification": None}
    od = a.out or SCANS
    os.makedirs(od, exist_ok=True)
    jp = os.path.join(od, f"{sid}.json")
    json.dump(out, open(jp, "w"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(od, f"{sid}.draft.md"), "w").write(draft(out, gs))
    print(f"scan 底稿：{jp}｜草稿：{sid}.draft.md")
    print(f"可开仓：{can_open}  {'；'.join(why_not)}")
    for r_, res in sides.items():
        print(f"  {r_}：过关 {len(res['ok'])} 行｜" + "、".join(f"{x['ticker']} {x['expiry']} {x['strike']:g}{r_}" for x in res["ok"][:6]))


def draft(s, gs):
    """报告草稿：确定性部分填好；需要判断的地方留 【待判断】，会话改写后另存为 <id>.md 再跑 verify。"""
    L = []
    concl = "今天可以开新仓（见候选）" if s["can_open"] else "今天不开新仓：" + "；".join(s["why_not"])
    L += [f"结论：{concl}", "", "## 今日消息面"]
    seen = set()
    for h in [h for h in s["fed"]["headlines"] if not (h["headline"] in seen or seen.add(h["headline"]))][:4]:  # 同一篇多人命中只列一次
        L.append(f"- {h['time_utc']} · {h['source']} · {h['headline']} → 【待判断：鹰/鸽、影响板块】")
    for n in s["market_news"][:3]:
        L.append(f"- {n['time_utc']} · {n['source']} · {n['headline']} → 【待判断】")
    L += ["", "## 候选" + ("" if s["can_open"] else "（今日不开，供下个可开仓日参考）")]
    for r_, res in s["sides"].items():
        for x in res["ok"]:
            L.append(f"- {x['ticker']} {x['expiry']} {x['strike']:g}{r_}｜收入 ${x['income']:.0f}/张｜保证金 ${x['margin']:.0f}"
                     f"｜z {x['z']:.2f}｜报价差 {x['spread']:.0%}{'｜' + x['mark'][1:] if len(x['mark']) > 1 else ''}")
            L.append(f"  止损亏损 1/3/6 张：${x['stop_loss_1_3_6'][0]} / ${x['stop_loss_1_3_6'][1]} / ${x['stop_loss_1_3_6'][2]}"
                     f"｜接货 ${x['assign_1']:,}/张（只提示）")
            if x["pressure"]:
                L.append(f"  ⚠ 事件压力初筛命中（第 4 条，人工判断是否只观察）：{'；'.join(x['pressure'][:2])}")
            L.append(f"  跳空：{gs.fmt(x['gap'])}")
            nh = "；".join(f"{n['headline']}（{n['source']} {n['time_utc']}）" for n in x["news"][:2])
            L.append(f"  📰 {nh + ' → 【待判断：不利/有利/中性】' if nh else '无'}")
    if not any(res["ok"] for res in s["sides"].values()):
        from collections import Counter
        for r_, res in s["sides"].items():
            c = Counter(res["main_cause"].values()).most_common()
            L.append(f"- {r_} 侧无过关合约。各标的主因计数：" + "、".join(f"{k} {v} 只" for k, v in c))
    L += ["", "## 请在平台核实", f"- 可取现金（本次按 ${s['bp']:,.0f}）", "- 下单前在平台预览保证金与报价"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--timeout", type=int, default=900)
    r = sub.add_parser("run")
    r.add_argument("--bp", type=float, required=True, help="平台可取现金（不是最大购买力）")
    r.add_argument("--z-min", type=float, default=1.2)
    r.add_argument("--max-age", type=float, default=20)
    r.add_argument("--asof", help="固定时刻（回归测试 / 复盘）")
    r.add_argument("--root", help="数据目录（回归测试用固定样例目录）")
    r.add_argument("--history", help="tail_risk 历史 JSON（不读 git，回归测试用）")
    r.add_argument("--out", help="产物目录（默认 memory/state/scans）")
    v = sub.add_parser("verify")
    v.add_argument("report")
    v.add_argument("--scan")
    a = ap.parse_args()
    if a.cmd == "fetch":
        cmd_fetch(a)
    elif a.cmd == "run":
        cmd_run(a)
    else:
        import verify_scan
        sys.exit(verify_scan.run(a.report, a.scan))


if __name__ == "__main__":
    main()
