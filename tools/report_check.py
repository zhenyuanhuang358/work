#!/usr/bin/env python3
"""HTML 研究 / 财报报告的机械检查（2026-11-06 改造，期权线方法推广到报告线）

为什么：CLAUDE.md 的 Earner 模板规则、Merlin / restaurant-research 的交付规则、profile 里约 15 条报告教训，
全部只有文字、没有程序检查。11/06 抽查 13 份已交付财报报告：没有一份正好 14 节，INTC / AVGO 连双语标题 class 都不同——
规则写着、没人查，就漂移。本工具查「有明确标准答案」的部分；来源可信度、论证质量、置信度校准留给 Critic（AI）与人。

用户 11/06 定的优先级：**数据来源与合规最不能错**（S / G 项），模板格式其次（E / R 项）。

用法：
  python3 tools/report_check.py reports/X.html [--kind earner|research] [--pdf reports/X.pdf] [--record]
  --kind 不给按文件名判断（*_Copilot_Report.html = earner，其余 research）
  --record 把结果连同 sha256 追加到 memory/state/report_checks.jsonl（交付前必须；self_check C13 核对）
退出码：0 = 无 FAIL；1 = 有 FAIL。WARN 不阻断，但要在交付说明里写明。
"""
import argparse
import hashlib
import html as H
import json
import os
import re
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(REPO, "memory", "state", "report_checks.jsonl")

# 合规（CLAUDE.md / handoff：不披露海底捞 6862.HK、绿茶 6831.HK 未公开经营数据；用户曾任两家运营高管）
COMPLIANCE_ENTITIES = re.compile(r"海底捞|Haidilao|6862|绿茶|Green ?Tea|6831", re.I)
NONPUBLIC = re.compile(r"内部数据|内部口径|内部资料|内部人士|据内部|内部了解|内部报表|内部系统|未公开(?:的)?(?:数据|经营|口径)|"
                       r"我在任时|我任职期间|据我所知(?:的)?内部|internal data|non-public", re.I)
# 只认明确的合规否定 / 请求短语（「不对外公布的内部数据」这类真违规里也有「不」字，不能单字匹配）
NEGATION = re.compile(r"不应|不披露|不含|不涉及|不使用|不抖现|不得|不能说|不可说|不透露|不提供|不包括|未使用|禁止|避免|拒绝|"
                      r"请受访者|请提供|若客户方|如有|target|do(?:es)? not|without", re.I)
# 来源：摘要级 / 无出处的转述措辞（profile 1.1y：搜索摘要不是来源）
SUMMARY_LEVEL = re.compile(r"据搜索|搜索结果显示|网上资料显示|据网络|有消息称|据悉")
# Merlin / restaurant-research 正文禁用句（两份 SKILL.md 明文）
BANNED_BODY = re.compile(r"本报告未能核实|置信度较低|需要说明的是|相关站点无法访问|公开渠道未见披露，我们尝试|整体经营平稳|市场竞争激烈")
EARNER_FONTS = ["IM Fell English", "Songti SC"]
EARNER_COLORS = ["#0a0a0b", "#f1efea", "#8b6c42", "#c9a84c"]


def text_of(s):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return H.unescape(re.sub(r"<[^>]+>", " ", body))


