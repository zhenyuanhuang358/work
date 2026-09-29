"""用 selection-score.md 给 gold.jsonl 逐条打分，出门槛扫描报告。

照 AIHOT 的做法（packages/backend/src/editorial/analyze.ts）：
- 输入格式与 buildScoreInput 一致：发布时间 / 标题 / 完整正文，不给信源分级
- 每条独立打两次分，两次之和 ≥ 2 × 门槛才入选

在 GitHub Actions 里跑（key 在仓库 Secrets 的 ANTHROPIC_API_KEY）：
    CALIB_MODEL=claude-opus-5-5 python aihot_canyin/calib/score.py
产物：calib/results.jsonl（逐条分数）、calib/report.md（门槛扫描 + 分歧清单）
"""
import json, os, pathlib, statistics, sys
from concurrent.futures import ThreadPoolExecutor

import anthropic

HERE = pathlib.Path(__file__).parent
PROMPT = (HERE.parent / "industry/prompts/selection-score.md").read_text(encoding="utf-8").replace("{{siteName}}", "餐饮HOT")
MODEL = os.environ.get("CALIB_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CALIB_EFFORT", "low")
SCORE_CALLS = 2
AIHOT_THRESHOLDS = {"T1": 60, "T1_5": 65, "T2": 76}  # AIHOT 在 AI 领域调出的门槛，作对照
SCHEMA = {"type": "object", "properties": {"attentionScore": {"type": "integer"}},
          "required": ["attentionScore"], "additionalProperties": False}

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY 为空：仓库 Settings → Secrets and variables → Actions 里没有这个 Secret")
client = anthropic.Anthropic()
usage = {"in": 0, "out": 0}
errors: list[str] = []


def score_input(m: dict) -> str:
    return "\n\n".join([
        "请按系统规则评估以下单篇材料所代表的事件。只输出 attentionScore。",
        f"【发布时间（北京时间）】\n{m['publishedAt']}",
        f"【标题】\n{m['title'].strip()}",
        f"【完整正文】\n{(m.get('bodyZh') or m.get('bodyOriginal') or m['title']).strip()}",
    ])


