#!/usr/bin/env python3
"""巴菲特估值计算器回归（2026-11-07）。期望值用独立循环按 owner-earnings-model.md 公式重算，不复用被测函数。
运行：python3 -m unittest tests/test_owner_value.py -v
"""
import copy
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import owner_value as ov  # noqa: E402

S = "测试来源"
BASE = {
    "ticker": "TST", "as_of": "2026-11-07", "price": {"v": 100.0, "src": S}, "shares": {"v": 10.0, "src": S},
    "r": {"v": 0.10, "src": S}, "debt_ratio": {"v": 0.3, "src": S}, "moat_score": 8, "tech_disruption": False,
    "maint_capex": {"method": "da_proxy"},
    "years": [{"fy": 2023, "src": S, "net_income": 90, "da": 20, "capex": 30, "dwc": 0, "fcf": 100.0, "revenue": 1000, "ebit": 150, "interest": 10},
              {"fy": 2024, "src": S, "net_income": 95, "da": 20, "capex": 30, "dwc": 0, "fcf": 121.0, "revenue": 1100, "ebit": 160, "interest": 10},
              {"fy": 2025, "src": S, "net_income": 100, "da": 20, "capex": 30, "dwc": 0, "fcf": 146.41, "revenue": 1200, "ebit": 170, "interest": 10}],
    "peer_p_fcf": {"v": 1000.0, "src": S},  # 极大值：交叉验证不会取代 DCF，便于核算
    "scores": {"business": 25, "financial": 24, "management": 18, "price": 8},
}


def ref_iv(oe0, g1, ratio2, gt, r, shares):
    pv, oe = 0.0, oe0
    for t in range(1, 11):
        oe *= 1 + (g1 if t <= 5 else g1 * ratio2)
        pv += oe / (1 + r) ** t
    return (pv + oe * (1 + gt) / (r - gt) / (1 + r) ** 10) / shares


