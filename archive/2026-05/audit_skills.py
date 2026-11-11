"""
audit_skills.py — Skill / Script 静态审计

2026-09-01 首次全仓审计后固化。**审计标准按「能不能静默产出错误结论」排序，
不按代码整洁度**——这是本仓库反复吃亏的地方。

  P0  会静默出错（不报错、不崩溃，只安静地给出错的结论）
      - 硬编码日期/年份/期间：跨年后失效，frames 返回空但脚本照跑
      - 单位/口径混用：13F 千美元 vs 美元差 1000 倍，不会报错
      - 排序/筛选前无定义域检查：负 EV 会被升序排到「最便宜」榜首
      - 静默剔除样本：丢了几条不落库，产物看不出缺口
  P1  结构性：hub >200 行、Spoke 断链、孤儿 spoke、缺 frontmatter
  P2  可维护性：缺质量自检

用法：python scripts/audit_skills.py          # 全查
     python scripts/audit_skills.py --p0     # 只查 P0
退出码：有 P0 → 2；只有 P1/P2 → 1；全清 → 0
"""

import glob
import os
import re
import sys

SKILLS = ".claude/skills"
SCRIPTS = "scripts"

# 允许硬编码日期的白名单：这些是「制度事实」，不随时间改变
DATE_WHITELIST = {
    "VALUE_DOLLARS_FROM",   # 13F 单位切换日 2023-01-03，是 SEC 规则变更日，不是「当前时间」
}


def audit_skills():
    out = []
    for d in sorted(glob.glob(f"{SKILLS}/*/")):
        name = os.path.basename(d.rstrip("/"))
        hub = os.path.join(d, "SKILL.md")
        if not os.path.exists(hub):
            out.append(("P0", name, "SKILL.md 缺失")); continue
        t = open(hub, encoding="utf-8").read()
        ln = t.count("\n") + 1
        if ln > 200:
            out.append(("P1", name, f"hub {ln} 行 > 200（CLAUDE.md 上限）"))
        if not t.startswith("---"):
            out.append(("P1", name, "缺 YAML frontmatter"))
        else:
            fm = t.split("---")[1]
            for k in ("name:", "description:"):
                if k not in fm:
                    out.append(("P1", name, f"frontmatter 缺 {k}"))
        # 引用可以是 references/xxx.md，也可以是资源树里的裸 xxx.md
        have = [os.path.basename(x) for x in glob.glob(os.path.join(d, "references", "*.md"))]
        for h in have:
            if h not in t:
                out.append(("P1", name, f"孤儿 spoke（hub 未提及，永不加载）: {h}"))
        for r in set(re.findall(r"references/([\w\-.]+\.md)", t)):
            if not os.path.exists(os.path.join(d, "references", r)):
                out.append(("P1", name, f"Spoke 断链: references/{r}"))
        if "质量自检" not in t:
            out.append(("P2", name, "无质量自检清单"))
    return out


def audit_scripts():
    """P0 扫描。注意：这些是**启发式**，会有误报——
    目的是把可疑点顶到眼前，不是自动判罪。每条都要人工确认。"""
    out = []
    yr = re.compile(r"\b(20[2-9]\d)\b")
    for f in sorted(glob.glob(f"{SCRIPTS}/*.py")):
        base = os.path.basename(f)
        lines = open(f, encoding="utf-8").read().split("\n")
        in_doc = False
        for i, l in enumerate(lines, 1):
            if l.count('"""') % 2: in_doc = not in_doc
            if in_doc or l.strip().startswith("#"):
                continue
            code = l.split("#")[0]
            # P0-1 硬编码年份/期间
            if yr.search(code) and not any(w in code for w in DATE_WHITELIST):
                if re.search(r'CY20|"20[2-9]\d"|range\(\s*20[12]\d', code):
                    out.append(("P0", base, f"L{i} 疑似硬编码年份/期间 → 跨年后静默失效: {code.strip()[:70]}"))
            # P0-4 裸的量纲换算
            if re.search(r"[*/]\s*1000(?!\d)", code) and "print" not in code and "f\"" not in code:
                out.append(("P0", base, f"L{i} 裸的 1000 换算，确认量纲注释: {code.strip()[:70]}"))
        src = "\n".join(lines)
        # P0-3 静默剔除
        n_cont = len(re.findall(r"^\s+continue\s*$", src, re.M))
        # ⚠ 2026-09-01 修误报：ses_screener.py 的 5 处 continue 是在 XBRL 事实里
        #   **挑选**正确期间（表单类型/缺日期/期间长度），不是丢弃公司；
        #   失败路径也确实落了库，只是用的是 error / notes 字段名。
        #   一个会喊狼来了的检测器最终会被忽略——宁可漏报也不要习惯性误报。
        counted = any(k in src for k in
                      ("skipped", "incomplete", "missing_data", "not_applicable",
                       "warn", "dropped", '"error"', "notes.append"))
        if n_cont >= 2 and not counted:
            out.append(("P0", base, f"{n_cont} 处 continue 但无丢弃计数 → 产物看不出缺口"))
        # P0-2 排序前定义域
        if re.search(r"\.sort\(|sorted\(", src) and not re.search(r"<=\s*0|>\s*0|is None", src):
            out.append(("P0", base, "有排序但未见非正数/None 守卫 → 确认定义域检查"))
    return out


def main():
    only_p0 = "--p0" in sys.argv
    rows = audit_scripts() + audit_skills()
    if only_p0:
        rows = [r for r in rows if r[0] == "P0"]
    n_skills = len(glob.glob(f"{SKILLS}/*/"))
    print(f"审计 {n_skills} 个 skill、{len(glob.glob(f'{SCRIPTS}/*.py'))} 个脚本\n")
    worst = 0
    for sev in ("P0", "P1", "P2"):
        hit = [r for r in rows if r[0] == sev]
        if not hit:
            print(f"  {sev}  ✓ 无"); continue
        worst = max(worst, {"P0": 2, "P1": 1, "P2": 1}[sev])
        print(f"  {sev}  ⚠ {len(hit)} 项")
        for _, who, what in hit:
            print(f"      [{who}] {what}")
    print()
    if worst == 0:
        print("全部通过。")
    elif worst == 1:
        print("⚠ 有 P1/P2，不阻断但应排期修。")
    else:
        print("⛔ 有 P0——这类缺陷不会报错、不会崩溃，只会安静地给出错的结论。优先修。")
    return worst


if __name__ == "__main__":
    sys.exit(main())
