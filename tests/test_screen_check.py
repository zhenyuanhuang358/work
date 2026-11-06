#!/usr/bin/env python3
"""筛选器回归（2026-11-06 推广到第二档）：产物不变量 + Stage A 分类语义。不联网、不读 SEC。
运行：python3 -m unittest tests/test_screen_check.py -v
"""
import copy
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import screen_check as sc  # noqa: E402


def failed(rs):
    return {c["id"] for c in rs if not c["pass"] and c["level"] == "FAIL"}


def good_burry():
    r = {"cik": "1", "ticker": "AAA", "revenue": 100.0, "ebitda": 20.0, "equity": 50.0, "shares": 10.0, "net_debt": 10.0,
         "fcf": 8.0, "price": 5.0, "sbc_ratio": 0.005, "passed": True}
    r["net_debt_ebitda"] = r["net_debt"] / r["ebitda"]
    r["mktcap"] = r["price"] * r["shares"]
    r["ev"] = r["mktcap"] + r["net_debt"]
    r.update({"ev_ebitda": r["ev"] / r["ebitda"], "pb": r["mktcap"] / r["equity"], "fcf_yield": r["fcf"] / r["ev"]})
    return {"sample": {"universe": 10, "complete": 4, "missing_data": 2, "not_applicable": 4, "missing_ratio": round(2 / 6, 4),
                       "stage_a_survivors": 3},
            "warnings": ["数据缺失率 33.3% > 30%"], "thresholds": {"net_debt_ebitda_cut": 1.0, "sbc_ratio_cut": 0.01},
            "results": [r]}


class Burry(unittest.TestCase):
    def test_good_artifact_passes(self):
        self.assertEqual(failed(sc.check_burry(good_burry())), set())

    def test_double_counted_sample_caught(self):
        """11/06 真实发现：Stage B 移出的 137 家仍计在「完整」里，完整 + 缺失 + 不适用 > 全集。"""
        d = good_burry()
        d["sample"]["complete"] += 3
        self.assertIn("B1", failed(sc.check_burry(d)))

    def test_stale_missing_ratio_caught(self):
        d = good_burry()
        d["sample"]["missing_ratio"] = 0.20
        self.assertIn("B2", failed(sc.check_burry(d)))

    def test_fcf_yield_definition_is_over_ev(self):
        """burry 口径 FCF ÷ EV；按市值算就该报（watch_fundamentals 的同名字段是另一个口径）。"""
        d = good_burry()
        r = d["results"][0]
        r["fcf_yield"] = r["fcf"] / r["mktcap"]
        self.assertIn("B4", failed(sc.check_burry(d)))

    def test_passed_must_meet_threshold(self):
        d = good_burry()
        d["results"][0]["net_debt"] = 40.0
        d["results"][0]["net_debt_ebitda"] = 2.0
        d["results"][0]["ev"] = d["results"][0]["mktcap"] + 40.0
        d["results"][0]["ev_ebitda"] = d["results"][0]["ev"] / 20.0
        d["results"][0]["fcf_yield"] = 8.0 / d["results"][0]["ev"]
        self.assertIn("B5", failed(sc.check_burry(d)))

    def test_silent_empty_caught(self):
        """profile 1.1u：吞异常导致产物静默变空。"""
        d = good_burry()
        d["results"] = []
        self.assertIn("B3", failed(sc.check_burry(d)))


class StageA(unittest.TestCase):
    def test_missing_vs_not_applicable_vs_da_fallback(self):
        """「数据缺失」与「不适用」必须分开（前者影响分位数代表性）；D&A 缺失时用折旧 + 摊销分项兜底。"""
        import burry_screener as bs
        base = {"name": "X", "revenue": 100.0, "operating_income": 10.0, "dep_amort": 5.0, "equity": 50.0, "shares": 10.0,
                "cash": 1.0, "debt_lt": 2.0, "debt_st": 0.0, "cfo": 9.0, "capex": 1.0, "sbc": 0.5}
        uni = {"ok": dict(base),
               "neg": dict(base, operating_income=-20.0),
               "miss": {k: v for k, v in base.items() if k != "equity"},
               "da": dict({k: v for k, v in base.items() if k != "dep_amort"}, depreciation_only=3.0, amortization_only=1.0)}
        for e in uni.values():
            e.setdefault("shares_gaap", None)
        full, missing, na = bs.stage_a(copy.deepcopy(uni), {}, {})
        f = {r["cik"]: r for r in full}
        self.assertEqual(set(f), {"ok", "da"})
        self.assertEqual(f["da"]["ebitda"], 10.0 + 4.0)
        self.assertTrue(f["da"].get("da_derived"))
        self.assertEqual([r["cik"] for r in missing], ["miss"])
        self.assertEqual([r["cik"] for r in na], ["neg"])


class MacroCalendar(unittest.TestCase):
    def test_fomc_parser(self):
        """美联储页面结构：年份面板 + month / date；决议日取会期第二天，* 表示含经济预测，跨月取后一个月。"""
        import fetch_calendar as fc
        html = ('<h4>2027 FOMC Meetings</h4><div class="fomc-meeting__month"><strong>January</strong></div>'
                '<div class="fomc-meeting__date">26-27</div><div class="fomc-meeting__month"><strong>Apr/May</strong></div>'
                '<div class="fomc-meeting__date">30-1*</div><h4>2026 FOMC Meetings</h4>'
                '<div class="fomc-meeting__month"><strong>December</strong></div><div class="fomc-meeting__date">8-9*</div>')
        self.assertEqual(fc.parse_fomc(html), [("2026-12-09", True), ("2027-01-27", False), ("2027-05-01", True)])

    def test_option_quote_reads_unified_calendar(self):
        """利率敏感拦截读 macro_calendar.json（options-screen 里不再有日期副本）。"""
        import option_quote as oq
        ev = oq.macro_events(os.path.join(REPO, "memory", "state", "macro_calendar.json"))
        self.assertEqual(ev.get("2026-12-09"), "FOMC")
        self.assertEqual(ev.get("2026-11-10"), "CPI")
        screen = json.load(open(os.path.join(REPO, "memory", "state", "options-screen.json")))
        self.assertNotIn("events", screen["rate_sensitive"])


class Ses(unittest.TestCase):
    def test_flags_and_window(self):
        d = json.load(open(os.path.join(REPO, "ses_screen.json")))
        self.assertEqual(failed(sc.check_ses(d)), set(), "当前 SES 产物应通过（⚑分部 是合法旗标）")
        bad = copy.deepcopy(d)
        bad["results"][0]["signals"]["window_years"] = 2.0  # F10 基期污染：窗口悄悄变短
        self.assertIn("S3", failed(sc.check_ses(bad)))


if __name__ == "__main__":
    unittest.main()
