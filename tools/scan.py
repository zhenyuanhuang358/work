#!/usr/bin/env python3
"""期权日常扫描统一入口（2026-11-06 改造：把流水线里确定性的步骤从「会话手工拼」变成一条命令）

为什么：11/05 四次扫描，问题集中在会话手工拼接——等错了数据（链到了价格没到）、灯色手算、逐只调 120 次、
主因被闸门盖住、HOOD 靠手工否决、报告里的数字与工具对不上没人查。确定性的部分全部在这里做完并落盘，
会话只负责两件需要判断的事：新闻标注（读标题判断鹰鸽 / 利好利空）和写结论；写完用 verify 机器核对。

子命令：
  fetch                    写触发文件 → commit → push → 等本批六份产物 → merge
  fetch --trigger <批次>   接收 GitHub 连接器已触发的批次，只读取远端，快进临时副本
  fetch --trigger <批次> --bp <可取现金>  在临时副本接收并扫描，底稿写回原工作区
  fetch --git-fallback --bp <可取现金>  在临时副本通过已授权 Git 推送触发，再接收同批数据
  run  --bp <可取现金>     灯色 + 事件闸门 + P/C 全清单筛选 + 跳空压力 + 新闻素材 → memory/state/scans/<id>.json + <id>.draft.md
  verify <报告.md> [--scan <id>.json]   报告与 scan.json 逐项核对（tools/verify_scan.py），结果写回 scan.json

产物 memory/state/scans/<id>.json 是本次扫描的「事实底稿」：报告里的每个数字都应能在这里找到。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
BRANCH = "claude/install-claude-hud-d51E6"
YELLOW_DTE, YELLOW_RISK = 21, 0.025  # 黄灯：到期 ≤ 3 周；单笔最大跳空亏损 ≤ 净值 2.5%（regime-playbook，用户 11/10 定）
ARTIFACTS = ["options_chain.json", "stock_prices.json", "news.json", "fed_speak.json", "macro_actuals.json", "voices.json"]
SCANS = os.path.join(REPO, "memory", "state", "scans")
# position-discipline 第 4 条「事件压力」（增发 / 大股东减持 / 指引下调 / 监管处罚）的标题初筛——只标 ⚠ 交人工判断，不自动否决
PRESSURE_RE = re.compile(r"offering|secondary|dilut|insider sell|stake sale|sells? .*stake|cuts? (?:guidance|outlook|forecast)|"
                         r"lowers? (?:guidance|outlook|forecast)|downgrade|SEC (?:probe|charges)|investigation|fine[sd]? ", re.I)
RATE_SECTORS = {"债券", "银行", "金融科技", "公用事业"}  # news-channels：美联储讲话偏鹰 / 偏鸽直接作用的板块
EVENT_RE = re.compile(r"Non-Farm|CPI|PPI|FOMC|Federal Funds|Fed Chair .* Testifies", re.I)
FOMC_MINUTES_RE = re.compile(r"\bFOMC\b.*\bminutes\b|\bminutes\b.*\bFOMC\b", re.I)
ET = ZoneInfo("America/New_York")


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year, month, weekday):
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def easter_sunday(year):
    """Gregorian Easter (Anonymous Gregorian algorithm), used only for NYSE Good Friday."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f, g = (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def observed(day):
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def market_holidays(year):
    return {
        observed(date(year, 1, 1)): "New Year's Day",
        nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        easter_sunday(year) - timedelta(days=2): "Good Friday",
        last_weekday(year, 5, 0): "Memorial Day",
        observed(date(year, 6, 19)): "Juneteenth",
        observed(date(year, 7, 4)): "Independence Day",
        nth_weekday(year, 9, 0, 1): "Labor Day",
        nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
        observed(date(year, 12, 25)): "Christmas Day",
    }


def market_session(now):
    et = now.astimezone(ET)
    if et.weekday() >= 5:
        return {"pass": False, "status": "CLOSED_WEEKEND", "reason": "美股周末休市", "time_et": et.isoformat()}
    holiday = market_holidays(et.year).get(et.date())
    if holiday:
        return {"pass": False, "status": "CLOSED_HOLIDAY", "reason": f"美股休市：{holiday}", "time_et": et.isoformat()}
    current = et.time().replace(tzinfo=None)
    if current < clock_time(9, 30):
        return {"pass": False, "status": "PREMARKET", "reason": "美股尚未开盘", "time_et": et.isoformat()}
    if current > clock_time(16, 0):
        return {"pass": False, "status": "AFTER_HOURS", "reason": "美股已收盘", "time_et": et.isoformat()}
    return {"pass": True, "status": "OPEN", "reason": "美股常规交易时段", "time_et": et.isoformat()}


