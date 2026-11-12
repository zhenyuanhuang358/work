#!/usr/bin/env python3
"""天道 · 交付前检查（2026-11-09，用户定的验收标准 → 程序检查）。

为什么：天道的规则写在 SKILL.md 里，但「每个结论带置信度和否定条件」「不替用户填认错线」
「法律问题不给确定结论」这些，过去只能靠模型自觉。用户定为「必须满足 / 最不能接受」后，按工具修复 > 程序检查的顺序，
把能机械判断的部分变成检查；判断质量本身（规则用得对不对）仍是 AI 评估，不在这里。

用法：
  python3 tools/tiandao_verify.py answer <回答.md>      # 检查一次天道回答
  python3 tools/tiandao_verify.py card <决策卡.md>      # 检查一张决策卡
退出码 0 = 无 FAIL。每项输出 ✅ / ❌，FAIL 不得交付。

检查项（对应用户 11/09 定的验收标准）：
  A1 结论：首段有「结论：做 / 不做 / 等」（诊断模式除外）
  A2 置信度：结论带 高 / 中 / 低
  A3 否定条件：有「否定条件」且非空（最不能接受：迎合或没有否定条件）
  A4 关键依据 ≤ 3 条
  A5 「做」或「等」必须附决策卡（或写明卡的存档路径）
  A6 个人规则数字：提到借款 / 入股 / 黄金占比 / 期权亏损上限时，必须引用 tiandao_check 输出；工具 ok=false 时结论不得是「做」
  A7 法律 / 合规：涉及违法、洗钱、外汇、税务等时，必须提示律师 / 专业意见，且不得出现确定性定罪措辞
  A8 防依赖与迎合：不得出现「听我的」「照做就行」「稳赚」等
  A9 诊断模式：问题 ≤ 3 个
  K1–K5 决策卡：首部字段、七项齐全、第 2 / 4 项标明来自用户、第 4 项可观测且写明执行机制、不接受「感觉不对就走」
"""
import json
import re
import sys

LEGAL = re.compile(r"违法|犯罪|洗钱|外汇管理|结汇|逃税|税务责任|刑事|反洗钱|帮信|掩饰隐瞒|合规风险|法律责任")
LAWYER = re.compile(r"律师|法律意见|专业意见|持牌顾问")
DEFINITIVE = re.compile(r"一定(?:会)?(?:违法|构成|被判|坐牢)|肯定(?:违法|构成|被判)|必然(?:构成|被判)|就是犯罪|铁定")
PANDER = re.compile(r"听我的|照做就行|稳赚|放心去做|包赚|一定能赚")
RULE_TOPIC = re.compile(r"借给|借出|借款|入股|担保|黄金|保值配置|价差|裸卖|单笔最大亏损|权益跌到")
AMOUNT = re.compile(r"\d[\d,，.]*\s*(?:元|万|美元|\$|%)|\$\s*\d")
VAGUE = re.compile(r"感觉不对|看情况|差不多了|心里不舒服|到时候再说|视情况而定")
OBSERVABLE = re.compile(r"\d|出现|当|若|一旦|跌破|超过|低于|到期|逾期|不同意|拒绝|出面|大吵|日期|价格|占比")
MECHANISM = re.compile(r"条件单|合同|条款|借条|日历|复核|监督|冷却期|自动|占比上限|提醒|书面")


def chk(res, cid, ok, name, ev=""):
    res.append({"id": cid, "pass": bool(ok), "check": name, "evidence": ev})


def section(text, title):
    m = re.search(rf"{title}[^\n]*\n?(.*?)(?=\n\s*(?:\*\*)?(?:\d+\.\s*)?(?:局的类型|关键依据|否定条件|出局风险|下一步|决策卡|怎么|\Z))", text, re.S)
    return m.group(1).strip() if m else ""


