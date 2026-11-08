#!/usr/bin/env python3
"""生成 SKILLS.md：全部 skill 与子代理的索引（名字 / 路径 / 何时用 / spoke 数），给不认识 .claude/ 目录约定的 harness 用。

为什么（2026-11-08 用户：「家当全放在 GitHub，让 DeepSeek harness 自己读」）：
Claude Code 会自动扫描 .claude/skills/*/SKILL.md 的 frontmatter、按触发词加载；别的 harness 不会。
索引从 frontmatter 生成而不是手写——手写的路由表会漂移（CLAUDE.md C5 的教训）。tests/test_skill_index.py 核对它是最新的。
用法：python3 tools/skill_index.py            # 重写 SKILLS.md
      python3 tools/skill_index.py --check    # 只比对，过期则退出码 1
"""
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "SKILLS.md")


def front(path):
    s = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---", s, re.S)
    if not m:
        return {}
    fm, out, key = m.group(1), {}, None
    for line in fm.splitlines():
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if km:
            key = km.group(1)
            out[key] = km.group(2).strip().strip("|>").strip()
        elif key and line.startswith((" ", "\t")):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def one_line(desc):
    desc = re.sub(r"\s+", " ", desc).strip().strip('"')
    return desc.replace("|", "／")


def build():
    rows = []
    for p in sorted(glob.glob(os.path.join(REPO, ".claude/skills/*/SKILL.md"))):
        f = front(p)
        d = os.path.dirname(p)
        spokes = len(glob.glob(os.path.join(d, "references", "*.md")))
        rel = os.path.relpath(p, REPO)
        lines = sum(1 for _ in open(p, encoding="utf-8"))
        rows.append(f"| `{f.get('name', os.path.basename(d))}` | `{rel}` | {one_line(f.get('description', ''))} | {spokes} | {lines} |")
    agents = []
    for p in sorted(glob.glob(os.path.join(REPO, ".claude/agents/*.md"))):
        f = front(p)
        agents.append(f"| `{f.get('name', '')}` | `{os.path.relpath(p, REPO)}` | `{f.get('skills', '')}` | {one_line(f.get('description', ''))[:160]} |")
    return "\n".join([
        "# Skill 索引（自动生成，勿手改：`python3 tools/skill_index.py`）",
        "",
        "用法：用户的话命中某行「何时用」里的触发词或场景 → 先读该 SKILL.md（hub）→ 按 hub 里的「Spoke 加载表」再读 references/。",
        "CLAUDE.md 里的路由规则（报告类路由、COO 流水线、Critic 门控）优先于这里的触发词。",
        "",
        "| skill | 入口 | 何时用（frontmatter 原文） | spoke 数 | hub 行数 |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "## 子代理（.claude/agents/）",
        "",
        "Claude Code 里它们以独立上下文运行。别的 harness：开一个**新对话 / 新上下文**，把该文件正文当系统提示，只喂任务需要的文件——",
        "Critic 必须这样跑（生成与评审不能是同一个上下文，CLAUDE.md「Critic 质量门控」）。",
        "",
        "| 子代理 | 文件 | 绑定 skill | 说明 |",
        "|---|---|---|---|",
        *agents,
        "",
    ])


def main():
    txt = build()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if cur != txt:
            sys.exit("SKILLS.md 过期：跑 python3 tools/skill_index.py 重新生成")
        print("SKILLS.md 最新")
        return
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"→ SKILLS.md（{txt.count(chr(10))} 行）")


if __name__ == "__main__":
    main()
