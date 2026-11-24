"""Merlin 机械检查（M0–M9）回归：2026-11-24 针对用户三类投诉建立。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import merlin_check  # noqa: E402

GOOD = """<html><body>
<p>数据截止 2026-11-24。</p>
<p>Q1 翻台率多少？ 【推测】翻台 5–6 次/天，来源：公司公告（pages/a.txt），置信 中。</p>
<p>Q2 利润率多少？ 稳定期利润率 10%–15%，来源：年报与行业均值（pages/b.txt），置信 低。</p>
<p>Q3 竞争对手是谁？ 主要对手人均 100 元，来源：研报（pages/c.txt），置信 中。</p>
<p>分析师附注</p><p>来源索引：https://a.example/1 https://b.example/2 https://c.example/3</p>
<p><a href="https://spontaneous-youtiao-b9cde9.netlify.app?product=merlin&report=x">反馈</a></p>
</body></html>"""


class MerlinCheck(unittest.TestCase):
    def _write(self, html):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "x_Research_Report.html")
        open(f, "w", encoding="utf-8").write(html)
        open(os.path.splitext(f)[0] + ".pdf", "wb").write(b"%PDF-1.4")
        return f

    def test_good_report_passes(self):
        r = merlin_check.run(self._write(GOOD))
        self.assertTrue(r["pass"], r["fails"])

    def test_missing_q_ids_fail_m1(self):
        r = merlin_check.run(self._write(GOOD.replace("Q1", "问题一").replace("Q2", "问题二").replace("Q3", "问题三")))
        self.assertIn("M1", r["fails"])

    def test_meta_opening_fails_m2(self):
        bad = GOOD.replace("【推测】翻台 5–6 次/天", "需要说明的是翻台数据难以获得")
        r = merlin_check.run(self._write(bad))
        self.assertIn("M2", r["fails"])

    def test_missing_source_fails_m3(self):
        bad = GOOD.replace("来源：公司公告（pages/a.txt）", "")
        r = merlin_check.run(self._write(bad))
        self.assertIn("M3", r["fails"])

    def test_missing_cutoff_fails_m5(self):
        r = merlin_check.run(self._write(GOOD.replace("数据截止 2026-11-24。", "")))
        self.assertIn("M5", r["fails"])


if __name__ == "__main__":
    unittest.main()
