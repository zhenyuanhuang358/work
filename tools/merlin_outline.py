#!/usr/bin/env python3
"""Merlin M0 输入契约工具：把客户提纲变成 outline.json / outline_map.md，并在开搜前检查完整性。

用法：
  python3 tools/merlin_outline.py init <task> --questions <提纲文件>   # 生成模板（每题 intent/decision 需人工/模型补）
  python3 tools/merlin_outline.py check <task> [--json]                # 检查每题四要素齐全且非占位符
目录：memory/state/research/<task>/{outline.json,outline_map.md}
退出码：0 = 通过；1 = 有缺口。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.join("memory", "state", "research")
FIELDS = ["intent", "decision", "answer_form", "data_need"]
FIELD_ZH = {"intent": "真实想问", "decision": "决策用途", "answer_form": "答案形态", "data_need": "数据需求"}
PLACEHOLDERS = ("", "待补", "todo", "tbd", "na", "n/a", "—", "-")


def parse_questions(path):
    qs = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\|?\s*[Qq](\d{1,2})\s*[|·:：\-\t ]\s*(.*?)\s*\|?$", line)
        if m:
            qs.append({"id": f"Q{int(m.group(1))}", "text": m.group(2).strip() or f"Q{int(m.group(1))}"})
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and re.match(r"^[Qq]\d{1,2}$", cells[0]):
                qs.append({"id": cells[0].upper(), "text": cells[1] if len(cells) > 1 else cells[0]})
    seen, out = set(), []
    for q in qs:
        if q["id"] not in seen:
            seen.add(q["id"])
            out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "check"])
    ap.add_argument("task")
    ap.add_argument("--questions")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = os.path.join(a.root, a.task)
    jp = os.path.join(d, "outline.json")
    mp = os.path.join(d, "outline_map.md")

    if a.cmd == "init":
        if not a.questions:
            sys.exit("init 需要 --questions <提纲文件>")
        qs = parse_questions(a.questions)
        if not qs:
            sys.exit("提纲里没识别到 Q1..Qn（每行形如「Q1 | 问题」）")
        os.makedirs(d, exist_ok=True)
        for q in qs:
            q.update({k: "待补" for k in FIELDS})
        obj = {"task": a.task, "questions": qs}
        json.dump(obj, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rows = ["# M0 输入契约 · " + a.task, "",
                "| Q | 客户原问 | 真实想问（决策场景） | 答案形态 | 数据需求 / 可获取性 |",
                "|---|---|---|---|---|"]
        for q in qs:
            rows.append(f"| {q['id']} | {q['text']} | 待补 | 待补 | 待补 |")
        open(mp, "w", encoding="utf-8").write("\n".join(rows) + "\n")
        print(f"已生成 {jp} / {mp}：请补 intent/decision/answer_form/data_need，然后跑 check")
        return

    # check
    if not os.path.exists(jp):
        sys.exit(f"缺 {jp}，先跑 init")
    obj = json.load(open(jp, encoding="utf-8"))
    qs = obj.get("questions", [])
    gaps = []
    ids = [q.get("id") for q in qs]
    if not qs:
        gaps.append("outline.json 无 questions")
    if ids and ids != [f"Q{i}" for i in range(1, len(ids) + 1)]:
        gaps.append(f"Q 编号不连续：{ids}")
    for q in qs:
        for f in FIELDS:
            v = str(q.get(f, "")).strip()
            if v.lower() in PLACEHOLDERS:
                gaps.append(f"{q.get('id')} 缺 {FIELD_ZH[f]}（{f}）")
    if a.json:
        print(json.dumps({"task": a.task, "ok": not gaps, "questions": len(qs), "gaps": gaps},
                         ensure_ascii=False, indent=1))
    else:
        print(f"{a.task}（Q×{len(qs)}）：{'通过' if not gaps else '有缺口'}")
        for g in gaps:
            print("  ❌", g)
    sys.exit(0 if not gaps else 1)


if __name__ == "__main__":
    main()
