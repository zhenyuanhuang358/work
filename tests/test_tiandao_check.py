#!/usr/bin/env python3
"""天道个人规则检查回归（2026-11-08）。期望值按 personal-rules.md 的条文手算，不复用被测函数。
运行：python3 -m unittest tests/test_tiandao_check.py
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import tiandao_check as tc  # noqa: E402

R = {"lending": {"loan_outstanding_cap": 5000, "equity_principal_cap": 50000},
     "gold": {"max_share": 0.20},
     "options": {"per_trade_max_loss": 275, "open_max_loss_total": 550, "halt_equity": 4400, "stop_loss_share_of_capital": 0.15}}


class Lending(unittest.TestCase):
    def test_outstanding_total_blocks_split_loans(self):
        """第 8 条：不分对象，防止分笔绕过——两人各借 3000 合计 6000 必须拦。"""
        led = {"loans": [{"amount": 3000, "repaid": 0}]}
        r = tc.lend(R, led, 3000)
        self.assertFalse(r["ok"])
        self.assertEqual(r["max_this_loan"], 2000)
        self.assertTrue(tc.lend(R, led, 2000)["ok"])

    def test_repaid_frees_room(self):
        led = {"loans": [{"amount": 5000, "repaid": 5000}]}
        self.assertTrue(tc.lend(R, led, 5000)["ok"])

    def test_equity_cap_counts_cash_returned_only(self):
        """第 11–12 条：未收回本金 ≤ 50000；收回以现金到账为准。"""
        led = {"equity": [{"principal": 40000, "cash_returned": 0}]}
        self.assertFalse(tc.equity(R, led, 20000)["ok"])
        led["equity"][0]["cash_returned"] = 10000
        self.assertTrue(tc.equity(R, led, 20000)["ok"])


class Gold(unittest.TestCase):
    def test_share_and_sell_back(self):
        """保值第 1–3 条：占比 = 黄金 ÷ 可投资资产；超过就卖回到 20%。"""
        r = tc.gold(R, 120000, 500000)
        self.assertFalse(r["ok"])
        self.assertAlmostEqual(r["sell_back_to_cap"], 120000 - 0.2 * 500000)
        self.assertTrue(tc.gold(R, 80000, 500000, buy=20000)["ok"])  # (80k+20k)/(520k) = 19.2%


class Options(unittest.TestCase):
    def test_spread_max_loss_formula_and_cap(self):
        """期权第 2 条：(宽度 − 权利金) × 100 × 张数 ≤ 275。"""
        r = tc.spread(R, {}, 5, 2.5, 1)
        self.assertEqual(r["max_loss"], 250)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["stop_loss_amount"], 250 * 0.15)
        self.assertFalse(tc.spread(R, {}, 5, 2.0, 1)["ok"])  # 300 > 275

    def test_open_total_and_halt_line(self):
        """第 3 条：在手合计 ≤ 550；第 7 条：权益 ≤ 4400 暂停。"""
        led = {"option_positions": [{"max_loss": 275, "status": "open"}, {"max_loss": 200, "status": "closed"}]}
        self.assertTrue(tc.spread(R, led, 5, 2.5, 1)["ok"])  # 275 + 250 = 525
        led["option_positions"].append({"max_loss": 100, "status": "open"})
        self.assertFalse(tc.spread(R, led, 5, 2.5, 1)["ok"])  # 375 + 250 = 625
        self.assertFalse(tc.long_opt(R, {}, 1.0, 1, equity_now=4400)["ok"])

    def test_position_size(self):
        self.assertAlmostEqual(tc.size(2000, 0.08)["position"], 25000)


if __name__ == "__main__":
    unittest.main()
