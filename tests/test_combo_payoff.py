"""combo_payoff：三种看涨组合到期盈亏（只做分析）。合成链，数字可手算。"""
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import combo_payoff as cp  # noqa: E402

E = "2026-12-18"


def chain(spot_reported, s_true=100.0):
    rows = []
    for k, c, p in [(95, (6.0, 6.2), (1.0, 1.1)), (100, (3.0, 3.2), (2.9, 3.1)), (105, (1.0, 1.1), (5.9, 6.1)), (110, (0.3, 0.4), (10.2, 10.4))]:
        rows.append({"expiry": E, "right": "C", "strike": float(k), "bid": c[0], "ask": c[1]})
        rows.append({"expiry": E, "right": "P", "strike": float(k), "bid": p[0], "ask": p[1]})
    return {"spot": spot_reported, "rows": rows, "quote_time_utc": "2026-11-20 16:00:00"}


ASOF = datetime(2026, 11, 20, 16, tzinfo=timezone.utc)


class ComboPayoff(unittest.TestCase):
    def test_hand_computed_extremes(self):
        o = cp.analyze(chain(100.0), E, k1=100, k2=110, ratio=2, asof=ASOF)
        st = o["structures"]
        # 牛市：买 100 付 ask 3.2、卖 110 收 bid 0.3 → 净付 2.9；最大盈利 (10 − 2.9)×100
        self.assertAlmostEqual(st["bull"]["open_cash"], -290)
        self.assertAlmostEqual(st["bull"]["max_profit"], 710)
        self.assertAlmostEqual(st["bull"]["max_loss"], -290)
        self.assertEqual(st["bull"]["breakevens"], [102.9])
        # 熊市：卖 100 收 bid 3.0、买 110 付 ask 0.4 → 净收 2.6；最大亏损 (10 − 2.6)×100
        self.assertAlmostEqual(st["bear"]["open_cash"], 260)
        self.assertAlmostEqual(st["bear"]["max_loss"], -740)
        # 反向 1:2：卖 100 收 3.0、买 2×110 付 0.8 → 净收 2.2；最大亏损在 K2：(2.2 − 10)×100
        self.assertAlmostEqual(st["back"]["open_cash"], 220)
        self.assertAlmostEqual(st["back"]["max_loss"], -780)
        self.assertIsNone(st["back"]["max_profit"])
        self.assertEqual(st["back"]["breakevens"], [102.2, 117.8])

    def test_stale_spot_uses_parity(self):
        # 11/12 NVDA：链上现价是盘后价，期权报价停在收盘 → 以平价反推为准并报警
        o = cp.analyze(chain(90.0), E, k1=100, k2=110, asof=ASOF)
        self.assertIsNotNone(o["warn"])
        self.assertAlmostEqual(o["spot_used"], 100.07, places=1)
        self.assertIsNone(cp.analyze(chain(100.0), E, k1=100, k2=110, asof=ASOF)["warn"])

    def test_output_states_analysis_only(self):
        o = cp.analyze(chain(100.0), E, k1=100, k2=110, asof=ASOF)
        self.assertIn("不登记 candidate_ledger", cp.fmt(o, "TEST"))


if __name__ == "__main__":
    unittest.main()
