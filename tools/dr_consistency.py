#!/usr/bin/env python3
"""跨文件一致性门禁（Decision Mode v0.2）。

问题来源：v0.1 首测 Critic R2 判 REWRITE——报告改了 2027 目标/情景，冲突表、memo、台账还留旧数。
做法：把「关键事实」声明在 facts.json（单一事实源）；每个事实的 canonical 必须出现在指定文件，
旧口径（stale）不得出现在任何指定文件。不是靠人记，而是 gate 拦。

用法：
  python3 tools/dr_consistency.py <task> [--json]
退出码 0 通过，1 有不一致。
"""
import argparse
import json
import os
import sys

ROOT = os.path.join("memory", "state", "research")
ARTIFACTS = {
    "report": ["report.html", "reports/${task}_Research_Report.html"],
    "conflicts": ["conflicts.json"],
    "memo": ["decision_memo.md"],
    "hypotheses": ["hypotheses.json"],
    "redteam": ["redteam.md"],
    "calc": ["calc.json"],
}


def load_artifacts(task):
    d = os.path.join(ROOT, task)
    import glob as _glob
    out = {}
    for key, pats in ARTIFACTS.items():
        for p in pats:
            p = p.replace("${task}", task)
            cands = _glob.glob(os.path.join(d, p)) + _glob.glob(p)
            if cands:
                out[key] = open(cands[0], encoding="utf-8").read()
                break
    return out


def check(task):
    d = os.path.join(ROOT, task)
    fp = os.path.join(d, "facts.json")
    if not os.path.exists(fp):
        return [f"缺 {fp}（关键事实未声明，一致性不可核）"]
    facts = json.load(open(fp, encoding="utf-8")).get("facts", [])
    arts = load_artifacts(task)
    issues = []
    for f in facts:
        canon = f.get("canonical", [])
        stale = f.get("stale", [])
        for key in f.get("must_in", []):
            txt = arts.get(key)
            if txt is None:
                issues.append(f"{f['id']}：缺产物 {key}")
                continue
            if not any(c in txt for c in canon):
                issues.append(f"{f['id']}（{f.get('desc','')}）：{key} 找不到 canonical {canon[:2]}")
            for s in stale:
                if s in txt:
                    issues.append(f"{f['id']}（{f.get('desc','')}）：{key} 残留旧口径「{s}」")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    issues = check(a.task)
    if a.json:
        print(json.dumps({"task": a.task, "ok": not issues, "issues": issues}, ensure_ascii=False, indent=1))
    else:
        print(f"{a.task} 一致性：{'通过' if not issues else '有 %d 处不一致' % len(issues)}")
        for x in issues:
            print("  ❌", x)
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