def sh(*cmd, check=True, timeout=None, cwd=REPO):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"命令超时（{timeout}s）：{' '.join(cmd)}") from None
    if check and r.returncode:
        raise SystemExit(f"命令失败：{' '.join(cmd)}\n{r.stderr[-500:]}")
    return r.stdout


def remote_trigger(path, commit, repo):
    out = sh("git", "show", f"{commit}:{path}", check=False, cwd=repo)
    try:
        data = json.loads(out)
        return data.get("trigger") if isinstance(data, dict) else None
    except ValueError:
        return None


def remote_artifact_evidence(commit, repo):
    return {
        path: {
            "blob_sha": sh("git", "rev-parse", f"{commit}:{path}", cwd=repo).strip(),
            "trigger": remote_trigger(path, commit, repo),
        }
        for path in ARTIFACTS
    }


def cmd_fetch(a):
    import options_state as state

    receipt_dir = os.path.abspath(a.out) if a.out else SCANS
    receipt_path = os.path.join(receipt_dir, f"{a.run_id}.fetch.json") if a.run_id else None
    reserved = state.reserve_fetch(receipt_path, a.run_id) if receipt_path else None
    if reserved and a.trigger and reserved["trigger"] != a.trigger:
        raise SystemExit(f"run_id {a.run_id} 已预留批次 {reserved['trigger']}，拒绝接收另一批 {a.trigger}")
    if a.git_fallback:
        requested = reserved["trigger"] if reserved else None
        commit, evidence = scan_external_batch(requested, a.timeout, a.bp, a.out, run_id=a.run_id, create_trigger=True)
        if receipt_path:
            state.complete_fetch(receipt_path, trigger=requested, commit=commit, artifacts=evidence)
        return
    if a.trigger:
        if a.bp is None:
            commit = await_batch(a.trigger, a.timeout)
            evidence = remote_artifact_evidence(commit, REPO)
            sh("git", "merge", "-q", "--ff-only", commit)
        else:
            commit, evidence = scan_external_batch(a.trigger, a.timeout, a.bp, a.out, run_id=a.run_id)
        if receipt_path:
            state.complete_fetch(receipt_path, trigger=a.trigger, commit=commit, artifacts=evidence)
        return

    try:
        sh("git", "fetch", "-q", "origin", BRANCH, timeout=20)
    except SystemExit as exc:
        raise SystemExit(f"GitHub 工作分支访问预检失败。尚未写入扫描触发文件。\n{exc}") from None
    try:
        sh("git", "push", "--dry-run", "origin", f"FETCH_HEAD:refs/heads/{BRANCH}", timeout=20)
    except SystemExit as exc:
        raise SystemExit(f"GitHub 推送预检失败。尚未写入扫描触发文件。Codex 请用连接器触发后传入 --trigger。\n{exc}") from None

    trig = reserved["trigger"] if reserved else f"scan-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    with open(os.path.join(REPO, "price_fetch_trigger.txt"), "w") as f:
        f.write(trig + "\n")
    sh("git", "commit", "-qm", f"chore: trigger scan fetch {trig}", "--", "price_fetch_trigger.txt")
    for i in range(5):  # Actions 并发提交会让推送被拒：fetch+merge 后重试
        sh("git", "fetch", "-q", "origin", BRANCH)
        sh("git", "merge", "-q", "--no-edit", "FETCH_HEAD")
        if subprocess.run(["git", "push", "-q", "origin", BRANCH], cwd=REPO).returncode == 0:
            break
        time.sleep(2 ** (i + 1))
    else:
        raise SystemExit("推送触发失败 5 次")
    commit = await_batch(trig, a.timeout)
    evidence = remote_artifact_evidence(commit, REPO)
    sh("git", "merge", "-q", "--no-edit", commit)
    if receipt_path:
        state.complete_fetch(receipt_path, trigger=trig, commit=commit, artifacts=evidence)


