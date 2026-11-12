#!/usr/bin/env python3
"""fetch_financials.annual 回归（2026-11-09 NVDA capex 静默缺失）。不联网，用合成 companyfacts。"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import fetch_financials as ff  # noqa: E402


def row(end, val, filed):
    return {"form": "10-K", "fp": "FY", "fy": int(end[:4]), "end": end, "start": f"{int(end[:4]) - 1}{end[4:]}",
            "val": val, "accn": "x", "filed": filed}


FACTS = {"facts": {"us-gaap": {
    "OldTag": {"units": {"USD": [row("2010-12-31", 1, "2011-02-01"), row("2011-12-31", 2, "2012-02-01")]}},
    "NewTag": {"units": {"USD": [row("2011-12-31", 99, "2012-02-01"), row("2025-12-31", 7, "2026-02-01")]}},
}}}


class Annual(unittest.TestCase):
    def test_later_tag_fills_years_the_first_tag_lacks(self):
        """NVDA：第一个标签只有早年数据时，后面的标签必须补上近年。"""
        out = ff.annual(FACTS, ["OldTag", "NewTag"])
        self.assertEqual(out[2025]["v"], 7)
        self.assertEqual(out[2025]["tag"], "NewTag")

    def test_priority_kept_when_both_have_the_year(self):
        out = ff.annual(FACTS, ["OldTag", "NewTag"])
        self.assertEqual(out[2011]["v"], 2)


if __name__ == "__main__":
    unittest.main()
