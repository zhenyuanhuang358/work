#!/usr/bin/env python3
"""Merlin 报告机械检查（M0–M9）——把「写不到痛点 / 搜索面窄 / 答非所问 / 不够专业」变成可检查项。

对应 `.claude/skills/merlin/references/quality-rubric.md`：
  M0 输入契约（给了 --outline 时）：每题必须有 intent / decision
  M1 覆盖：Q1..Qn 全覆盖、不缺号、不发明编号
  M2 答案前置：每答第一句是数字/判断/区间，开头禁止元叙述
  M3 每答来源：每答至少 1 处来源标记
  M4 每答置信：每答至少 1 个置信徽章/标注
  M5 数据截止：报告写明数据截止时间
  M6 交付：分析师附注 + 来源索引 + 反馈链接
  M7 PDF：同名 PDF 存在
  M8 搜索广度（WARN）：真实域名数 ≥ 题数；每 Q 来源数 ≥ 2
  M9 专业口径（WARN）：至少 5 个专业口径标记（定义/口径/单位/期间/可比/基准/区间/敏感性）

用法：
  python3 tools/merlin_check.py reports/xxx_Research_Report.html [--outline memory/state/research/<task>/outline.json] [--pdf reports/xxx.pdf] [--json]
退出码：0 = 无 FAIL；1 = 有 FAIL。
"""
import argparse
import html as H
import json
import os
import re
import sys

META_STARTS = ("本报告", "需要说明的是", "公开渠道未见", "关于这个问题", "先说", "由于无法", "本报告未能核实")
SRC_MARKS = ("来源：", "来源:", "http", "《", "原文", "pages/", "公告", "年报", "官网", "招股书", "访谈", "研报", "数据来源")
PRO_MARKS = ("口径", "定义", "单位", "期间", "可比", "行业均值", "基准", "区间", "敏感性", "假设")
SKIP_HOSTS = ("fonts.googleapis.com", "spontaneous-youtiao-b9cde9.netlify.app", "www.w3.org", "localhost", "127.0.0.1")


def text_of(s):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", body))).strip()


def q_ids(t):
    """Q 编号（取首次出现，按出现顺序）。"""
    seen = {}
    for m in re.finditer(r"(?<![\w])Q(\d{1,2})(?![\d.])", t):
        n = int(m.group(1))
        if n not in seen:
            seen[n] = m.start()
    return sorted(seen.items(), key=lambda kv: kv[1])


def segments(t, ids):
    out = []
    for i, (n, pos) in enumerate(ids):
        end = ids[i + 1][1] if i + 1 < len(ids) else len(t)
        out.append((n, t[pos:end]))
    return out


def answer_lead(seg):
    """去掉 Q 编号与标题、问句，取答案开头 300 字（用于答案前置检查）。"""
    seg = re.sub(r"^Q\d{1,2}\s*[·:：]?\s*", "", seg).strip()
    q = re.search(r"[？?]", seg[:200])
    if q:  # 提纲原问以问号结尾 → 答案从问号之后开始
        seg = seg[q.end():].lstrip()
    return seg[:300]


def domains(s):
    hosts = set()
    for u in re.findall(r"https?://([^\s/\"'<>]+)", s):
        h = u.lower().split(":")[0]
        if h not in SKIP_HOSTS and "fonts." not in h:
            hosts.add(h)
    return hosts