def one_score(text: str) -> int | None:
    resp = client.messages.create(
        model=MODEL, max_tokens=4096,
        system=[{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": text}],
    )
    usage["in"] += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0) + (resp.usage.cache_creation_input_tokens or 0)
    usage["out"] += resp.usage.output_tokens
    if resp.stop_reason == "refusal":
        return None
    txt = next((b.text for b in resp.content if b.type == "text"), "")
    return max(0, min(100, int(json.loads(txt)["attentionScore"])))


def run_case(case: dict) -> dict:
    text = score_input(case["material"])
    values = []
    for _ in range(SCORE_CALLS):  # 顺序两次：第二次复用缓存的系统提示
        try:
            values.append(one_score(text))
        except (anthropic.APIStatusError, anthropic.APIConnectionError, json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"  {case['caseId']} 打分失败：{type(e).__name__}: {e}", file=sys.stderr)
            errors.append(f"{case['caseId']}: {type(e).__name__}: {str(e)[:300]}")
            values.append(None)
    return {"caseId": case["caseId"], "title": case["material"]["title"], "tier": case["sourceFacts"]["sourceTier"],
            "gold": case["gold"]["decision"], "stratum": case["samplingContext"]["samplingStratum"],
            "borderline": case["review"]["borderline"], "why": case["review"]["why"], "scores": values}


def metrics(rows, thr_of):
    tp = fp = fn = tn = 0
    for r in rows:
        pred = sum(r["scores"]) >= 2 * thr_of(r)
        gold = r["gold"] == "select"
        tp += pred and gold; fp += pred and not gold; fn += (not pred) and gold; tn += (not pred) and not gold
    n = tp + fp + fn + tn
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"acc": (tp + tn) / n if n else 0, "precision": p, "recall": rc, "f1": 2 * p * rc / (p + rc) if p + rc else 0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main():
    cases = [json.loads(l) for l in (HERE / "gold.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(run_case, cases))
    (HERE / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    ok = [r for r in rows if None not in r["scores"]]
    failed = [r["caseId"] for r in rows if None in r["scores"]]
    if not ok:
        (HERE / "report.md").write_text("# 校准失败：没有一条打分成功\n\n" + "\n".join(f"- {e}" for e in errors[:10]) + "\n", encoding="utf-8")
        print("没有一条打分成功", errors[:3], file=sys.stderr)
        sys.exit(1)
    L = [f"# 校准结果", "", f"模型 `{MODEL}` · effort `{EFFORT}` · 每条 {SCORE_CALLS} 次独立打分 · 有效 {len(ok)}/{len(rows)} 条"
         + (f"（失败或拒答：{', '.join(failed)}）" if failed else ""),
         f"token：输入 {usage['in']:,} / 输出 {usage['out']:,}", ""]

    # 1. 两类分数是否分得开
    sel = [statistics.mean(r["scores"]) for r in ok if r["gold"] == "select"]
    rej = [statistics.mean(r["scores"]) for r in ok if r["gold"] == "reject"]
    L += ["## 1. 两类样本的平均分分布", "", "| | 条数 | 中位数 | 最低 | 最高 |", "|---|---:|---:|---:|---:|"]
    for name, xs in (("该选", sel), ("不该选", rej)):
        if xs:
            L.append(f"| {name} | {len(xs)} | {statistics.median(xs):.1f} | {min(xs):.1f} | {max(xs):.1f} |")
    gaps = [abs(r["scores"][0] - r["scores"][1]) for r in ok]
    L += ["", f"两次打分差的中位数 {statistics.median(gaps):.1f}，最大 {max(gaps)}（衡量同一条打两次稳不稳）", ""]

    # 2. AIHOT 原门槛直接套用
    m0 = metrics(ok, lambda r: AIHOT_THRESHOLDS.get(r["tier"], 76))
    L += ["## 2. 直接套用 AIHOT 原门槛（T1 60 / T2 76）", "",
          f"准确率 {m0['acc']:.1%} · 查准 {m0['precision']:.1%} · 查全 {m0['recall']:.1%}（漏选 {m0['fn']} 条，误选 {m0['fp']} 条）", ""]

    # 3. 统一门槛扫描
    L += ["## 3. 统一门槛扫描（不分信源分级）", "", "| 门槛 | 准确率 | 查准 | 查全 | 漏选 | 误选 |", "|---:|---:|---:|---:|---:|---:|"]
    best = None
    for t in range(40, 91, 2):
        m = metrics(ok, lambda r, t=t: t)
        L.append(f"| {t} | {m['acc']:.1%} | {m['precision']:.1%} | {m['recall']:.1%} | {m['fn']} | {m['fp']} |")
        if best is None or m["f1"] > best[1]["f1"]:
            best = (t, m)
    L += ["", f"F1 最高的门槛：**{best[0]}**（准确率 {best[1]['acc']:.1%}）", ""]

    # 4. 分歧清单：在最佳门槛下模型与我的标签不一致的
    t = best[0]
    L += [f"## 4. 分歧清单（门槛 {t} 下，模型判断 ≠ 预标）——这些要你来裁", "",
          "| # | 预标 | 两次分数 | 边界 | 标题 | 我的理由 |", "|---|---|---|---|---|---|"]
    for r in sorted(ok, key=lambda r: r["caseId"]):
        pred = "select" if sum(r["scores"]) >= 2 * t else "reject"
        if pred != r["gold"]:
            L.append(f"| {r['caseId']} | {'选' if r['gold']=='select' else '不选'} | {r['scores'][0]} / {r['scores'][1]} | "
                     f"{'是' if r['borderline'] else ''} | {r['title'][:40]} | {r['why']} |")

    # 5. 按层看
    L += ["", "## 5. 按内容层的平均分", "", "| 层 | 条数 | 平均分 |", "|---|---:|---:|"]
    by = {}
    for r in ok:
        by.setdefault(r["stratum"], []).append(statistics.mean(r["scores"]))
    for k, xs in sorted(by.items(), key=lambda kv: -statistics.mean(kv[1])):
        L.append(f"| {k} | {len(xs)} | {statistics.mean(xs):.1f} |")

    (HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