def scan_external_batch(trig, timeout, bp, out, *, run_id=None, create_trigger=False):
    origin = sh("git", "remote", "get-url", "origin").strip()
    output = os.path.abspath(out) if out else SCANS
    # 保留完整历史供尾部风险灯计算，避免在用户的检出目录合并远端产物。
    with tempfile.TemporaryDirectory(prefix="options-scan-") as directory:
        repo = os.path.join(directory, "work")
        sh("git", "clone", "--quiet", "--shared", "--single-branch", "--branch", BRANCH, REPO, repo, timeout=45)
        sh("git", "remote", "set-url", "origin", origin, cwd=repo)
        if create_trigger or trig is None:
            sh("git", "fetch", "-q", "origin", BRANCH, cwd=repo, timeout=20)
            sh("git", "switch", "-q", "-C", BRANCH, "FETCH_HEAD", cwd=repo)
            trig = trig or f"scan-{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
            trigger_path = os.path.join(repo, "price_fetch_trigger.txt")
            with open(trigger_path, encoding="utf-8") as file:
                active = file.read().strip()
            if active == trig:
                print(f"远端已是批次 {trig}，复用而不重复触发", flush=True)
            else:
                with open(trigger_path, "w", encoding="utf-8") as f:
                    f.write(trig + "\n")
                sh("git", "add", "--", "price_fetch_trigger.txt", cwd=repo)
                sh("git", "commit", "-qm", f"Trigger options scan {trig}", cwd=repo)
                print(f"Git 备用取数批次：{trig}", flush=True)
                try:
                    sh("git", "push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=repo, timeout=30)
                except SystemExit as exc:
                    raise SystemExit(f"{exc}\n请回读远端触发文件确认写入状态，避免重复触发。") from None
        commit = await_batch(trig, timeout, repo=repo)
        sh("git", "switch", "-q", "-C", BRANCH, commit, cwd=repo)
        local_script = os.path.join(repo, "tools", "scan.py")
        shutil.copyfile(__file__, local_script)
        shutil.copyfile(os.path.join(HERE, "options_state.py"), os.path.join(repo, "tools", "options_state.py"))
        command = [sys.executable, local_script, "run", "--bp", str(bp), "--out", output]
        if run_id:
            command += ["--run-id", run_id]
        result = subprocess.run(command, cwd=repo)
        if result.returncode:
            raise SystemExit(result.returncode)
        return commit, remote_artifact_evidence(commit, repo)


def cmd_reserve(a):
    import options_state as state

    directory = os.path.abspath(a.out) if a.out else SCANS
    path = os.path.join(directory, f"{a.run_id}.fetch.json")
    receipt = state.reserve_fetch(path, a.run_id)
    print(json.dumps({"run_id": receipt["run_id"], "trigger": receipt["trigger"],
                      "status": receipt["status"], "receipt": path}, ensure_ascii=False))


def await_batch(trig, timeout, *, repo=REPO):
    started = time.monotonic()
    deadline = started + timeout
    last_progress = started
    pending = ARTIFACTS
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SystemExit(f"等待批次 {trig} 超时（{timeout}s），未就绪：{', '.join(pending)}")
        sh("git", "fetch", "-q", "origin", BRANCH, timeout=min(30, remaining), cwd=repo)
        # 固定到一次 fetch 的提交，避免其它 Git 操作更新 FETCH_HEAD 后混入不同批次。
        commit = sh("git", "rev-parse", "FETCH_HEAD", cwd=repo).strip()
        active = sh("git", "show", f"{commit}:price_fetch_trigger.txt", cwd=repo).strip()
        if active != trig:
            raise SystemExit(f"远端当前批次为 {active}，与要求的 {trig} 不同。请核对连接器提交或更新后的批次。")
        pending = [path for path in ARTIFACTS if remote_trigger(path, commit, repo) != trig]
        if not pending:
            break
        now = time.monotonic()
        if now - last_progress >= 30:
            print(f"等待批次 {trig}：已用时 {now - started:.0f}s，未就绪 {', '.join(pending)}", flush=True)
            last_progress = now
        time.sleep(max(0, min(15, deadline - time.monotonic())))
    print(f"{len(ARTIFACTS)} 份产物就绪（trigger {trig}），用时 {time.monotonic() - started:.0f}s", flush=True)
    return commit


def next_trading_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def cmd_run(a):
    """为一次扫描建立可恢复运行记录，再调用原有确定性分析。"""
    import options_state as state

    now = datetime.fromisoformat(a.asof).replace(tzinfo=timezone.utc) if a.asof else datetime.now(timezone.utc)
    run_id = a.run_id or now.strftime("%Y-%m-%d_%H%MZ")
    output = os.path.abspath(a.out) if a.out else SCANS
    os.makedirs(output, exist_ok=True)
    manifest_path = os.path.join(output, f"{run_id}.manifest.json")
    trigger_path = os.path.join(os.path.abspath(a.root) if a.root else REPO, "price_fetch_trigger.txt")
    trigger = None
    if os.path.exists(trigger_path):
        with open(trigger_path, encoding="utf-8") as file:
            trigger = file.read().strip() or None
    manifest = state.create_or_load_manifest(manifest_path, run_id, asof=now.isoformat(timespec="seconds"), trigger=trigger)
    scan_path = os.path.join(output, f"{run_id}.json")
    draft_path = os.path.join(output, f"{run_id}.draft.md")
    if not getattr(a, "force", False) and manifest["stage"] in {"DRAFTED", "VERIFIED", "DELIVERED"} \
            and os.path.exists(scan_path) and os.path.exists(draft_path):
        print(f"复用已完成运行：{run_id}｜阶段 {manifest['stage']}｜未重复扫描", flush=True)
        return
    state.transition(manifest_path, "ANALYZING", detail="开始确定性期权扫描")
    print(f"运行 {run_id}：开始分析；状态记录 {manifest_path}", flush=True)
    try:
        _cmd_run(a, run_id=run_id, manifest_path=manifest_path)
    except BaseException as exc:
        state.transition(manifest_path, "FAILED_ANALYSIS", detail=f"{type(exc).__name__}: {exc}")
        raise


def _cmd_run(a, *, run_id, manifest_path):
    import option_quote as oq
    import gap_stress as gs
    import tail_light as tl
    import rule_replay as rr
    import options_state as state

    for k in ("history", "out"):  # 先转绝对路径再切目录（11/06 试跑：相对路径在 --root 下找不到）
        if getattr(a, k):
            setattr(a, k, os.path.abspath(getattr(a, k)))
    os.chdir(REPO if not a.root else a.root)
    now = datetime.fromisoformat(a.asof).replace(tzinfo=timezone.utc) if a.asof else datetime.now(timezone.utc)
    oq.NOW = now if a.asof else None
    def load(path):
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    chain, prices = load("options_chain.json"), load("stock_prices.json")
    news = load("news.json") if os.path.exists("news.json") else {}
    screen = load("memory/state/options-screen.json") if os.path.exists("memory/state/options-screen.json") else {}
    fed = load("fed_speak.json") if os.path.exists("fed_speak.json") else {}
    macro = load("macro_actuals.json") if os.path.exists("macro_actuals.json") else {}
    voices = load("voices.json") if os.path.exists("voices.json") else {}
    if os.path.exists("price_fetch_trigger.txt"):
        with open("price_fetch_trigger.txt", encoding="utf-8") as file:
            trig = file.read().strip()
    else:
        trig = None

    # 1 新鲜度：六份产物必须属于同一次触发；缺任何一份都保守阻断。
    artifact_data = (("options_chain.json", chain), ("stock_prices.json", prices), ("news.json", news),
                     ("fed_speak.json", fed), ("macro_actuals.json", macro), ("voices.json", voices))
    fresh = {}
    for path, data in artifact_data:
        fresh[path] = {
            "trigger_ok": (data.get("trigger") == trig) if data else False,
            "updated_at": data.get("updated_at") if data else None,
            "sha256": state.sha256_file(path) if os.path.exists(path) else None,
        }
    qts = [r.get("quote_time_utc") for r in chain["tickers"].values() if r.get("quote_time_utc")]
    newest = max(qts) if qts else chain["updated_at"][:19].replace("T", " ")
    age = (now - datetime.fromisoformat(newest.replace(" ", "T")).replace(tzinfo=timezone.utc)).total_seconds() / 60
    fresh["quote_age_min"] = round(age, 1)
    fresh["ok"] = all(v["trigger_ok"] for k, v in fresh.items() if isinstance(v, dict)) and age <= a.max_age

    # 2 灯色
    light = tl.compute(rr.load_history() if not a.history else load(a.history), prices)

    # 3 事件闸门：下一个交易日有高影响美国数据 / FOMC → 今日不新开
    session = market_session(now)
    today = now.astimezone(ET).date()
    ntd = next_trading_day(today)
    fed_events = [e for e in fed.get("usd_high", []) if EVENT_RE.search(e["title"])]
    reminders = [e for e in fed_events if FOMC_MINUTES_RE.search(e["title"])]
    events = [e for e in fed_events if not FOMC_MINUTES_RE.search(e["title"])]
    cal_ev = oq.macro_events()  # 统一日历补 FF 周历只看两周的盲区（持有期 20–45 天）
    events += [{"time": d + "T08:30:00-05:00", "title": f"{n}（macro_calendar）"} for d, n in cal_ev.items()
               if not any(e["time"][:10] == d for e in events)]
    eve = [e for e in events if e["time"][:10] == ntd.isoformat()]
    can_open = light["light"] < 2 and not eve and fresh["ok"] and session["pass"]
    why_not = ([f"尾部灯 {light['light_name']}"] if light["light"] >= 2 else []) + \
              ([f"明日（{ntd}）{'、'.join(sorted({e['title'] for e in eve}))}，事件前一交易日不新开"] if eve else []) + \
              ([session["reason"]] if not session["pass"] else []) + \
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
            x["stop_alert"] = gs.stop_alert(x["right"], x["spot"], x["strike"], x["t"], x["iv"], x["bid"])
            x["assign_1"] = round(x["strike"] * 100)  # R5 接货金额（每张）：只提示，profile 1.1t
            x["pressure"] = [n.get("headline") for n in news.get("tickers", {}).get(x["ticker"], [])
                             if PRESSURE_RE.search(n.get("headline") or "")]
            tn = news.get("tickers", {}).get(x["ticker"], [])[:3]
            if screen.get("sectors", {}).get(x["ticker"]) in RATE_SECTORS and fed.get("headlines"):
                x["fed_channel"] = fed["headlines"][0]["headline"]  # 11/05 回放：TLT 的个股新闻全是无关长文，真相关的是联储讲话
            x["news"] = [{k: n.get(k) for k in ("time_utc", "source", "headline")} for n in tn]
        # 黄灯缩量（tail-risk regime-playbook；用户 11/10 定：取消「只做熟标的」，保留两条）：
        # 到期 ≤ 3 周，且最大跳空亏损（一年最差 / ±5% 等压力情景取最大）≤ 净值 2.5%（净值按可取现金）。
        # 11/10 午盘：草稿写「可以开」并列 21 行，全靠会话手工再筛——规则写在 skill 里、工具不执行。
        if light["light"] == 1:
            cap = YELLOW_RISK * a.bp
            keep, cut = [], []
            for x in res["ok"]:
                dte = (date.fromisoformat(x["expiry"]) - today).days
                worst = max(g["loss"] for g in x["gap"])
                (keep if dte <= YELLOW_DTE and worst <= cap else cut).append(x)
                x["yellow"] = {"dte": dte, "worst_loss": worst, "cap": cap}
            res["ok"], res["yellow_cut"] = keep, [(x["ticker"], x["expiry"], x["strike"], x["yellow"]) for x in cut]
        sides[right] = res

    scale = sh("python3", os.path.join(HERE, "scale_check.py"), "report", check=False).strip().splitlines()[:1]
    # 当天（美东）已公布的高影响数据：实际值必须进报告（11/06 用户：「非农这么重要，怎么可以抓不到就算了」）
    names = {"payrolls": "非农就业", "unrate": "失业率", "ahe": "平均时薪", "cpi": "CPI", "core_cpi": "核心 CPI", "ppi": "PPI"}
    macro_today = [{"key": k, "name": names[k], **v} for k, v in macro.get("indicators", {}).items()
                   if (v.get("release_et") or "")[:10] == today.isoformat()]
    released_today = [e for e in events if e["time"][:10] == today.isoformat()]
    if released_today and not macro_today:
        why_not.append("今日有高影响数据公布但 macro_actuals.json 没拿到实际值——先查 errors，补齐再出报告")
        can_open = False
    sid = run_id
    positions_path = os.path.join(os.getcwd(), "memory", "state", "current_positions.json")
    positions = state.inspect_positions(positions_path, now=now)
    market_gate = {
        "pass": can_open,
        "status": "PASS" if can_open else "BLOCK",
        "reasons": list(why_not),
    }
    gates = {
        "data": {"pass": fresh["ok"], "status": "PASS" if fresh["ok"] else "BLOCK",
                 "quote_age_min": fresh["quote_age_min"]},
        "market": market_gate,
        "position": {"pass": positions["pass"], "status": positions["status"], "reason": positions["reason"]},
        "report": {"pass": False, "status": "PENDING", "reason": "报告尚未运行 verify"},
    }
    out = {"id": sid, "run_id": sid, "asof": now.isoformat(timespec="seconds"), "trigger": trig,
           "bp": a.bp, "freshness": fresh, "market_session": session, "light": light,
           "events_next": [e for e in events + reminders if today.isoformat() <= e["time"][:10] <= (today + timedelta(days=7)).isoformat()],
           "event_eve": eve, "macro_today": macro_today, "macro_source": macro.get("source"),
           "macro_errors": macro.get("errors"), "can_open": can_open, "why_not": why_not, "scale": scale,
           "fed": {"schedule": fed.get("schedule", []), "headlines": fed.get("headlines", [])[:8], "errors": fed.get("errors")},
           "market_news": news.get("market", [])[:8],
           "voices": [{"name": p["name"], "role": p["role"], "sectors": p["sectors"], "headline": h["headline"], "source": h["source"],
                       "time_utc": h["time_utc"]} for p in voices.get("people", []) for h in p["headlines"][:1]],
           "positions": positions, "gates": gates, "delivery_status": "DRAFT_ONLY", "actionable": False,
           "run_manifest": manifest_path, "sides": sides, "verification": None}
    od = a.out or SCANS
    os.makedirs(od, exist_ok=True)
    jp = os.path.join(od, f"{sid}.json")
    # 11/10：用 --asof 复盘 11/09 时同 id 覆盖了当天的正式底稿（事后改了当天记录）。底稿是当日事实，已存在就拒绝覆盖。
    if os.path.exists(jp) and not getattr(a, "force", False):
        sys.exit(f"拒绝覆盖：{jp} 已存在（当日正式底稿）。复盘请用 --out 指向别的目录；确需重写加 --force")
    state.atomic_write_json(jp, out)
    draft_path = os.path.join(od, f"{sid}.draft.md")
    draft_text = draft(out, gs)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-options-", suffix=".md", dir=od)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(draft_text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, draft_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    state.transition(manifest_path, "ANALYZED", artifacts={"scan": {"path": jp, "sha256": state.sha256_file(jp)}})
    state.transition(manifest_path, "DRAFTED", artifacts={"draft": {"path": draft_path, "sha256": state.sha256_file(draft_path)}})
    print(f"scan 底稿：{jp}｜草稿：{sid}.draft.md")
    print(f"可开仓：{can_open}  {'；'.join(why_not)}")
    for r_, res in sides.items():
        print(f"  {r_}：过关 {len(res['ok'])} 行｜" + "、".join(f"{x['ticker']} {x['expiry']} {x['strike']:g}{r_}" for x in res["ok"][:6]))


def draft(s, gs):
    """报告草稿：确定性部分填好；需要判断的地方留 【待判断】，会话改写后另存为 <id>.md 再跑 verify。"""
    L = []
    if s["can_open"] and s.get("positions", {}).get("pass"):
        concl = "市场门禁已通过；候选仍须完成报告验证和券商平台复核"
    elif s["can_open"]:
        concl = "市场筛选有候选，但持仓未确认；暂不提供开仓张数"
    else:
        concl = "今天不开新仓：" + "；".join(s["why_not"])
    L += [f"结论：{concl}",
          f"运行编号：{s.get('run_id') or s.get('id')}｜数据时点：{s.get('asof')}｜交易时段：{s.get('market_session', {}).get('status', 'UNKNOWN')}｜状态：DRAFT_ONLY",
          "", "## 今日消息面"]
    for event in s["events_next"]:
        if FOMC_MINUTES_RE.search(event["title"]):
            L.append(f"- {event['time']} · {event['title']}（风险提醒）")
    for m in s.get("macro_today", []):
        L.append(f"- 【{m['name']}】{m['month']} 实际 {m['actual']:g}{m['unit']}，预期 {m.get('forecast') or '—'}"
                 + (f"，差 {m['surprise']:+g}" if m.get("surprise") is not None else "")
                 + f"（{s.get('macro_source')}）→ 【待判断：对利率 / 板块的含义】")
    seen = set()
    for h in [h for h in s["fed"]["headlines"] if not (h["headline"] in seen or seen.add(h["headline"]))][:4]:  # 同一篇多人命中只列一次
        L.append(f"- {h['time_utc']} · {h['source']} · {h['headline']} → 【待判断：鹰/鸽、影响板块】")
    for v in s.get("voices", [])[:4]:  # 政要与知名投资人（fetch_voices.py）：每人最新一条
        L.append(f"- {v['time_utc']} · {v['source']} · 【{v['role']} {v['name']}】{v['headline']} → 【待判断：是否本人表态、影响{v['sectors']}】")
    for n in s["market_news"][:3]:
        L.append(f"- {n['time_utc']} · {n['source']} · {n['headline']} → 【待判断】")
    position = s.get("positions") or {}
    L += ["", "## 当前持仓",
          f"- 状态：{position.get('status', 'MISSING')}｜更新时间：{position.get('as_of') or '未提供'}｜{position.get('reason') or ''}"]
    for item in position.get("positions") or []:
        L.append(f"- {item.get('ticker', 'UNKNOWN')} {item.get('expiry', '')} {item.get('strike', '')}{item.get('right', '')} × {item.get('contracts', '?')}")
    L += ["", "## 公司关键数据发布",
          "- 【待判断：查持仓与拟推荐标的官方日历至到期日的月度运营、产销交付、交易量、净入金及业务更新；列美东/北京时间、盘前盘后、来源与确认状态，并同步相关 📰 行。未找到写未核实。】"]
    L += ["", "## 候选" + ("" if s["can_open"] else "（今日不开，供下个可开仓日参考）")]
    cut = [c for r_ in ("P", "C") for c in s["sides"][r_].get("yellow_cut", [])]
    if s["light"]["light"] == 1:
        L.append(f"- 🟡 黄灯缩量：只留到期 ≤ {YELLOW_DTE} 天、最大跳空亏损 ≤ 净值 {YELLOW_RISK:.1%}（${YELLOW_RISK * s['bp']:.0f}）的合约；"
                 f"另有 {len(cut)} 张过关但超限，已剔除（底稿 yellow_cut）。")
    for r_, res in s["sides"].items():
        for x in res["ok"]:
            # 11/06 用户反馈：「79P」看不出买卖与看涨看跌 → 每行先写动作与亏损方向，代码放后面
            act = (f"卖出 {x['ticker']} {x['strike']:g} put（看跌），{x['expiry'][5:].replace('-', '/')} 到期，正股下跌时承压"
                   if r_ == "P" else
                   f"卖出 {x['ticker']} {x['strike']:g} call（看涨），{x['expiry'][5:].replace('-', '/')} 到期，正股上涨时承压")
            L.append(f"- **{act}**（现价 {x['spot']:.2f}）")
            L.append(f"  代码 {x['ticker']} {x['expiry']} {x['strike']:g}{r_}｜收入 ${x['income']:.0f}/张｜保证金 ${x['margin']:.0f}"
                     f"｜z {x['z']:.2f}｜报价差 {x['spread']:.0%}{'｜' + x['mark'][1:] if len(x['mark']) > 1 else ''}")
            L.append(f"  财报/关键事件：{x.get('earnings_check') or '未核实'}"
                     + (f"｜事件压力：{'；'.join(x['pressure'][:2])}" if x.get("pressure") else "｜新闻压力初筛未命中"))
            L.append(f"  止损亏损 1/3/6 张：${x['stop_loss_1_3_6'][0]} / ${x['stop_loss_1_3_6'][1]} / ${x['stop_loss_1_3_6'][2]}"
                     + (f"｜接货 ${x['assign_1']:,}/张（只提示）" if r_ == "P" else f"｜被行权需按 ${x['strike']:g} 交付股票（未持股即卖空，只提示）"))
            al = x.get("stop_alert")
            if al:
                # 11/11 USO 120P：IV +10 个点时提醒价 = 现价，说明光 IV 上升就会触发止损 → 提醒价改用 IV 不变那档，另起一行警示
                iv_only = abs(al[1] - x["spot"]) / x["spot"] < 0.005
                alert = al[0] if iv_only else al[1]
                L.append(f"  止损（第 8 条，平台无期权条件单）：正股提醒设 ${alert:.2f}"
                         + (f"（IV 不变时期权到 2× 收入）" if iv_only else f"（IV +10 个点时期权到 2× 收入；IV 不变约 ${al[0]:.2f}）")
                         + f"，触发后手动看卖价 ≥ {2 * x['bid']:.2f} 即买回｜止盈：挂限价买回 {0.5 * x['bid']:.2f}")
                if iv_only:
                    L.append(f"  ⚠ IV 再升 10 个点，现价不动也会触及止损——股价提醒管不住这种情形，要盯期权价")
            if x["pressure"]:
                L.append("  ⚠ 事件压力初筛命中（第 4 条，人工判断是否只观察）")
            L.append(f"  跳空：{gs.fmt(x['gap'])}")
            nh = "；".join(f"{n['headline']}（{n['source']} {n['time_utc']}）" for n in x["news"][:2])
            if x.get("fed_channel"):
                nh = f"利率敏感板块，联储讲话：{x['fed_channel']}" + ("；个股：" + nh if nh else "")
            L.append(f"  📰 {nh + ' → 【待判断：不利/有利/中性】' if nh else '无'}")
    from collections import Counter as _C
    secs = _C(x["ticker"] for res in s["sides"].values() for x in res["ok"])
    for t, n in secs.items():
        if n > 1:
            L.append(f"- 注意：{t} 有 {n} 张过关合约，但行业分散（第 16 条）同时只能开 1 笔——挑一张")
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
    f.add_argument("--trigger", help="接收连接器已触发的批次（只从 GitHub 读取，建议使用干净副本）")
    f.add_argument("--git-fallback", action="store_true", help="在临时副本用现有 Git 授权触发并扫描")
    f.add_argument("--bp", type=float, help="与 --trigger 或 --git-fallback 同用，输入可取现金")
    f.add_argument("--out", help="与 --trigger、--bp 同用，指定底稿目录")
    f.add_argument("--run-id", help="先用 reserve 生成；重复执行时复用同一批次和运行记录")
    reserve = sub.add_parser("reserve", help="为一次连接器取数生成稳定 run_id/trigger，重复调用不会生成新批次")
    reserve.add_argument("--run-id", required=True)
    reserve.add_argument("--out", help="取数回执目录（默认 memory/state/scans）")
    r = sub.add_parser("run")
    r.add_argument("--bp", type=float, required=True, help="平台可取现金（不是最大购买力）")
    r.add_argument("--z-min", type=float, default=1.2)
    r.add_argument("--max-age", type=float, default=20)
    r.add_argument("--asof", help="固定时刻（回归测试 / 复盘）")
    r.add_argument("--root", help="数据目录（回归测试用固定样例目录）")
    r.add_argument("--history", help="tail_risk 历史 JSON（不读 git，回归测试用）")
    r.add_argument("--out", help="产物目录（默认 memory/state/scans）")
    r.add_argument("--force", action="store_true", help="允许覆盖同 id 的已有底稿（默认拒绝）")
    r.add_argument("--run-id", help="稳定运行编号；与 reserve/fetch 共用以支持断点恢复")
    v = sub.add_parser("verify")
    v.add_argument("report")
    v.add_argument("--scan")
    a = ap.parse_args()
    if a.cmd == "reserve":
        cmd_reserve(a)
    elif a.cmd == "fetch":
        if a.git_fallback and (a.trigger or a.bp is None):
            f.error("--git-fallback 需要 --bp，且不能同时指定 --trigger")
        if (a.bp is not None and not (a.trigger or a.git_fallback)) or (a.out and a.bp is None):
            f.error("--bp 需要 --trigger 或 --git-fallback，--out 需要 --bp")
        cmd_fetch(a)
    elif a.cmd == "run":
        cmd_run(a)
    else:
        import verify_scan
        sys.exit(verify_scan.run(a.report, a.scan))


if __name__ == "__main__":
    main()
