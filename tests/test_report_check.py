#!/usr/bin/env python3
"""报告检查回归（2026-11-06 期权线方法推广到报告线）。样例 = 已交付报告的冻结副本（tests/fixtures/reports，原件不动）。
每条测试钉住一个真实发现：误报（合规声明被当违规、表头「#」被当 Markdown）和真违规写法必须被抓。
运行：python3 -m unittest tests/test_report_check.py -v
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(REPO, "tests", "fixtures", "reports")
sys.path.insert(0, os.path.join(REPO, "tools"))
import report_check as rc  # noqa: E402


def ids(r, failed=True):
    return {c["id"] for c in r["checks"] if (not c["pass"]) == failed}


def synth(body, suffix="_Research_Report.html"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(f"<html><body>{body}<div>来源：公司年报 https://example.com/a</div><p>结尾</p><p>分析师附注 Analyst's Note</p></body></html>")
    f.close()
    return f.name


class Compliance(unittest.TestCase):
    """用户 11/06：数据来源与合规最不能错。"""

    def test_true_violations_caught(self):
        for bad in ["<p>海底捞华南区 2025 年翻台率 4.2 次，来自内部报表。</p>",
                    "<p>海底捞不对外公布的内部数据显示，华南人效 12 万。</p>",
                    "<p>据我任职期间了解，绿茶门店人效为内部数据 12 万元。</p>"]:
            p = synth(bad)
            self.assertIn("G1", ids(rc.run(p)), bad)
            os.unlink(p)

    def test_compliance_disclaimers_not_flagged(self):
        """11/06 基线：10 份 G1 命中全是合规声明 / 第三方数据，修正后这几份必须不报。"""
        for f in ("catering_2026_greentea_positioning_Research_Report.html", "greentea_ai_spend_survey_2026.html"):
            self.assertNotIn("G1", ids(rc.run(os.path.join(FX, f))), f)

    def test_known_listed_disclaimer_still_flagged_for_human(self):
        """botinkit 的「不应披露」清单否定词在 80 字外：宁可多报交人工，不放宽窗口（合规优先）。"""
        self.assertIn("G1", ids(rc.run(os.path.join(FX, "botinkit_Research_Report.html"))))


class Sources(unittest.TestCase):
    def test_no_source_index_fails(self):
        p = tempfile.NamedTemporaryFile("w", suffix="_Research_Report.html", delete=False, encoding="utf-8")
        p.write("<html><body><p>营收 12 亿元，同比 30%。</p><p>分析师附注</p></body></html>")
        p.close()
        self.assertIn("S1", ids(rc.run(p.name)))
        os.unlink(p.name)

    def test_summary_level_phrases_warned(self):
        p = synth("<p>据搜索，门店数 1,200 家。</p>")
        self.assertIn("S3", ids(rc.run(p)))
        os.unlink(p)

    def test_reference_report_has_no_source_index(self):
        """11/06 发现：Earner 参考样例 00538 没有来源索引（只有「数据质量声明」）——检查必须照实报。"""
        self.assertIn("S1", ids(rc.run(os.path.join(FX, "00538_Copilot_Report.html"))))


class Format(unittest.TestCase):
    def test_table_hash_header_not_markdown(self):
        """11/06 基线：表头单独一格「#」被误报 Markdown（4 份）。"""
        self.assertNotIn("C1", ids(rc.run(os.path.join(FX, "618_2026_ecommerce_Research_Report.html"))))

    def test_real_markdown_caught(self):
        p = synth("<p>## 核心结论</p><p>营收 **12 亿**</p>")
        self.assertIn("C1", ids(rc.run(p)))
        os.unlink(p)

    def test_earner_template_drift_detected(self):
        """11/06 抽查：已交付财报报告没有一份是 14 节；00538 只有 8 组双语标题。"""
        r = rc.run(os.path.join(FX, "00538_Copilot_Report.html"))
        self.assertIn("E1", ids(r))
        self.assertTrue({"E3", "E4", "E5", "E6"} <= ids(r, failed=False))

    def test_earner_full_template_passes_structure(self):
        secs = "".join(f'<section data-sec="{i}"><div class="section-zh">中{i}</div><div class="section-en">EN{i}</div>'
                       f'{"<svg></svg>" if i <= 5 else ""}</section>' for i in range(1, 15))
        body = (secs + "<p>熊市 基准 牛市 目标价</p><div class='verdict'></div>"
                "<style>body{font-family:'IM Fell English','Songti SC';color:#0a0a0b;background:#f1efea}"
                ".c{color:#8b6c42}.g{color:#c9a84c}</style>")
        p = synth(body, suffix="_Copilot_Report.html")
        r = rc.run(p)
        self.assertFalse({"E1", "E2", "E3", "E4", "E5", "E6"} & ids(r), ids(r))
        os.unlink(p)

    def test_c3_requires_each_scenario_price(self):
        """11/06 首次实测：UBER 报告三情景未登记，但 predictions.md 里有一条 UBER 期权旧预测，C3 只查标的名就放行了。"""
        p = synth("<p>熊市 $11 基准 $22 牛市 $33 目标价</p>", suffix="_Copilot_Report.html")
        stem_path = os.path.join(os.path.dirname(p), "uber_" + os.path.basename(p).split("_", 1)[1])
        os.rename(p, stem_path)
        r = rc.run(stem_path)
        c3 = [c for c in r["checks"] if c["id"] == "C3"][0]
        self.assertFalse(c3["pass"], c3)  # 11/22/33 不在任何 UBER 预测行里
        os.unlink(stem_path)

    def test_research_rules(self):
        """Merlin / restaurant-research：无分析师附注、正文禁用句 → FAIL。"""
        p = tempfile.NamedTemporaryFile("w", suffix="_Research_Report.html", delete=False, encoding="utf-8")
        p.write("<html><body><p>需要说明的是，本题数据有限。</p><div>来源：年报</div></body></html>")
        p.close()
        self.assertTrue({"R1", "R2"} <= ids(rc.run(p.name)))
        os.unlink(p.name)

    def test_good_samples_pass(self):
        """好样例：11/06 基线中无 FAIL 的两份。规则改了导致它们失败，要么规则错，要么写进 feedback 说明。"""
        for f in ("haichang_it_Research_Report.html", "greentea_ai_spend_survey_2026.html"):
            self.assertTrue(rc.run(os.path.join(FX, f))["pass"], f)


if __name__ == "__main__":
    unittest.main()