class OwnerValue(unittest.TestCase):
    def test_formula_and_margin_on_lower_bound(self):
        """CAGR 21% → 保守 g1=12.6%（×60%）、基准 17.85%（×85%，未触 18% 上限）；终端 2.5% / 4%。
        用户 11/07 定：安全边际按下沿（保守 IV）算，不按中值。"""
        out = ov.run(copy.deepcopy(BASE))
        oe = 100 + 20 - 20  # 净利润 + D&A − 维护性 Capex（D&A 代理）
        lo = ref_iv(oe, 0.21 * 0.6, 0.5, 0.025, 0.10, 10)
        hi = ref_iv(oe, 0.21 * 0.85, 0.6, 0.03, 0.10, 10)  # 基准终端封顶 3%（用户 11/07 定）
        self.assertAlmostEqual(out["iv_range"][0], lo, places=6)
        self.assertAlmostEqual(out["iv_range"][1], hi, places=6)
        m = out["margin_of_safety"]
        self.assertAlmostEqual(m["value"], (lo - 100) / lo, places=9)
        self.assertNotAlmostEqual(m["value"], ((lo + hi) / 2 - 100) / ((lo + hi) / 2), places=3)
        self.assertEqual(out["scorecard"]["total"], 75)

    def test_no_source_refused(self):
        bad = copy.deepcopy(BASE)
        bad["price"]["src"] = ""
        with self.assertRaises(ov.NoSource):
            ov.run(bad)
        bad = copy.deepcopy(BASE)
        bad["years"][1]["src"] = ""
        with self.assertRaises(ov.NoSource):
            ov.run(bad)

    def test_anomalous_growth_needs_override(self):
        """CAGR > 50%：照公式会得荒谬增速（270% × 60%），必须给共识 / FCF yield 反推的 g_override，门槛升到 40%。"""
        d = copy.deepcopy(BASE)
        d["years"][2]["fcf"] = 400.0
        with self.assertRaises(ov.NoSource):
            ov.run(d)
        d["g_override"] = {"g1": 0.30, "g2": 0.40, "src": "共识"}
        out = ov.run(d)
        self.assertEqual(out["scenarios"]["conservative"]["g1"], 0.18)  # 被护城河上限截断
        self.assertEqual(out["margin_of_safety"]["hurdle"], 0.40)

    def test_failure_conditions_block_buy(self):
        d = copy.deepcopy(BASE)
        d["revenue_prior"] = {"v": 400, "src": S}
        for y, r in zip(d["years"], (720, 432, 691)):  # +80% / −40% / +60%：增速标准差约 64 个点
            y["revenue"] = r
        out = ov.run(d)
        self.assertTrue(any("营收增速波动率" in f for f in out["failure_conditions"]))
        self.assertTrue(out["zone"].startswith("估值失效"))

    def test_terminal_growth_clamped_below_r_minus_2(self):
        d = copy.deepcopy(BASE)
        d["r"]["v"] = 0.03  # r − 2% = 1%：两个情景的终端增长都必须被压到 1%
        out = ov.run(d)
        for sc in ("conservative", "base"):
            self.assertAlmostEqual(out["scenarios"][sc]["g_terminal"], 0.01, places=12)

    def test_moat_below_3_stops(self):
        d = copy.deepcopy(BASE)
        d["moat_score"] = 2
        self.assertIn("终止", ov.run(d)["verdict"])

    def test_score_out_of_range_refused(self):
        d = copy.deepcopy(BASE)
        d["scores"]["price"] = 20
        with self.assertRaises(ov.NoSource):
            ov.run(d)


    def test_one_off_adjustment_normalizes_fcf_and_dwc(self):
        """11/07 KO 实测：一次性现金流出（IRS 保证金、fairlife 或有对价）把 FCF 与 ΔWC 压低，
        不调会把 CAGR 和 OE 基准一起算错。调整同时加回 FCF 与 ΔWC；缺来源拒算。"""
        d = copy.deepcopy(BASE)
        d["years"][2]["fcf"] = 146.41 - 50
        d["years"][2]["dwc"] = -50
        raw = ov.run(copy.deepcopy(d))
        d["years"][2]["adjustments"] = [{"item": "保证金", "amount": 50, "src": S, "why": "一次性"}]
        out = ov.run(copy.deepcopy(d))
        ref = ov.run(copy.deepcopy(BASE))
        self.assertAlmostEqual(out["iv_range"][0], ref["iv_range"][0], places=6)
        self.assertAlmostEqual(out["owner_earnings"]["value"], 100, places=9)
        self.assertLess(raw["iv_range"][0], out["iv_range"][0])
        self.assertEqual(out["normalization"][0]["fcf_reported"], 146.41 - 50)
        self.assertTrue(any("一次性项调整" in f for f in out["flags"]))
        self.assertAlmostEqual(out["without_adjustments"]["iv_range"][0], raw["iv_range"][0], places=6)
        d["years"][2]["adjustments"][0]["src"] = ""
        with self.assertRaises(ov.NoSource):
            ov.run(d)

    def test_sensitivity_and_implied_growth(self):
        """逆向验证：把隐含增速代回基准结构必须得到现价；r +1% 必须压低 IV。"""
        out = ov.run(copy.deepcopy(BASE))
        ig = out["implied_g1"]
        self.assertAlmostEqual(ref_iv(100, ig["g1"], 0.6, ig["g_terminal"], 0.10, 10), 100.0, places=4)
        rows = {(x["var"], x["delta"]): x for x in out["sensitivity"]["rows"]}
        self.assertLess(rows[("r", 0.01)]["change"], 0)
        self.assertAlmostEqual(rows[("g1", 0.03)]["iv_per_share"], ref_iv(100, 0.21 * 0.6 + 0.03, 0.5, 0.025, 0.10, 10), places=6)

    def test_exit_multiple_equity_basis(self):
        """11/07 KO Critic R2 + 用户定：交叉验证用股权口径，前 10 年 OE 现值必须计入（原公式只比终值，KO 碰巧「差 0%」实为 36%）。"""
        d = copy.deepcopy(BASE)
        d["r"]["v"] = 0.06  # 终值占比 > 60%，触发交叉验证
        d["peer_p_fcf"]["v"] = 20.0
        sc = ov.run(copy.deepcopy(d))["scenarios"]["base"]
        self.assertAlmostEqual(sc["exit_multiple_iv"], (sc["pv_cash"] + sc["oe_year10"] * 20.0 / 1.06 ** 10) / 10, places=9)

    def test_revenue_volatility_is_growth_stdev_not_level_swing(self):
        """11/09 NVDA + 用户定：持续高增长不是波动（原实现按最高 ÷ 最低把 NVDA 判成 254% 失效）；忽高忽低才触发。"""
        d = copy.deepcopy(BASE)
        d["revenue_prior"] = {"v": 400, "src": S}
        for y, r in zip(d["years"], (900, 1900, 3200)):  # +125% / +111% / +68%：标准差约 30 个点
            y["revenue"] = r
        d["g_override"] = {"g1": 0.1, "g2": 0.15, "src": S}
        self.assertFalse(any("营收" in f for f in ov.run(copy.deepcopy(d))["failure_conditions"]))
        for y, r in zip(d["years"], (720, 432, 691)):  # +80% / −40% / +60%
            y["revenue"] = r
        self.assertTrue(any("营收增速波动率" in f for f in ov.run(d)["failure_conditions"]))


if __name__ == "__main__":
    unittest.main()