def run(path, kind=None, pdf=None):
    s = open(path, encoding="utf-8", errors="ignore").read()
    t = text_of(s)
    kind = kind or ("earner" if path.endswith("_Copilot_Report.html") else "research")
    res = []

    def chk(cid, level, name, ok, evidence=""):
        res.append({"id": cid, "level": level, "check": name, "pass": bool(ok), "evidence": evidence})

    # ── G 合规（最高优先级）──────────────────────────────────────────
    # 11/06 基线：10 份命中全是误报——合规声明（「不披露未公开经营数据」）、请受访者提供、第三方（美团内部数据经媒体引用）。
    # 只算：同一句里出现海底捞 / 绿茶，且命中词前 12 字内没有否定 / 请求词。
    hits = []
    for m in NONPUBLIC.finditer(t):
        sent = re.split(r"[。；;\n!?！？]", t[max(0, m.start() - 60):m.start()])[-1] + t[m.start():m.end() + 40].split("。")[0]
        before = t[max(0, m.start() - 80):m.start()]
        if COMPLIANCE_ENTITIES.search(sent) and not NEGATION.search(before):
            hits.append(re.sub(r"\s+", " ", sent.strip())[:80])
    chk("G1", "FAIL", "同一句里把海底捞 / 绿茶与「内部 / 未公开」数据连在一起且非否定（交付前须人工确认）", not hits, hits[:3])

    # ── S 数据来源 ───────────────────────────────────────────────────
    urls = set(re.findall(r"https?://[^\s\"'<>)]+", s))
    cites = len(re.findall(r"来源[:：]|Source[s]?[:：]|资料来源|数据来源|出处[:：]", t))
    has_index = bool(re.search(r"来源索引|参考来源|数据来源|Sources|References|资料来源", t))
    chk("S1", "FAIL", "有来源索引 / 来源段落", has_index, f"URL {len(urls)} 个，来源标注 {cites} 处")
    nums = len(re.findall(r"\d[\d,.]*\s*(?:%|亿|万|元|美元|港元|家|店|倍|x|X|bp)", t))
    chk("S2", "WARN", "数字密度与来源数相称（每 25 个带单位数字至少 1 处来源 / URL）",
        nums <= 25 * max(1, len(urls) + cites), f"带单位数字 {nums}，来源 {len(urls) + cites}")
    sl = sorted({m.group(0) for m in SUMMARY_LEVEL.finditer(t)})
    chk("S3", "WARN", "无「据搜索 / 据悉」等摘要级转述（profile 1.1y，需三关核实或改写成具体出处）", not sl, sl)

    # ── C 通用格式 ───────────────────────────────────────────────────
    # 按 HTML 文本节点判断（11/06 基线：表头单独一格「#」序号列被拼进下一格文字，误报 4 份）
    nodes = [H.unescape(n).strip() for n in re.findall(r">([^<]+)<", re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S | re.I))]
    md = [n[:30] for n in nodes if re.search(r"\*\*[^*]{1,60}\*\*|`[^`]{1,40}`", n) or re.match(r"#{1,6}\s+\S", n)]
    chk("C1", "FAIL", "零 Markdown 符号（**、#、`）", not md, md[:3])
    chk("C2", "WARN", "手机交付附 PDF（profile 1.1zb）", (pdf and os.path.exists(pdf)) or
        os.path.exists(os.path.splitext(path)[0] + ".pdf"), pdf or "未给 --pdf，同名 .pdf 不存在")
    chk("C4", "WARN", "反馈链接（Critic D4：netlify 反馈页）", "spontaneous-youtiao-b9cde9.netlify.app" in s, "")
    target = re.search(r"目标价|Target Price|三情景|安全边际|PoP", t)
    if target:
        pred = open(os.path.join(REPO, "memory/state/predictions.md"), encoding="utf-8").read().lower().splitlines()
        stem = os.path.basename(path).split("_")[0].lower()
        # 11/06 首次实测发现：只查「标的名出现过」会被同标的的旧预测（UBER 期权那条）糊弄过去。
        # 改为：报告里每个情景目标价，都要在 predictions.md 找到一行同时含标的名与该价。
        tps = sorted({m.group(2) for m in re.finditer(r"(熊市|基准|牛市)\s*\$?\s*(\d+(?:\.\d+)?)", t)})
        missing = [p_ for p_ in tps if not any(stem in l and re.search(rf"(?<![\d.]){re.escape(p_)}(?![\d])", l) for l in pred)]
        chk("C3", "FAIL", "含目标价 / 三情景 → 每个情景价都已登记 predictions.md（CLAUDE.md 铁律）",
            tps and not missing, f"情景价 {tps or '未解析到'}；未登记 {missing}")

    if kind == "earner":
        secs = [int(x) for x in re.findall(r'data-sec="(\d+)"', s)]
        chk("E1", "FAIL", "14 节固定顺序（每节根元素 data-sec=\"1\"…\"14\"）", secs == list(range(1, 15)),
            f"data-sec = {secs or '无（旧报告未标注）'}；section-zh {s.count('section-zh')} 个")
        chk("E2", "FAIL", "中英双语标题成对（section-zh 与 section-en 数量相等且 ≥ 10）",
            s.count("section-zh") == s.count("section-en") >= 10, f"zh {s.count('section-zh')} / en {s.count('section-en')}")
        chk("E3", "FAIL", "SVG 图表 ≥ 5（营收 / 分部 / EPS / 毛利率 / 目标价区间）", s.count("<svg") >= 5, f"{s.count('<svg')} 个")
        chk("E4", "FAIL", "目标价三情景（熊 / 基准 / 牛）", all(k in t for k in ("熊", "基准", "牛")), "")
        miss = [f for f in EARNER_FONTS if f not in s] + [c for c in EARNER_COLORS if c.lower() not in s.lower()]
        chk("E5", "FAIL", "字体与配色符合视觉规范", not miss, f"缺 {miss}")
        chk("E6", "FAIL", "有 Verdict 裁决框", re.search(r"verdict", s, re.I), "")
        # E7（11/06 用户：「电话会原话一定要拿到」）：美股报告必须引用电话会原话（class="quote" ≥ 2）且来源索引有原文链接；
        # 港股 / A 股常无电话会（文件名前缀为数字），不强制
        stem_ = os.path.basename(path).split("_")[0]
        if not stem_.isdigit():
            nq = len(re.findall(r'class="quote"', s))
            has_tr = bool(re.search(r"https?://[^\s\"'<>]*transcript", s, re.I))
            # E8：每段引语必须在 transcripts/<stem>_*.txt 原文里逐字找到（防编造 / 防改写后仍打引号）
            import glob as _g
            norm = lambda x: re.sub(r"\s+", " ", x.replace("’", "'").replace("‘", "'")).strip().lower()  # noqa: E731
            src_txt = " ".join(norm(open(f, encoding="utf-8").read()) for f in _g.glob(os.path.join(REPO, "transcripts", f"{stem_.lower()}_*.txt")))
            qs = [H.unescape(q) for q in re.findall(r'class="quote">\s*[“"]([^”"<]{10,400})[”"]', s)]
            bad_q = [q[:50] for q in qs if not src_txt or norm(q) not in src_txt]
            if qs:
                chk("E8", "FAIL", "引语逐字出自电话会原文（transcripts/）", not bad_q,
                    f"{len(qs)} 段引语，原文 {'已找到' if src_txt else '缺失'}；对不上：{bad_q}")
            chk("E7", "FAIL", "美股：引用电话会原话（class=\"quote\" ≥ 2）且来源索引有原文链接（scripts/fetch_transcript.py）",
                nq >= 2 and has_tr, f"原话 {nq} 段，原文链接 {'有' if has_tr else '无'}")
    else:
        notes = re.search(r"分析师附注|Analyst'?s Note", t)
        chk("R1", "FAIL", "末尾有「分析师附注」板块", notes and notes.start() > len(t) * 0.5,
            f"位置 {notes.start() / len(t):.0%}" if notes else "无")
        body = t[:notes.start()] if notes else t
        bb = sorted({m.group(0) for m in BANNED_BODY.finditer(body)})
        chk("R2", "FAIL", "正文无禁用句（应移到附注或删掉）", not bb, bb)
        paras = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", s, re.S)]
        paras = [p for p in paras if len(p) > 20]
        first = paras[0] if paras else ""
        chk("R3", "WARN", "答案前置：第一段正文含结论或数字", re.search(r"\d|结论|判断|答案|建议", first[:80]), first[:60])
        chk("R4", "WARN", "趋势 / 拆分数据有 SVG 图（restaurant-research 规则）", "<svg" in s, f"{s.count('<svg')} 个")

    fails = [r for r in res if not r["pass"] and r["level"] == "FAIL"]
    return {"file": os.path.relpath(os.path.abspath(path), REPO), "kind": kind,
            "sha256": hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest(),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pass": not fails, "checks": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--kind", choices=["earner", "research"])
    ap.add_argument("--pdf")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run(a.report, a.kind, a.pdf)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        for c in r["checks"]:
            mark = "✅" if c["pass"] else ("❌" if c["level"] == "FAIL" else "⚠️")
            print(f"{mark} {c['id']} {c['check']}" + ("" if c["pass"] else f"｜{c['evidence']}"))
        print(f"{r['file']}（{r['kind']}）：" + ("无 FAIL" if r["pass"] else "有 FAIL，交付前修复"))
    if a.record:
        with open(RECORDS, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
