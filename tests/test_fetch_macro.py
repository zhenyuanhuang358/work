"""fetch_macro 的 PPI 回归（2026-11-14）：季调口径与核心 PPI。

为什么：11/13 公布 10 月 PPI 后，macro_actuals 里 ppi=0.45%，而官方是 0.3%——
根因是脚本用了未季调系列 WPUFD4。官方发布口径是季调（WPSFD4）；核心 pPI 需 WPSFD49104
（实测：9 月修正 +0.82%、10 月 +0.33%、同比 +5.04%，与多家报道一致）。
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import fetch_macro  # noqa: E402


class PpiSeries(unittest.TestCase):
    def test_bls_series_are_seasonally_adjusted(self):
        self.assertEqual(fetch_macro.BLS["ppi"], "WPSFD4")
        self.assertEqual(fetch_macro.BLS["core_ppi"], "WPSFD49104")

    def test_ff_map_maps_core_ppi_separately(self):
        def keys_for(title):
            return {k for pat, k in fetch_macro.FF_MAP if re.search(pat, title)}
        self.assertIn("ppi", keys_for("PPI m/m"))
        self.assertIn("core_ppi", keys_for("Core PPI m/m"))
        self.assertNotIn("ppi", keys_for("Core PPI m/m"))

    def test_summarize_ppi_oct_2026(self):
        series = {"ppi": [("2026-08", 157.482), ("2026-09", 159.699), ("2026-10", 160.254)]}
        r = fetch_macro.summarize(series)["ppi"]
        self.assertEqual(r["month"], "2026-10")
        self.assertAlmostEqual(r["actual"], 0.35, places=2)          # 官方四舍五入 0.3%
        self.assertAlmostEqual(r["previous_recomputed"], 1.41, places=2)  # 9 月修正后 +1.4%

    def test_summarize_core_ppi_oct_2026(self):
        series = {"core_ppi": [("2026-08", 154.960), ("2026-09", 156.230), ("2026-10", 156.740)]}
        r = fetch_macro.summarize(series)["core_ppi"]
        self.assertAlmostEqual(r["actual"], 0.33, places=2)      # 官方 0.3%
        self.assertAlmostEqual(r["previous_recomputed"], 0.82, places=2)  # 9 月修正 +0.8%


if __name__ == "__main__":
    unittest.main()