def run(report, outline=None, pdf=None):
    s = open(report, encoding="utf-8", errors="ignore").read()
    t = text_of(s)
    res = []

    def chk(cid, level, name, ok, ev=""):
        res.append({"id": cid, "level": level, "check": name, "pass": bool(ok), "evidence": "" if ok else ev})

    ids = q_ids(t)
    nq = len(ids)

    # M0 输入契约
    if outline:
        try:
            od = json.load(open(outline, encoding="utf-8"))
            qs = od.get("questions", [])
            miss = [q.get("id") for q in qs if not str(q.get("intent", "")).strip() or not str(q.get("decision", "")).strip()]
            chk("M0", "FAIL", "输入契约：每题有「真实想问 / 决策用途」", not miss, f"缺 intent/decision：{miss[:6]}")
        except Exception as e:
            chk("M0", "FAIL", "输入契约可读", False, repr(e)[:120])

    # M1 覆盖
    if outline:
        qs = json.load(open(outline, encoding="utf-8")).get("questions", [])
        want = [str(q.get("id", "")).upper() for q in qs]
        missing = [w for w in want if w not in {f"Q{n}" for n, _ in ids}]
        extra = [f"Q{n}" for n, _ in ids if f"Q{n}" not in want]
        chk("M1", "FAIL", "Q1..Qn 全覆盖（不缺号、不发明编号）", not missing and not extra,
            f"缺 {missing[:6]}；多余 {extra[:6]}")
    else:
        chk("M1", "FAIL", "Q 编号连续（Q1..Qn）", nq > 0 and [n for n, _ in ids] == list(range(1, nq + 1)),
            f"识别到 {[n for n, _ in ids][:12]}")

    segs = segments(t, ids)

    # M2 答案前置
    bad = []
    for n, seg in segs:
        lead = answer_lead(seg)
        if not lead:
            bad.append(f"Q{n} 无内容")
            continue
        has_conclusion = bool(re.search(r"\d", lead)) or "【推测】" in lead or any(
            k in lead for k in ("结论", "判断", "区间", "高于", "低于", "持平", "约为", "估值", "目标"))
        meta = lead.startswith(META_STARTS)
        if meta or not has_conclusion:
            bad.append(f"Q{n}: {lead[:40]}")
    chk("M2", "FAIL", "每答开头给结论（数字/判断，禁止元叙述）", not bad, "; ".join(bad[:5]))

    # M3 每答来源
    weak = []
    for n, seg in segs:
        if not any(m in seg for m in SRC_MARKS):
            weak.append(f"Q{n}")
    chk("M3", "FAIL", "每答至少 1 处来源标记", not weak, f"无来源：{weak[:8]}")

    # M4 每答置信
    no_conf = [f"Q{n}" for n, seg in segs
               if not re.search(r"置信|可信度|confidence", seg, re.I)
               and not re.search(r"(?<!\S)[高中低](?!\S)", seg)]
    chk("M4", "FAIL", "每答有置信徽章", not no_conf, f"缺置信：{no_conf[:8]}")

    # M5 数据截止
    chk("M5", "FAIL", "写明数据截止时间", bool(re.search(r"(数据截止|截至)\s*[:：]?\s*20\d{2}[-/年.]|as of\s+20\d{2}", t)),
        "无「数据截止/截至 20xx」")

    # M6 交付形态
    chk("M6", "FAIL", "分析师附注 + 来源索引 + 反馈链接",
        "分析师附注" in t and "来源索引" in t and "spontaneous-youtiao" in s,
        f"附注={'✓' if '分析师附注' in t else '✗'} 来源索引={'✓' if '来源索引' in t else '✗'} 反馈={'✓' if 'spontaneous-youtiao' in s else '✗'}")

    # M7 PDF
    pdf_path = pdf or (os.path.splitext(report)[0] + ".pdf")
    chk("M7", "FAIL", "HTML 附 PDF", os.path.exists(pdf_path), pdf_path)

    # M8 搜索广度（WARN）
    hosts = domains(s)
    per_q = [len([m for m in SRC_MARKS if m in seg]) for _, seg in segs]
    chk("M8", "WARN", "搜索广度：真实域名 ≥ 题数，且每 Q ≥2 类来源",
        nq > 0 and len(hosts) >= nq and all(c >= 2 for c in per_q),
        f"域名 {len(hosts)}（题 {nq}）；每 Q 来源计数 {per_q[:12]}")

    # M9 专业口径（WARN）
    marks = [m for m in PRO_MARKS if m in t]
    chk("M9", "WARN", "专业口径标记 ≥5 类", len(marks) >= 5, f"命中 {marks}")

    fails = [r for r in res if r["level"] == "FAIL" and not r["pass"]]
    warns = [r for r in res if r["level"] == "WARN" and not r["pass"]]
    return {"file": os.path.relpath(report), "questions": nq, "checks": res,
            "pass": not fails, "fails": [r["id"] for r in fails], "warns": [r["id"] for r in warns]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--outline")
    ap.add_argument("--pdf")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run(a.report, a.outline, a.pdf)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"{r['file']}（Q×{r['questions']}）：{'无 FAIL' if r['pass'] else '有 FAIL'}")
        for c in r["checks"]:
            mark = "✅" if c["pass"] else ("❌" if c["level"] == "FAIL" else "⚠️")
            print(f"  {mark} {c['id']} {c['check']}" + ("" if c["pass"] else f"｜{c['evidence']}"))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
