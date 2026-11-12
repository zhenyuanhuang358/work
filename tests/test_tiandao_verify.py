#!/usr/bin/env python3
"""天道交付检查回归（2026-11-09）。好样例 = 两次实验冻结件（tests/fixtures/tiandao）；
每个「最不能接受」的错误各有一个反例，必须被抓住。运行：python3 -m unittest tests/test_tiandao_verify.py
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(REPO, "tests", "fixtures", "tiandao")
sys.path.insert(0, os.path.join(REPO, "tools"))
import tiandao_verify as tv  # noqa: E402


def fails(res):
    return {r["id"] for r in res if not r["pass"]}


def read(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return f.read()


GOOD = "**结论：不做。置信度：高。**\n**关键依据**\n1. 规则 4\n**否定条件**\n- 对方提供书面担保且有第二还款来源时重审\n"


class GoodSamples(unittest.TestCase):
    def test_frozen_samples_pass(self):
        self.assertEqual(fails(tv.verify_answer(read("transfer_answer.md"))), set())
        self.assertEqual(fails(tv.verify_answer(read("dept_diagnosis.md"))), set())
        self.assertEqual(fails(tv.verify_card(read("card_dept.md"))), set())


class MustCatch(unittest.TestCase):
    """用户 11/09 定的「最不能接受」，每条一个反例。"""

    def test_missing_negation_condition(self):  # 迎合或没有否定条件
        self.assertIn("A3", fails(tv.verify_answer(GOOD.replace("**否定条件**\n- 对方提供书面担保且有第二还款来源时重审\n", ""))))

    def test_missing_confidence(self):
        self.assertIn("A2", fails(tv.verify_answer(GOOD.replace("置信度：高。", ""))))

    def test_rule_numbers_without_tool(self):  # 突破个人规则上限：数字必须来自工具
        bad = GOOD.replace("不做", "做") + "借给他 3000 元在上限内，决策卡见下。\n"
        self.assertIn("A6", fails(tv.verify_answer(bad)))

    def test_tool_says_violation_but_answer_says_do(self):
        bad = GOOD.replace("不做", "做") + '借给他 3000 元，决策卡见下。tiandao_check 输出：{"ok": false, "room": 2000}\n'
        self.assertIn("A6b", fails(tv.verify_answer(bad)))

    def test_legal_question_needs_lawyer_and_no_definitive_verdict(self):  # 法律问题给确定结论
        bad = GOOD + "这样做一定违法，涉及洗钱。\n"
        self.assertTrue({"A7", "A7b"} <= fails(tv.verify_answer(bad)))

    def test_pandering_phrases(self):
        self.assertIn("A8", fails(tv.verify_answer(GOOD + "听我的，照做就行。\n")))

    def test_do_without_decision_card(self):
        self.assertIn("A5", fails(tv.verify_answer(GOOD.replace("不做", "做"))))

    def test_card_filled_by_ai_not_user(self):  # 替我填认错线或理由
        card = read("card_dept.md").replace("为什么做（用户原话）", "为什么做").replace("认错线 / 暂停条件（用户写）", "认错线 / 暂停条件")
        self.assertIn("K3", fails(tv.verify_card(card)))

    def test_card_vague_stop_line_and_no_mechanism(self):
        card = read("card_dept.md")
        card = "\n".join("| 4 | 认错线 / 暂停条件（用户写） | 感觉不对就走 |" if l.startswith("| 4 |") else
                         ("| 4b | 执行机制（用户写） | 靠自己 |" if l.startswith("| 4b |") else l) for l in card.splitlines())
        self.assertTrue({"K4", "K5"} <= fails(tv.verify_card(card)))

    def test_diagnosis_more_than_three_questions(self):
        d = read("dept_diagnosis.md") + "\n4. **还有什么？** 你怎么想？\n"
        self.assertIn("A9", fails(tv.verify_answer(d)))


if __name__ == "__main__":
    unittest.main()
