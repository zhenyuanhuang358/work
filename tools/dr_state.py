#!/usr/bin/env python3
"""Decision Mode 状态机与门禁（Merlin 客户调研）。

用法：
  python3 tools/dr_state.py init <task> --decision "..."      # 初始化 state.json
  python3 tools/dr_state.py gate <task> frame --confirm        # G0
  python3 tools/dr_state.py gate <task> source                 # G1
  python3 tools/dr_state.py gate <task> triangulate            # G2
  python3 tools/dr_state.py gate <task> redteam                # G3
  python3 tools/dr_state.py gate <task> synthesize             # G4/G5
  python3 tools/dr_state.py status <task>
退出码 0 通过，1 有缺口。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.join("memory", "state", "research")


def paths(task):
    d = os.path.join(ROOT, task)
    return d, os.path.join(d, "state.json")


def load_state(task):
    d, sp = paths(task)
    if not os.path.exists(sp):
        sys.exit(f"缺 {sp}，先 init")
    return json.load(open(sp, encoding="utf-8")), d


def save_state(task, st):
    _, sp = paths(task)
    json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def jload(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def gate(task, phase, confirm=False):
    st, d = load_state(task)
    gaps, notes = [], []

    if phase == "frame":
        h = jload(os.path.join(d, "hypotheses.json"))
        if not h:
            gaps.append("缺 hypotheses.json")
        else:
            st["decision"] = h.get("decision", st.get("decision", ""))
            hs = h.get("hypotheses", [])
            if not hs:
                gaps.append("hypotheses 为空")
            for x in hs:
                if not str(x.get("statement", "")).strip():
                    gaps.append(f"{x.get('id')} 缺 statement")
                if not str(x.get("falsifier", "")).strip():
                    gaps.append(f"{x.get('id')} 缺 falsifier（证伪条件）")
                if not x.get("evidence_needed"):
                    gaps.append(f"{x.get('id')} 缺 evidence_needed")
        if confirm:
            st["decision_confirmed"] = True
        if not st.get("decision_confirmed"):
            gaps.append("决策未确认：补 --confirm")
        st["phase"] = "source"
        notes.append(f"假设 {len(h.get('hypotheses', [])) if h else 0} 条")

    elif phase == "source":
        ev = [json.loads(l) for l in open(os.path.join(d, "evidence.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(d, "evidence.jsonl")) else []
        h = jload(os.path.join(d, "hypotheses.json")) or {}
        per, primary = {}, {}
        for r in ev:
            per[r.get("hypothesis_id", "")] = per.get(r.get("hypothesis_id", ""), 0) + 1
            if r.get("source_type") == "primary":
                primary[r.get("hypothesis_id", "")] = primary.get(r.get("hypothesis_id", ""), 0) + 1
        for x in h.get("hypotheses", []):
            if not x.get("core"):
                continue
            if per.get(x["id"], 0) < 2:
                gaps.append(f"{x['id']} 证据 <2 条")
            if primary.get(x["id"], 0) < 1:
                gaps.append(f"{x['id']} 缺一手来源")
        if len(ev) > st.get("budget", {}).get("sources_max", 30):
            gaps.append("来源数超预算")
        st["phase"] = "triangulate"
        notes.append(f"证据 {len(ev)} 条")

    elif phase == "triangulate":
        conf = jload(os.path.join(d, "conflicts.json"))
        if not conf:
            gaps.append("缺 conflicts.json")
        else:
            for c in conf.get("conflicts", []):
                if c.get("resolution") not in ("resolved", "blind_spot"):
                    gaps.append(f"冲突未处理：{c.get('claim')}")
        if not os.path.exists(os.path.join(d, "calc.json")):
            gaps.append("缺 calc.json（数值必须由 calc.py 生成）")
        st["phase"] = "redteam"
        notes.append(f"冲突 {len((conf or {}).get('conflicts', []))} 条")

    elif phase == "redteam":
        p = os.path.join(d, "redteam.md")
        if not os.path.exists(p):
            gaps.append("缺 redteam.md")
        else:
            t = open(p, encoding="utf-8").read()
            q = len(re.findall(r"^\s*[-*]\s*检索词", t, re.M))
            ce = len(re.findall(r"^\s*[-*]\s*反证", t, re.M))
            if q < 3:
                gaps.append(f"反向检索词 <3（{q}）")
            if ce < 2:
                gaps.append(f"反证 <2 条（{ce}）")
            if "证伪复核" not in t:
                gaps.append("缺「证伪复核」段")
        st["phase"] = "synthesize"
        notes.append("红队记录已核")

    elif phase == "synthesize":
        import glob as _glob
        cands = [os.path.join(d, "report.html")] + _glob.glob(f"reports/*{task}*_Research_Report.html") + _glob.glob(f"reports/*{task}*.html")
        rp = next((c for c in cands if os.path.exists(c)), "")
        if not rp:
            gaps.append("缺 report.html")
        else:
            t = open(rp, encoding="utf-8").read()
            ev = [json.loads(l) for l in open(os.path.join(d, "evidence.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(d, "evidence.jsonl")) else []
            core = {r["claim_id"] for r in ev if r.get("claim_id")}
            miss = [c for c in sorted(core) if c not in t]
            if miss:
                gaps.append(f"报告缺 claim 绑定：{miss[:8]}")
        if not os.path.exists(os.path.join(d, "decision_memo.md")):
            gaps.append("缺 decision_memo.md")
        rounds = st.get("loops", {}).get("source_rounds", 0)
        if rounds > 2:
            gaps.append(f"补采轮次 {rounds} >2")
        if st.get("loops", {}).get("reframes", 0) > 1:
            gaps.append("重构次数 >1")
        st["phase"] = "done"
        notes.append("交付门已核")

    else:
        sys.exit("未知 phase")

    st.setdefault("gates", {})[phase] = {"pass": not gaps, "gaps": gaps}
    save_state(task, st)
    print(f"{task} / {phase}：{'通过' if not gaps else '有缺口'} " + "；".join(notes))
    for g in gaps:
        print("  ❌", g)
    return 0 if not gaps else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "gate", "status"])
    ap.add_argument("task")
    ap.add_argument("phase", nargs="?")
    ap.add_argument("--decision")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    d, sp = paths(a.task)
    if a.cmd == "init":
        os.makedirs(d, exist_ok=True)
        if os.path.exists(sp):
            sys.exit(f"{sp} 已存在")
        st = {"task": a.task, "decision": a.decision or "", "decision_confirmed": False,
              "phase": "frame", "loops": {"source_rounds": 0, "reframes": 0},
              "budget": {"minutes_max": 90, "sources_max": 30, "pages_max": 8},
              "gates": {}}
        save_state(a.task, st)
        print(f"初始化 {sp}；下一步写 hypotheses.json，再 gate frame --confirm")
        return
    if a.cmd == "status":
        st, _ = load_state(a.task)
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return
    sys.exit(gate(a.task, a.phase, a.confirm))


if __name__ == "__main__":
    main()