def verify_answer(text):
    res = []
    t = text
    diag = bool(re.search(r"(?:先|需要你)(?:回答|停下|问清)|会改变结论|三个问题", t)) and not re.search(r"结论[:：]\s*(?:\*\*)?(?:做|不做|等)", t)
    if diag:
        qs = [l for l in t.splitlines() if re.match(r"\s*(?:\d+[.、]|[①②③④⑤])", l) and "？" in l]
        chk(res, "A9", 1 <= len(qs) <= 3, "诊断模式：问题 1–3 个", f"{len(qs)} 个")
        chk(res, "A8", not PANDER.search(t), "无「听我的 / 照做就行 / 稳赚」", (PANDER.search(t) or [""])[0])
        return res
    m = re.search(r"结论[:：]\s*(?:\*\*)?\s*(不做|做|等|不答应|答应|不借|借)", t[:600])
    concl = m.group(1) if m else None
    norm = {"不答应": "不做", "答应": "做", "不借": "不做", "借": "做"}.get(concl, concl)
    chk(res, "A1", norm in ("做", "不做", "等"), "开头有结论（做 / 不做 / 等）", concl or "未找到")
    chk(res, "A2", re.search(r"置信度[:：]?\s*(?:\*\*)?\s*[高中低]", t), "结论带置信度（高 / 中 / 低）", "")
    neg = re.search(r"否定条件[^\n]*\n((?:.*\n){0,8})", t)
    chk(res, "A3", neg and len(neg.group(1).strip()) > 10, "有否定条件且非空（最不能接受：没有否定条件）", "")
    basis = section(t, "关键依据")
    n = len([l for l in basis.splitlines() if re.match(r"\s*(?:\d+[.、]|[-•·])\s*\S", l)])
    chk(res, "A4", n <= 3, "关键依据 ≤ 3 条", f"{n} 条")
    if norm in ("做", "等"):
        chk(res, "A5", re.search(r"决策卡", t), "「做 / 等」附决策卡（或存档路径）", "")
    # 话题词与金额相距 25 字以内才算「在谈个人规则的数字」（11/09 转账样例：「担保」只是类比，金额远在别处，不应触发）
    near = any(abs(a.start() - b.start()) <= 25 for a in RULE_TOPIC.finditer(t) for b in AMOUNT.finditer(t))
    if near:
        cited = re.search(r"tiandao_check", t)
        chk(res, "A6", cited, "提到个人规则相关数字时引用 tiandao_check 输出（不心算）", "")
        for blob in re.findall(r"\{[^{}]*\"ok\"\s*:\s*false[^{}]*\}", t):
            chk(res, "A6b", norm != "做", "工具判违反（ok=false）时结论不得是「做」", blob[:60])
    if LEGAL.search(t):
        chk(res, "A7", LAWYER.search(t), "涉法问题提示律师 / 专业意见", LEGAL.search(t).group(0))
        d = DEFINITIVE.search(t)
        chk(res, "A7b", not d, "涉法问题不用确定性定罪措辞", d.group(0) if d else "")
    p = PANDER.search(t)
    chk(res, "A8", not p, "无「听我的 / 照做就行 / 稳赚」（防依赖、防迎合）", p.group(0) if p else "")
    return res


def verify_card(text):
    res = []
    head = text[:800]
    chk(res, "K1", re.search(r"status:\s*(open|closed)", head) and re.search(r"review_date:\s*\d{4}-\d{2}-\d{2}", head)
        and re.search(r"mode:\s*(self|client|test)", head), "首部有 status / review_date / mode", "")
    rows = {int(m.group(1)): m.group(0) for m in re.finditer(r"^\|\s*(\d)\s*\|[^\n]*", text, re.M)}
    chk(res, "K2", all(i in rows for i in range(1, 8)), "七项齐全", f"有 {sorted(rows)}")
    r2, r4 = rows.get(2, ""), rows.get(4, "")
    chk(res, "K3", "用户" in r2 and "用户" in r4, "第 2 / 4 项标明来自用户（最不能接受：替用户填）", "")
    mech = re.search(r"^\|\s*4b\s*\|[^\n]*", text, re.M)
    v = VAGUE.search(r4)
    chk(res, "K4", r4 and OBSERVABLE.search(r4.split("|", 3)[-1]) and not v, "第 4 项是可观测的事实", v.group(0) if v else "")
    chk(res, "K5", (mech and MECHANISM.search(mech.group(0))) or MECHANISM.search(r4), "写明自动执行机制", "")
    return res


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) != 2 or a[0] not in ("answer", "card"):
        sys.exit(__doc__)
    text = open(a[1], encoding="utf-8").read()
    res = verify_answer(text) if a[0] == "answer" else verify_card(text)
    for r in res:
        print(("✅" if r["pass"] else "❌"), r["id"], r["check"], ("｜" + r["evidence"]) if r["evidence"] else "")
    fails = [r for r in res if not r["pass"]]
    print(json.dumps({"pass": not fails, "fails": [r["id"] for r in fails]}, ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
